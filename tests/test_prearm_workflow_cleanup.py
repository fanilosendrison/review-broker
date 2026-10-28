import json
from pathlib import Path
import unittest

from review_broker.identity import request_identity
from review_broker.queue import AttemptRecord, AttemptState
from review_broker.reconciliation import reconcile_repository
from review_broker.request import build_issue_body
from tests.test_orchestration import FakeController, SharedJournal


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "review-request.yml"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-request.json"


def workflow_step(name: str) -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = f"      - name: {name}\n"
    start = workflow.index(marker)
    next_step = workflow.find("      - name:", start + len(marker))
    return workflow[start:] if next_step == -1 else workflow[start:next_step]


class PrearmWorkflowCleanupTests(unittest.TestCase):
    def test_terminal_capture_requires_successful_durable_armament(self):
        step = workflow_step("Establish complete terminal capture")
        self.assertIn("steps.arm.outcome == 'success'", step)
        self.assertIn("steps.runtime_quarantine.outcome == 'success'", step)
        self.assertIn("internal-capture-terminal", step)

    def test_indeterminate_marking_requires_armament_and_failed_capture(self):
        step = workflow_step("Preserve ambiguous execution as indeterminate")
        self.assertIn("id: indeterminate", step)
        self.assertIn("steps.arm.outcome == 'success'", step)
        self.assertIn("steps.capture.outcome == 'failure'", step)
        self.assertIn("internal-mark-indeterminate", step)

    def test_physical_shutdown_still_runs_after_started_prearm_failure(self):
        step = workflow_step("Stop and independently observe Shutdown")
        self.assertIn("always()", step)
        self.assertIn("steps.start.outcome != 'skipped'", step)
        self.assertIn("internal-stop-codespace", step)

    def test_stopped_transition_requires_a_legal_workflow_predecessor(self):
        step = workflow_step("Record stopped state from observed evidence")
        self.assertIn("steps.stop.outcome == 'success'", step)
        self.assertIn("steps.publish.outcome == 'success'", step)
        self.assertIn("steps.indeterminate.outcome == 'success'", step)
        self.assertIn("internal-record-stopped", step)
        self.assertNotIn("steps.arm.outcome", step)

    def test_partial_prearm_evidence_and_shutdown_receipt_remain_uploadable(self):
        stop = workflow_step("Stop and independently observe Shutdown")
        quarantine = workflow_step("Recheck all recovered evidence before final artifact")
        preserve = workflow_step("Preserve recovered evidence")
        self.assertIn("--output evidence", stop)
        self.assertIn("always()", quarantine)
        self.assertIn("always()", preserve)
        self.assertIn("path: |\n            evidence", preserve)

    def test_prearm_failure_cannot_publish_or_manufacture_result_validity(self):
        validation = workflow_step("Validate captured evidence")
        publication = workflow_step("Publish bounded result")
        self.assertIn("steps.capture.outcome == 'success'", validation)
        self.assertIn("steps.validation.outcome == 'success'", publication)


class ScheduledPrearmRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.request_id = request_identity(self.request)
        self.environment = {
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": "fanilosendrison/proto-scope",
            "REVIEW_BROKER_DEFAULT_BRANCH": "dev",
            "REVIEW_BROKER_SECURITY_QUALIFIED": "true",
            "REVIEW_BROKER_SECURITY_EVIDENCE_ID": "evidence:qualified",
        }

    def reconcile(self, state):
        journal = SharedJournal()
        journal.records[self.request_id] = AttemptRecord(
            request_id=self.request_id,
            attempt_id="attempt:sha256:" + "e" * 64,
            state=state,
            evidence_ids=("admission", "packet"),
            invocation_count=0,
        )
        dispatched = []

        def get_json(endpoint):
            if "/issues?" in endpoint:
                return [{
                    "number": 42,
                    "body": build_issue_body(self.request),
                    "user": {"login": "trusted"},
                }]
            if "/git/matching-refs/" in endpoint:
                return []
            if "/pulls/" in endpoint:
                return {"head": {"sha": "0" * 40}, "base": {"sha": "1" * 40, "repo": {"id": 7}}}
            if "/compare/" in endpoint:
                return {"merge_base_commit": {"sha": "2" * 40}}
            raise AssertionError(endpoint)

        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=self.environment,
            get_json=get_json,
            journal=journal,
            controller=FakeController(),
            dispatch=lambda *args: dispatched.append(args),
        )
        return journal, dispatched, decisions

    def test_scheduled_reconciliation_does_not_redispatch_prepared_attempt(self):
        journal, dispatched, decisions = self.reconcile(AttemptState.PREPARED)
        self.assertEqual(dispatched, [])
        self.assertEqual(decisions[0]["action"], "AWAIT_EXPLICIT_PREPARED_RECOVERY")
        self.assertEqual(decisions[0]["outcome"], "BLOCKED")
        self.assertEqual(journal.records[self.request_id].state, AttemptState.PREPARED)
        self.assertEqual(journal.records[self.request_id].invocation_count, 0)

    def test_admitted_lost_delivery_still_dispatches_automatically(self):
        _, dispatched, decisions = self.reconcile(AttemptState.ADMITTED)
        self.assertEqual(dispatched, [("fanilosendrison/review-broker", "dev", 42)])
        self.assertEqual(decisions[0]["action"], "DISPATCH_PRE_MODEL")


if __name__ == "__main__":
    unittest.main()
