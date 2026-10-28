"""Bounded, non-secret observations of Codex invocation failures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, BinaryIO, Iterable, Mapping

from .evidence import credential_material_detected
from .fileobservation import FileObservationError, observed_regular_file

UNDETERMINED = "UNDETERMINED"
_MAX_EVENT_BYTES = 65_536
_MAX_EVENT_COUNT = 1_024
_MAX_FAILURE_EVENTS = 16
_HASH_BLOCK_BYTES = 65_536
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
    """Retain legacy text classification for callers, not evidence claims."""
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
    """Return structured facts without promoting free diagnostic text."""
    del stderr_bytes  # Free-form stderr is not evidence of a specific cause.
    stream_status, failure_events = _failure_events(event_bytes)
    return _observation(returncode, stream_status, failure_events, transport)


def observe_codex_failure_files(
    *,
    returncode: int | None,
    events_path: Path,
    stderr_path: Path,
    transport: str | None = None,
) -> dict[str, Any]:
    """Observe an event file incrementally; stderr never establishes cause."""
    del stderr_path
    stream_status, failure_events = _failure_events_file(events_path)
    return _observation(returncode, stream_status, failure_events, transport)


def _observation(
    returncode: int | None,
    stream_status: str,
    failure_events: list[dict[str, Any]],
    transport: str | None,
) -> dict[str, Any]:
    exit_code: int | str = (
        returncode if type(returncode) is int and returncode >= 0 else UNDETERMINED
    )
    signal: int | str = (
        -returncode if type(returncode) is int and returncode < 0 else UNDETERMINED
    )
    process_outcome = UNDETERMINED
    if transport == "TIMEOUT":
        classification, process_outcome = "CODEX_TIMEOUT_INDETERMINATE", "TIMEOUT"
    elif transport is not None:
        classification, process_outcome = "CODEX_TRANSPORT_FAILURE", "TRANSPORT_FAILURE"
    elif type(returncode) is int and returncode < 0:
        classification = "CODEX_SIGNAL_TERMINATION"
        process_outcome = "SIGNAL_TERMINATION"
    elif any(item["http_status"] != UNDETERMINED for item in failure_events):
        classification = "CODEX_PROVIDER_ERROR"
        process_outcome = _exit_outcome(returncode)
    elif failure_events:
        classification = "CODEX_APPLICATION_ERROR"
        process_outcome = _exit_outcome(returncode)
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


def _exit_outcome(returncode: int | None) -> str:
    if type(returncode) is int and returncode != 0:
        return "EXITED_NONZERO"
    if returncode == 0:
        return "EXITED_ZERO_WITH_FAILURE_EVENT"
    return UNDETERMINED


def failure_artifact_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    """Hash stable regular artifacts incrementally without following aliases."""
    artifacts: dict[str, dict[str, Any]] = {}
    for name in _FAILURE_ARTIFACTS:
        try:
            length, digest = _hash_regular_file(directory / name)
        except (OSError, FileObservationError):
            artifacts[name] = {
                "present": False,
                "byte_length": 0,
                "sha256": UNDETERMINED,
            }
        else:
            artifacts[name] = {
                "present": True,
                "byte_length": length,
                "sha256": digest,
            }
    return artifacts


def _hash_regular_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    length = 0
    with observed_regular_file(path) as stream:
        while chunk := stream.read(_HASH_BLOCK_BYTES):
            digest.update(chunk)
            length += len(chunk)
    return length, digest.hexdigest()


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
    return _parse_failure_lines(value.splitlines())


def _failure_events_file(path: Path) -> tuple[str, list[dict[str, Any]]]:
    try:
        with observed_regular_file(path) as stream:
            lines = _bounded_lines(stream)
            observation = _parse_failure_lines(lines)
            for _ in lines:
                pass
            return observation
    except (OSError, FileObservationError):
        return "UNAVAILABLE", []


def _bounded_lines(stream: BinaryIO) -> Iterable[bytes]:
    while line := stream.readline(_MAX_EVENT_BYTES + 2):
        if line.endswith(b"\n"):
            line = line[:-1]
            if line.endswith(b"\r"):
                line = line[:-1]
        yield line


def _parse_failure_lines(lines: Iterable[bytes]) -> tuple[str, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    content_seen = False
    for index, line in enumerate(lines):
        if index >= _MAX_EVENT_COUNT or len(line) > _MAX_EVENT_BYTES:
            return "LIMIT_EXCEEDED", []
        if not line.strip():
            continue
        content_seen = True
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
    if not content_seen:
        return "EMPTY", []
    statuses = {
        event["http_status"] for event in events
        if event["http_status"] != UNDETERMINED
    }
    if len(statuses) > 1:
        return "CONTRADICTORY", []
    return "PARSED", events


def _sanitized_event(event: Mapping[str, Any], index: int) -> dict[str, Any]:
    observed: dict[str, Any] = {
        "event_index": index,
        "event_type": event["type"],
        "event_id": UNDETERMINED,
        "category": UNDETERMINED,
        "code": UNDETERMINED,
        "http_status": UNDETERMINED,
        "parameter": UNDETERMINED,
    }
    error = event.get("error")
    structured = error if isinstance(error, Mapping) else event
    category = structured.get("type") if structured is not event else structured.get("category")
    _fill_text(observed, "category", category)
    _fill_text(observed, "code", structured.get("code"))
    _fill_text(observed, "parameter", structured.get("param"))
    status = event.get("status")
    if type(status) is not int and structured is not event:
        status = structured.get("status")
    if type(status) is int and 100 <= status <= 599:
        observed["http_status"] = status
    return observed


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
