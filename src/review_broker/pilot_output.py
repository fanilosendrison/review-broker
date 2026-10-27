"""Bounded validation of private synthetic-pilot model evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .codexfailure import observe_codex_failure
from .fileobservation import FileObservationError, read_regular_file_bounded
from .packets import source_lines
from .validation import _citation_errors, _findings_schema, _ordered_final_agent_message

_MAX_PILOT_EVENT_STREAM_BYTES = (65_536 + 1) * 1_024
_MAX_PILOT_FINAL_BYTES = 65_536
_MAX_PILOT_EXIT_BYTES = 32


def _pilot_events(value: bytes) -> tuple[list[dict[str, Any]], str | None]:
    status = observe_codex_failure(
        returncode=0, event_bytes=value, stderr_bytes=None,
    )["event_stream_status"]
    if status != "PARSED":
        return [], "PILOT_CODEX_EVENTS_" + status
    try:
        events = [json.loads(line) for line in value.decode("utf-8").splitlines()
                  if line.strip()]
    except (UnicodeError, json.JSONDecodeError):
        return [], "PILOT_CODEX_EVENTS_MALFORMED"
    return events, None


def pilot_output(evidence: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Check bounded pilot evidence; do not claim production EvidenceStatus.VALID."""
    errors: list[str] = []
    try:
        event_bytes = read_regular_file_bounded(
            evidence / "codex-events.jsonl", _MAX_PILOT_EVENT_STREAM_BYTES,
        )
    except (OSError, FileObservationError):
        event_bytes, events, event_error = b"", [], "PILOT_CODEX_EVENTS_UNAVAILABLE"
    else:
        events, event_error = _pilot_events(event_bytes)
    if event_error:
        errors.append(event_error)
    final_agent_message, sequence_valid, failed = _ordered_final_agent_message(events)
    if not sequence_valid or failed:
        errors.append("PILOT_TERMINAL_EVENTS_INVALID")
    try:
        exit_code = read_regular_file_bounded(
            evidence / "codex-exit-code.txt", _MAX_PILOT_EXIT_BYTES,
        ).decode("ascii").strip()
    except (OSError, UnicodeError, FileObservationError):
        exit_code = "MISSING"
    if exit_code != "0":
        errors.append("PILOT_CODEX_EXIT_INVALID")
    try:
        final_bytes = read_regular_file_bounded(
            evidence / "codex-final.json", _MAX_PILOT_FINAL_BYTES,
        )
        raw_final = final_bytes.decode("utf-8").strip()
    except (OSError, UnicodeError, FileObservationError):
        final_bytes, raw_final = b"", ""
    if not raw_final or raw_final != final_agent_message:
        errors.append("PILOT_FINAL_MESSAGE_MISMATCH")
    response: dict[str, Any] = {}
    try:
        candidate = json.loads(raw_final)
        if not isinstance(candidate, dict):
            raise ValueError("not an object")
        response = candidate
    except (ValueError, TypeError):
        errors.append("PILOT_RESULT_JSON_INVALID")
    if response:
        if list(Draft202012Validator(_findings_schema()).iter_errors(response)):
            errors.append("PILOT_RESULT_SCHEMA_INVALID")
        if any(response.get(key) != manifest.get(key)
               for key in ("request_id", "subject_id", "packet_id")):
            errors.append("PILOT_RESULT_IDENTITY_MISMATCH")
        if response.get("sources_examined") != ["S001"]:
            errors.append("PILOT_SOURCE_COVERAGE_MISMATCH")
        errors.extend(_citation_errors(response, source_lines(evidence, manifest)))
        expected_defect = any(
            item.get("source_id") == "S001"
            and item.get("line") == 3
            and "return age > 18" in item.get("quote", "")
            for finding in response.get("findings", [])
            if isinstance(finding, dict)
            for item in finding.get("evidence", [])
            if isinstance(item, dict)
        )
        if response.get("verdict") != "NO_GO" or not expected_defect:
            errors.append("PILOT_EXPECTED_DEFECT_NOT_FOUND")
    else:
        errors.append("PILOT_RESULT_ABSENT")
    status = "PASS" if not errors else "FAIL"
    return {
        "pilot_functional": status,
        "pilot_execution": "COMPLETED" if sequence_valid and not failed and exit_code == "0"
                           else "INDETERMINATE",
        "schema_and_citations": "PASS" if status == "PASS" else "FAIL",
        "verdict": response.get("verdict") if status == "PASS" else "UNDETERMINED",
        "findings_count": len(response.get("findings", [])) if status == "PASS" else 0,
        "validation_reasons": sorted(set(errors)),
        "events_sha256": hashlib.sha256(event_bytes).hexdigest() if event_bytes else None,
        "final_sha256": hashlib.sha256(final_bytes).hexdigest() if final_bytes else None,
    }
