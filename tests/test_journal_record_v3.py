from __future__ import annotations

from copy import deepcopy
import unittest

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import (
    JournalRecordV3Error,
    WorkerIdentityV3,
    decode_journal_v2,
    encode_journal_v2,
    initial_record,
)
from review_broker.pre_model_control_v3 import (
    refuse_permanently,
    register_worker,
    reserve_initial,
    transition_state,
)
from review_broker.queue import AttemptState
from tests.journal_v3_test_support import (
    ADMISSION,
    ADMISSION_ID,
    PACKET_ID,
    REQUEST_ID,
    failure_receipt,
)


WORKER = WorkerIdentityV3(101, 1)
AUTHORITY_ID = "artifact:sha256:" + "5" * 64


def bound_record():
    record = reserve_initial(initial_record(REQUEST_ID, ADMISSION))
    return register_worker(
        record, record.control.reservation_id, 1, WORKER, AUTHORITY_ID
    )


def admitted_record():
    record = bound_record()
    return transition_state(
        record, AttemptState.ADMITTED, ADMISSION_ID,
        record.control.reservation_id, 1, WORKER,
    )


class StrictJournalRecordV3Tests(unittest.TestCase):
    def decode_value(self, value):
        return decode_journal_v2(canonical_bytes(value) + b"\n")

    def test_generation_zero_reservation_and_worker_events_are_rejected(self):
        initial = initial_record(REQUEST_ID, ADMISSION)
        cases = (
            ("PRE_MODEL_DISPATCH_RESERVED", None),
            ("PRE_MODEL_WORKER_BOUND", {
                "request_id": REQUEST_ID, "attempt_id": initial.attempt.attempt_id,
                "generation": 0, "reservation_id": None,
                "worker": {"run_id": 777, "run_attempt": 1},
                "authority_evidence_id": AUTHORITY_ID,
            }),
        )
        for event, receipt in cases:
            value = initial.as_dict()
            basis = {"event": event, "request_id": REQUEST_ID,
                     "attempt_id": initial.attempt.attempt_id, "generation": 0,
                     "prior_history_count": len(value["history"])}
            if receipt is not None:
                basis["receipt"] = receipt
            evidence = artifact_identity(canonical_bytes(basis) + b"\n")
            pre_model = {"generation": 0, "reservation_id": None}
            if receipt is not None:
                pre_model["receipt"] = receipt
            value["evidence_ids"].append(evidence)
            value["history"].append({"event": event, "evidence_ids": [evidence],
                                     "pre_model": pre_model})
            with self.subTest(event=event), self.assertRaisesRegex(
                JournalRecordV3Error, "GENERATION_ZERO_EVENT_INVALID"
            ):
                self.decode_value(value)

    def test_orphan_worker_binding_for_wrong_reservation_is_rejected(self):
        record = reserve_initial(initial_record(REQUEST_ID, ADMISSION))
        value = record.as_dict()
        wrong = "preparation-dispatch:sha256:" + "f" * 64
        receipt = {
            "request_id": REQUEST_ID, "attempt_id": record.attempt.attempt_id,
            "generation": 1, "reservation_id": wrong,
            "worker": {"run_id": 777, "run_attempt": 1},
            "authority_evidence_id": AUTHORITY_ID,
        }
        evidence = artifact_identity(canonical_bytes({
            "event": "PRE_MODEL_WORKER_BOUND", "request_id": REQUEST_ID,
            "attempt_id": record.attempt.attempt_id, "generation": 1,
            "prior_history_count": len(value["history"]), "receipt": receipt,
        }) + b"\n")
        value["evidence_ids"].append(evidence)
        value["history"].append({
            "event": "PRE_MODEL_WORKER_BOUND", "evidence_ids": [evidence],
            "pre_model": {"generation": 1, "reservation_id": wrong,
                          "receipt": receipt},
        })
        with self.assertRaisesRegex(JournalRecordV3Error, "ORPHAN_WORKER_BINDING"):
            self.decode_value(value)

    def test_reservation_event_cannot_precede_initial_requested_entry(self):
        value = admitted_record().as_dict()
        event = value["history"].pop(1)
        old_evidence = event["evidence_ids"][0]
        new_evidence = artifact_identity(canonical_bytes({
            "event": "PRE_MODEL_DISPATCH_RESERVED", "request_id": REQUEST_ID,
            "attempt_id": value["attempt_id"], "generation": 1,
            "prior_history_count": 0,
        }) + b"\n")
        event["evidence_ids"] = [new_evidence]
        value["evidence_ids"].remove(old_evidence)
        value["evidence_ids"].append(new_evidence)
        value["history"].insert(0, event)
        with self.assertRaisesRegex(JournalRecordV3Error, "INITIAL_HISTORY_ENTRY_INVALID"):
            self.decode_value(value)

    def test_worker_binding_must_precede_admission_and_prepared(self):
        prepared = transition_state(
            admitted_record(), AttemptState.PREPARED, PACKET_ID,
            admitted_record().control.reservation_id, 1, WORKER,
        )
        value = prepared.as_dict()
        worker_event = value["history"].pop(2)
        old_evidence = worker_event["evidence_ids"][0]
        receipt = worker_event["pre_model"]["receipt"]
        new_evidence = artifact_identity(canonical_bytes({
            "event": "PRE_MODEL_WORKER_BOUND", "request_id": REQUEST_ID,
            "attempt_id": prepared.attempt.attempt_id, "generation": 1,
            "prior_history_count": len(value["history"]), "receipt": receipt,
        }) + b"\n")
        worker_event["evidence_ids"] = [new_evidence]
        value["evidence_ids"].remove(old_evidence)
        value["evidence_ids"].append(new_evidence)
        value["history"].append(worker_event)
        with self.assertRaisesRegex(JournalRecordV3Error, "WORKER_AFTER_ADMISSION"):
            self.decode_value(value)

    def test_missing_reservation_event_and_evidence_are_rejected(self):
        value = reserve_initial(initial_record(REQUEST_ID, ADMISSION)).as_dict()
        event = value["history"].pop()
        value["evidence_ids"].remove(event["evidence_ids"][0])
        with self.assertRaisesRegex(JournalRecordV3Error, "RESERVATION_HISTORY_MISMATCH"):
            self.decode_value(value)

    def test_changed_worker_authority_receipt_without_new_identity_is_rejected(self):
        value = bound_record().as_dict()
        event = value["history"][-1]
        event["pre_model"]["receipt"]["authority_evidence_id"] = (
            "artifact:sha256:" + "6" * 64
        )
        with self.assertRaisesRegex(JournalRecordV3Error, "EVENT_IDENTITY_MISMATCH"):
            self.decode_value(value)

    def test_failure_event_envelope_must_match_control_and_receipt(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        value = refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER
        ).as_dict()
        value["history"][-1]["pre_model"]["generation"] = 0
        value["history"][-1]["pre_model"]["reservation_id"] = None
        with self.assertRaisesRegex(JournalRecordV3Error, "FAILURE_HISTORY_MISMATCH"):
            self.decode_value(value)

    def test_refusal_without_failure_history_is_rejected(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        refused = refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER
        )
        value = refused.as_dict()
        event = value["history"].pop()
        value["evidence_ids"].remove(event["evidence_ids"][0])
        with self.assertRaisesRegex(JournalRecordV3Error, "FAILURE_HISTORY_MISMATCH"):
            self.decode_value(value)

    def test_permanent_failure_history_cannot_be_reopened_as_reserved(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        refused = refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER
        )
        value = refused.as_dict()
        value["pre_model_control"]["disposition"] = "RESERVED"
        value["pre_model_control"]["failure_receipt_id"] = None
        with self.assertRaisesRegex(JournalRecordV3Error, "FAILURE_HISTORY_IRREVERSIBLE"):
            self.decode_value(value)

    def test_forged_admission_evidence_cannot_be_committed(self):
        record = bound_record()
        with self.assertRaisesRegex(JournalRecordV3Error, "ADMISSION_EVIDENCE_ID_MISMATCH"):
            transition_state(
                record, AttemptState.ADMITTED, "caller-forged-admission-evidence",
                record.control.reservation_id, 1, WORKER,
            )

    def test_failure_history_cannot_be_followed_by_dispatch_event(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        value = refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER
        ).as_dict()
        evidence = artifact_identity(canonical_bytes({
            "event": "PRE_MODEL_DISPATCH_RESERVED", "request_id": REQUEST_ID,
            "attempt_id": record.attempt.attempt_id, "generation": 1,
            "prior_history_count": len(value["history"]),
        }) + b"\n")
        value["evidence_ids"].append(evidence)
        value["history"].append({
            "event": "PRE_MODEL_DISPATCH_RESERVED", "evidence_ids": [evidence],
            "pre_model": {"generation": 1,
                          "reservation_id": record.control.reservation_id},
        })
        with self.assertRaisesRegex(
            JournalRecordV3Error,
            "RESERVATION_HISTORY_MISMATCH|FAILURE_HISTORY_NOT_FINAL",
        ):
            self.decode_value(value)

    def test_refusal_cannot_be_appended_after_prior_prepared_history(self):
        prepared = transition_state(
            admitted_record(), AttemptState.PREPARED, PACKET_ID,
            admitted_record().control.reservation_id, 1, WORKER,
        )
        indeterminate_evidence = "artifact:sha256:" + "b" * 64
        value = prepared.as_dict()
        value["state"] = "INDETERMINATE"
        value["evidence_ids"].append(indeterminate_evidence)
        value["history"].append({
            "state": "INDETERMINATE", "evidence_ids": [indeterminate_evidence]
        })
        failure_id, receipt = failure_receipt(
            prepared.attempt.attempt_id, prepared.control.reservation_id, WORKER
        )
        value["pre_model_control"]["disposition"] = "REFUSED_PERMANENT"
        value["pre_model_control"]["failure_receipt_id"] = failure_id
        value["evidence_ids"].append(failure_id)
        value["history"].append({
            "event": "PRE_MODEL_FAILURE", "evidence_ids": [failure_id],
            "pre_model": {"generation": 1,
                          "reservation_id": prepared.control.reservation_id,
                          "receipt": receipt},
        })
        with self.assertRaisesRegex(JournalRecordV3Error, "FAILURE_AFTER_MODEL_CAPABLE"):
            self.decode_value(value)

    def test_failure_history_cannot_be_followed_by_model_capable_states(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        value = refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER
        ).as_dict()
        for state, digit in (("PREPARED", "7"), ("ARMED", "8"), ("INDETERMINATE", "9")):
            evidence = "artifact:sha256:" + digit * 64
            value["evidence_ids"].append(evidence)
            value["history"].append({"state": state, "evidence_ids": [evidence]})
        value["state"] = "INDETERMINATE"
        value["invocation_count"] = 1
        with self.assertRaisesRegex(
            JournalRecordV3Error,
            "FAILURE_AFTER_MODEL_CAPABLE_HISTORY|FAILURE_HISTORY_NOT_FINAL",
        ):
            self.decode_value(value)

    def test_unsupported_recovery_event_is_rejected(self):
        value = initial_record(REQUEST_ID, ADMISSION).as_dict()
        evidence = "artifact:sha256:" + "a" * 64
        value["evidence_ids"].append(evidence)
        value["history"].append({
            "event": "PRE_MODEL_RECOVERY_AUTHORIZED",
            "evidence_ids": [evidence],
            "pre_model": {"generation": 0, "reservation_id": None,
                          "receipt": {"caller": "forged"}},
        })
        with self.assertRaisesRegex(JournalRecordV3Error, "EVENT_UNSUPPORTED"):
            self.decode_value(value)

    def test_boolean_control_schema_version_is_rejected(self):
        value = initial_record(REQUEST_ID, ADMISSION).as_dict()
        value["pre_model_control"]["schema_version"] = True
        with self.assertRaisesRegex(JournalRecordV3Error, "CONTROL_VERSION_INVALID"):
            self.decode_value(value)

    def test_prepared_packet_evidence_must_be_artifact_identity(self):
        prepared = transition_state(
            admitted_record(), AttemptState.PREPARED, PACKET_ID,
            admitted_record().control.reservation_id, 1, WORKER,
        )
        value = deepcopy(prepared.as_dict())
        value["evidence_ids"][-1] = "not-an-artifact"
        value["history"][-1]["evidence_ids"] = ["not-an-artifact"]
        with self.assertRaisesRegex(JournalRecordV3Error, "PACKET_EVIDENCE_INVALID"):
            self.decode_value(value)

    def test_blocked_disposition_is_explicitly_unsupported(self):
        value = admitted_record().as_dict()
        value["pre_model_control"]["disposition"] = "BLOCKED"
        value["pre_model_control"]["failure_receipt_id"] = (
            "artifact:sha256:" + "f" * 64
        )
        with self.assertRaisesRegex(JournalRecordV3Error, "BLOCKED_UNSUPPORTED"):
            self.decode_value(value)

    def test_generation_two_is_explicitly_unsupported(self):
        value = reserve_initial(initial_record(REQUEST_ID, ADMISSION)).as_dict()
        value["pre_model_control"].update({
            "generation": 2,
            "authorization_id": "pre-model-recovery:sha256:" + "a" * 64,
            "reservation_id": "preparation-dispatch:sha256:" + "b" * 64,
        })
        with self.assertRaisesRegex(JournalRecordV3Error, "GENERATION_UNSUPPORTED"):
            self.decode_value(value)

    def test_permanent_receipt_rejects_boolean_version_unknown_reason_and_bad_date(self):
        record = admitted_record()
        failure_id, receipt = failure_receipt(
            record.attempt.attempt_id, record.control.reservation_id, WORKER
        )
        cases = (
            ("schema_version", True),
            ("reason_code", "TOTALLY_BOGUS_PERMANENT_REASON"),
            ("observed_at", "2026-99-99T99:99:99Z"),
            ("reference_id", None),
        )
        for field, invalid in cases:
            candidate = dict(receipt)
            candidate[field] = invalid
            with self.subTest(field=field), self.assertRaises(JournalRecordV3Error):
                refuse_permanently(
                    record, failure_id, candidate,
                    record.control.reservation_id, 1, WORKER,
                )

    def test_generated_record_remains_canonical_and_decodable(self):
        record = admitted_record()
        self.assertEqual(decode_journal_v2(encode_journal_v2(record)), record)


if __name__ == "__main__":
    unittest.main()
