from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from review_broker.evidence import build_shutdown_observation
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.queue import (
    AttemptRecord,
    AttemptState,
    InMemoryJournal,
    ReviewerBusy,
    StateTransitionError,
    record_shutdown_transition,
    transition_record,
)


class QueueTests(unittest.TestCase):
    def advance_to_prepared(self, journal, request_id):
        record = journal.claim(request_id)
        journal.transition(record.attempt_id, AttemptState.ADMITTED, ["admission-evidence"])
        journal.transition(record.attempt_id, AttemptState.PREPARED, ["packet-evidence"])
        return record

    def test_duplicate_request_delivery_has_one_attempt(self):
        journal = InMemoryJournal()
        first = journal.claim("request:sha256:" + "a" * 64)
        second = journal.claim("request:sha256:" + "a" * 64)
        self.assertEqual(first.attempt_id, second.attempt_id)
        self.assertEqual(journal.attempt_count, 1)

    def test_concurrent_identical_admission_is_atomic(self):
        journal = InMemoryJournal()
        barrier = threading.Barrier(8)

        def claim(_):
            barrier.wait()
            return journal.claim("request:sha256:" + "b" * 64).attempt_id

        with ThreadPoolExecutor(max_workers=8) as pool:
            attempts = list(pool.map(claim, range(8)))
        self.assertEqual(len(set(attempts)), 1)
        self.assertEqual(journal.attempt_count, 1)

    def test_concurrent_different_requests_share_one_reviewer(self):
        journal = InMemoryJournal()
        first = self.advance_to_prepared(journal, "request:sha256:" + "c" * 64)
        second = self.advance_to_prepared(journal, "request:sha256:" + "d" * 64)
        journal.transition(first.attempt_id, AttemptState.ARMED, ["claim"])
        with self.assertRaises(ReviewerBusy):
            journal.transition(second.attempt_id, AttemptState.ARMED, ["claim"])

    def test_armed_is_durable_before_invocation(self):
        journal = InMemoryJournal()
        attempt = self.advance_to_prepared(journal, "request:sha256:" + "e" * 64)
        journal.transition(attempt.attempt_id, AttemptState.ARMED, ["durable-ref"])
        journal.record_invocation(attempt.attempt_id)
        self.assertEqual(journal.get(attempt.attempt_id).invocation_count, 1)
        with self.assertRaises(StateTransitionError):
            journal.record_invocation(attempt.attempt_id)

    def test_indeterminate_attempt_is_not_retried(self):
        journal = InMemoryJournal()
        attempt = self.advance_to_prepared(journal, "request:sha256:" + "f" * 64)
        journal.transition(attempt.attempt_id, AttemptState.ARMED, ["durable-ref"])
        journal.record_invocation(attempt.attempt_id)
        journal.transition(attempt.attempt_id, AttemptState.INDETERMINATE, ["lost-terminal"])
        with self.assertRaises(StateTransitionError):
            journal.transition(attempt.attempt_id, AttemptState.ARMED, ["retry"])

    def test_illegal_transition_is_rejected(self):
        journal = InMemoryJournal()
        attempt = journal.claim("request:sha256:" + "1" * 64)
        with self.assertRaises(StateTransitionError):
            journal.transition(attempt.attempt_id, AttemptState.VALIDATED, ["invented"])

    def test_generic_terminal_capture_transition_is_rejected(self):
        record = AttemptRecord(
            request_id="request:sha256:" + "7" * 64,
            attempt_id="attempt:sha256:" + "8" * 64,
            state=AttemptState.ARMED,
            invocation_count=1,
        )
        with self.assertRaisesRegex(StateTransitionError, "SPECIALIZED_EVIDENCE_REQUIRED"):
            transition_record(
                record,
                AttemptState.TERMINAL_CAPTURED,
                ["artifact:sha256:" + "9" * 64],
            )

    def test_generic_stopped_transition_is_rejected(self):
        record = AttemptRecord(
            request_id="request:sha256:" + "7" * 64,
            attempt_id="attempt:sha256:" + "8" * 64,
            state=AttemptState.REPORTED,
        )
        with self.assertRaisesRegex(StateTransitionError, "SPECIALIZED_EVIDENCE_REQUIRED"):
            transition_record(record, AttemptState.STOPPED, ["artifact:sha256:" + "9" * 64])

    def test_stopped_transition_requires_matching_shutdown_observation(self):
        record = AttemptRecord(
            request_id="request:sha256:" + "7" * 64,
            attempt_id="attempt:sha256:" + "8" * 64,
            state=AttemptState.REPORTED,
        )
        receipt = build_shutdown_observation(
            codespace_name="review-broker-safe",
            request_id=record.request_id,
            attempt_id=record.attempt_id,
            observed_state="Shutdown",
            context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
        )
        updated = record_shutdown_transition(record, receipt)
        self.assertEqual(updated.state, AttemptState.STOPPED)
        self.assertEqual(
            updated.evidence_ids[-1],
            artifact_identity(canonical_bytes(receipt) + b"\n"),
        )
        contradictory = dict(receipt)
        contradictory["observed_state"] = "Available"
        with self.assertRaisesRegex(StateTransitionError, "SHUTDOWN_OBSERVATION_INVALID"):
            record_shutdown_transition(record, contradictory)

    def test_shutdown_observation_must_bind_attempt(self):
        record = AttemptRecord(
            request_id="request:sha256:" + "7" * 64,
            attempt_id="attempt:sha256:" + "8" * 64,
            state=AttemptState.INDETERMINATE,
        )
        receipt = build_shutdown_observation(
            codespace_name="review-broker-safe",
            request_id=record.request_id,
            attempt_id="attempt:sha256:" + "0" * 64,
            observed_state="Shutdown",
            context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
        )
        with self.assertRaisesRegex(StateTransitionError, "SHUTDOWN_ATTEMPT_MISMATCH"):
            record_shutdown_transition(record, receipt)

    def test_evidence_is_required_for_every_transition(self):
        journal = InMemoryJournal()
        attempt = journal.claim("request:sha256:" + "2" * 64)
        with self.assertRaisesRegex(StateTransitionError, "EVIDENCE_REQUIRED"):
            journal.transition(attempt.attempt_id, AttemptState.ADMITTED, [])


if __name__ == "__main__":
    unittest.main()
