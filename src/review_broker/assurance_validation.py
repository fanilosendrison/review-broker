"""Mode-specific pre-arm assurance evidence validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .admission import (
    BOUNDED_PRIVATE_V1_ADMISSION, BOUNDED_V1_ADMISSION, COMPREHENSIVE_ADMISSION,
)
from .bounded_preflight import RUNTIME_EVIDENCE_KEYS, validate_bounded_preflight_receipt
from .codex_runtime_identity import load_codex_release_trust
from .identity import canonical_bytes
from .reviewer_profile import PROFILE_NAME
from .security_probe import validate_probe_receipt


def admission_mode(directory: Path) -> str | None:
    metadata = _admission_metadata(directory)
    value = metadata.get("admission_mode") if metadata is not None else None
    return value if isinstance(value, str) else None


def assurance_errors(
    directory: Path,
    manifest: dict[str, Any],
    mode: str | None,
) -> list[str]:
    try:
        attempt = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["SECURITY_PROFILE_EVIDENCE_INVALID"]
    metadata = _admission_metadata(directory)
    if not isinstance(attempt, dict) or metadata is None:
        return ["SECURITY_PROFILE_EVIDENCE_INVALID"]
    errors: list[str] = []
    if (
        metadata.get("request_id") != manifest.get("request_id")
        or metadata.get("attempt_id") != attempt.get("attempt_id")
    ):
        errors.append("ASSURANCE_METADATA_IDENTITY_MISMATCH")
    errors.extend(_runtime_identity_errors(attempt))
    expected_profile = attempt.get("permission_profile")
    if (
        not isinstance(expected_profile, str)
        or not expected_profile.startswith(PROFILE_NAME + "-")
        or len(expected_profile) != len(PROFILE_NAME) + 1 + 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_profile[len(PROFILE_NAME) + 1:]
        )
    ):
        errors.append("ATTEMPT_PERMISSION_PROFILE_INVALID")
    if attempt.get("credential_paths_denied") is not True:
        errors.append("ATTEMPT_CREDENTIAL_DENIAL_UNVERIFIED")
    if attempt.get("trusted_workspace_denied") is not True:
        errors.append("ATTEMPT_TRUSTED_WORKSPACE_DENIAL_UNVERIFIED")
    if attempt.get("network_access") is not False:
        errors.append("ATTEMPT_NETWORK_ACCESS_INVALID")
    broker_wheel_sha256 = attempt.get("broker_wheel_sha256")
    if not _sha256(broker_wheel_sha256):
        errors.append("ATTEMPT_BROKER_WHEEL_SHA256_INVALID")
    profile_sha256 = attempt.get("permission_profile_sha256")
    if not _sha256(profile_sha256):
        errors.append("ATTEMPT_PERMISSION_PROFILE_SHA256_INVALID")
        return errors
    if mode == COMPREHENSIVE_ADMISSION:
        return errors + _comprehensive_errors(
            directory, profile_sha256, expected_profile
        )
    if mode in {BOUNDED_V1_ADMISSION, BOUNDED_PRIVATE_V1_ADMISSION}:
        return errors + _bounded_errors(
            directory,
            manifest,
            metadata,
            attempt,
            expected_profile,
            profile_sha256,
            broker_wheel_sha256,
        )
    return errors + ["ASSURANCE_MODE_INVALID"]


def _comprehensive_errors(
    directory: Path,
    profile_sha256: str,
    expected_profile: str,
) -> list[str]:
    errors = []
    if (directory / "bounded-v1-preflight.json").exists():
        errors.append("CROSS_MODE_ASSURANCE_EVIDENCE_PRESENT")
    try:
        receipt = json.loads(
            (directory / "reviewer-security-probe.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return errors + ["SECURITY_PROFILE_EVIDENCE_INVALID"]
    if not isinstance(receipt, dict):
        return errors + ["SECURITY_PROFILE_EVIDENCE_INVALID"]
    return errors + validate_probe_receipt(
        receipt, profile_sha256, expected_profile
    )


def _bounded_errors(
    directory: Path,
    manifest: dict[str, Any],
    metadata: dict[str, Any],
    attempt: dict[str, Any],
    expected_profile: str,
    profile_sha256: str,
    broker_wheel_sha256: str,
) -> list[str]:
    errors = []
    if (directory / "reviewer-security-probe.json").exists():
        errors.append("CROSS_MODE_ASSURANCE_EVIDENCE_PRESENT")
    try:
        receipt = json.loads(
            (directory / "bounded-v1-preflight.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return errors + ["BOUNDED_PREFLIGHT_EVIDENCE_INVALID"]
    if not isinstance(receipt, dict):
        return errors + ["BOUNDED_PREFLIGHT_EVIDENCE_INVALID"]
    argv = attempt.get("argv")
    if (
        attempt.get("model_requested") != "gpt-5.6-sol"
        or attempt.get("reasoning_effort_requested") != "xhigh"
        or attempt.get("shell_tool_requested") is not False
        or attempt.get("effective_policy_attestation") != "UNAVAILABLE"
        or attempt.get("api_key_fallback_forbidden") is not True
        or not isinstance(argv, list)
        or argv.count("features.shell_tool=false") != 1
        or "--api-key" in argv
    ):
        errors.append("BOUNDED_PREFLIGHT_EXECUTION_POLICY_INVALID")
    if receipt.get("environment_keys_removed") != attempt.get("environment_keys_removed"):
        errors.append("BOUNDED_PREFLIGHT_ENVIRONMENT_EVIDENCE_MISMATCH")
    runtime_evidence = {key: attempt.get(key) for key in RUNTIME_EVIDENCE_KEYS}
    return errors + validate_bounded_preflight_receipt(
        receipt,
        request_id=manifest.get("request_id"),
        attempt_id=attempt.get("attempt_id"),
        packet_id=manifest.get("packet_id"),
        subject_id=manifest.get("subject_id"),
        executing_broker_sha=metadata.get("executing_broker_sha"),
        permission_profile=expected_profile,
        permission_profile_sha256=profile_sha256,
        broker_wheel_sha256=broker_wheel_sha256,
        runtime_evidence=runtime_evidence,
        admission_mode=metadata.get("admission_mode"),
    )


def _runtime_identity_errors(attempt: dict[str, Any]) -> list[str]:
    trust = load_codex_release_trust()
    distribution = trust["distribution"]
    platform_trust = trust["platforms"]["linux-x86_64"]
    expected = {
        "runtime_identity_verification": "VERIFIED_OFFICIAL_NPM_ARTIFACT",
        "distribution": distribution["name"],
        "distribution_version": distribution["version"],
        "platform_alias": platform_trust["npm_alias"],
        "platform_version": platform_trust["published_version"],
        "codex_launcher_sha256": distribution["launcher_sha256"],
        "codex_native_sha256": platform_trust["native_sha256"],
        "root_dist_integrity": distribution["dist_integrity"],
        "platform_dist_integrity": platform_trust["dist_integrity"],
        "node_interpreter_used": False,
        "execution_stability": "ROOT_OWNED_NON_WRITABLE_PACKAGE_LAYOUT",
    }
    if any(attempt.get(key) != value for key, value in expected.items()):
        return ["ATTEMPT_CODEX_RUNTIME_IDENTITY_INVALID"]
    protected_root = attempt.get("protected_runtime_root")
    executable = attempt.get("execution_native")
    if (
        not isinstance(protected_root, str)
        or not Path(protected_root).is_absolute()
        or not isinstance(executable, str)
        or Path(executable) != Path(protected_root) / "bin" / "codex"
    ):
        return ["ATTEMPT_CODEX_EXECUTION_PATH_INVALID"]
    return []


def _admission_metadata(directory: Path) -> dict[str, Any] | None:
    try:
        raw = (directory / "broker-metadata.json").read_bytes()
        metadata = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict) or raw != canonical_bytes(metadata) + b"\n":
        return None
    return metadata


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
