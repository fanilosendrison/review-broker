"""Offline tests for factual synthetic-pilot process dispatch observations."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from review_broker.codex import invoke_once
from review_broker.codex_runtime_identity import CodexRuntimeIdentityError
from review_broker.pilot_runner import PilotRunner
from review_broker.pilot_synthetic import _run_synthetic_pilot, pilot_fixture_02


class PilotRunnerTests(unittest.TestCase):
    def test_not_dispatched_observation_starts_at_zero(self):
        runner = PilotRunner(native_runner=Mock())
        self.assertEqual(runner.observation(), {
            "runner_dispatches": 0,
            "process_start_status": "NOT_DISPATCHED",
            "inference_process_invocations": 0,
        })

    def test_completed_process_confirms_one_process_for_any_exit(self):
        for returncode in (0, 1):
            with self.subTest(returncode=returncode):
                native = Mock(return_value=subprocess.CompletedProcess(["codex"], returncode))
                runner = PilotRunner(native_runner=native)
                result = runner(["codex"], check=False)
                self.assertEqual(result.returncode, returncode)
                self.assertEqual(runner.observation(), {
                    "runner_dispatches": 1,
                    "process_start_status": "CONFIRMED",
                    "inference_process_invocations": 1,
                })
                native.assert_called_once_with(["codex"], check=False)

    def test_timeout_confirms_process_start(self):
        native = Mock(side_effect=subprocess.TimeoutExpired(["codex"], 10))
        runner = PilotRunner(native_runner=native)
        with self.assertRaises(subprocess.TimeoutExpired):
            runner(["codex"], timeout=10)
        self.assertEqual(runner.observation(), {
            "runner_dispatches": 1,
            "process_start_status": "CONFIRMED",
            "inference_process_invocations": 1,
        })

    def test_os_error_preserves_process_start_ambiguity(self):
        native = Mock(side_effect=OSError("synthetic pre-start failure"))
        runner = PilotRunner(native_runner=native)
        with self.assertRaises(OSError):
            runner(["codex"])
        self.assertEqual(runner.observation(), {
            "runner_dispatches": 1,
            "process_start_status": "UNDETERMINED",
            "inference_process_invocations": "UNDETERMINED",
        })

    def test_second_dispatch_is_refused_without_native_call(self):
        native = Mock(return_value=subprocess.CompletedProcess(["codex"], 0))
        runner = PilotRunner(native_runner=native)
        runner(["codex"])
        with self.assertRaisesRegex(RuntimeError, "PILOT_RUNNER_ALREADY_DISPATCHED"):
            runner(["codex"])
        self.assertEqual(native.call_count, 1)

    def test_pilot_receipts_preserve_runner_observations(self):
        scenarios = (
            ("exit-zero", subprocess.CompletedProcess(["codex"], 0),
             "CONFIRMED", 1),
            ("exit-nonzero", subprocess.CompletedProcess(["codex"], 1),
             "CONFIRMED", 1),
            ("timeout", subprocess.TimeoutExpired(["codex"], 10),
             "CONFIRMED", 1),
            ("os-error", OSError("synthetic uncertain start"),
             "UNDETERMINED", "UNDETERMINED"),
        )
        for name, native_outcome, expected_status, expected_processes in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                home = root / "home"
                workspace = root / "workspace"
                (home / ".codex").mkdir(parents=True)
                workspace.mkdir()
                run = root / "run"
                claim = root / "claim.json"
                environment = {
                    "HOME": str(home), "CODEX_HOME": str(home / ".codex"),
                    "PATH": "/bin",
                }
                native = (Mock(side_effect=native_outcome)
                          if isinstance(native_outcome, BaseException)
                          else Mock(return_value=native_outcome))

                def simulated_invoke(*_args, runner, **_kwargs):
                    result = runner(["codex"], check=False)
                    if result.returncode:
                        raise RuntimeError("simulated nonzero after dispatch")

                with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                    "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
                ), patch("review_broker.pilot_synthetic.preflight_codex_runtime"), patch(
                    "review_broker.pilot_runner.subprocess.run", native,
                ), patch(
                    "review_broker.pilot_synthetic.invoke_once",
                    side_effect=simulated_invoke,
                ):
                    result = _run_synthetic_pilot(
                        run,
                        fixture_builder=pilot_fixture_02,
                        pilot_id="RB-PILOT-02",
                        acknowledge_unqualified_pilot=True,
                        broker_wheel_sha256="a" * 64,
                        trusted_workspace=workspace,
                        codex_runtime_root=root / "runtime",
                        environment=environment,
                    )
                self.assertEqual(result["runner_dispatches"], 1)
                self.assertEqual(result["process_start_status"], expected_status)
                self.assertEqual(result["inference_process_invocations"],
                                 expected_processes)
                failure = (run / "pilot-failure.json").read_text(encoding="utf-8")
                self.assertIn('"runner_dispatches":1', failure)
                self.assertIn(f'"process_start_status":"{expected_status}"', failure)
                native.assert_called_once_with(["codex"], check=False)

    def test_real_invoke_rejection_before_runner_reports_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / "home"
            workspace = root / "workspace"
            (home / ".codex").mkdir(parents=True)
            workspace.mkdir()
            run = root / "run"
            claim = root / "claim.json"
            environment = {
                "HOME": str(home), "CODEX_HOME": str(home / ".codex"), "PATH": "/bin",
            }
            native = Mock()

            def invoke_with_runtime_rejection(evidence, schema, attempt_id, **kwargs):
                def reject_runtime(_environment, _runtime_root):
                    raise CodexRuntimeIdentityError("SYNTHETIC_PRE_RUN_REJECTION")
                return invoke_once(
                    evidence, schema, attempt_id,
                    runtime_verifier=reject_runtime,
                    **kwargs,
                )

            with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
            ), patch("review_broker.pilot_synthetic.preflight_codex_runtime"), patch(
                "review_broker.pilot_runner.subprocess.run", native,
            ), patch(
                "review_broker.pilot_synthetic.invoke_once",
                side_effect=invoke_with_runtime_rejection,
            ):
                result = _run_synthetic_pilot(
                    run,
                    fixture_builder=pilot_fixture_02,
                    pilot_id="RB-PILOT-02",
                    acknowledge_unqualified_pilot=True,
                    broker_wheel_sha256="a" * 64,
                    trusted_workspace=workspace,
                    codex_runtime_root=root / "runtime",
                    environment=environment,
                )
            self.assertEqual(result["runner_dispatches"], 0)
            self.assertEqual(result["process_start_status"], "NOT_DISPATCHED")
            self.assertEqual(result["inference_process_invocations"], 0)
            failure = (run / "pilot-failure.json").read_text(encoding="utf-8")
            self.assertIn('"runner_dispatches":0', failure)
            self.assertIn('"process_start_status":"NOT_DISPATCHED"', failure)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
