"""Strict candidate journal-v2 record and pre-model transition invariants."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

from .identity import artifact_identity, attempt_identity, canonical_bytes
from .pre_model_failure_v3 import PreModelFailureV3Error, validate_permanent_failure_receipt
from .queue import LEGAL_TRANSITIONS, AttemptRecord, AttemptState

class JournalRecordV3Error(ValueError):
    """The candidate v3 journal record or transition is invalid."""

_ID_PATTERNS = {
    "request": re.compile(r"request:sha256:[0-9a-f]{64}\Z"),
    "attempt": re.compile(r"attempt:sha256:[0-9a-f]{64}\Z"),
    "artifact": re.compile(r"artifact:sha256:[0-9a-f]{64}\Z"),
    "reservation": re.compile(r"preparation-dispatch:sha256:[0-9a-f]{64}\Z"),
}
_TOP_LEVEL_FIELDS = {
    "schema_version", "request_id", "attempt_id", "state", "evidence_ids",
    "invocation_count", "evidence_locator_plan", "evidence_locator",
    "publication_intent", "publication_receipt", "admission", "pre_model_control", "history",
}
_CONTROL_FIELDS = {"schema_version", "generation", "disposition", "reservation_id",
                   "authorization_id", "worker", "failure_receipt_id"}
_WORKER_FIELDS = {"run_id", "run_attempt"}
_DISPOSITIONS = {"UNRESERVED", "RESERVED", "BLOCKED", "REFUSED_PERMANENT"}
_PRE_MODEL_EVENTS = {"PRE_MODEL_DISPATCH_RESERVED", "PRE_MODEL_WORKER_BOUND",
                     "PRE_MODEL_FAILURE", "PRE_MODEL_RECOVERY_AUTHORIZED",
                     "PRE_MODEL_REFUSAL_STOPPED"}

def _require(condition: bool, marker: str) -> None:
    if not condition:
        raise JournalRecordV3Error(marker)

def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0

def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0

def _matches(kind: str, value: object) -> bool:
    return isinstance(value, str) and _ID_PATTERNS[kind].fullmatch(value) is not None

def _validate_json_object_or_none(value: object, marker: str) -> None:
    _require(value is None or isinstance(value, dict), marker)

def _validate_evidence_ids(value: object, marker: str) -> None:
    _require(isinstance(value, list), marker)
    _require(all(isinstance(item, str) and item for item in value), marker)


def _validate_history(history: object) -> None:
    _require(isinstance(history, list) and history, "JOURNAL_V2_HISTORY_INVALID")
    for entry in history:
        _require(isinstance(entry, dict), "JOURNAL_V2_HISTORY_INVALID")
        keys = set(entry)
        if keys == {"state", "evidence_ids"}:
            _require(entry["state"] in {state.value for state in AttemptState},
                     "JOURNAL_V2_HISTORY_STATE_INVALID")
            _validate_evidence_ids(entry["evidence_ids"], "JOURNAL_V2_HISTORY_EVIDENCE_INVALID")
        elif keys == {"event", "evidence_ids"}:
            _require(isinstance(entry["event"], str) and bool(entry["event"])
                     and entry["event"] not in _PRE_MODEL_EVENTS,
                     "JOURNAL_V2_HISTORY_EVENT_INVALID")
            _validate_evidence_ids(entry["evidence_ids"], "JOURNAL_V2_HISTORY_EVIDENCE_INVALID")
        elif keys == {"event", "evidence_ids", "pre_model"}:
            _require(entry["event"] in _PRE_MODEL_EVENTS,
                     "JOURNAL_V2_PRE_MODEL_EVENT_INVALID")
            _require(entry["event"] not in {
                "PRE_MODEL_RECOVERY_AUTHORIZED", "PRE_MODEL_REFUSAL_STOPPED",
            }, "JOURNAL_V2_PRE_MODEL_EVENT_UNSUPPORTED")
            evidence = entry["evidence_ids"]
            _validate_evidence_ids(evidence, "JOURNAL_V2_HISTORY_EVIDENCE_INVALID")
            _require(bool(evidence) and all(_matches("artifact", item) for item in evidence),
                     "JOURNAL_V2_PRE_MODEL_EVIDENCE_INVALID")
            pre_model = entry["pre_model"]
            _require(isinstance(pre_model, dict), "JOURNAL_V2_PRE_MODEL_HISTORY_INVALID")
            _require(set(pre_model).issubset({"generation", "reservation_id", "receipt"})
                     and {"generation", "reservation_id"}.issubset(pre_model),
                     "JOURNAL_V2_PRE_MODEL_HISTORY_FIELDS_INVALID")
            _require(_is_nonnegative_int(pre_model["generation"]),
                     "JOURNAL_V2_PRE_MODEL_HISTORY_GENERATION_INVALID")
            reservation = pre_model["reservation_id"]
            _require(reservation is None or _matches("reservation", reservation),
                     "JOURNAL_V2_PRE_MODEL_HISTORY_RESERVATION_INVALID")
            if "receipt" in pre_model:
                _require(isinstance(pre_model["receipt"], dict) and bool(pre_model["receipt"]),
                         "JOURNAL_V2_PRE_MODEL_HISTORY_RECEIPT_INVALID")
            if entry["event"] == "PRE_MODEL_WORKER_BOUND":
                receipt = pre_model.get("receipt")
                fields = {"request_id", "attempt_id", "generation", "reservation_id",
                          "worker", "authority_evidence_id"}
                _require(isinstance(receipt, dict) and set(receipt) == fields
                         and _matches("request", receipt["request_id"])
                         and _matches("attempt", receipt["attempt_id"])
                         and receipt["generation"] == pre_model["generation"]
                         and receipt["reservation_id"] == pre_model["reservation_id"]
                         and isinstance(receipt["worker"], dict)
                         and set(receipt["worker"]) == _WORKER_FIELDS
                         and _is_positive_int(receipt["worker"]["run_id"])
                         and _is_positive_int(receipt["worker"]["run_attempt"])
                         and _matches("artifact", receipt["authority_evidence_id"]),
                         "JOURNAL_V2_WORKER_BINDING_EVIDENCE_INVALID")
        else:
            raise JournalRecordV3Error("JOURNAL_V2_HISTORY_FIELDS_INVALID")


@dataclass(frozen=True)
class WorkerIdentityV3:
    run_id: int
    run_attempt: int

    def __post_init__(self) -> None:
        _require(_is_positive_int(self.run_id) and _is_positive_int(self.run_attempt),
                 "WORKER_IDENTITY_INVALID")

    def as_dict(self) -> dict[str, object]:
        return {"run_id": self.run_id, "run_attempt": self.run_attempt}
@dataclass(frozen=True)
class PreModelControlV3:
    generation: int
    disposition: str
    reservation_id: str | None
    authorization_id: str | None
    worker: WorkerIdentityV3 | None
    failure_receipt_id: str | None
    @classmethod
    def initial(cls) -> "PreModelControlV3":
        return cls(0, "UNRESERVED", None, None, None, None)
    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "generation": self.generation,
            "disposition": self.disposition,
            "reservation_id": self.reservation_id,
            "authorization_id": self.authorization_id,
            "worker": None if self.worker is None else self.worker.as_dict(),
            "failure_receipt_id": self.failure_receipt_id,
        }
@dataclass(frozen=True)
class JournalRecordV3:
    attempt: AttemptRecord
    control: PreModelControlV3

    def as_dict(self) -> dict[str, object]:
        value: dict[str, object] = deepcopy(self.attempt.as_dict())
        value["schema_version"] = 2
        value["pre_model_control"] = self.control.as_dict()
        return value
def _validate_control(value: object, state: AttemptState) -> PreModelControlV3:
    _require(isinstance(value, dict) and set(value) == _CONTROL_FIELDS,
             "JOURNAL_V2_CONTROL_FIELDS_INVALID")
    _require(type(value["schema_version"]) is int
             and value["schema_version"] == 1,
             "JOURNAL_V2_CONTROL_VERSION_INVALID")
    generation = value["generation"]
    disposition = value["disposition"]
    _require(_is_nonnegative_int(generation), "JOURNAL_V2_GENERATION_INVALID")
    _require(generation <= 1, "JOURNAL_V2_GENERATION_UNSUPPORTED")
    _require(disposition in _DISPOSITIONS, "JOURNAL_V2_DISPOSITION_INVALID")
    _require(disposition != "BLOCKED", "JOURNAL_V2_BLOCKED_UNSUPPORTED")
    reservation = value["reservation_id"]
    authorization = value["authorization_id"]
    worker_value = value["worker"]
    failure = value["failure_receipt_id"]
    _require(reservation is None or _matches("reservation", reservation),
             "JOURNAL_V2_RESERVATION_INVALID")
    _require(authorization is None or _matches("request", authorization)
             or isinstance(authorization, str)
             and re.fullmatch(r"pre-model-recovery:sha256:[0-9a-f]{64}", authorization),
             "JOURNAL_V2_AUTHORIZATION_INVALID")
    _require(worker_value is None or isinstance(worker_value, dict)
             and set(worker_value) == _WORKER_FIELDS,
             "JOURNAL_V2_WORKER_FIELDS_INVALID")
    worker = None if worker_value is None else WorkerIdentityV3(
        worker_value["run_id"], worker_value["run_attempt"]
    )
    _require(failure is None or _matches("artifact", failure),
             "JOURNAL_V2_FAILURE_RECEIPT_INVALID")
    if generation == 0:
        _require(reservation is None and authorization is None and worker is None,
                 "JOURNAL_V2_GENERATION_ZERO_INVALID")
    else:
        _require(reservation is not None and authorization is not None,
                 "JOURNAL_V2_RESERVED_IDENTITY_MISSING")
    if disposition == "UNRESERVED":
        _require(generation == 0 and worker is None and failure is None
                 and state is AttemptState.REQUESTED,
                 "JOURNAL_V2_UNRESERVED_INVALID")
    elif disposition == "RESERVED":
        _require(generation > 0 and reservation is not None and authorization is not None
                 and failure is None,
                 "JOURNAL_V2_RESERVED_INVALID")
    else:
        _require(failure is not None, "JOURNAL_V2_FAILURE_RECEIPT_REQUIRED")
    if state in {AttemptState.PREPARED, AttemptState.ARMED}:
        _require(disposition == "RESERVED" and worker is not None,
                 "JOURNAL_V2_MODEL_CAPABLE_CONTROL_INVALID")
    return PreModelControlV3(generation, disposition, reservation, authorization, worker, failure)

def _validate_pre_model_semantics(value: dict[str, object],
                                  control: PreModelControlV3) -> None:
    history = value["history"]
    assert isinstance(history, list)
    all_reservations = [entry for entry in history
                        if entry.get("event") == "PRE_MODEL_DISPATCH_RESERVED"]
    all_bindings = [entry for entry in history
                    if entry.get("event") == "PRE_MODEL_WORKER_BOUND"]
    if control.generation == 0:
        _require(not all_reservations and not all_bindings,
                 "JOURNAL_V2_GENERATION_ZERO_EVENT_INVALID")
    if control.generation >= 1:
        _require(len(all_reservations) == 1
                 and all_reservations[0]["pre_model"]["generation"] == control.generation
                 and all_reservations[0]["pre_model"]["reservation_id"] == control.reservation_id,
                 "JOURNAL_V2_RESERVATION_HISTORY_MISMATCH")
        reservation_index = history.index(all_reservations[0])
        _require(all(entry["pre_model"]["generation"] == control.generation
                     and entry["pre_model"]["reservation_id"] == control.reservation_id
                     for entry in all_bindings),
                 "JOURNAL_V2_ORPHAN_WORKER_BINDING")
        bindings = all_bindings
        _require(control.worker is not None or not bindings,
                 "JOURNAL_V2_UNBOUND_WORKER_HISTORY")
        if control.worker is not None:
            _require(len(bindings) == 1 and reservation_index < history.index(bindings[0]),
                     "JOURNAL_V2_WORKER_HISTORY_ORDER_INVALID")
            worker_index = history.index(bindings[0])
            admitted_indices = [index for index, entry in enumerate(history)
                                if entry.get("state") == "ADMITTED"]
            prepared_indices = [index for index, entry in enumerate(history)
                                if entry.get("state") == "PREPARED"]
            _require(not admitted_indices or worker_index < admitted_indices[0],
                     "JOURNAL_V2_WORKER_AFTER_ADMISSION")
            _require(not prepared_indices or admitted_indices
                     and admitted_indices[0] < prepared_indices[0],
                     "JOURNAL_V2_PREPARED_ORDER_INVALID")
    for index, entry in enumerate(history):
        event = entry.get("event")
        if event not in {"PRE_MODEL_DISPATCH_RESERVED", "PRE_MODEL_WORKER_BOUND"}:
            continue
        basis: dict[str, object] = {
            "event": event, "request_id": value["request_id"],
            "attempt_id": value["attempt_id"],
            "generation": entry["pre_model"]["generation"],
            "prior_history_count": index,
        }
        receipt = entry["pre_model"].get("receipt")
        if receipt is not None:
            basis["receipt"] = receipt
        expected = artifact_identity(canonical_bytes(basis) + b"\n")
        _require(entry["evidence_ids"] == [expected],
                 "JOURNAL_V2_PRE_MODEL_EVENT_IDENTITY_MISMATCH")
    prepared = [entry for entry in history if entry.get("state") == "PREPARED"]
    _require(all(len(entry["evidence_ids"]) == 1
                 and _matches("artifact", entry["evidence_ids"][0])
                 for entry in prepared),
             "JOURNAL_V2_PACKET_EVIDENCE_INVALID")
    all_failures = [entry for entry in history
                    if entry.get("event") == "PRE_MODEL_FAILURE"]
    _require(not all_failures or control.disposition == "REFUSED_PERMANENT",
             "JOURNAL_V2_FAILURE_HISTORY_IRREVERSIBLE")
    if all_failures:
        failure_index = history.index(all_failures[0])
        state_names = {entry.get("state") for entry in history}
        _require(not state_names.intersection({"PREPARED", "ARMED"}),
                 "JOURNAL_V2_FAILURE_AFTER_MODEL_CAPABLE_HISTORY")
        _require(failure_index == len(history) - 1
                 and value["invocation_count"] == 0,
                 "JOURNAL_V2_FAILURE_HISTORY_NOT_FINAL")
    if control.disposition == "REFUSED_PERMANENT":
        failures = [entry for entry in all_failures
                    if entry["evidence_ids"] == [control.failure_receipt_id]
                    and entry["pre_model"]["generation"] == control.generation
                    and entry["pre_model"]["reservation_id"] == control.reservation_id]
        _require(len(failures) == 1 and control.worker is not None,
                 "JOURNAL_V2_FAILURE_HISTORY_MISMATCH")
        try:
            validate_permanent_failure_receipt(
                failures[0]["pre_model"].get("receipt", {}),
                failure_receipt_id=control.failure_receipt_id,
                request_id=value["request_id"], attempt_id=value["attempt_id"],
                admission_evidence_id=value["admission"].get("admission_evidence_id"),
                generation=control.generation, reservation_id=control.reservation_id,
                worker=control.worker,
                accepted_reference_ids=value["admission"].get("reference_ids"),
            )
        except PreModelFailureV3Error as exc:
            raise JournalRecordV3Error(str(exc)) from exc

def decode_journal_v2(raw: bytes) -> JournalRecordV3:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise JournalRecordV3Error("JOURNAL_V2_JSON_INVALID") from exc
    _require(isinstance(value, dict), "JOURNAL_V2_OBJECT_REQUIRED")
    _require(canonical_bytes(value) + b"\n" == raw, "JOURNAL_V2_NONCANONICAL")
    _require(set(value) == _TOP_LEVEL_FIELDS, "JOURNAL_V2_TOP_LEVEL_FIELDS_INVALID")
    _require(value["schema_version"] == 2, "JOURNAL_V2_VERSION_UNSUPPORTED")
    _require(_matches("request", value["request_id"]), "JOURNAL_V2_REQUEST_ID_INVALID")
    _require(_matches("attempt", value["attempt_id"]), "JOURNAL_V2_ATTEMPT_ID_INVALID")
    _require(value["attempt_id"] == attempt_identity(value["request_id"], 1),
             "JOURNAL_V2_ATTEMPT_ID_MISMATCH")
    _require(value["state"] in {state.value for state in AttemptState},
             "JOURNAL_V2_STATE_INVALID")
    _validate_evidence_ids(value["evidence_ids"], "JOURNAL_V2_EVIDENCE_IDS_INVALID")
    _require(value["invocation_count"] in (0, 1)
             and type(value["invocation_count"]) is int,
             "JOURNAL_V2_INVOCATION_COUNT_INVALID")
    for field in ("evidence_locator_plan", "evidence_locator", "publication_intent",
                  "publication_receipt"):
        _validate_json_object_or_none(value[field], f"JOURNAL_V2_{field.upper()}_INVALID")
    _require(isinstance(value["admission"], dict) and bool(value["admission"]),
             "JOURNAL_V2_ADMISSION_INVALID")
    _validate_history(value["history"])
    _require(value["history"][0] == {"state": "REQUESTED", "evidence_ids": []},
             "JOURNAL_V2_INITIAL_HISTORY_ENTRY_INVALID")
    evidence_set = set(value["evidence_ids"])
    _require(all(
        set(entry["evidence_ids"]).issubset(evidence_set)
        for entry in value["history"]
    ), "JOURNAL_V2_HISTORY_EVIDENCE_NOT_BOUND")
    worker_receipts = [entry["pre_model"]["receipt"] for entry in value["history"]
                       if entry.get("event") == "PRE_MODEL_WORKER_BOUND"]
    _require(all(receipt["request_id"] == value["request_id"]
                 and receipt["attempt_id"] == value["attempt_id"]
                 for receipt in worker_receipts),
             "JOURNAL_V2_WORKER_BINDING_IDENTITY_MISMATCH")
    state_history = [AttemptState(entry["state"]) for entry in value["history"] if "state" in entry]
    _require(bool(state_history) and state_history[0] is AttemptState.REQUESTED,
             "JOURNAL_V2_INITIAL_STATE_HISTORY_INVALID")
    _require(all(
        successor in LEGAL_TRANSITIONS[predecessor]
        for predecessor, successor in zip(state_history, state_history[1:])
    ), "JOURNAL_V2_STATE_HISTORY_TRANSITION_INVALID")
    state = AttemptState(value["state"])
    _require(state_history[-1] is state, "JOURNAL_V2_CURRENT_STATE_HISTORY_MISMATCH")
    control = _validate_control(value["pre_model_control"], state)
    if control.generation == 1:
        expected_reservation = preparation_dispatch_identity(
            value["request_id"], value["attempt_id"], 1, value["request_id"]
        )
        _require(control.authorization_id == value["request_id"]
                 and control.reservation_id == expected_reservation,
                 "JOURNAL_V2_INITIAL_RESERVATION_IDENTITY_INVALID")
    if control.worker is not None:
        current_bindings = [receipt for receipt in worker_receipts
                            if receipt["generation"] == control.generation
                            and receipt["reservation_id"] == control.reservation_id]
        _require(len(current_bindings) == 1
                 and current_bindings[0]["worker"] == control.worker.as_dict(),
                 "JOURNAL_V2_CURRENT_WORKER_HISTORY_MISMATCH")
    _validate_pre_model_semantics(value, control)
    legacy_value = deepcopy(value)
    del legacy_value["pre_model_control"]
    legacy_value["schema_version"] = 1
    attempt = AttemptRecord.from_dict(legacy_value)
    _require(attempt.as_dict() == legacy_value, "JOURNAL_V2_LEGACY_FIELDS_NOT_PRESERVED")
    return JournalRecordV3(attempt, control)

def encode_journal_v2(record: JournalRecordV3) -> bytes:
    raw = canonical_bytes(record.as_dict()) + b"\n"
    decode_journal_v2(raw)
    return raw

def preparation_dispatch_identity(request_id: str, attempt_id: str, generation: int,
                                  authorization_id: str) -> str:
    basis = {"schema_version": 1, "request_id": request_id, "attempt_id": attempt_id,
             "generation": generation, "authorization_id": authorization_id}
    return "preparation-dispatch:sha256:" + hashlib.sha256(canonical_bytes(basis)).hexdigest()

def initial_record(request_id: str, admission: Mapping[str, object]) -> JournalRecordV3:
    _require(_matches("request", request_id), "REQUEST_ID_INVALID")
    _require(bool(admission), "ADMISSION_REQUIRED")
    _require(admission.get("request_id") == request_id,
             "ADMISSION_REQUEST_ID_MISMATCH")
    _require(_matches("artifact", admission.get("admission_evidence_id")),
             "ADMISSION_EVIDENCE_ID_INVALID")
    reference_ids = admission.get("reference_ids")
    _require(isinstance(reference_ids, list)
             and all(isinstance(item, str) and item for item in reference_ids)
             and len(reference_ids) == len(set(reference_ids)),
             "ADMISSION_REFERENCE_IDS_INVALID")
    attempt = AttemptRecord(
        request_id=request_id,
        attempt_id=attempt_identity(request_id, 1),
        state=AttemptState.REQUESTED,
        admission=deepcopy(dict(admission)),
        history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
    )
    record = JournalRecordV3(attempt, PreModelControlV3.initial())
    encode_journal_v2(record)
    return record

