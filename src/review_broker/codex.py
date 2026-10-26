"""Pinned one-shot Codex CLI adapter with failure-preserving evidence."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import os
from pathlib import Path
import subprocess
from typing import Callable, Mapping

from .identity import canonical_bytes
from .reviewer_profile import (
    PROFILE_NAME,
    ReviewerProfileError,
    reviewer_home_from_environment,
    verify_reviewer_profile,
)


class InvocationError(RuntimeError):
    """Codex invocation was rejected or did not complete successfully."""


@dataclass(frozen=True)
class CodexPolicy:
    distribution: str = "@openai/codex"
    distribution_version: str = "0.164.0"
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "xhigh"
    sandbox: str = "credential-isolated-read-only"
    permission_profile: str = PROFILE_NAME


REQUIRED_FLAGS = (
    "--json",
    "--ephemeral",
    "--profile",
    "--strict-config",
    "--ignore-rules",
    "--skip-git-repo-check",
    "--model",
    "--output-schema",
    "--output-last-message",
)

REMOVED_ENVIRONMENT_KEYS = (
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def build_command(schema_path: Path, output_path: Path, policy: CodexPolicy) -> list[str]:
    return [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--profile",
        policy.permission_profile,
        "--strict-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--model",
        policy.model,
        "-c",
        f'model_reasoning_effort="{policy.reasoning_effort}"',
        "--output-schema",
        str(schema_path.resolve()),
        "--output-last-message",
        str(output_path.resolve()),
        "-",
    ]


def ensure_cli_compatibility(help_text: str) -> None:
    for flag in REQUIRED_FLAGS:
        if flag not in help_text:
            raise InvocationError(f"UNSUPPORTED_FLAG:{flag}")


def sanitized_environment(source: Mapping[str, str]) -> tuple[dict[str, str], tuple[str, ...]]:
    environment = dict(source)
    removed: list[str] = []
    for key in REMOVED_ENVIRONMENT_KEYS:
        if key in environment:
            removed.append(key)
            environment.pop(key)
    return environment, tuple(removed)


def classify_failure(text: str) -> str:
    lowered = text.lower()
    if "model" in lowered and any(word in lowered for word in ("unavailable", "not available", "not found")):
        return "MODEL_UNAVAILABLE"
    if any(word in lowered for word in ("login required", "authentication expired", "not logged in", "oauth expired")):
        return "OAUTH_EXPIRED"
    if any(word in lowered for word in ("quota", "usage limit", "rate limit")):
        return "QUOTA_EXHAUSTED"
    return "CODEX_CRASH"


def invoke_once(
    packet_directory: Path,
    schema_path: Path,
    attempt_id: str,
    *,
    trusted_workspace: Path,
    policy: CodexPolicy = CodexPolicy(),
    armed: bool = True,
    runner: Runner = subprocess.run,
    timeout_seconds: int = 3600,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Invoke Codex at most once for a caller-durably-armed attempt."""
    if not armed:
        raise InvocationError("NOT_ARMED")
    packet_directory = packet_directory.resolve(strict=True)
    schema_path = schema_path.resolve(strict=True)
    prompt_path = packet_directory / "input.txt"
    manifest_path = packet_directory / "input-manifest.json"
    output_path = packet_directory / "codex-final.json"
    if not prompt_path.is_file() or not manifest_path.is_file() or not schema_path.is_file():
        raise InvocationError("INVOCATION_INPUT_MISSING")
    protected = (
        "attempt.json",
        "prompt.sha256",
        "codex-events.jsonl",
        "codex-stderr.txt",
        "codex-final.json",
        "codex-exit-code.txt",
        "input-before.sha256",
        "input-after.sha256",
        "validation.json",
    )
    if any((packet_directory / name).exists() for name in protected):
        raise InvocationError("ALREADY_ATTEMPTED")
    prompt_before = _digest(prompt_path.read_bytes())
    command = build_command(schema_path, output_path, policy)
    child_environment, removed = sanitized_environment(environment or os.environ)
    try:
        reviewer_home = reviewer_home_from_environment(child_environment)
        profile_path = verify_reviewer_profile(reviewer_home, trusted_workspace)
    except ReviewerProfileError as exc:
        raise InvocationError(f"SECURITY_PROFILE_INVALID:{exc}") from exc
    attempt = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "executor": "codex-cli",
        "distribution": policy.distribution,
        "distribution_version": policy.distribution_version,
        "model_requested": policy.model,
        "reasoning_effort_requested": policy.reasoning_effort,
        "effective_model_identity_verified": False,
        "effective_reasoning_effort_verified": False,
        "sandbox": policy.sandbox,
        "permission_profile": policy.permission_profile,
        "permission_profile_sha256": _digest(profile_path.read_bytes()),
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
    transport_error: str | None = None
    try:
        with prompt_path.open("rb") as source, _exclusive_stream(packet_directory / "codex-events.jsonl") as events, _exclusive_stream(packet_directory / "codex-stderr.txt") as stderr:
            try:
                result = runner(
                    command,
                    cwd=str(packet_directory),
                    stdin=source,
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
                transport_error = "CODEX_TIMEOUT_INDETERMINATE"
            except OSError:
                exit_value = "OS_ERROR"
                transport_error = "CODEX_OS_ERROR"
    finally:
        prompt_after = _digest(prompt_path.read_bytes())
        _write_exclusive(packet_directory / "input-after.sha256", (prompt_after + "\n").encode("ascii"))
        _write_exclusive(packet_directory / "codex-exit-code.txt", (exit_value + "\n").encode("ascii"))
        if not output_path.exists():
            _write_exclusive(output_path, b"")
    if prompt_after != prompt_before:
        raise InvocationError("INPUT_CHANGED_DURING_EXECUTION")
    if transport_error is not None:
        raise InvocationError(transport_error)
    if exit_value != "0":
        stderr_text = (packet_directory / "codex-stderr.txt").read_text(encoding="utf-8", errors="replace")
        event_text = (packet_directory / "codex-events.jsonl").read_text(encoding="utf-8", errors="replace")
        raise InvocationError(classify_failure(stderr_text + "\n" + event_text))
    if output_path.stat().st_size == 0:
        raise InvocationError("CODEX_FINAL_MISSING")


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
