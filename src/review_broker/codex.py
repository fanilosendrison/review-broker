"""Pinned one-shot Codex CLI adapter with failure-preserving evidence."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
from typing import Callable, Mapping

from .codex_runtime_identity import (
    CodexRuntimeIdentityError,
    VerifiedCodexRuntime,
    verify_codex_runtime,
)
from .codexfailure import classify_diagnostic_text, observe_codex_failure_files
from .identity import canonical_bytes
from .codex_policy import (
    CodexPolicy, InvocationError, REQUIRED_FLAGS, REMOVED_ENVIRONMENT_KEYS,
    REMOVED_ENVIRONMENT_PREFIXES, build_command, ensure_cli_compatibility, sanitized_environment,
)
from .packets import PacketError, verify_packet
from .input_capacity import CapacityError, MAX_CHARS, capacity_receipt, measure_input, read_verified_input
from .fileobservation import read_regular_file_bounded
from .reviewer_profile import (
    profile_name,
    ReviewerProfileError,
    reviewer_home_from_environment,
    verify_reviewer_profile,
)


_INVOCATION_ARTIFACTS = frozenset({
    "attempt.json",
    "prompt.sha256",
    "codex-events.jsonl",
    "codex-stderr.txt",
    "codex-final.json",
    "codex-exit-code.txt",
    "input-before.sha256",
    "input-after.sha256",
})

Runner = Callable[..., subprocess.CompletedProcess[bytes]]
RuntimeVerifier = Callable[[Mapping[str, str], Path], VerifiedCodexRuntime]


def preflight_codex_runtime(
    protected_runtime_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
    runtime_verifier: RuntimeVerifier = verify_codex_runtime,
) -> dict[str, object]:
    """Verify official runtime identity and supported flags without model transport."""
    child_environment, removed = sanitized_environment(environment or os.environ)
    try:
        runtime = runtime_verifier(child_environment, protected_runtime_root)
    except CodexRuntimeIdentityError as exc:
        raise InvocationError(f"CODEX_RUNTIME_IDENTITY:{exc}") from exc
    result = runner(
        [str(runtime.executable), "exec", "--help"],
        env=child_environment,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise InvocationError("CODEX_RUNTIME_HELP_FAILED")
    ensure_cli_compatibility(result.stdout.decode("utf-8", errors="strict"))
    return {
        "schema_version": 1,
        "evidence_type": "codex-runtime-identity-preflight",
        **runtime.evidence(),
        "cli_compatibility_verified": True,
        "environment_keys_removed": list(removed),
    }


def classify_failure(text: str) -> str:
    """Retain the public diagnostic classifier with a truthful neutral fallback."""
    return classify_diagnostic_text(text)


def invoke_once(
    packet_directory: Path,
    schema_path: Path,
    attempt_id: str,
    *,
    expected_packet_id: str,
    broker_wheel_sha256: str,
    trusted_workspace: Path,
    codex_runtime_root: Path,
    policy: CodexPolicy = CodexPolicy(),
    armed: bool = True,
    runner: Runner = subprocess.run,
    runtime_verifier: RuntimeVerifier = verify_codex_runtime,
    timeout_seconds: int = 3600,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Invoke Codex at most once for a caller-durably-armed attempt."""
    if not armed:
        raise InvocationError("NOT_ARMED")
    if (
        len(broker_wheel_sha256) != 64
        or any(character not in "0123456789abcdef" for character in broker_wheel_sha256)
    ):
        raise InvocationError("BROKER_WHEEL_IDENTITY_INVALID")
    packet_directory = packet_directory.resolve(strict=True)
    schema_path = schema_path.resolve(strict=True)
    prompt_path = packet_directory / "input.txt"
    manifest_path = packet_directory / "input-manifest.json"
    output_path = packet_directory / "codex-final.json"
    if not prompt_path.is_file() or not manifest_path.is_file() or not schema_path.is_file():
        raise InvocationError("INVOCATION_INPUT_MISSING")
    protected = (*_INVOCATION_ARTIFACTS, "validation.json")
    if any((packet_directory / name).exists() for name in protected):
        raise InvocationError("ALREADY_ATTEMPTED")
    verify_packet_tree(packet_directory, schema_path)
    prompt_before = _digest(prompt_path.read_bytes())
    permission_profile = profile_name(packet_directory)
    child_environment, removed = sanitized_environment(environment or os.environ)
    try:
        runtime = runtime_verifier(child_environment, codex_runtime_root)
    except CodexRuntimeIdentityError as exc:
        raise InvocationError(f"CODEX_RUNTIME_IDENTITY:{exc}") from exc
    if (
        runtime.distribution != policy.distribution
        or runtime.distribution_version != policy.distribution_version
    ):
        raise InvocationError("CODEX_RUNTIME_POLICY_IDENTITY_MISMATCH")
    command = build_command(
        runtime.executable, schema_path, output_path, policy, permission_profile
    )
    try:
        reviewer_home = reviewer_home_from_environment(child_environment)
        profile_path = verify_reviewer_profile(reviewer_home, trusted_workspace, packet_directory)
    except ReviewerProfileError as exc:
        raise InvocationError(f"SECURITY_PROFILE_INVALID:{exc}") from exc
    try:
        observed_packet = verify_packet(packet_directory)
    except (PacketError, OSError, KeyError) as exc:
        raise InvocationError("INVOCATION_PACKET_INVALID") from exc
    if observed_packet["packet_id"] != expected_packet_id:
        raise InvocationError("INVOCATION_PACKET_ID_MISMATCH")
    try:
        _, prompt_bytes = read_verified_input(packet_directory, expected_packet_id)
        counts = measure_input(prompt_bytes)
        if counts["capacity_units"] > MAX_CHARS:
            raise InvocationError("INPUT_CAPACITY_REJECTED:" + canonical_bytes(counts).decode("utf-8"))
        if counts["input_sha256"] != prompt_before:
            raise InvocationError("INPUT_CHANGED_BEFORE_EXECUTION")
        metadata_path = packet_directory / "broker-metadata.json"
        if metadata_path.exists():
            raw_metadata = read_regular_file_bounded(metadata_path, 100_000)
            metadata = json.loads(raw_metadata)
            if not isinstance(metadata, dict) or raw_metadata != canonical_bytes(metadata) + b"\n":
                raise InvocationError("INVOCATION_CAPACITY_BINDING_INVALID")
            capacity = capacity_receipt(prompt_bytes, request_id=observed_packet["request_id"],
                packet_id=expected_packet_id, attempt_id=attempt_id,
                executing_broker_sha=metadata["executing_broker_sha"])
            if (metadata.get("request_id") != observed_packet["request_id"]
                or metadata.get("attempt_id") != attempt_id
                or read_regular_file_bounded(packet_directory / "input-capacity.json", 100_000)
                != canonical_bytes(capacity) + b"\n"):
                raise InvocationError("INVOCATION_CAPACITY_BINDING_INVALID")
    except (CapacityError, OSError, KeyError, TypeError, ValueError) as exc:
        raise InvocationError("INVOCATION_INPUT_CAPACITY_INVALID") from exc
    attempt = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "broker_wheel_sha256": broker_wheel_sha256,
        "executor": "codex-cli",
        "distribution": policy.distribution,
        "distribution_version": policy.distribution_version,
        **runtime.evidence(),
        "model_requested": policy.model,
        "reasoning_effort_requested": policy.reasoning_effort,
        "effective_model_identity_verified": False,
        "effective_reasoning_effort_verified": False,
        "sandbox": policy.sandbox,
        "permission_profile": permission_profile,
        "permission_profile_sha256": _digest(profile_path.read_bytes()),
        "shell_tool_requested": False,
        "effective_policy_attestation": "UNAVAILABLE",
        "effective_shell_tool_verified": False,
        "effective_permission_profile_verified": False,
        "effective_approval_policy_verified": False,
        "effective_filesystem_policy_verified": False,
        "effective_network_policy_verified": False,
        "credential_paths_denied": True,
        "trusted_workspace_denied": True,
        "network_access": False,
        "api_key_fallback_forbidden": True,
        "environment_keys_removed": list(removed),
        "argv": command,
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _write_exclusive(packet_directory / "attempt.json", canonical_bytes(attempt) + b"\n")
    _write_exclusive(packet_directory / "prompt.sha256", (prompt_before + "\n").encode("ascii"))
    _write_exclusive(packet_directory / "input-before.sha256", (prompt_before + "\n").encode("ascii"))
    exit_value = "NOT_STARTED"
    transport: str | None = None
    try:
        with _exclusive_stream(packet_directory / "codex-events.jsonl") as events, _exclusive_stream(packet_directory / "codex-stderr.txt") as stderr:
            try:
                result = runner(
                    command,
                    cwd=str(packet_directory),
                    input=prompt_bytes,
                    stdout=events,
                    stderr=stderr,
                    env=child_environment,
                    timeout=timeout_seconds,
                    check=False,
                    shell=False,
                )
                exit_value = str(result.returncode)
            except subprocess.TimeoutExpired:
                exit_value = "TIMEOUT"
                transport = "TIMEOUT"
            except OSError:
                exit_value = "OS_ERROR"
                transport = "OS_ERROR"
    finally:
        prompt_after = _digest(prompt_path.read_bytes())
        _write_exclusive(packet_directory / "input-after.sha256", (prompt_after + "\n").encode("ascii"))
        _write_exclusive(packet_directory / "codex-exit-code.txt", (exit_value + "\n").encode("ascii"))
        if not output_path.exists():
            _write_exclusive(output_path, b"")
    if prompt_after != prompt_before:
        raise InvocationError("INPUT_CHANGED_DURING_EXECUTION")
    if transport is not None:
        observation = observe_codex_failure_files(
            returncode=None,
            events_path=packet_directory / "codex-events.jsonl",
            stderr_path=packet_directory / "codex-stderr.txt",
            transport=transport,
        )
        raise InvocationError(
            observation["classification"], failure_observation=observation,
        )
    if exit_value != "0":
        observation = observe_codex_failure_files(
            returncode=int(exit_value),
            events_path=packet_directory / "codex-events.jsonl",
            stderr_path=packet_directory / "codex-stderr.txt",
        )
        raise InvocationError(
            observation["classification"], failure_observation=observation,
        )
    if output_path.stat().st_size == 0:
        raise InvocationError("CODEX_FINAL_MISSING")


def verify_post_invocation_packet(
    directory: Path,
    schema_path: Path,
    expected_manifest: Mapping[str, object],
) -> None:
    """Revalidate immutable inputs and permit only bounded invocation artifacts."""
    try:
        if directory.is_symlink() or directory.resolve(strict=True) != directory:
            raise InvocationError("POST_INVOCATION_PACKET_ROOT_UNTRUSTED")
        observed_manifest = verify_packet(directory)
    except (PacketError, OSError, KeyError) as exc:
        raise InvocationError("POST_INVOCATION_PACKET_INVALID") from exc
    if observed_manifest != expected_manifest:
        raise InvocationError("POST_INVOCATION_MANIFEST_MISMATCH")
    verify_packet_tree(
        directory,
        schema_path.resolve(strict=True),
        allowed_artifacts=_INVOCATION_ARTIFACTS,
    )


def verify_packet_tree(
    directory: Path,
    schema_path: Path,
    *,
    allowed_artifacts: frozenset[str] = frozenset(),
) -> None:
    """Deny extra paths and aliases around the immutable packet inputs."""
    try:
        manifest = json.loads((directory / "input-manifest.json").read_bytes())
        sources = manifest["sources"]
        expected_sources = {entry["snapshot"] for entry in sources}
        if not isinstance(sources, list) or len(expected_sources) != len(sources):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvocationError("PACKET_TREE_MANIFEST_INVALID") from exc
    allowed = {"input.txt", "input-manifest.json", "resolved-request.json",
               "broker-metadata.json", "input-capacity.json", *allowed_artifacts}
    if "changes" in manifest:
        allowed.add("changes.patch")
    if schema_path.parent == directory:
        allowed.add(schema_path.name)
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        metadata = path.lstat()
        if (len(relative.parts) == 1 and relative.name == "sources"
            and stat.S_ISDIR(metadata.st_mode)):
            continue
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or
            not (len(relative.parts) == 1 and relative.name in allowed or
                 len(relative.parts) == 2 and relative.as_posix() in expected_sources)):
            raise InvocationError("PACKET_TREE_UNTRUSTED")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _exclusive_stream(path: Path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "wb")
