"""Bounded, non-secret observations of Codex invocation failures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .evidence import credential_material_detected

UNDETERMINED = "UNDETERMINED"
_MAX_EVENT_BYTES = 65_536
_MAX_EVENT_COUNT = 1_024
_MAX_FAILURE_EVENTS = 16
_MAX_NESTED_MESSAGE_BYTES = 4_096
_SAFE_FIELD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,127}")
_FAILURE_ARTIFACTS = (
    "attempt.json",
    "input-manifest.json",
    "codex-events.jsonl",
    "codex-stderr.txt",
    "codex-final.json",
    "codex-exit-code.txt",
    "input-before.sha256",
    "input-after.sha256",
)


def classify_diagnostic_text(text: str) -> str:
    """Classify known diagnostics without treating the fallback as a crash."""
    lowered = text.lower()
    if "model" in lowered and any(
        word in lowered for word in ("unavailable", "not available", "not found")
    ):
        return "MODEL_UNAVAILABLE"
    if any(word in lowered for word in (
        "login required", "authentication expired", "not logged in", "oauth expired",
    )):
        return "OAUTH_EXPIRED"
    if any(word in lowered for word in ("quota", "usage limit", "rate limit")):
        return "QUOTA_EXHAUSTED"
    return "CODEX_FAILURE_UNCLASSIFIED"


def observe_codex_failure(
    *,
    returncode: int | None,
    event_bytes: bytes | None,
    stderr_bytes: bytes | None,
    transport: str | None = None,
) -> dict[str, Any]:
    """Return bounded structured facts, never raw provider diagnostics."""
    stream_status, failure_events = _failure_events(event_bytes)
    diagnostic = _diagnostic_text(event_bytes, stderr_bytes)
    known = classify_diagnostic_text(diagnostic)
    exit_code: int | str = returncode if type(returncode) is int and returncode >= 0 else UNDETERMINED
    signal: int | str = -returncode if type(returncode) is int and returncode < 0 else UNDETERMINED
    process_outcome = "UNDETERMINED"
    if transport == "TIMEOUT":
        classification = "CODEX_TIMEOUT_INDETERMINATE"
        process_outcome = "TIMEOUT"
    elif transport is not None:
        classification = "CODEX_TRANSPORT_FAILURE"
        process_outcome = "TRANSPORT_FAILURE"
    elif type(returncode) is int and returncode < 0:
        classification = "CODEX_NATIVE_CRASH"
        process_outcome = "NATIVE_SIGNAL"
    elif any(item["http_status"] != UNDETERMINED for item in failure_events):
        classification = "CODEX_PROVIDER_ERROR"
        process_outcome = "EXITED_NONZERO"
    elif known != "CODEX_FAILURE_UNCLASSIFIED":
        classification = known
        process_outcome = "EXITED_NONZERO"
    elif failure_events:
        classification = "CODEX_APPLICATION_ERROR"
        process_outcome = "EXITED_NONZERO"
    elif type(returncode) is int and returncode != 0:
        classification = "CODEX_NONZERO_EXIT_UNCLASSIFIED"
        process_outcome = "EXITED_NONZERO"
    else:
        classification = "CODEX_FAILURE_UNCLASSIFIED"

    return {
        "classification": classification,
        "process_outcome": process_outcome,
        "exit_code": exit_code,
        "signal": signal,
        "event_stream_status": stream_status,
        "failure_events": failure_events,
        "raw_diagnostic_retained": False,
    }


def observe_codex_failure_files(
    *,
    returncode: int | None,
    events_path: Path,
    stderr_path: Path,
    transport: str | None = None,
) -> dict[str, Any]:
    """Observe invocation files while preserving unreadable evidence as unknown."""
    return observe_codex_failure(
        returncode=returncode,
        event_bytes=_optional_bytes(events_path),
        stderr_bytes=_optional_bytes(stderr_path),
        transport=transport,
    )


def failure_artifact_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    """Hash available bounded artifacts without following aliases."""
    artifacts: dict[str, dict[str, Any]] = {}
    for name in _FAILURE_ARTIFACTS:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            artifacts[name] = {
                "present": False,
                "byte_length": 0,
                "sha256": UNDETERMINED,
            }
            continue
        try:
            content = path.read_bytes()
        except OSError:
            artifacts[name] = {
                "present": False,
                "byte_length": 0,
                "sha256": UNDETERMINED,
            }
            continue
        artifacts[name] = {
            "present": True,
            "byte_length": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return artifacts


def build_pilot_failure_receipt(
    *,
    request_id: str,
    attempt_id: str,
    packet_id: str,
    classification: str,
    failure_observation: Mapping[str, Any] | None,
    credential_screen: str,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the private sanitized receipt for one consumed synthetic attempt."""
    safe_classification = _safe_field(classification)
    observation: Mapping[str, Any] | str = UNDETERMINED
    bounded_observation = _bounded_observation(failure_observation)
    exit_code: int | str = UNDETERMINED
    if bounded_observation is not None:
        exit_code = bounded_observation["exit_code"]
        if credential_screen == "PASS_NO_MATCH":
            observation = bounded_observation
    return {
        "schema_version": 1,
        "evidence_type": "synthetic-pilot-failure",
        "scope": "SYNTHETIC_NONPRODUCTION_ONLY",
        "issue": 26,
        "request_id": request_id,
        "request_ordinal": 1,
        "attempt_id": attempt_id,
        "attempt_ordinal": 1,
        "packet_id": packet_id,
        "attempt_identity_consumed": True,
        "classification": safe_classification,
        "exit_code": exit_code,
        "credential_screen": credential_screen,
        "failure_observation": observation,
        "artifacts": {name: dict(value) for name, value in artifacts.items()},
        "raw_error_messages_retained": False,
        "github_publication": "NONE",
    }


def _bounded_observation(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    expected = {
        "classification", "process_outcome", "exit_code", "signal",
        "event_stream_status", "failure_events", "raw_diagnostic_retained",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected
        or value.get("raw_diagnostic_retained") is not False
        or credential_material_detected(value)
    ):
        return None
    classification = _safe_field(value.get("classification"))
    process_outcome = _safe_field(value.get("process_outcome"))
    stream_status = _safe_field(value.get("event_stream_status"))
    if UNDETERMINED in {classification, process_outcome, stream_status}:
        return None
    exit_code = value.get("exit_code")
    signal = value.get("signal")
    if not (exit_code == UNDETERMINED or type(exit_code) is int and exit_code >= 0):
        return None
    if not (signal == UNDETERMINED or type(signal) is int and signal > 0):
        return None
    events = value.get("failure_events")
    if not isinstance(events, list) or len(events) > _MAX_FAILURE_EVENTS:
        return None
    expected_event = {
        "event_index", "event_type", "event_id", "category",
        "code", "http_status", "parameter",
    }
    for event in events:
        if not isinstance(event, dict) or set(event) != expected_event:
            return None
        if type(event["event_index"]) is not int or event["event_index"] < 0:
            return None
        if event["event_type"] not in {"error", "turn.failed"}:
            return None
        for key in ("event_id", "category", "code", "parameter"):
            if event[key] != UNDETERMINED and _safe_field(event[key]) != event[key]:
                return None
        status = event["http_status"]
        if not (status == UNDETERMINED or type(status) is int and 100 <= status <= 599):
            return None
    return {
        "classification": classification,
        "process_outcome": process_outcome,
        "exit_code": exit_code,
        "signal": signal,
        "event_stream_status": stream_status,
        "failure_events": [dict(event) for event in events],
        "raw_diagnostic_retained": False,
    }


def _failure_events(value: bytes | None) -> tuple[str, list[dict[str, Any]]]:
    if value is None:
        return "UNAVAILABLE", []
    if not value.strip():
        return "EMPTY", []
    lines = value.splitlines()
    if len(lines) > _MAX_EVENT_COUNT:
        return "LIMIT_EXCEEDED", []
    events: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if len(line) > _MAX_EVENT_BYTES:
            return "LIMIT_EXCEEDED", []
        try:
            event = json.loads(line.decode("utf-8", errors="strict"))
        except (UnicodeError, json.JSONDecodeError):
            return "MALFORMED", []
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            return "MALFORMED", []
        if event["type"] in {"error", "turn.failed"}:
            if len(events) == _MAX_FAILURE_EVENTS:
                return "LIMIT_EXCEEDED", []
            events.append(_sanitized_event(event, index))
    return "PARSED", events


def _sanitized_event(event: Mapping[str, Any], index: int) -> dict[str, Any]:
    observed: dict[str, Any] = {
        "event_index": index,
        "event_type": event["type"],
        "event_id": _safe_field(event.get("id", event.get("event_id"))),
        "category": UNDETERMINED,
        "code": UNDETERMINED,
        "http_status": UNDETERMINED,
        "parameter": UNDETERMINED,
    }
    for candidate in _structured_candidates(event):
        error = candidate.get("error") if isinstance(candidate.get("error"), Mapping) else candidate
        _fill_text(observed, "category", error.get("type"))
        _fill_text(observed, "code", error.get("code"))
        _fill_text(observed, "parameter", error.get("param"))
        status = candidate.get("status", error.get("status"))
        if observed["http_status"] == UNDETERMINED and type(status) is int and 100 <= status <= 599:
            observed["http_status"] = status
    return observed


def _structured_candidates(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = [event]
    error = event.get("error")
    if isinstance(error, Mapping):
        candidates.append(error)
        nested = _nested_object(error.get("message"))
        if nested is not None:
            candidates.append(nested)
    nested = _nested_object(event.get("message"))
    if nested is not None:
        candidates.append(nested)
    return candidates


def _nested_object(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, str) or len(value.encode("utf-8")) > _MAX_NESTED_MESSAGE_BYTES:
        return None
    decoder = json.JSONDecoder()
    for index, character in enumerate(value):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(value, index)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return None


def _fill_text(target: dict[str, Any], key: str, value: Any) -> None:
    if target[key] == UNDETERMINED:
        target[key] = _safe_field(value)


def _safe_field(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not _SAFE_FIELD.fullmatch(value)
        or credential_material_detected(value)
    ):
        return UNDETERMINED
    return value


def _diagnostic_text(events: bytes | None, stderr: bytes | None) -> str:
    chunks = []
    for value in (stderr, events):
        if isinstance(value, bytes):
            chunks.append(value[:_MAX_EVENT_BYTES].decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _optional_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None
