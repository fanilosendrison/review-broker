from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import unittest

from review_broker.identity import request_identity
from review_broker.codespace import CodespaceError
from review_broker.execution_recovery import (
    ExecutionRecoveryError,
    recover_runtime_evidence,
    stop_and_observe_shutdown,
)
from review_broker.orchestration import OrchestrationError, _pull_request_files
from review_broker.reconciliation import ReconciliationError, reconcile_repository
from review_broker.queue import (
    AttemptRecord,
    AttemptState,
    record_shutdown_transition,
    transition_record,
)
from review_broker.request import build_issue_body


FIXTURE = Path(__file__).parent / "fixtures" / "sample-request.json"


class SharedJournal:
    def __init__(self):
        self._lock = threading.Lock()
        self.records = {}
        self.claim_count = 0

    def claim(self, request_id):
        with self._lock:
            record = self.records.get(request_id)
            if record is None:
                record = AttemptRecord(
                    request_id=request_id,
                    attempt_id="attempt:sha256:" + "a" * 64,
                    state=AttemptState.REQUESTED,
                )
                self.records[request_id] = record
                self.claim_count += 1
            return record

    def get(self, request_id):
        with self._lock:
            if request_id not in self.records:
                raise KeyError(request_id)
            return self.records[request_id]

    def transition(self, request_id, target, evidence_ids):
        with self._lock:
            updated = transition_record(self.records[request_id], target, evidence_ids)
            self.records[request_id] = updated
            return updated

    def record_stopped(self, request_id, receipt):
        with self._lock:
            updated = record_shutdown_transition(self.records[request_id], receipt)
            self.records[request_id] = updated
            return updated


class FakeController:
    name = "review-broker-safe"

    def __init__(self, state="Shutdown"):
        self.observed_state = state
        self.stop_count = 0

    def state(self):
        return self.observed_state

    def stop(self):
        self.stop_count += 1
        self.observed_state = "Shutdown"


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.environment = {
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": "fanilosendrison/proto-scope",
            "REVIEW_BROKER_DEFAULT_BRANCH": "dev",
            "REVIEW_BROKER_SECURITY_QUALIFIED": "true",
            "REVIEW_BROKER_SECURITY_EVIDENCE_ID": "evidence:qualified",
        }

    def issue(self, number=42, actor="trusted"):
        return {
            "number": number,
            "body": build_issue_body(self.request),
            "user": {"login": actor},
        }

    def getter(self, issues, refs=()):
        def get_json(endpoint):
            if "/issues?" in endpoint:
                return list(issues)
            if "/git/matching-refs/" in endpoint:
                return list(refs)
            if "/pulls/" in endpoint:
                return {
                    "head": {"sha": "0" * 40},
                    "base": {"sha": "1" * 40, "repo": {"id": 7}},
                }
            if "/compare/" in endpoint:
                return {"merge_base_commit": {"sha": "2" * 40}}
            raise AssertionError(endpoint)

        return get_json

    def reconcile(self, issues, journal, dispatched, **kwargs):
        return reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=self.environment,
            get_json=self.getter(issues),
            journal=journal,
            controller=FakeController(),
            dispatch=lambda repository, branch, issue_number: dispatched.append(
                (repository, branch, issue_number)
            ),
            **kwargs,
        )

    def test_pull_request_head_change_during_file_enumeration_is_rejected(self):
        def get_json(endpoint):
            if "/files?" in endpoint:
                return [{"filename": "README.md", "status": "modified"}]
            if "/pulls/" in endpoint:
                return {"head": {"sha": "9" * 40}}
            raise AssertionError(endpoint)

        with self.assertRaisesRegex(
            OrchestrationError,
            "PULL_REQUEST_HEAD_CHANGED_DURING_PREPARATION",
        ):
            _pull_request_files(
                "sample/repo",
                7,
                expected_head="8" * 40,
                get_json=get_json,
            )

    def test_partial_runtime_recovery_is_preserved_without_complete_claim(self):
        class PartialController:
            name = "review-broker-safe"

            def recover(self, remote_path, destination):
                if remote_path.endswith("codex-events.jsonl"):
                    raise CodespaceError("COMMAND_FAILED:codespace:cp")
                destination.write_bytes(b"partial")

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = recover_runtime_evidence(
                PartialController(),
                "/tmp/evidence",
                root,
                request_id="request:sha256:" + "1" * 64,
                attempt_id="attempt:sha256:" + "2" * 64,
                context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
            )
            self.assertFalse(manifest["complete"])
            self.assertFalse(manifest["artifacts"]["codex-events.jsonl"]["recovered"])
            self.assertTrue((root / "attempt.json").is_file())
            self.assertTrue((root / "recovery-manifest.json").is_file())

    def test_shutdown_observation_is_bound_to_actual_controller_state(self):
        controller = FakeController("Available")
        with self.subTest("observed shutdown"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as temporary:
                receipt = stop_and_observe_shutdown(
                    controller,
                    Path(temporary),
                    request_id="request:sha256:" + "1" * 64,
                    attempt_id="attempt:sha256:" + "2" * 64,
                    context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
                )
                self.assertEqual(receipt["observed_state"], "Shutdown")
                self.assertTrue((Path(temporary) / "shutdown-observation.json").is_file())

    def test_failed_shutdown_writes_incident_not_observation(self):
        class BrokenController(FakeController):
            def stop(self):
                raise CodespaceError("SHUTDOWN_NOT_CONFIRMED")

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ExecutionRecoveryError, "SHUTDOWN_UNVERIFIED"):
                stop_and_observe_shutdown(
                    BrokenController("Available"),
                    root,
                    request_id="request:sha256:" + "1" * 64,
                    attempt_id="attempt:sha256:" + "2" * 64,
                    context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
                )
            self.assertTrue((root / "shutdown-incident.json").is_file())
            self.assertFalse((root / "shutdown-observation.json").exists())

    def test_armed_recovery_becomes_indeterminate_and_stopped_without_dispatch(self):
        request_id = "request:sha256:" + "a" * 64
        journal = SharedJournal()
        journal.records[request_id] = AttemptRecord(
            request_id=request_id,
            attempt_id="attempt:sha256:" + "b" * 64,
            state=AttemptState.ARMED,
            invocation_count=1,
        )
        controller = FakeController("Available")
        dispatched = []
        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=self.environment,
            get_json=self.getter([], [{"ref": "refs/heads/review-claims/" + "a" * 64}]),
            journal=journal,
            controller=controller,
            dispatch=lambda *args: dispatched.append(args),
        )
        self.assertEqual(journal.records[request_id].state, AttemptState.STOPPED)
        self.assertEqual(dispatched, [])
        self.assertEqual(decisions[0]["outcome"], "INDETERMINATE_AND_STOPPED")
        self.assertEqual(controller.stop_count, 1)

    def test_terminal_recovery_is_explicitly_blocked_without_artifact_locator(self):
        request_id = "request:sha256:" + "c" * 64
        journal = SharedJournal()
        journal.records[request_id] = AttemptRecord(
            request_id=request_id,
            attempt_id="attempt:sha256:" + "d" * 64,
            state=AttemptState.TERMINAL_CAPTURED,
            invocation_count=1,
        )
        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=self.environment,
            get_json=self.getter([], [{"ref": "refs/heads/review-claims/" + "c" * 64}]),
            journal=journal,
            controller=FakeController(),
            dispatch=lambda *args: self.fail("dispatch forbidden"),
        )
        self.assertEqual(decisions[0]["outcome"], "BLOCKED")
        self.assertEqual(journal.records[request_id].state, AttemptState.TERMINAL_CAPTURED)

    def test_lost_issue_event_creates_canonical_claim_and_dispatches(self):
        journal = SharedJournal()
        dispatched = []
        decisions = self.reconcile([self.issue()], journal, dispatched)
        request_id = request_identity(self.request)
        self.assertEqual(journal.claim_count, 1)
        self.assertEqual(journal.records[request_id].state, AttemptState.REQUESTED)
        self.assertEqual(dispatched, [("fanilosendrison/review-broker", "dev", 42)])
        self.assertEqual(decisions[0]["action"], "DISPATCH_PRE_MODEL")

    def test_duplicate_issue_delivery_dispatches_one_canonical_request(self):
        journal = SharedJournal()
        dispatched = []
        self.reconcile([self.issue(43), self.issue(42)], journal, dispatched)
        self.assertEqual(journal.claim_count, 1)
        self.assertEqual(dispatched, [("fanilosendrison/review-broker", "dev", 42)])

    def test_concurrent_reconciliation_keeps_one_attempt(self):
        journal = SharedJournal()
        dispatched = []
        dispatch_lock = threading.Lock()

        def dispatch(repository, branch, issue_number):
            with dispatch_lock:
                dispatched.append((repository, branch, issue_number))

        def run(_):
            return reconcile_repository(
                "fanilosendrison/review-broker",
                "review-broker-safe",
                environment=self.environment,
                get_json=self.getter([self.issue()]),
                journal=journal,
                controller=FakeController(),
                dispatch=dispatch,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run, range(2)))
        self.assertEqual(journal.claim_count, 1)
        self.assertEqual(len(journal.records), 1)
        self.assertGreaterEqual(len(dispatched), 1)

    def test_private_source_without_dedicated_read_token_is_explicitly_blocked(self):
        journal = SharedJournal()
        dispatched = []
        environment = {
            **self.environment,
            "REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES": "fanilosendrison/proto-scope",
        }
        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=environment,
            get_json=self.getter([self.issue()]),
            journal=journal,
            controller=FakeController(),
            dispatch=lambda *args: dispatched.append(args),
        )
        self.assertEqual(decisions[0]["action"], "PRIVATE_SOURCE_CREDENTIAL_REQUIRED")
        self.assertEqual(decisions[0]["outcome"], "BLOCKED")
        self.assertEqual(journal.claim_count, 0)
        self.assertEqual(dispatched, [])

    def test_unauthorized_private_request_does_not_disclose_credential_state(self):
        journal = SharedJournal()
        dispatched = []
        environment = {
            **self.environment,
            "REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES": "fanilosendrison/proto-scope",
        }
        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            "review-broker-safe",
            environment=environment,
            get_json=self.getter([self.issue(actor="untrusted")]),
            journal=journal,
            controller=FakeController(),
            dispatch=lambda *args: dispatched.append(args),
        )
        self.assertEqual(decisions[0]["action"], "REJECTED_REQUEST")
        self.assertNotIn("credential", decisions[0].get("reason", "").lower())

    def test_unauthorized_discovered_issue_is_not_claimed_or_dispatched(self):
        journal = SharedJournal()
        dispatched = []
        decisions = self.reconcile(
            [self.issue(actor="untrusted")],
            journal,
            dispatched,
        )
        self.assertEqual(journal.claim_count, 0)
        self.assertEqual(dispatched, [])
        self.assertEqual(decisions[0]["action"], "REJECTED_REQUEST")

    def test_incomplete_issue_scan_fails_before_claim_or_dispatch(self):
        journal = SharedJournal()
        dispatched = []
        issues = [self.issue(number=index + 1) for index in range(100)]
        with self.assertRaisesRegex(ReconciliationError, "ISSUE_SCAN_INCOMPLETE"):
            self.reconcile(
                issues,
                journal,
                dispatched,
                max_issue_pages=1,
            )
        self.assertEqual(journal.claim_count, 0)
        self.assertEqual(dispatched, [])


if __name__ == "__main__":
    unittest.main()
