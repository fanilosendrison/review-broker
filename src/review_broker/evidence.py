"""Evidence inventory, byte identities, and credential-leak rejection."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .identity import artifact_identity, canonical_bytes

REQUIRED_EVIDENCE_FILES = (
    "attempt.json",
    "input-manifest.json",
    "prompt.sha256",
    "codex-events.jsonl",
    "codex-stderr.txt",
    "codex-final.json",
    "codex-exit-code.txt",
    "input-before.sha256",
    "input-after.sha256",
    "reviewer-security-probe.json",
    "recovery-manifest.json",
    "terminal-capture.json",
    "validation.json",
)

TERMINAL_CAPTURE_FILES = (
    "attempt.json",
    "codex-events.jsonl",
    "codex-stderr.txt",
    "codex-final.json",
    "codex-exit-code.txt",
    "input-before.sha256",
    "input-after.sha256",
)


class EvidenceCaptureError(ValueError):
    """Observed evidence cannot support the requested durable claim."""


_CREDENTIAL_PATTERNS = (
    re.compile(rb'"(?:access_token|refresh_token|session_cookie|authorization)"\s*:', re.IGNORECASE),
    re.compile(rb"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
)


def evidence_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_EVIDENCE_FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            manifest[name] = {"present": False, "byte_length": 0, "sha256": None}
            continue
        data = path.read_bytes()
        manifest[name] = {
            "present": True,
            "byte_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return manifest


def missing_evidence(directory: Path) -> list[str]:
    return [name for name, entry in evidence_manifest(directory).items() if not entry["present"]]


def scan_for_credentials(directory: Path) -> list[str]:
    contaminated: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in _CREDENTIAL_PATTERNS):
            contaminated.append(path.name)
    return contaminated


def build_terminal_capture_receipt(
    directory: Path,
    *,
    request_id: str,
    attempt_id: str,
    packet_id: str,
    context: Mapping[str, str],
    observed_at: str | None = None,
) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {}
    for name in TERMINAL_CAPTURE_FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise EvidenceCaptureError(f"TERMINAL_ARTIFACT_MISSING:{name}")
        data = path.read_bytes()
        artifacts[name] = {
            "byte_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    attempt = _json_object(directory / "attempt.json", "TERMINAL_ATTEMPT_INVALID")
    if attempt.get("attempt_id") != attempt_id:
        raise EvidenceCaptureError("TERMINAL_ATTEMPT_ID_MISMATCH")
    manifest = _json_object(
        directory / "input-manifest.json",
        "TERMINAL_PACKET_MANIFEST_INVALID",
    )
    if manifest.get("request_id") != request_id:
        raise EvidenceCaptureError("TERMINAL_REQUEST_ID_MISMATCH")
    if manifest.get("packet_id") != packet_id:
        raise EvidenceCaptureError("TERMINAL_PACKET_ID_MISMATCH")
    events = _terminal_events(directory / "codex-events.jsonl")
    started = [index for index, event in enumerate(events) if event["type"] == "turn.started"]
    terminal = [
        (index, event["type"])
        for index, event in enumerate(events)
        if event["type"] in {"turn.completed", "turn.failed"}
    ]
    if len(started) != 1 or len(terminal) != 1 or started[0] >= terminal[0][0]:
        raise EvidenceCaptureError("TERMINAL_EVENT_SEQUENCE_INVALID")
    if any(
        event["type"] in {"turn.started", "turn.completed", "turn.failed"}
        for event in events[terminal[0][0] + 1:]
    ):
        raise EvidenceCaptureError("TERMINAL_EVENT_SEQUENCE_INVALID")

    exit_value = (directory / "codex-exit-code.txt").read_text(
        encoding="utf-8", errors="strict"
    ).strip()
    terminal_event = terminal[0][1]
    if terminal_event == "turn.completed" and exit_value != "0":
        raise EvidenceCaptureError("TERMINAL_EXIT_CONTRADICTORY")
    if terminal_event == "turn.failed" and (
        not exit_value.isdigit() or int(exit_value) == 0
    ):
        raise EvidenceCaptureError("TERMINAL_EXIT_CONTRADICTORY")

    checked_context = _observation_context(context)
    receipt = {
        "schema_version": 1,
        "evidence_type": "terminal-capture",
        "request_id": request_id,
        "attempt_id": attempt_id,
        "packet_id": packet_id,
        "terminal_event": terminal_event,
        "observed_at": observed_at or _utc_now(),
        "context": checked_context,
        "artifacts": artifacts,
    }
    validate_terminal_capture_receipt(
        receipt,
        request_id=request_id,
        attempt_id=attempt_id,
    )
    return receipt


def validate_terminal_capture_receipt(
    receipt: Mapping[str, Any],
    *,
    request_id: str,
    attempt_id: str,
) -> str:
    if receipt.get("evidence_type") != "terminal-capture":
        raise EvidenceCaptureError("TERMINAL_RECEIPT_INVALID")
    if receipt.get("request_id") != request_id:
        raise EvidenceCaptureError("TERMINAL_REQUEST_ID_MISMATCH")
    if receipt.get("attempt_id") != attempt_id:
        raise EvidenceCaptureError("TERMINAL_ATTEMPT_ID_MISMATCH")
    if receipt.get("terminal_event") not in {"turn.completed", "turn.failed"}:
        raise EvidenceCaptureError("TERMINAL_EVENT_INVALID")
    _validate_timestamp(receipt.get("observed_at"), "TERMINAL_OBSERVATION_TIME_INVALID")
    _observation_context(receipt.get("context"))
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(TERMINAL_CAPTURE_FILES):
        raise EvidenceCaptureError("TERMINAL_ARTIFACT_INVENTORY_INVALID")
    for name in TERMINAL_CAPTURE_FILES:
        entry = artifacts[name]
        if (
            not isinstance(entry, dict)
            or type(entry.get("byte_length")) is not int
            or entry["byte_length"] < 0
            or not _sha256(entry.get("sha256"))
        ):
            raise EvidenceCaptureError(f"TERMINAL_ARTIFACT_IDENTITY_INVALID:{name}")
    return artifact_identity(canonical_bytes(dict(receipt)) + b"\n")


def build_shutdown_observation(
    *,
    codespace_name: str,
    request_id: str,
    attempt_id: str,
    observed_state: str,
    context: Mapping[str, str],
    observed_at: str | None = None,
) -> dict[str, Any]:
    if observed_state != "Shutdown":
        raise EvidenceCaptureError("SHUTDOWN_OBSERVATION_INVALID")
    receipt = {
        "schema_version": 1,
        "evidence_type": "codespace-shutdown-observation",
        "codespace_name": codespace_name,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "observed_state": observed_state,
        "observed_at": observed_at or _utc_now(),
        "context": _observation_context(context),
    }
    validate_shutdown_observation(
        receipt,
        request_id=request_id,
        attempt_id=attempt_id,
    )
    return receipt


def validate_shutdown_observation(
    receipt: Mapping[str, Any],
    *,
    request_id: str,
    attempt_id: str,
) -> str:
    if receipt.get("evidence_type") != "codespace-shutdown-observation":
        raise EvidenceCaptureError("SHUTDOWN_OBSERVATION_INVALID")
    if receipt.get("request_id") != request_id:
        raise EvidenceCaptureError("SHUTDOWN_REQUEST_MISMATCH")
    if receipt.get("attempt_id") != attempt_id:
        raise EvidenceCaptureError("SHUTDOWN_ATTEMPT_MISMATCH")
    if receipt.get("observed_state") != "Shutdown":
        raise EvidenceCaptureError("SHUTDOWN_OBSERVATION_INVALID")
    if not isinstance(receipt.get("codespace_name"), str) or not receipt["codespace_name"]:
        raise EvidenceCaptureError("SHUTDOWN_CODESPACE_INVALID")
    _validate_timestamp(receipt.get("observed_at"), "SHUTDOWN_OBSERVATION_TIME_INVALID")
    _observation_context(receipt.get("context"))
    return artifact_identity(canonical_bytes(dict(receipt)) + b"\n")


def _terminal_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise EvidenceCaptureError("TERMINAL_EVENTS_UNREADABLE") from exc
    if not lines:
        raise EvidenceCaptureError("TERMINAL_EVENTS_MISSING")
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceCaptureError("TERMINAL_EVENTS_JSON_INVALID") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise EvidenceCaptureError("TERMINAL_EVENT_INVALID")
        events.append(event)
    if not events:
        raise EvidenceCaptureError("TERMINAL_EVENTS_MISSING")
    return events


def _json_object(path: Path, error: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceCaptureError(error) from exc
    if not isinstance(value, dict):
        raise EvidenceCaptureError(error)
    return value


def _observation_context(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise EvidenceCaptureError("OBSERVATION_CONTEXT_INVALID")
    context = dict(value)
    if any(not isinstance(key, str) or not isinstance(item, str) for key, item in context.items()):
        raise EvidenceCaptureError("OBSERVATION_CONTEXT_INVALID")
    required = {"workflow_run_id", "workflow_run_attempt"}
    if not required <= set(context) or any(not context[key] for key in required):
        raise EvidenceCaptureError("OBSERVATION_CONTEXT_INVALID")
    return context


def _validate_timestamp(value: Any, error: str) -> None:
    if not isinstance(value, str):
        raise EvidenceCaptureError(error)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceCaptureError(error) from exc
    if parsed.tzinfo is None:
        raise EvidenceCaptureError(error)


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
