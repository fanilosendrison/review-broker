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
    AttemptState.REPORTED,
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
    evidence_locator_plan: dict[str, Any] | None = None
    evidence_locator: dict[str, Any] | None = None
    publication_intent: dict[str, Any] | None = None
    publication_receipt: dict[str, Any] | None = None
    admission: dict[str, Any] | None = None
    history: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        value = {
            "schema_version": 1,
            "request_id": self.request_id,
            "attempt_id": self.attempt_id,
            "state": self.state.value,
            "evidence_ids": list(self.evidence_ids),
            "invocation_count": self.invocation_count,
            "evidence_locator_plan": self.evidence_locator_plan,
            "evidence_locator": self.evidence_locator,
            "publication_intent": self.publication_intent,
            "publication_receipt": self.publication_receipt,
            "history": list(self.history),
        }
        if self.admission is not None:
            value["admission"] = self.admission
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AttemptRecord":
        return cls(
            request_id=value["request_id"],
            attempt_id=value["attempt_id"],
            state=AttemptState(value["state"]),
            evidence_ids=tuple(value.get("evidence_ids", [])),
            invocation_count=value.get("invocation_count", 0),
            evidence_locator_plan=value.get("evidence_locator_plan"),
            evidence_locator=value.get("evidence_locator"),
            publication_intent=value.get("publication_intent"),
            publication_receipt=value.get("publication_receipt"),
            admission=value.get("admission"),
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

    def claim(
        self, request_id: str, admission: dict[str, Any] | None = None,
    ) -> AttemptRecord:
        with self._lock:
            existing = self._by_request.get(request_id)
            if existing is not None:
                if admission is not None and existing.admission != admission:
                    raise StateTransitionError("CLAIM_ADMISSION_CONFLICT")
                return existing
            record = AttemptRecord(
                request_id=request_id,
                attempt_id=attempt_identity(request_id, 1),
                state=AttemptState.REQUESTED,
                admission=admission,
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


def record_publication_transition(
    current: AttemptRecord,
    receipt: Mapping[str, Any],
    evidence_id: str,
) -> AttemptRecord:
    intent = current.publication_intent
    if current.state is not AttemptState.VALIDATED or intent is None:
        raise StateTransitionError("PUBLICATION_INTENT_REQUIRED")
    if (
        receipt.get("publication_id") != intent.get("publication_id")
        or receipt.get("result_id") != intent.get("result_id")
    ):
        raise StateTransitionError("PUBLICATION_RECEIPT_IDENTITY_MISMATCH")
    with_receipt = replace(current, publication_receipt=dict(receipt))
    return _verified_transition_record(
        with_receipt,
        AttemptState.REPORTED,
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
