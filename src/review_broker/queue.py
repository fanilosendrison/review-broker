"""Durable attempt state, atomic claims, and single-reviewer serialization."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading
from typing import Any, Mapping

from .evidence import (
    EvidenceCaptureError,
    validate_shutdown_observation,
    validate_terminal_capture_receipt,
)
from .identity import attempt_identity


class AttemptState(str, Enum):
    REQUESTED = "REQUESTED"
    ADMITTED = "ADMITTED"
    PREPARED = "PREPARED"
    ARMED = "ARMED"
    TERMINAL_CAPTURED = "TERMINAL_CAPTURED"
    VALIDATED = "VALIDATED"
    REPORTED = "REPORTED"
    STOPPED = "STOPPED"
    INDETERMINATE = "INDETERMINATE"


EVIDENCE_GATED_STATES = {
    AttemptState.TERMINAL_CAPTURED,
    AttemptState.STOPPED,
}


LEGAL_TRANSITIONS = {
    AttemptState.REQUESTED: {AttemptState.ADMITTED, AttemptState.INDETERMINATE},
    AttemptState.ADMITTED: {AttemptState.PREPARED, AttemptState.INDETERMINATE},
    AttemptState.PREPARED: {AttemptState.ARMED, AttemptState.INDETERMINATE},
    AttemptState.ARMED: {AttemptState.TERMINAL_CAPTURED, AttemptState.INDETERMINATE},
    AttemptState.TERMINAL_CAPTURED: {AttemptState.VALIDATED, AttemptState.INDETERMINATE},
    AttemptState.VALIDATED: {AttemptState.REPORTED, AttemptState.INDETERMINATE},
    AttemptState.REPORTED: {AttemptState.STOPPED, AttemptState.INDETERMINATE},
    AttemptState.INDETERMINATE: {AttemptState.STOPPED},
    AttemptState.STOPPED: set(),
}


class StateTransitionError(RuntimeError):
    pass


class ReviewerBusy(StateTransitionError):
    pass


@dataclass(frozen=True)
class AttemptRecord:
    request_id: str
    attempt_id: str
    state: AttemptState
    evidence_ids: tuple[str, ...] = ()
    invocation_count: int = 0
    history: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_id": self.request_id,
            "attempt_id": self.attempt_id,
            "state": self.state.value,
            "evidence_ids": list(self.evidence_ids),
            "invocation_count": self.invocation_count,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AttemptRecord":
        return cls(
            request_id=value["request_id"],
            attempt_id=value["attempt_id"],
            state=AttemptState(value["state"]),
            evidence_ids=tuple(value.get("evidence_ids", [])),
            invocation_count=value.get("invocation_count", 0),
            history=tuple(value.get("history", [])),
        )


class InMemoryJournal:
    """Deterministic test journal with the same transition invariants as GitHub refs."""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_request: dict[str, AttemptRecord] = {}
        self._by_attempt: dict[str, AttemptRecord] = {}
        self._armed_attempt: str | None = None

    @property
    def attempt_count(self) -> int:
        with self._lock:
            return len(self._by_attempt)

    def claim(self, request_id: str) -> AttemptRecord:
        with self._lock:
            existing = self._by_request.get(request_id)
            if existing is not None:
                return existing
            record = AttemptRecord(
                request_id=request_id,
                attempt_id=attempt_identity(request_id, 1),
                state=AttemptState.REQUESTED,
                history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
            )
            self._save(record)
            return record

    def get(self, attempt_id: str) -> AttemptRecord:
        with self._lock:
            return self._by_attempt[attempt_id]

    def transition(
        self,
        attempt_id: str,
        target: AttemptState,
        evidence_ids: list[str] | tuple[str, ...],
    ) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            updated = transition_record(current, target, evidence_ids)
            if target is AttemptState.ARMED:
                if self._armed_attempt not in (None, attempt_id):
                    raise ReviewerBusy("SINGLE_REVIEWER_BUSY")
                self._armed_attempt = attempt_id
            if target is AttemptState.STOPPED and self._armed_attempt == attempt_id:
                self._armed_attempt = None
            self._save(updated)
            return updated

    def record_terminal_capture(
        self,
        attempt_id: str,
        receipt: Mapping[str, Any],
    ) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            updated = record_terminal_capture_transition(current, receipt)
            self._save(updated)
            return updated

    def record_stopped(
        self,
        attempt_id: str,
        receipt: Mapping[str, Any],
    ) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            updated = record_shutdown_transition(current, receipt)
            if self._armed_attempt == attempt_id:
                self._armed_attempt = None
            self._save(updated)
            return updated

    def record_invocation(self, attempt_id: str) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            if current.state is not AttemptState.ARMED or current.invocation_count != 0:
                raise StateTransitionError("INVOCATION_NOT_PERMITTED")
            updated = replace(current, invocation_count=1)
            self._save(updated)
            return updated

    def _save(self, record: AttemptRecord) -> None:
        self._by_request[record.request_id] = record
        self._by_attempt[record.attempt_id] = record


def transition_record(
    current: AttemptRecord,
    target: AttemptState,
    evidence_ids: list[str] | tuple[str, ...],
) -> AttemptRecord:
    if target in EVIDENCE_GATED_STATES:
        raise StateTransitionError("SPECIALIZED_EVIDENCE_REQUIRED")
    return _verified_transition_record(current, target, evidence_ids)


def record_terminal_capture_transition(
    current: AttemptRecord,
    receipt: Mapping[str, Any],
) -> AttemptRecord:
    try:
        evidence_id = validate_terminal_capture_receipt(
            receipt,
            request_id=current.request_id,
            attempt_id=current.attempt_id,
        )
    except EvidenceCaptureError as exc:
        raise StateTransitionError(str(exc)) from exc
    return _verified_transition_record(
        current,
        AttemptState.TERMINAL_CAPTURED,
        [evidence_id],
    )


def record_shutdown_transition(
    current: AttemptRecord,
    receipt: Mapping[str, Any],
) -> AttemptRecord:
    try:
        evidence_id = validate_shutdown_observation(
            receipt,
            request_id=current.request_id,
            attempt_id=current.attempt_id,
        )
    except EvidenceCaptureError as exc:
        raise StateTransitionError(str(exc)) from exc
    return _verified_transition_record(current, AttemptState.STOPPED, [evidence_id])


def _verified_transition_record(
    current: AttemptRecord,
    target: AttemptState,
    evidence_ids: list[str] | tuple[str, ...],
) -> AttemptRecord:
    evidence = tuple(evidence_ids)
    if not evidence:
        raise StateTransitionError("EVIDENCE_REQUIRED")
    if target not in LEGAL_TRANSITIONS[current.state]:
        raise StateTransitionError(f"ILLEGAL_TRANSITION:{current.state.value}->{target.value}")
    history_entry = {"state": target.value, "evidence_ids": list(evidence)}
    return replace(
        current,
        state=target,
        evidence_ids=current.evidence_ids + evidence,
        history=current.history + (history_entry,),
    )
