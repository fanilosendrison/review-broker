"""Independent execution, response-schema, and citation validation."""
from __future__ import annotations

import hashlib
from importlib import resources
import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .admission import BOUNDED_V1_ADMISSION, COMPREHENSIVE_ADMISSION
from .assurance_validation import admission_mode as read_admission_mode, assurance_errors
from .evidence import (
    EvidenceCaptureError,
    REQUIRED_EVIDENCE_FILES,
    TERMINAL_CAPTURE_FILES,
    credential_material_detected,
    evidence_manifest,
    scan_for_credentials,
    validate_terminal_capture_receipt,
)
from .identity import artifact_identity, canonical_bytes
from .packets import PacketError, source_lines, verify_packet


def validate_evidence(directory: Path, *, setup: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate observed artifacts without adjudicating reviewer semantics."""
    if (directory / "validation.json").exists():
        raise ValueError("ALREADY_VALIDATED")
    reasons: list[str] = []
    execution_status = "COMPLETED"
    evidence_status = "VALID"
    review_verdict = "UNDETERMINED"
    response: dict[str, Any] = {}
    manifest: dict[str, Any] = setup or {}
    try:
        verified = verify_packet(directory)
        if setup is not None and verified.get("packet_id") != setup.get("packet_id"):
            reasons.append("SETUP_PACKET_ID_MISMATCH")
        manifest = verified
    except (PacketError, OSError, KeyError, json.JSONDecodeError) as exc:
        reasons.append(f"PACKET_INVALID:{type(exc).__name__}")
    inventory = evidence_manifest(directory)
    admission_mode = read_admission_mode(directory)
    inactive_assurance = {
        BOUNDED_V1_ADMISSION: "reviewer-security-probe.json",
        COMPREHENSIVE_ADMISSION: "bounded-v1-preflight.json",
    }.get(admission_mode)
    missing = [
        name for name in REQUIRED_EVIDENCE_FILES
        if name not in {"validation.json", inactive_assurance}
        and not inventory[name]["present"]
    ]
    if missing:
        reasons.append("MISSING_EVIDENCE:" + ",".join(missing))
        execution_status = "INDETERMINATE"
    contaminated = scan_for_credentials(directory)
    incident = directory / "credential-incident.json"
    incident_present = incident.exists() or incident.is_symlink()
    if incident_present:
        # A sanitized incident remains a permanent publication veto after raw
        # evidence has been destroyed, even if the incident is malformed.
        reasons.append("CREDENTIAL_MATERIAL_DETECTED_QUARANTINED")
    if contaminated:
        reasons.append("CREDENTIAL_MATERIAL_DETECTED")
    reasons.extend(assurance_errors(directory, manifest, admission_mode))
    reasons.extend(_terminal_capture_errors(directory, manifest, inventory))
    exit_value = _read_text(directory / "codex-exit-code.txt").strip()
    if exit_value and exit_value != "0":
        execution_status = "INDETERMINATE" if exit_value in {"TIMEOUT", "NOT_STARTED"} else "FAILED"
        reasons.append("CODEX_EXIT:" + exit_value)
    events, event_error = _events(directory / "codex-events.jsonl")
    if event_error:
        reasons.append(event_error)
    final_agent_message, sequence_valid, failure_event = _ordered_final_agent_message(events)
    if failure_event:
        execution_status = "FAILED"
        reasons.append("CODEX_FAILURE_EVENT")
    if not sequence_valid:
        if execution_status == "COMPLETED":
            execution_status = "INDETERMINATE"
        reasons.append("TERMINAL_EVENT_SEQUENCE_INVALID")
    before = _read_text(directory / "input-before.sha256").strip()
    after = _read_text(directory / "input-after.sha256").strip()
    expected_prompt = manifest.get("prompt_sha256")
    if not expected_prompt or before != expected_prompt or after != expected_prompt:
        reasons.append("PROMPT_INTEGRITY_INVALID")
    final_text = _read_text(directory / "codex-final.json").strip()
    if not final_text or final_text != final_agent_message:
        reasons.append("FINAL_MESSAGE_EVENT_MISMATCH")
        if execution_status == "COMPLETED":
            execution_status = "INDETERMINATE"
    if final_text:
        try:
            loaded = json.loads(final_text)
            if not isinstance(loaded, dict):
                raise TypeError
            response = loaded
        except (json.JSONDecodeError, TypeError):
            reasons.append("RESPONSE_JSON_INVALID")
    schema_errors = []
    if response:
        schema = _findings_schema()
        schema_errors = list(Draft202012Validator(schema).iter_errors(response))
        if schema_errors:
            reasons.append("RESPONSE_SCHEMA_INVALID")
    if response and not schema_errors and manifest:
        if response.get("request_id") != manifest.get("request_id"):
            reasons.append("RESPONSE_REQUEST_ID_MISMATCH")
        if response.get("subject_id") != manifest.get("subject_id"):
            reasons.append("RESPONSE_SUBJECT_ID_MISMATCH")
        if response.get("packet_id") != manifest.get("packet_id"):
            reasons.append("RESPONSE_PACKET_ID_MISMATCH")
        expected_sources = [entry["source_id"] for entry in manifest.get("sources", [])]
        if response.get("sources_examined") != expected_sources:
            reasons.append("SOURCE_COVERAGE_MISMATCH")
        try:
            indexed = source_lines(directory, manifest)
            reasons.extend(_citation_errors(response, indexed))
        except (PacketError, OSError, KeyError):
            reasons.append("SOURCE_INDEX_UNAVAILABLE")
    if reasons:
        evidence_status = "INVALID"
        review_verdict = "UNDETERMINED"
    elif execution_status == "COMPLETED":
        evidence_status = "VALID"
        review_verdict = response["verdict"]
    else:
        evidence_status = "UNDETERMINED"
    # Never serialize model-authored data into a publishable validation record
    # when known credential material was detected anywhere in recovered evidence.
    unsafe = bool(contaminated) or incident_present
    if unsafe:
        response = {}
        reasons = ["SANITIZED_VALIDATION_REASON" if credential_material_detected(reason)
                   else reason for reason in reasons]
        inventory = {name: {"present": entry["present"], "byte_length": None,
                            "sha256": None} for name, entry in inventory.items()}
    result = {
        "schema_version": 1,
        "execution_status": execution_status,
        "evidence_status": evidence_status,
        "review_verdict": review_verdict,
        "request_id": manifest.get("request_id"),
        "subject_id": manifest.get("subject_id"),
        "packet_id": manifest.get("packet_id"),
        "sources_examined": response.get("sources_examined", []),
        "findings": response.get("findings", []),
        "remaining_uncertainties": response.get("remaining_uncertainties", []),
        "assurance_scope": (
            "LOW_SENSITIVITY_V1" if admission_mode == BOUNDED_V1_ADMISSION
            else "COMPREHENSIVE_SECURITY" if admission_mode == COMPREHENSIVE_ADMISSION
            else "UNDETERMINED"
        ),
        "comprehensive_isolation_qualified": False,
        "semantic_correctness_validated": False,
        "effective_model_identity_verified": False,
        "effective_reasoning_effort_verified": False,
        "validation_reasons": reasons,
        "artifact_inventory": inventory,
        "events_sha256": None if unsafe else _file_hash(directory / "codex-events.jsonl"),
        "final_sha256": None if unsafe else _file_hash(directory / "codex-final.json"),
    }
    _write_exclusive(directory / "validation.json", canonical_bytes(result) + b"\n")
    return result


def _terminal_capture_errors(
    directory: Path,
    manifest: dict[str, Any],
    inventory: dict[str, dict[str, Any]],
) -> list[str]:
    try:
        attempt = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
        receipt = json.loads(
            (directory / "terminal-capture.json").read_text(encoding="utf-8")
        )
        recovery = json.loads(
            (directory / "recovery-manifest.json").read_text(encoding="utf-8")
        )
        if not all(isinstance(value, dict) for value in (attempt, receipt, recovery)):
            raise TypeError
        validate_terminal_capture_receipt(
            receipt,
            request_id=manifest["request_id"],
            attempt_id=attempt["attempt_id"],
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError, EvidenceCaptureError):
        return ["TERMINAL_CAPTURE_RECEIPT_INVALID"]
    errors: list[str] = []
    if receipt.get("packet_id") != manifest.get("packet_id"):
        errors.append("TERMINAL_CAPTURE_PACKET_ID_MISMATCH")
    if (
        recovery.get("evidence_type") != "runtime-evidence-recovery"
        or recovery.get("request_id") != manifest.get("request_id")
        or recovery.get("attempt_id") != attempt.get("attempt_id")
        or recovery.get("complete") is not True
    ):
        errors.append("RECOVERY_MANIFEST_INVALID")
    recovered = recovery.get("artifacts")
    for name in TERMINAL_CAPTURE_FILES:
        actual = inventory[name]
        captured = receipt["artifacts"][name]
        recovered_entry = recovered.get(name) if isinstance(recovered, dict) else None
        if (
            not actual["present"]
            or captured["sha256"] != actual["sha256"]
            or captured["byte_length"] != actual["byte_length"]
        ):
            errors.append(f"TERMINAL_CAPTURE_ARTIFACT_MISMATCH:{name}")
        actual_artifact_id = (
            artifact_identity((directory / name).read_bytes())
            if actual["present"]
            else None
        )
        if (
            not isinstance(recovered_entry, dict)
            or recovered_entry.get("recovered") is not True
            or recovered_entry.get("artifact_id") != actual_artifact_id
        ):
            errors.append(f"RECOVERY_ARTIFACT_MISMATCH:{name}")
    return errors


def _citation_errors(response: dict[str, Any], indexed: dict[str, tuple[str, ...]]) -> list[str]:
    errors: list[str] = []
    for finding in response.get("findings", []):
        for citation in finding.get("evidence", []):
            source_id = citation.get("source_id")
            line = citation.get("line")
            quote = citation.get("quote")
            lines = indexed.get(source_id)
            if (
                lines is None
                or type(line) is not int
                or line < 1
                or line > len(lines)
                or not isinstance(quote, str)
                or quote not in lines[line - 1]
            ):
                errors.append(f"CITATION_NOT_ANCHORED:{finding.get('id', 'UNKNOWN')}")
    return errors


def _ordered_final_agent_message(
    events: list[dict[str, Any]],
) -> tuple[str | None, bool, bool]:
    """Return the last in-turn agent message and strict sequence validity."""
    started = [index for index, event in enumerate(events)
               if event.get("type") == "turn.started"]
    terminal = [index for index, event in enumerate(events)
                if event.get("type") in {"turn.completed", "turn.failed"}]
    failure_event = any(
        event.get("type") in {"turn.failed", "error"} for event in events
    )
    if len(started) != 1 or len(terminal) != 1 or started[0] >= terminal[0]:
        return None, False, failure_event
    messages = [
        (index, item["text"].strip())
        for index, event in enumerate(events)
        if event.get("type") == "item.completed"
        and isinstance((item := event.get("item")), dict)
        and item.get("type") == "agent_message"
        and isinstance(item.get("text"), str)
    ]
    if not messages or any(
        index <= started[0] or index >= terminal[0] for index, _ in messages
    ):
        return None, False, failure_event
    return messages[-1][1], True, failure_event


def _events(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    events: list[dict[str, Any]] = []
    text = _read_text(path)
    if not text:
        return events, "CODEX_EVENTS_MISSING"
    try:
        for line in text.splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict) or not isinstance(value.get("type"), str):
                    return events, "CODEX_EVENT_INVALID"
                events.append(value)
    except json.JSONDecodeError:
        return events, "CODEX_EVENTS_JSON_INVALID"
    return events, None


def _findings_schema() -> dict[str, Any]:
    target = resources.files("review_broker.schemas").joinpath("reviewer-findings-v1.schema.json")
    return json.loads(target.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _write_exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
