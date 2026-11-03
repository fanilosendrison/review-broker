"""Proportionate pre-arm evidence for admitted low-sensitivity v1 reviews."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .admission import BOUNDED_PRIVATE_V1_ADMISSION, BOUNDED_V1_ADMISSION
from .codex import (
    CodexPolicy,
    build_command,
    sanitized_environment,
    verify_packet_tree,
)
from .codex_runtime_identity import VerifiedCodexRuntime, verify_codex_runtime
from .identity import canonical_bytes
from .input_capacity import CapacityError, capacity_receipt, read_verified_input, validate_capacity_receipt
from .packets import verify_packet
from .reviewer_profile import profile_name, reviewer_home_from_environment, verify_reviewer_profile


class BoundedPreflightError(ValueError):
    """Bounded-v1 pre-arm evidence cannot be established or validated."""


RuntimeVerifier = Callable[[Mapping[str, str], Path], VerifiedCodexRuntime]
RUNTIME_EVIDENCE_KEYS = (
    "runtime_identity_verification", "distribution", "distribution_version",
    "platform_alias", "platform_version", "codex_launcher_sha256",
    "codex_native_sha256", "protected_runtime_root", "execution_native",
    "root_dist_integrity", "platform_dist_integrity", "node_interpreter_used",
    "execution_stability",
)


def build_bounded_preflight(
    packet_directory: Path,
    schema_path: Path,
    *,
    attempt_id: str,
    expected_packet_id: str,
    broker_wheel_sha256: str,
    trusted_workspace: Path,
    codex_runtime_root: Path,
    executing_broker_sha: str,
    environment: Mapping[str, str] | None = None,
    runtime_verifier: RuntimeVerifier = verify_codex_runtime,
) -> dict[str, Any]:
    packet_directory = packet_directory.resolve(strict=True)
    schema_path = schema_path.resolve(strict=True)
    child_environment, removed = sanitized_environment(environment or os.environ)
    runtime = runtime_verifier(child_environment, codex_runtime_root)
    manifest = verify_packet(packet_directory)
    if manifest.get("packet_id") != expected_packet_id:
        raise BoundedPreflightError("PREFLIGHT_PACKET_ID_MISMATCH")
    verify_packet_tree(packet_directory, schema_path)
    metadata = _canonical_object(packet_directory / "broker-metadata.json")
    resolved = _canonical_object(packet_directory / "resolved-request.json")
    expected_profile = profile_name(packet_directory)
    home = reviewer_home_from_environment(child_environment)
    profile = verify_reviewer_profile(home, trusted_workspace, packet_directory)
    admission_mode = metadata.get("admission_mode")
    if admission_mode not in {BOUNDED_V1_ADMISSION, BOUNDED_PRIVATE_V1_ADMISSION}:
        raise BoundedPreflightError("PREFLIGHT_ADMISSION_MODE_INVALID")
    admission_checks = _admission_checks(admission_mode)
    if metadata.get("admission_checks") != admission_checks:
        raise BoundedPreflightError("PREFLIGHT_ADMISSION_EVIDENCE_INVALID")
    identities = {
        "request_id": manifest.get("request_id"),
        "attempt_id": attempt_id,
        "packet_id": expected_packet_id,
        "executing_broker_sha": executing_broker_sha,
    }
    if (
        metadata.get("request_id") != identities["request_id"]
        or metadata.get("attempt_id") != attempt_id
        or metadata.get("executing_broker_sha") != executing_broker_sha
        or resolved.get("request_id") != identities["request_id"]
        or resolved.get("subject_id") != manifest.get("subject_id")
        or not _sha(executing_broker_sha, 40)
        or not _sha(broker_wheel_sha256, 64)
    ):
        raise BoundedPreflightError("PREFLIGHT_IDENTITY_MISMATCH")
    _, input_bytes = read_verified_input(packet_directory, expected_packet_id)
    capacity = capacity_receipt(input_bytes, request_id=manifest["request_id"],
        packet_id=expected_packet_id, attempt_id=attempt_id, executing_broker_sha=executing_broker_sha)
    if capacity["status"] != "PASS":
        raise BoundedPreflightError("INPUT_CAPACITY_REJECTED:" + canonical_bytes(capacity).decode("utf-8"))
    policy = CodexPolicy()
    command = build_command(
        runtime.executable,
        schema_path,
        packet_directory / "codex-final.json",
        policy,
        expected_profile,
    )
    if command.count("features.shell_tool=false") != 1:
        raise BoundedPreflightError("PREFLIGHT_SHELL_DISABLE_INVALID")
    receipt = {
        "schema_version": 1,
        "evidence_type": _evidence_type(admission_mode),
        "assurance_scope": _assurance_scope(admission_mode),
        "admission_mode": admission_mode,
        "direct_sandbox_probe_executed": False,
        "comprehensive_isolation_qualified": False,
        "runtime_identity": "VERIFIED",
        "profile_identity": "VERIFIED",
        "packet_tree_integrity": "VERIFIED",
        "effective_codex_policy_attestation": "UNAVAILABLE",
        **identities,
        "subject_id": manifest["subject_id"],
        "input_capacity": capacity,
        "permission_profile": expected_profile,
        "permission_profile_sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
        "broker_wheel_sha256": broker_wheel_sha256,
        "shell_tool_requested": False,
        "model_requested": policy.model,
        "reasoning_effort_requested": policy.reasoning_effort,
        "api_key_fallback_forbidden": True,
        "model_substitution_forbidden": True,
        "reviewer_publication_authority": False,
        "trusted_admission": "VERIFIED_PRE_CLAIM",
        "admission_checks": admission_checks,
        "environment_keys_removed": list(removed),
        **runtime.evidence(),
    }
    errors = validate_bounded_preflight_receipt(
        receipt,
        request_id=manifest["request_id"],
        attempt_id=attempt_id,
        packet_id=expected_packet_id,
        subject_id=manifest["subject_id"],
        executing_broker_sha=executing_broker_sha,
        permission_profile=expected_profile,
        permission_profile_sha256=receipt["permission_profile_sha256"],
        broker_wheel_sha256=broker_wheel_sha256,
        runtime_evidence=runtime.evidence(),
        admission_mode=admission_mode,
    )
    if errors:
        raise BoundedPreflightError(errors[0])
    return receipt


def validate_bounded_preflight_receipt(
    receipt: Mapping[str, Any],
    *,
    request_id: str,
    attempt_id: str,
    packet_id: str,
    subject_id: str,
    executing_broker_sha: str,
    permission_profile: str,
    permission_profile_sha256: str,
    broker_wheel_sha256: str,
    runtime_evidence: Mapping[str, Any],
    admission_mode: str = BOUNDED_V1_ADMISSION,
) -> list[str]:
    required = {
        "evidence_type": _evidence_type(admission_mode),
        "assurance_scope": _assurance_scope(admission_mode),
        "direct_sandbox_probe_executed": False,
        "comprehensive_isolation_qualified": False,
        "runtime_identity": "VERIFIED",
        "profile_identity": "VERIFIED",
        "packet_tree_integrity": "VERIFIED",
        "effective_codex_policy_attestation": "UNAVAILABLE",
        "request_id": request_id,
        "attempt_id": attempt_id,
        "packet_id": packet_id,
        "subject_id": subject_id,
        "executing_broker_sha": executing_broker_sha,
        "permission_profile": permission_profile,
        "permission_profile_sha256": permission_profile_sha256,
        "broker_wheel_sha256": broker_wheel_sha256,
        "shell_tool_requested": False,
        "model_requested": CodexPolicy().model,
        "reasoning_effort_requested": CodexPolicy().reasoning_effort,
        "api_key_fallback_forbidden": True,
        "model_substitution_forbidden": True,
        "reviewer_publication_authority": False,
        "trusted_admission": "VERIFIED_PRE_CLAIM",
        "admission_checks": _admission_checks(admission_mode),
    }
    errors = [
        "BOUNDED_PREFLIGHT_FIELD_INVALID:" + key
        for key, value in required.items() if receipt.get(key) != value
    ]
    capacity = receipt.get("input_capacity")
    if "input_capacity" in receipt:
        try:
            validate_capacity_receipt(capacity)
            if (capacity["status"] != "PASS" or any(capacity[k] != v for k, v in {
                "request_id": request_id, "attempt_id": attempt_id,
                "packet_id": packet_id, "executing_broker_sha": executing_broker_sha,
            }.items())):
                raise CapacityError("CAPACITY_BINDING_INVALID")
        except (CapacityError, TypeError, KeyError):
            errors.append("BOUNDED_PREFLIGHT_INPUT_CAPACITY_INVALID")
    receipt_mode = receipt.get("admission_mode")
    if admission_mode == BOUNDED_PRIVATE_V1_ADMISSION:
        if receipt_mode != admission_mode:
            errors.append("BOUNDED_PREFLIGHT_FIELD_INVALID:admission_mode")
    elif receipt_mode not in {None, BOUNDED_V1_ADMISSION}:
        errors.append("BOUNDED_PREFLIGHT_FIELD_INVALID:admission_mode")
    if receipt.get("schema_version") != 1:
        errors.append("BOUNDED_PREFLIGHT_SCHEMA_INVALID")
    if any(receipt.get(key) != runtime_evidence.get(key) for key in RUNTIME_EVIDENCE_KEYS):
        errors.append("BOUNDED_PREFLIGHT_RUNTIME_IDENTITY_INVALID")
    removed = receipt.get("environment_keys_removed")
    if not isinstance(removed, list) or any(not isinstance(item, str) for item in removed):
        errors.append("BOUNDED_PREFLIGHT_ENVIRONMENT_EVIDENCE_INVALID")
    return errors


def _evidence_type(mode: str) -> str:
    return ("bounded-private-v1-preflight" if mode == BOUNDED_PRIVATE_V1_ADMISSION
            else "bounded-low-sensitivity-v1-preflight")


def _assurance_scope(mode: str) -> str:
    return "BOUNDED_PRIVATE_V1" if mode == BOUNDED_PRIVATE_V1_ADMISSION else "LOW_SENSITIVITY_V1"


def _admission_checks(mode: str) -> dict[str, bool]:
    common = {"requester_authorized": True, "repository_authorized": True,
              "executing_sha_admitted": True}
    if mode == BOUNDED_PRIVATE_V1_ADMISSION:
        return {**common, "bounded_private_request_admitted": True,
                "private_repository_verified": True,
                "private_source_credential_scope_verified": True,
                "public_repository_verified": False}
    return {**common, "low_sensitivity_repository_admitted": True,
            "public_repository_verified": True}


def add_bounded_preflight_arguments(subcommands: Any) -> None:
    command = subcommands.add_parser("internal-bounded-v1-preflight")
    command.add_argument("--packet-dir", required=True, type=Path)
    command.add_argument("--schema", required=True, type=Path)
    command.add_argument("--attempt", required=True)
    command.add_argument("--packet-id", required=True)
    command.add_argument("--broker-wheel-sha256", required=True)
    command.add_argument("--trusted-workspace", required=True, type=Path)
    command.add_argument("--codex-runtime-root", required=True, type=Path)
    command.add_argument("--executing-broker-sha", required=True)


def run_bounded_preflight_command(args: Any) -> dict[str, Any]:
    return build_bounded_preflight(
        args.packet_dir,
        args.schema,
        attempt_id=args.attempt,
        expected_packet_id=args.packet_id,
        broker_wheel_sha256=args.broker_wheel_sha256,
        trusted_workspace=args.trusted_workspace,
        codex_runtime_root=args.codex_runtime_root,
        executing_broker_sha=args.executing_broker_sha,
    )


def _canonical_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedPreflightError("PREFLIGHT_METADATA_INVALID") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
        raise BoundedPreflightError("PREFLIGHT_METADATA_INVALID")
    return value


def _sha(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in "0123456789abcdef" for c in value)
