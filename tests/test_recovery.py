import unittest

from review_broker.queue import AttemptRecord, AttemptState
from review_broker.recovery import RecoveryAction, decide_recovery


class RecoveryTests(unittest.TestCase):
    def record(self, state, invocation_count=0):
        return AttemptRecord(
            request_id="request:sha256:" + "a" * 64,
            attempt_id="attempt:sha256:" + "b" * 64,
            state=state,
            evidence_ids=("evidence",),
            invocation_count=invocation_count,
        )

    def test_lost_event_before_arming_is_safely_resumable(self):
        decision = decide_recovery(self.record(AttemptState.ADMITTED), codespace_state="Shutdown")
        self.assertEqual(decision.action, RecoveryAction.RESUME_PRE_MODEL)

    def test_crash_after_armed_without_terminal_is_indeterminate(self):
        decision = decide_recovery(self.record(AttemptState.ARMED, 1), codespace_state="Available")
        self.assertEqual(decision.action, RecoveryAction.MARK_INDETERMINATE_AND_STOP)

    def test_terminal_capture_resumes_validation_without_inference(self):
        decision = decide_recovery(self.record(AttemptState.TERMINAL_CAPTURED, 1), codespace_state="Available")
        self.assertEqual(decision.action, RecoveryAction.VALIDATE_EXISTING)

    def test_validated_attempt_resumes_publication(self):
        decision = decide_recovery(self.record(AttemptState.VALIDATED, 1), codespace_state="Shutdown")
        self.assertEqual(decision.action, RecoveryAction.PUBLISH_EXISTING)

    def test_reported_attempt_with_running_codespace_is_stopped(self):
        decision = decide_recovery(self.record(AttemptState.REPORTED, 1), codespace_state="Available")
        self.assertEqual(decision.action, RecoveryAction.STOP_CODESPACE)

    def test_stopped_attempt_needs_no_action(self):
        decision = decide_recovery(self.record(AttemptState.STOPPED, 1), codespace_state="Shutdown")
        self.assertEqual(decision.action, RecoveryAction.NONE)

    def test_failed_stop_is_an_infrastructure_incident(self):
        decision = decide_recovery(self.record(AttemptState.REPORTED, 1), codespace_state="Unknown")
        self.assertEqual(decision.action, RecoveryAction.INFRASTRUCTURE_INCIDENT)


if __name__ == "__main__":
    unittest.main()
