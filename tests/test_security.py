import json
from pathlib import Path
import tempfile
import unittest

from review_broker.admission import AdmissionError, AuthorizationPolicy, authorize
from review_broker.codespace import CodespaceController, CodespaceError
from review_broker.publication import GitHubPublisher, PublicationError, result_is_current
from review_broker.security import (
    IsolationProbe,
    SecurityQualification,
    isolation_probe_passes,
    require_security_qualification,
)


class FakeCodespaceRunner:
    def __init__(self, states):
        self.states = iter(states)
        self.commands = []
        self.environments = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        self.environments.append(kwargs.get("env"))
        if command[:3] == ["gh", "codespace", "view"]:
            state = next(self.states)
            return type("Result", (), {"returncode": 0, "stdout": json.dumps({"state": state}), "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()


class SecurityTests(unittest.TestCase):
    def request(self, repo="fanilosendrison/proto-scope"):
        return {"subject": {"repository": repo}}

    def test_unauthorized_requester_is_rejected(self):
        policy = AuthorizationPolicy(frozenset({"trusted"}), frozenset({"fanilosendrison/proto-scope"}))
        with self.assertRaisesRegex(AdmissionError, "REQUESTER_UNAUTHORIZED"):
            authorize("attacker", self.request(), policy)

    def test_unauthorized_repository_is_rejected(self):
        policy = AuthorizationPolicy(frozenset({"trusted"}), frozenset({"fanilosendrison/proto-scope"}))
        with self.assertRaisesRegex(AdmissionError, "REPOSITORY_UNAUTHORIZED"):
            authorize("trusted", self.request("other/repo"), policy)

    def test_security_self_qualification_is_rejected(self):
        qualification = SecurityQualification(
            status="PASS", reviewer="review-broker", subject="review-broker", evidence_ids=("x",)
        )
        with self.assertRaisesRegex(PermissionError, "SELF_QUALIFICATION"):
            require_security_qualification(qualification)

    def test_missing_security_evidence_fails_closed(self):
        qualification = SecurityQualification(
            status="PASS", reviewer="external", subject="review-broker", evidence_ids=()
        )
        with self.assertRaisesRegex(PermissionError, "EVIDENCE_REQUIRED"):
            require_security_qualification(qualification)

    def test_credential_access_attempt_blocks_isolation_qualification(self):
        probe = IsolationProbe(
            packet_readable=True,
            credential_readable=True,
            github_token_visible=False,
            api_key_visible=False,
            unauthorized_network_succeeded=False,
        )
        self.assertFalse(isolation_probe_passes(probe))

    def test_stale_result_does_not_apply_to_new_sha(self):
        result = {"resolved_request": {"subject": {"head_commit": "a" * 40}}}
        self.assertFalse(result_is_current(result, "b" * 40))
        self.assertTrue(result_is_current(result, "a" * 40))

    def test_failed_result_upload_preserves_validated_result(self):
        result = {
            "schema_version": 1,
            "request_id": "request:sha256:" + "1" * 64,
            "subject_id": "subject:sha256:" + "2" * 64,
            "policy_id": "policy:sha256:" + "3" * 64,
            "packet_id": "packet:sha256:" + "4" * 64,
            "attempt_id": "attempt:sha256:" + "5" * 64,
            "execution_status": "COMPLETED",
            "evidence_status": "VALID",
            "review_verdict": "GO",
            "resolved_request": {"subject": {"head_commit": "a" * 40}},
            "reviewer": {
                "backend": "codex-cli",
                "model_requested": "gpt-5.6-sol",
                "reasoning_effort_requested": "xhigh",
                "effective_model_identity_verified": False,
                "effective_reasoning_effort_verified": False,
            },
            "sources_examined": [],
            "findings": [],
            "remaining_uncertainties": [],
            "validation": {"semantic_correctness_validated": False},
            "applicability": {"status": "CURRENT", "checked_head_commit": "a" * 40},
        }
        def runner(*args, **kwargs):
            return type(
                "Result", (), {"returncode": 1, "stdout": "", "stderr": "denied"}
            )()

        with self.assertRaisesRegex(PublicationError, "RESULT_PUBLICATION_FAILED"):
            GitHubPublisher("sample/repo", runner=runner).publish(1, result)

    def test_codespace_commands_do_not_shell_interpolate_untrusted_values(self):
        runner = FakeCodespaceRunner(["Available"])
        controller = CodespaceController("safe-name", runner=runner, sleep=lambda _: None)
        controller.wait_for("Available", attempts=1, interval_seconds=0)
        self.assertIsInstance(runner.commands[0], list)
        self.assertNotIn("shell=True", runner.commands[0])

    def test_codespace_copy_uses_qualified_scp_modes(self):
        runner = FakeCodespaceRunner([])
        controller = CodespaceController("safe-name", runner=runner)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.write_bytes(b"fixed")
            expected_source = source.resolve()
            destination = Path(temporary) / "recovered"
            controller.transfer(source, "/tmp/fixed-upload")
            controller.recover("/tmp/fixed-download", destination)

        self.assertEqual(
            runner.commands[0][:9],
            [
                "gh", "codespace", "cp", "-c", "safe-name",
                "-r", "--", "-O", str(expected_source),
            ],
        )
        self.assertEqual(
            runner.commands[1][:10],
            [
                "gh", "codespace", "cp", "--expand", "-c", "safe-name",
                "-r", "--", "-O", "remote:/tmp/fixed-download",
            ],
        )

    def test_review_workflow_uses_qualified_codespace_copy_transport(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/review-request.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cp -c "$CODESPACE_NAME" -r -- -O', workflow)
        self.assertIn("internal-recover", workflow)

    def test_privileged_workflows_refuse_non_default_dispatch_refs(self):
        workflow_root = Path(__file__).parents[1] / ".github/workflows"
        for name in ("review-request.yml", "review-reconciler.yml"):
            workflow = (workflow_root / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn(
                    "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",
                    workflow,
                )
                self.assertIn("ref: ${{ github.sha }}", workflow)

    def test_remote_broker_executable_is_pinned_and_not_loaded_from_workspace(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/review-request.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("ref: ${{ github.sha }}", workflow)
        self.assertIn("broker-wheel.sha256", workflow)
        self.assertIn("python3 -P -m review_broker.cli", workflow)
        self.assertNotIn("python3 -m pip install --user .", workflow)

    def test_workflow_cannot_record_stopped_after_failed_observation(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/review-request.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("steps.stop.outcome == 'success'", workflow)
        self.assertIn("internal-record-stopped", workflow)
        self.assertNotIn("printf '%s' Shutdown", workflow)

    def test_workflow_cannot_promote_partial_recovery_to_terminal_capture(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/review-request.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("internal-capture-terminal", workflow)
        self.assertIn("internal-mark-indeterminate", workflow)
        self.assertNotIn("--state TERMINAL_CAPTURED", workflow)
        self.assertNotIn('"remote:$REMOTE_ROOT/evidence/$name"', workflow)

    def test_codespace_controller_uses_only_supplied_control_environment(self):
        runner = FakeCodespaceRunner(["Available"])
        environment = {"GH_TOKEN": "placeholder-control-token"}
        controller = CodespaceController(
            "safe-name",
            runner=runner,
            sleep=lambda _: None,
            environment=environment,
        )
        controller.wait_for("Available", attempts=1, interval_seconds=0)
        self.assertEqual(runner.environments, [environment])

    def test_cleanup_requires_observed_shutdown(self):
        runner = FakeCodespaceRunner(["ShuttingDown", "Shutdown"])
        controller = CodespaceController("safe-name", runner=runner, sleep=lambda _: None)
        controller.stop(attempts=2, interval_seconds=0)
        self.assertEqual(runner.commands[-1][-1], "state")

    def test_cleanup_failure_is_explicit(self):
        runner = FakeCodespaceRunner(["ShuttingDown", "ShuttingDown"])
        controller = CodespaceController("safe-name", runner=runner, sleep=lambda _: None)
        with self.assertRaisesRegex(CodespaceError, "SHUTDOWN_NOT_CONFIRMED"):
            controller.stop(attempts=2, interval_seconds=0)


if __name__ == "__main__":
    unittest.main()
