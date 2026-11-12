"""Candidate v3 preparation-control transitions over strict journal records."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Callable, Mapping

from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import (
    JournalRecordV3,
    JournalRecordV3Error,
    PreModelControlV3,
    WorkerIdentityV3,
    preparation_dispatch_identity,
)
from .pre_model_failure_v3 import PreModelFailureV3Error, validate_permanent_failure_receipt
from .queue import AttemptState, StateTransitionError, transition_record
from .pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3


_ARTIFACT = re.compile(r"artifact:sha256:[0-9a-f]{64}\Z")


def _require(condition: bool, marker: str) -> None:
    if not condition:
        raise JournalRecordV3Error(marker)


def _event(record: JournalRecordV3, event: str, evidence_id: str | None = None,
           receipt: Mapping[str, object] | None = None) -> JournalRecordV3:
    event_basis: dict[str, object] = {
        "event": event, "request_id": record.attempt.request_id,
        "attempt_id": record.attempt.attempt_id,
        "generation": record.control.generation,
        "prior_history_count": len(record.attempt.history),
    }
    if receipt is not None:
        event_basis["receipt"] = deepcopy(dict(receipt))
    evidence = evidence_id or artifact_identity(canonical_bytes(event_basis) + b"\n")
    pre_model: dict[str, object] = {
        "generation": record.control.generation,
        "reservation_id": record.control.reservation_id,
    }
    if receipt is not None:
        pre_model["receipt"] = deepcopy(dict(receipt))
    entry = {"event": event, "evidence_ids": [evidence], "pre_model": pre_model}
    attempt = replace(
        record.attempt,
        evidence_ids=record.attempt.evidence_ids + (evidence,),
        history=record.attempt.history + (entry,),
    )
    return JournalRecordV3(attempt, record.control)


def reserve_initial(record: JournalRecordV3) -> JournalRecordV3:
    _require(record.attempt.state is AttemptState.REQUESTED
             and record.control == PreModelControlV3.initial(),
             "INITIAL_RESERVATION_NOT_PERMITTED")
    reservation = preparation_dispatch_identity(
        record.attempt.request_id, record.attempt.attempt_id, 1, record.attempt.request_id
    )
    updated = JournalRecordV3(record.attempt, PreModelControlV3(
        1, "RESERVED", reservation, record.attempt.request_id, None, None
    ))
    return _event(updated, "PRE_MODEL_DISPATCH_RESERVED")


def acknowledge_dispatch(record: JournalRecordV3,
                         receipt: DispatchAcknowledgmentV3) -> JournalRecordV3:
    from .pre_model_dispatch_ack_v3 import (
        ACK_EVENT, DispatchAcknowledgmentV3, acknowledgment_from_record,
    )
    _require(type(receipt) is DispatchAcknowledgmentV3, "DISPATCH_ACK_RECEIPT_REQUIRED")
    control = record.control
    _require(record.attempt.state is AttemptState.REQUESTED
             and control.disposition == "RESERVED" and control.generation == 1
             and control.worker is None
             and acknowledgment_from_record(record) is None
             and receipt.request_id == record.attempt.request_id
             and receipt.attempt_id == record.attempt.attempt_id
             and receipt.reservation_id == control.reservation_id,
             "DISPATCH_ACK_TRANSITION_REJECTED")
    return _event(record, ACK_EVENT, receipt=receipt.as_dict())


def register_worker(record: JournalRecordV3, reservation_id: str, generation: int,
                    worker: WorkerIdentityV3,
                    authority_evidence_id: str) -> JournalRecordV3:
    control = record.control
    _require(record.attempt.state in {AttemptState.REQUESTED, AttemptState.ADMITTED}
             and control.disposition == "RESERVED"
             and control.generation == generation
             and control.reservation_id == reservation_id
             and control.worker is None,
             "WORKER_REGISTRATION_REJECTED")
    _require(_ARTIFACT.fullmatch(authority_evidence_id) is not None,
             "WORKER_AUTHORITY_EVIDENCE_INVALID")
    updated = JournalRecordV3(record.attempt, replace(control, worker=worker))
    receipt = {
        "request_id": record.attempt.request_id, "attempt_id": record.attempt.attempt_id,
        "generation": generation, "reservation_id": reservation_id,
        "worker": worker.as_dict(), "authority_evidence_id": authority_evidence_id,
    }
    return _event(updated, "PRE_MODEL_WORKER_BOUND", receipt=receipt)


def transition_state(record: JournalRecordV3, target: AttemptState, evidence_id: str,
                     reservation_id: str, generation: int,
                     worker: WorkerIdentityV3) -> JournalRecordV3:
    control = record.control
    _require(control.disposition == "RESERVED" and control.generation == generation
             and control.reservation_id == reservation_id and control.worker == worker,
             "WORKER_GENERATION_FENCED")
    _require(target in {AttemptState.ADMITTED, AttemptState.PREPARED},
             "V3_TRANSITION_UNSUPPORTED")
    if target is AttemptState.ADMITTED:
        admission = record.attempt.admission or {}
        _require(evidence_id == admission.get("admission_evidence_id"),
                 "ADMISSION_EVIDENCE_ID_MISMATCH")
    if target is AttemptState.PREPARED:
        _require(_ARTIFACT.fullmatch(evidence_id) is not None,
                 "PACKET_EVIDENCE_ID_INVALID")
    try:
        attempt = transition_record(record.attempt, target, [evidence_id])
    except StateTransitionError as exc:
        raise JournalRecordV3Error(str(exc)) from exc
    return JournalRecordV3(attempt, control)


def refuse_permanently(record: JournalRecordV3, failure_receipt_id: str,
                       receipt: Mapping[str, object], reservation_id: str,
                       generation: int, worker: WorkerIdentityV3) -> JournalRecordV3:
    control = record.control
    admission = record.attempt.admission or {}
    try:
        receipt_value = validate_permanent_failure_receipt(
            receipt, failure_receipt_id=failure_receipt_id,
            request_id=record.attempt.request_id, attempt_id=record.attempt.attempt_id,
            admission_evidence_id=admission.get("admission_evidence_id"),
            generation=generation, reservation_id=reservation_id, worker=worker,
            accepted_reference_ids=admission.get("reference_ids"),
        )
    except PreModelFailureV3Error as exc:
        raise JournalRecordV3Error(str(exc)) from exc
    _require(record.attempt.state in {AttemptState.REQUESTED, AttemptState.ADMITTED}
             and control.disposition == "RESERVED"
             and control.generation == generation
             and control.reservation_id == reservation_id and control.worker == worker,
             "PERMANENT_REFUSAL_REJECTED")
    updated = JournalRecordV3(
        record.attempt,
        replace(control, disposition="REFUSED_PERMANENT", failure_receipt_id=failure_receipt_id),
    )
    return _event(updated, "PRE_MODEL_FAILURE", failure_receipt_id, receipt_value)


def block_pre_model(record: JournalRecordV3, failure_receipt_id: str,
                    receipt: Mapping[str, object], reservation_id: str,
                    generation: int, worker: WorkerIdentityV3) -> JournalRecordV3:
    """Only the original ADMITTED domain; no AttemptState or recovery is added."""
    from .pre_model_failure_domain_v3 import require_failure_predecessor_v3
    from .pre_model_failure_v3 import validate_blocked_failure_receipt
    control, admission = record.control, record.attempt.admission
    try:
        require_failure_predecessor_v3(record)
        value = validate_blocked_failure_receipt(receipt, failure_receipt_id=failure_receipt_id,
            request_id=record.attempt.request_id, attempt_id=record.attempt.attempt_id,
            admission_evidence_id=admission.get("admission_evidence_id"), generation=generation,
            reservation_id=reservation_id, worker=worker, accepted_reference_ids=admission.get("reference_ids"))
    except ValueError as exc:
        raise JournalRecordV3Error(str(exc)) from exc
    _require(type(generation) is int and generation == control.generation
             and reservation_id == control.reservation_id and worker == control.worker,
             "BLOCKED_WORKER_GENERATION_FENCED")
    updated = JournalRecordV3(record.attempt, replace(control,
        disposition="BLOCKED", failure_receipt_id=failure_receipt_id))
    return _event(updated, "PRE_MODEL_FAILURE", failure_receipt_id, value)


RecordMutationV3 = Callable[[JournalRecordV3], JournalRecordV3]
