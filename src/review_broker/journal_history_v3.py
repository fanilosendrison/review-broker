"""Strict candidate journal history validation (mechanically extracted)."""
from __future__ import annotations

from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import (
    PreModelControlV3, JournalRecordV3Error, _require, _matches,
    _validate_evidence_ids, _is_positive_int, _is_nonnegative_int,
    _PRE_MODEL_EVENTS, _WORKER_FIELDS,
)
from .pre_model_failure_v3 import (PreModelFailureV3Error, validate_permanent_failure_receipt,
                                   validate_blocked_failure_receipt)
from .queue import AttemptState

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
        if event not in {"PRE_MODEL_DISPATCH_RESERVED", "PRE_MODEL_WORKER_BOUND",
                         "PRE_MODEL_DISPATCH_ACKNOWLEDGED"}:
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
    from .pre_model_dispatch_ack_v3 import validate_ack_history
    try:
        validate_ack_history(value, control)
    except (ValueError, TypeError, KeyError) as exc:
        raise JournalRecordV3Error("JOURNAL_V2_DISPATCH_ACK_INVALID") from exc
    prepared = [entry for entry in history if entry.get("state") == "PREPARED"]
    _require(all(len(entry["evidence_ids"]) == 1
                 and _matches("artifact", entry["evidence_ids"][0])
                 for entry in prepared),
             "JOURNAL_V2_PACKET_EVIDENCE_INVALID")
    all_failures = [entry for entry in history
                    if entry.get("event") == "PRE_MODEL_FAILURE"]
    _require(not all_failures or control.disposition in {"REFUSED_PERMANENT", "BLOCKED"},
             "JOURNAL_V2_FAILURE_HISTORY_IRREVERSIBLE")
    if all_failures:
        failure_index = history.index(all_failures[0])
        state_names = {entry.get("state") for entry in history}
        _require(not state_names.intersection({"PREPARED", "ARMED"}),
                 "JOURNAL_V2_FAILURE_AFTER_MODEL_CAPABLE_HISTORY")
        _require(failure_index == len(history) - 1
                 and value["invocation_count"] == 0,
                 "JOURNAL_V2_FAILURE_HISTORY_NOT_FINAL")
    if control.disposition in {"REFUSED_PERMANENT", "BLOCKED"}:
        failures = [entry for entry in all_failures
                    if entry["evidence_ids"] == [control.failure_receipt_id]
                    and entry["pre_model"]["generation"] == control.generation
                    and entry["pre_model"]["reservation_id"] == control.reservation_id]
        _require(len(failures) == 1 and control.worker is not None,
                 "JOURNAL_V2_BLOCKED_UNSUPPORTED_WITHOUT_FAILURE_HISTORY"
                 if control.disposition == "BLOCKED" and not all_failures
                 else "JOURNAL_V2_FAILURE_HISTORY_MISMATCH")
        try:
            validator = (validate_blocked_failure_receipt if control.disposition == "BLOCKED"
                         else validate_permanent_failure_receipt)
            validator(
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
