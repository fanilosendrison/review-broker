"""Pure validation of one retained synthetic-pilot receipt set."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .fileobservation import FileObservationError, read_regular_file_bounded
from .identity import canonical_bytes

_RECEIPT_LIMIT = 1024 * 1024
_REQUEST_ID = re.compile(r"request:sha256:[0-9a-f]{64}\Z")
_ATTEMPT_ID = re.compile(r"attempt:sha256:[0-9a-f]{64}\Z")
_PACKET_ID = re.compile(r"packet:sha256:[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_FAILURE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,127}\Z")
_CONTRADICTORY_PASS_SCREEN_FAILURES = {
    "PILOT_QUARANTINE_FAILED",
    "PILOT_CREDENTIAL_OUTPUT_QUARANTINED",
    "PILOT_CREDENTIAL_SCREEN_UNAVAILABLE",
}


def _schema_v1(value: Mapping[str, Any]) -> bool:
    version = value.get("schema_version")
    return type(version) is int and version == 1


@dataclass(frozen=True)
class ReceiptSetValidation:
    """One authoritative structural and coherence decision for retained receipts."""

    valid: bool
    status: str
    summary: Mapping[str, Any] | None = None


def validate_pilot_receipt_set(
    receipt_directory: Path,
    controller_claim: Mapping[str, Any],
) -> ReceiptSetValidation:
    """Validate canonical receipts against one already-validated controller claim."""
    try:
        remote_claim = _read_receipt(receipt_directory / "pilot-claim.json")
        armed = _read_receipt(receipt_directory / "pilot-armed.json")
        summary = _read_receipt(receipt_directory / "pilot-summary.json")
        failure = _read_optional_receipt(receipt_directory / "pilot-failure.json")
        _validate_remote_claim(remote_claim, controller_claim)
        _validate_armed(armed, remote_claim, controller_claim)
        _validate_summary(summary, remote_claim, armed, controller_claim)
        _validate_outcome(summary, failure, remote_claim, armed, controller_claim)
    except (OSError, UnicodeError, json.JSONDecodeError, FileObservationError, ValueError):
        return ReceiptSetValidation(False, "RECEIPT_SET_INVALID")
    return ReceiptSetValidation(True, "RECEIPT_SET_VALID", summary)


def _read_receipt(path: Path) -> dict[str, Any]:
    raw = read_regular_file_bounded(path, _RECEIPT_LIMIT)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
        raise ValueError("RECEIPT_INVALID")
    return value


def _read_optional_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    return _read_receipt(path)


def _validate_remote_claim(value: Mapping[str, Any], controller: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "pilot_id", "request_id", "attempt_id",
        "packet_id", "status", "armed_utc",
    }
    if set(value) != required or any(value.get(key) != controller.get(key) for key in (
        "pilot_id", "request_id", "attempt_id",
    )):
        raise ValueError("REMOTE_CLAIM_INVALID")
    if (
        not _schema_v1(value) or value.get("status") != "ARMED"
        or not _PACKET_ID.fullmatch(value.get("packet_id", ""))
        or not _timestamp(value.get("armed_utc"))
    ):
        raise ValueError("REMOTE_CLAIM_INVALID")


def _validate_armed(
    value: Mapping[str, Any], remote: Mapping[str, Any], controller: Mapping[str, Any],
) -> None:
    required = {
        "schema_version", "scope", "issue", "attempt_id", "request_id",
        "packet_id", "broker_wheel_sha256", "acknowledged_residual_risk", "armed_utc",
    }
    if not required <= set(value) or any(value.get(key) != remote.get(key) for key in (
        "request_id", "attempt_id", "packet_id", "armed_utc",
    )):
        raise ValueError("ARMED_RECEIPT_INVALID")
    if any(value.get(key) != controller.get(key) for key in ("request_id", "attempt_id")):
        raise ValueError("ARMED_RECEIPT_INVALID")
    if (
        not _schema_v1(value)
        or value.get("scope") != "SYNTHETIC_NONPRODUCTION_ONLY"
        or type(value.get("issue")) is not int or value["issue"] != 26
        or value.get("acknowledged_residual_risk") is not True
        or not _SHA256.fullmatch(value.get("broker_wheel_sha256", ""))
    ):
        raise ValueError("ARMED_RECEIPT_INVALID")


def _validate_summary(
    value: Mapping[str, Any], remote: Mapping[str, Any], armed: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> None:
    required = {
        "schema_version", "issue", "pilot_id", "request_id", "attempt_id", "packet_id",
        "broker_wheel_sha256", "model_requested", "effort_requested",
        "pilot_functional", "pilot_execution", "credential_screen",
        "pilot_security_qualified", "production_security_qualified",
        "github_publication", "reviewer_authority",
    }
    if not required <= set(value):
        raise ValueError("SUMMARY_INVALID")
    if any(value.get(key) != remote.get(key) for key in ("pilot_id", "request_id", "attempt_id", "packet_id")):
        raise ValueError("SUMMARY_INVALID")
    if any(value.get(key) != controller.get(key) for key in ("pilot_id", "request_id", "attempt_id")):
        raise ValueError("SUMMARY_INVALID")
    if (
        not _schema_v1(value)
        or type(value.get("issue")) is not int or value["issue"] != 26
        or value.get("broker_wheel_sha256") != armed.get("broker_wheel_sha256")
        or not isinstance(value.get("model_requested"), str) or not value["model_requested"]
        or not isinstance(value.get("effort_requested"), str) or not value["effort_requested"]
        or value.get("pilot_functional") not in {"PASS", "FAIL"}
        or value.get("pilot_execution") not in {"COMPLETED", "FAILED", "INDETERMINATE"}
        or not isinstance(value.get("credential_screen"), str) or not value["credential_screen"]
        or value.get("pilot_security_qualified") is not False
        or value.get("production_security_qualified") is not False
        or value.get("github_publication") != "NONE"
        or value.get("reviewer_authority") != "NONE"
    ):
        raise ValueError("SUMMARY_INVALID")


def _validate_outcome(
    summary: Mapping[str, Any], failure: Mapping[str, Any] | None,
    remote: Mapping[str, Any], armed: Mapping[str, Any], controller: Mapping[str, Any],
) -> None:
    if summary["pilot_functional"] == "PASS":
        if (
            failure is not None or summary["pilot_execution"] != "COMPLETED"
            or summary.get("schema_and_citations") != "PASS"
            or summary.get("verdict") != "NO_GO"
            or summary["credential_screen"] != "PASS_NO_MATCH"
        ):
            raise ValueError("SUCCESS_RECEIPTS_INCOHERENT")
        return
    classification = summary.get("failure")
    if (
        failure is None or not isinstance(classification, str)
        or not _SAFE_FAILURE.fullmatch(classification)
        or summary["credential_screen"] == "PASS_NO_MATCH"
        and classification in _CONTRADICTORY_PASS_SCREEN_FAILURES
    ):
        raise ValueError("FAILURE_RECEIPTS_INCOHERENT")
    _validate_failure(failure, summary, remote, armed, controller)
    digest = summary.get("failure_receipt_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("FAILURE_RECEIPT_DIGEST_INVALID")
    actual = hashlib.sha256(canonical_bytes(dict(failure)) + b"\n").hexdigest()
    if actual != digest:
        raise ValueError("FAILURE_RECEIPT_DIGEST_INVALID")


def _validate_failure(
    value: Mapping[str, Any], summary: Mapping[str, Any], remote: Mapping[str, Any],
    armed: Mapping[str, Any], controller: Mapping[str, Any],
) -> None:
    required = {
        "schema_version", "pilot_id", "request_id", "attempt_id", "packet_id",
        "classification", "credential_screen", "attempt_identity_consumed",
        "raw_error_messages_retained", "github_publication",
    }
    if not required <= set(value):
        raise ValueError("FAILURE_RECEIPT_INVALID")
    if any(value.get(key) != remote.get(key) for key in ("pilot_id", "request_id", "attempt_id", "packet_id")):
        raise ValueError("FAILURE_RECEIPT_INVALID")
    if any(value.get(key) != controller.get(key) for key in ("pilot_id", "request_id", "attempt_id")):
        raise ValueError("FAILURE_RECEIPT_INVALID")
    if (
        not _schema_v1(value)
        or type(value.get("issue")) is not int or value["issue"] != 26
        or type(value.get("request_ordinal")) is not int or value["request_ordinal"] != 1
        or type(value.get("attempt_ordinal")) is not int or value["attempt_ordinal"] != 1
        or value.get("classification") != summary.get("failure")
        or value.get("credential_screen") != summary.get("credential_screen")
        or value.get("attempt_identity_consumed") is not True
        or value.get("raw_error_messages_retained") is not False
        or value.get("github_publication") != "NONE"
        or value.get("broker_wheel_sha256") != armed.get("broker_wheel_sha256")
        or value.get("model_requested") != summary.get("model_requested")
        or value.get("effort_requested") != summary.get("effort_requested")
        or value.get("pilot_security_qualified") is not False
        or value.get("production_security_qualified") is not False
    ):
        raise ValueError("FAILURE_RECEIPT_INVALID")


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
