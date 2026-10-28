"""Offline acceptance tests for the prepared RB-PILOT-02 entry point."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from review_broker.cli import main
from review_broker.codex import InvocationError
from review_broker.identity import attempt_identity, request_identity
from review_broker.packets import verify_packet
from review_broker.pilot_synthetic import (
    PILOT_MISSION,
    PILOT_SOURCE,
    PilotError,
    _run_synthetic_pilot,
    pilot_fixture,
    pilot_fixture_02,
    run_synthetic_pilot_02,
)


class SyntheticPilot02Tests(unittest.TestCase):
    def _run(self, temporary: str, invoke):
        root = Path(temporary).resolve()
        home = root / "home"
        workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        run = root / "pilot-02"
        claim = root / "pilot-02.claim.json"
        environment = {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "PATH": "/usr/bin",
        }
        with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
            "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
        ), patch(
            "review_broker.pilot_synthetic.preflight_codex_runtime",
            return_value={"cli_compatibility_verified": True},
        ) as preflight, patch(
            "review_broker.pilot_synthetic.invoke_once", side_effect=invoke,
        ) as invoked:
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
        self.assertEqual(preflight.call_count, 1)
        self.assertEqual(invoked.call_count, 1)
        return run, claim, result

    @staticmethod
    def _completed(evidence, *_args, **_kwargs):
        manifest = verify_packet(evidence)
        response = {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
            "packet_id": manifest["packet_id"],
            "verdict": "NO_GO",
            "sources_examined": ["S001"],
            "findings": [{
                "id": "F001",
                "category": "contradiction",
                "claim": "The age-18 boundary contradicts the documented behavior.",
                "consequence": "An applicant aged 18 is incorrectly rejected.",
                "evidence": [{
                    "source_id": "S001", "line": 3, "quote": "return age > 18",
                }],
            }],
            "remaining_uncertainties": [],
        }
        message = json.dumps(response)
        events = [
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
            {"type": "turn.completed"},
        ]
        (evidence / "codex-final.json").write_text(message, encoding="utf-8")
        (evidence / "codex-events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8",
        )
        (evidence / "codex-exit-code.txt").write_text("0\n", encoding="ascii")

    def test_fixture_and_mission_are_identical_but_identities_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = pilot_fixture(root / "first")
            second = pilot_fixture_02(root / "second")
            repeated = pilot_fixture_02(root / "repeated")
            digest = hashlib.sha256(PILOT_SOURCE).hexdigest()
            first_request = request_identity({
                "kind": "RB-PILOT-01", "fixture_sha256": digest, "ordinal": 1,
            })
            second_request = request_identity({
                "kind": "RB-PILOT-02", "fixture_sha256": digest, "ordinal": 1,
            })
            self.assertEqual(first["request_id"], first_request)
            self.assertEqual(second["request_id"], second_request)
            self.assertEqual(second, repeated)
            self.assertNotEqual(first_request, second_request)
            self.assertNotEqual(attempt_identity(first_request, 1),
                                attempt_identity(second_request, 1))
            self.assertEqual(
                PILOT_SOURCE, (root / "second/evidence/sources/S001.bin").read_bytes(),
            )
            self.assertIn(
                PILOT_MISSION.encode(), (root / "second/evidence/input.txt").read_bytes(),
            )
            self.assertEqual(first["subject_id"], second["subject_id"])
            self.assertEqual(first["sources"], second["sources"])

    def test_consumed_identity_refuses_before_arguments_environment_or_tmp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = root / "claim.json"
            run = root / "run"
            with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
            ), patch("review_broker.pilot_synthetic.preflight_codex_runtime") as preflight, patch(
                "review_broker.pilot_synthetic._write_pilot_02_claim",
            ) as claim_write, patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                for acknowledge, environment, wheel in (
                    (False, None, "invalid"),
                    (True, {"HOME": "/tmp/home", "PATH": "/bin", "GH_TOKEN": "x"}, "a" * 64),
                ):
                    with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                        run_synthetic_pilot_02(
                            acknowledge_unqualified_pilot=acknowledge,
                            broker_wheel_sha256=wheel,
                            environment=environment,
                        )
            preflight.assert_not_called(); claim_write.assert_not_called(); invoked.assert_not_called()
            self.assertFalse(claim.exists()); self.assertFalse(run.exists())

    def test_tmp_state_never_restores_consumed_identity(self):
        for claim_kind, run_present in (("absent", False), ("corrupt", False), ("regular", True)):
            with self.subTest(claim=claim_kind, run=run_present), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); claim = root / "claim.json"; run = root / "run"
                if claim_kind == "corrupt": claim.write_text("{")
                elif claim_kind == "regular": claim.write_text("{}")
                if claim.exists(): claim.chmod(0o600)
                if run_present: run.mkdir()
                with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                    "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
                ), patch("review_broker.pilot_synthetic.preflight_codex_runtime") as preflight, patch(
                    "review_broker.pilot_synthetic._write_pilot_02_claim",
                ) as claim_write, patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                    with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                        run_synthetic_pilot_02(
                            acknowledge_unqualified_pilot=True,
                            broker_wheel_sha256="a" * 64,
                            environment={"HOME": "/tmp/home", "PATH": "/bin"},
                        )
                preflight.assert_not_called(); claim_write.assert_not_called(); invoked.assert_not_called()

    def test_existing_claim_and_nonregular_claim_refuse_before_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            claim = root / "claim.json"
            digest = hashlib.sha256(PILOT_SOURCE).hexdigest()
            request_id = request_identity({
                "kind": "RB-PILOT-02", "fixture_sha256": digest, "ordinal": 1,
            })
            claim.write_text(json.dumps({
                "pilot_id": "RB-PILOT-02",
                "request_id": request_id,
                "attempt_id": attempt_identity(request_id, 1),
                "packet_id": "packet:sha256:synthetic",
                "status": "ARMED",
                "armed_utc": "2026-10-27T00:00:00+00:00",
            }), encoding="utf-8")
            claim.chmod(0o600)
            with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
            ), patch("review_broker.pilot_synthetic.preflight_codex_runtime") as preflight:
                with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                    run_synthetic_pilot_02(
                        acknowledge_unqualified_pilot=True,
                        broker_wheel_sha256="a" * 64,
                        environment={"HOME": "/tmp/home", "PATH": "/bin"},
                    )
            preflight.assert_not_called()
            claim.unlink(); claim.mkdir()
            with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                run_synthetic_pilot_02(
                    acknowledge_unqualified_pilot=True,
                    broker_wheel_sha256="a" * 64,
                    environment={"HOME": "/tmp/home", "PATH": "/bin"},
                )

    def test_success_writes_durable_claim_and_identity_bound_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            run, claim, result = self._run(temporary, self._completed)
            claim_value = json.loads(claim.read_text(encoding="utf-8"))
            armed = json.loads((run / "pilot-armed.json").read_text(encoding="utf-8"))
            summary = json.loads((run / "pilot-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(claim_value["pilot_id"], "RB-PILOT-02")
            self.assertEqual(claim_value["status"], "ARMED")
            self.assertEqual(stat.S_IMODE(claim.stat().st_mode), 0o600)
            for key in ("request_id", "attempt_id", "packet_id"):
                self.assertEqual(claim_value[key], armed[key])
                self.assertEqual(summary[key], armed[key])
            self.assertEqual(result["broker_wheel_sha256"], "a" * 64)
            self.assertEqual(result["model_requested"], "gpt-5.6-sol")
            self.assertEqual(result["effort_requested"], "xhigh")

    def test_structurally_invalid_results_close_with_private_failure_receipts(self):
        invalid_findings = (
            None,
            7,
            [None],
            [{
                "id": "F001", "category": "contradiction", "claim": "Invalid evidence.",
                "consequence": "The result is structurally invalid.", "evidence": None,
            }],
        )
        for findings in invalid_findings:
            with self.subTest(findings=findings), tempfile.TemporaryDirectory() as temporary:
                def invalid(evidence, *_args, **_kwargs):
                    manifest = verify_packet(evidence)
                    response = self._valid_response(manifest, findings=findings)
                    self._write_response(evidence, response)

                run, claim, result = self._run(temporary, invalid)
                armed = json.loads((run / "pilot-armed.json").read_text(encoding="utf-8"))
                summary_path = run / "pilot-summary.json"
                failure_path = run / "pilot-failure.json"
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                failure = json.loads(failure_path.read_text(encoding="utf-8"))
                self.assertEqual(result["pilot_functional"], "FAIL")
                self.assertEqual(result["schema_and_citations"], "FAIL")
                self.assertEqual(result["verdict"], "UNDETERMINED")
                self.assertEqual(result["validation_reasons"],
                                 ["PILOT_RESULT_SCHEMA_INVALID"])
                self.assertEqual(summary, result)
                self.assertEqual(stat.S_IMODE(summary_path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(failure_path.stat().st_mode), 0o600)
                for key in ("request_id", "attempt_id", "packet_id"):
                    self.assertEqual(failure[key], armed[key])
                    self.assertEqual(summary[key], armed[key])
                self.assertNotIn("Invalid evidence", failure_path.read_text(encoding="utf-8"))
                with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                    "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
                ), patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                    with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                        run_synthetic_pilot_02(
                            acknowledge_unqualified_pilot=True,
                            broker_wheel_sha256="a" * 64,
                        )
                invoked.assert_not_called()

    def test_unexpected_output_validation_error_is_sanitized_and_closed(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "review_broker.pilot_synthetic.pilot_output",
            side_effect=RuntimeError("raw synthetic provider material"),
        ):
            run, _, result = self._run(temporary, self._completed)
            self.assertEqual(result["failure"], "PILOT_OUTPUT_VALIDATION_UNAVAILABLE")
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertEqual(result["pilot_execution"], "INDETERMINATE")
            self.assertEqual(result["schema_and_citations"], "FAIL")
            self.assertEqual(result["verdict"], "UNDETERMINED")
            self.assertTrue((run / "pilot-summary.json").is_file())
            receipt = (run / "pilot-failure.json").read_text(encoding="utf-8")
            self.assertNotIn("raw synthetic provider material", receipt)
            self.assertNotIn("Traceback", receipt)

    @staticmethod
    def _valid_response(manifest, *, findings):
        return {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
            "packet_id": manifest["packet_id"],
            "verdict": "NO_GO",
            "sources_examined": ["S001"],
            "findings": findings,
            "remaining_uncertainties": [],
        }

    @staticmethod
    def _write_response(evidence, response):
        message = json.dumps(response)
        events = [
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
            {"type": "turn.completed"},
        ]
        (evidence / "codex-final.json").write_text(message, encoding="utf-8")
        (evidence / "codex-events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8",
        )
        (evidence / "codex-exit-code.txt").write_text("0\n", encoding="ascii")

    def test_failure_consumes_claim_and_second_invocation_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            run, claim, result = self._run(
                temporary, InvocationError("MODEL_UNAVAILABLE"),
            )
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertTrue(claim.is_file())
            with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", run), patch(
                "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", claim,
            ), patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                with self.assertRaisesRegex(PilotError, "PILOT_02_ALREADY_CONSUMED"):
                    run_synthetic_pilot_02(
                        acknowledge_unqualified_pilot=True,
                        broker_wheel_sha256="a" * 64,
                    )
            invoked.assert_not_called()

    def test_claim_write_failure_prevents_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / "home"
            workspace = root / "workspace"
            (home / ".codex").mkdir(parents=True)
            workspace.mkdir()
            with patch("review_broker.pilot_synthetic.PILOT_02_RUN_DIR", root / "run"), patch(
                "review_broker.pilot_synthetic.PILOT_02_CLAIM_PATH", root / "claim",
            ), patch("review_broker.pilot_synthetic.preflight_codex_runtime"), patch(
                "review_broker.pilot_synthetic._write_pilot_02_claim",
                side_effect=PilotError("PILOT_02_CLAIM_WRITE_FAILED"),
            ), patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                with self.assertRaisesRegex(PilotError, "PILOT_02_CLAIM_WRITE_FAILED"):
                    _run_synthetic_pilot(
                        root / "run",
                        fixture_builder=pilot_fixture_02,
                        pilot_id="RB-PILOT-02",
                        acknowledge_unqualified_pilot=True,
                        broker_wheel_sha256="a" * 64,
                        trusted_workspace=workspace,
                        codex_runtime_root=root / "runtime",
                        environment={"HOME": str(home), "PATH": "/bin"},
                    )
            invoked.assert_not_called()

    def test_cli_has_no_run_directory_and_does_not_pop_source_token(self):
        with patch.dict("os.environ", {"REVIEW_BROKER_SOURCE_TOKEN": "synthetic"}, clear=False), patch(
            "review_broker.cli.run_synthetic_pilot_02",
            side_effect=PilotError("PILOT_02_ALREADY_CONSUMED"),
        ):
            result = main([
                "pilot-synthetic-02", "--broker-wheel-sha256", "a" * 64,
                "--acknowledge-unqualified-pilot",
            ])
            self.assertEqual(result, 1)
            self.assertEqual(__import__("os").environ["REVIEW_BROKER_SOURCE_TOKEN"], "synthetic")
        with self.assertRaises(SystemExit):
            main([
                "pilot-synthetic-02", "--run-dir", "/tmp/other",
                "--broker-wheel-sha256", "a" * 64,
            ])


if __name__ == "__main__":
    unittest.main()
