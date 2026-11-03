"""Offline production CLI, scheduler and final transport boundaries (no model)."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from review_broker.cli import main
from review_broker.codex import invoke_once, InvocationError
from review_broker.identity import canonical_bytes, request_identity
from review_broker.input_capacity import MAX_CHARS, capacity_receipt
from review_broker.queue import AttemptRecord, AttemptState
from review_broker.reconciliation import reconcile_repository
from review_broker.request import build_issue_body
from review_broker.reviewer_profile import install_reviewer_profile
from tests import test_input_capacity as fixtures
from tests.test_codex import verified_runtime
from tests.test_orchestration import SharedJournal, FakeController


class CapacityBoundaryTests(unittest.TestCase):
    def setUp(self):
        # Reuse the exact real-packet fixture without importing a discoverable TestCase alias.
        self.factory = fixtures.InputCapacityTests()
        self.factory.setUp()
        self.addCleanup(self.factory.doCleanups)

    def cli(self, command, directory, manifest, journal):
        output, errors = io.StringIO(), io.StringIO()
        with patch("review_broker.capacity_cli.GitHubRefJournal", return_value=journal), \
             redirect_stdout(output), redirect_stderr(errors):
            code = main([command, "--request", fixtures.REQUEST, "--packet-id", manifest["packet_id"],
                         "--packet-dir", str(directory), "--executing-broker-sha", fixtures.BROKER])
        return code, output.getvalue(), errors.getvalue()

    def test_cli_success_rechecks_before_arm_and_returns_bound_counts(self):
        directory, manifest, journal = self.factory.packet()
        code, output, errors = self.cli("internal-input-capacity", directory, manifest, journal)
        self.assertEqual((code, errors), (0, ""))
        receipt = json.loads(output)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(journal.get(fixtures.REQUEST).state, AttemptState.PREPARED)
        code, output, errors = self.cli("internal-arm", directory, manifest, journal)
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(output), receipt)
        self.assertEqual(journal.get(fixtures.REQUEST).invocation_count, 1)

    def test_cli_capacity_failure_is_explicit_and_cannot_be_armed_later(self):
        directory, manifest, journal = self.factory.packet("x" * MAX_CHARS)
        for command in ["internal-input-capacity", "internal-arm"]:
            code, output, errors = self.cli(command, directory, manifest, journal)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output)["status"], "REJECTED")
            self.assertIn("INPUT_CAPACITY_REJECTED", errors)
            self.assertEqual(journal.get(fixtures.REQUEST).state, AttemptState.PREPARED)
            self.assertEqual(journal.get(fixtures.REQUEST).invocation_count, 0)

    def test_generic_cli_transition_cannot_bypass_specialized_armament(self):
        errors = io.StringIO()
        with patch("review_broker.cli.GitHubRefJournal") as journal, redirect_stderr(errors):
            code = main(["internal-transition", "--request", fixtures.REQUEST,
                         "--state", "ARMED", "--evidence", "packet-fixture"])
        self.assertEqual(code, 1)
        self.assertIn("CAPACITY_GATED_ARMAMENT_REQUIRED", errors.getvalue())
        journal.assert_not_called()

    def test_non_ascii_cannot_pass_by_counting_only_unicode_scalars(self):
        directory, manifest, journal = self.factory.packet("\u00e9" * (MAX_CHARS // 2))
        code, output, _ = self.cli("internal-input-capacity", directory, manifest, journal)
        receipt = json.loads(output)
        self.assertLess(receipt["unicode_scalar_characters"], MAX_CHARS)
        self.assertGreater(receipt["utf8_bytes"], MAX_CHARS)
        self.assertEqual(code, 1)
        self.assertEqual(journal.get(fixtures.REQUEST).invocation_count, 0)

    def invocation_fixture(self, mission="Review."):
        directory, manifest, journal = self.factory.packet(mission)
        root = directory.parent
        home, workspace = root / "home", root / "workspace"
        (home / ".codex").mkdir(parents=True, exist_ok=True)
        workspace.mkdir(exist_ok=True)
        schema = root / "schema.json"
        schema.write_text("{}")
        install_reviewer_profile(home, workspace, directory)
        arguments = dict(expected_packet_id=manifest["packet_id"], broker_wheel_sha256="1" * 64,
                         trusted_workspace=workspace, codex_runtime_root=root / "protected",
                         environment={"HOME": str(home), "PATH": "/trusted/bin"},
                         runtime_verifier=lambda *_: verified_runtime(root))
        return directory, manifest, journal, schema, arguments

    def test_final_adapter_rejects_oversized_input_without_transport_or_attempt_artifacts(self):
        directory, _, _, schema, arguments = self.invocation_fixture("x" * MAX_CHARS)
        runner = Mock(side_effect=AssertionError("model-capable runner forbidden"))
        with self.assertRaisesRegex(InvocationError, "INPUT_CAPACITY_REJECTED"):
            invoke_once(directory, schema, fixtures.ATTEMPT, runner=runner, **arguments)
        runner.assert_not_called()
        self.assertFalse((directory / "attempt.json").exists())

    def test_final_adapter_transmits_the_checked_memory_snapshot_not_a_reopened_path(self):
        directory, manifest, journal, schema, arguments = self.invocation_fixture()
        receipt = self.factory.check(directory, manifest, journal, arm=True)
        (directory / "input-capacity.json").write_bytes(canonical_bytes(receipt) + b"\n")
        original = (directory / "input.txt").read_bytes()
        calls = []
        def runner(command, **kwargs):
            calls.append(kwargs["input"])
            self.assertNotIn("stdin", kwargs)
            self.assertEqual(kwargs["input"], original)
            (directory / "input.txt").write_bytes(b"late path substitution")
            (directory / "codex-final.json").write_bytes(b"{}")
            return subprocess.CompletedProcess(command, 0)
        with self.assertRaisesRegex(InvocationError, "INPUT_CHANGED_DURING_EXECUTION"):
            invoke_once(directory, schema, fixtures.ATTEMPT, runner=runner, **arguments)
        self.assertEqual(calls, [original])
        self.assertEqual((directory / "input-before.sha256").read_text().strip(), receipt["input_sha256"])

    def test_missing_or_forged_capacity_receipt_prevents_transport(self):
        for forged in [False, True]:
            with self.subTest(forged=forged):
                directory, manifest, journal, schema, arguments = self.invocation_fixture()
                receipt = self.factory.check(directory, manifest, journal, arm=True)
                if forged:
                    receipt["executing_broker_sha"] = "f" * 40
                    (directory / "input-capacity.json").write_bytes(canonical_bytes(receipt) + b"\n")
                runner = Mock(side_effect=AssertionError("model-capable runner forbidden"))
                with self.assertRaisesRegex(InvocationError, "CAPACITY"):
                    invoke_once(directory, schema, fixtures.ATTEMPT, runner=runner, **arguments)
                runner.assert_not_called()

    def test_scheduler_does_not_dispatch_a_durable_capacity_rejection(self):
        request = json.loads((Path(__file__).parent / "fixtures/sample-request.json").read_text())
        request_id = request_identity(request)
        attempt_id = "attempt:sha256:" + "e" * 64
        receipt = capacity_receipt(b"x" * (MAX_CHARS + 1), request_id=request_id,
            packet_id="packet:sha256:" + "a" * 64, attempt_id=attempt_id, executing_broker_sha=fixtures.BROKER)
        journal = SharedJournal()
        journal.records[request_id] = AttemptRecord(request_id, attempt_id, AttemptState.PREPARED,
            input_capacity=receipt)
        def getter(endpoint):
            if "/issues?" in endpoint:
                return [{"number": 42, "body": build_issue_body(request), "user": {"login": "trusted"}}]
            if "/git/matching-refs/" in endpoint:
                return []
            if "/pulls/" in endpoint:
                return {"head": {"sha": "0" * 40}, "base": {"sha": "1" * 40, "repo": {"id": 7}}}
            if "/compare/" in endpoint:
                return {"merge_base_commit": {"sha": "2" * 40}}
            raise AssertionError(endpoint)
        dispatch = Mock()
        results = reconcile_repository("sample/broker", "fixture-codespace", journal=journal,
            controller=FakeController(), get_json=getter, dispatch=dispatch, environment={
                "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
                "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": "fanilosendrison/proto-scope",
                "REVIEW_BROKER_SECURITY_QUALIFIED": "true",
                "REVIEW_BROKER_SECURITY_EVIDENCE_ID": "evidence:qualified",
            })
        dispatch.assert_not_called()
        self.assertEqual(results[0]["action"], "BLOCKED_INPUT_CAPACITY")
        self.assertEqual(results[0]["outcome"], "BLOCKED")
        self.assertEqual(journal.records[request_id].state, AttemptState.PREPARED)
        self.assertEqual(journal.records[request_id].invocation_count, 0)

    def test_workflow_guards_lifecycle_final_arm_and_inference(self):
        from tests.test_prearm_workflow_cleanup import workflow_step, WORKFLOW
        early = workflow_step("Assess exact rendered-input capacity before lifecycle")
        arm = workflow_step("Durably arm exactly one invocation")
        invocation = workflow_step("Invoke Codex once")
        self.assertIn("internal-input-capacity", early)
        self.assertIn("evidence/input-capacity.json", early)
        self.assertIn("--packet-dir evidence", arm)
        self.assertIn('--executing-broker-sha "$GITHUB_SHA"', arm)
        self.assertIn("steps.arm.outcome == 'success'", invocation)
        self.assertLess(WORKFLOW.read_text().index("Assess exact rendered-input capacity"),
                        WORKFLOW.read_text().index("Start and observe dedicated Codespace"))


if __name__ == "__main__":
    unittest.main()
