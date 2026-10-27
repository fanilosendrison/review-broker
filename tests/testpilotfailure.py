"""Offline integration tests for synthetic-pilot failure receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from review_broker.codex import InvocationError
from review_broker.codexfailure import observe_codex_failure
from review_broker.identity import attempt_identity, request_identity
from review_broker.cli import main
from review_broker.pilot_synthetic import PILOT_SOURCE, PilotError, run_synthetic_pilot


class SyntheticPilotFailureReceiptTests(unittest.TestCase):
    def _run(self, temporary: str, invoke):
        root = Path(temporary)
        home = root / "home"
        workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        environment = {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
        }
        with patch(
            "review_broker.pilot_synthetic._require_unconsumed_pilot_identity",
            return_value=None,
        ), patch(
            "review_broker.pilot_synthetic.preflight_codex_runtime",
            return_value={"cli_compatibility_verified": True},
        ), patch("review_broker.pilot_synthetic.invoke_once", side_effect=invoke) as called:
            result = run_synthetic_pilot(
                root / "pilot",
                acknowledge_unqualified_pilot=True,
                broker_wheel_sha256="a" * 64,
                trusted_workspace=workspace,
                codex_runtime_root=root / "runtime",
                environment=environment,
            )
        self.assertEqual(called.call_count, 1)
        return root / "pilot", result

    def test_failure_receipt_is_private_structured_and_durable(self):
        event = {
            "type": "turn.failed",
            "id": "turn-1",
            "error": {
                "type": "invalid_request_error",
                "code": "unsupported_value",
                "message": "raw provider message",
                "param": "model",
            },
            "status": 400,
        }
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(event) + "\n").encode(),
            stderr_bytes=b"",
        )

        def failed(*_args, **_kwargs):
            raise InvocationError("CODEX_PROVIDER_ERROR", failure_observation=observation)

        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as temporary:
            run, result = self._run(temporary, failed)
            receipt_path = run / "pilot-failure.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(result["failure"], "CODEX_PROVIDER_ERROR")
            self.assertEqual(receipt["classification"], "CODEX_PROVIDER_ERROR")
            self.assertEqual(receipt["attempt_ordinal"], 1)
            self.assertTrue(receipt["attempt_identity_consumed"])
            self.assertEqual(receipt["exit_code"], 1)
            self.assertEqual(receipt["failure_observation"], observation)
            self.assertEqual(stat.S_IMODE(receipt_path.stat().st_mode), 0o600)
            self.assertNotIn("raw provider message", receipt_path.read_text(encoding="utf-8"))

    def test_credential_quarantine_has_priority_over_extracted_error(self):
        raw_secret = "Bearer SYNTHETIC00000000000000000000"
        event = {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "code": "unauthorized",
                "message": raw_secret,
            },
            "status": 401,
        }
        event_bytes = (json.dumps(event) + "\n").encode()
        observation = observe_codex_failure(
            returncode=1, event_bytes=event_bytes, stderr_bytes=b"",
        )

        def contaminated(evidence, *_args, **_kwargs):
            (evidence / "codex-events.jsonl").write_bytes(event_bytes)
            (evidence / "codex-exit-code.txt").write_text("1\n", encoding="ascii")
            raise InvocationError("CODEX_PROVIDER_ERROR", failure_observation=observation)

        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as temporary:
            run, result = self._run(temporary, contaminated)
            receipt_text = (run / "pilot-failure.json").read_text(encoding="utf-8")
            receipt = json.loads(receipt_text)
            self.assertEqual(result["failure"], "PILOT_CREDENTIAL_OUTPUT_QUARANTINED")
            self.assertEqual(receipt["classification"],
                             "PILOT_CREDENTIAL_OUTPUT_QUARANTINED")
            self.assertEqual(receipt["failure_observation"], "UNDETERMINED")
            self.assertEqual(receipt["exit_code"], 1)
            self.assertEqual(receipt["credential_screen"], "CONTAMINATED_QUARANTINED")
            self.assertNotIn(raw_secret, receipt_text)
            self.assertTrue((run / "evidence/credential-incident.json").is_file())

    def test_operator_procedure_requires_private_pre_shutdown_retention(self):
        procedure = (
            Path(__file__).parents[1] / "docs/qualification/pilot-synthetic-v1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("pilot-failure.json", procedure)
        self.assertIn("PILOT_SANITIZED_RECEIPT_RETENTION=FAIL", procedure)
        self.assertIn("Do not copy raw JSONL", procedure)
        self.assertIn("do not delay or skip Codespace shutdown", procedure)
        normalized = " ".join(procedure.split())
        self.assertIn("request ordinal `1` and attempt ordinal `1` as consumed", normalized)
        self.assertIn("distinct request and attempt identity", normalized)

    def test_consumed_identity_blocks_python_and_cli_before_side_effects(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as temporary:
            root = Path(temporary)
            for ordinal, acknowledged in ((1, False), (2, True)):
                run = root / f"fresh-{ordinal}"
                with patch(
                    "review_broker.pilot_synthetic.pilot_environment",
                ) as environment, patch(
                    "review_broker.pilot_synthetic.preflight_codex_runtime",
                ) as preflight, patch(
                    "review_broker.pilot_synthetic.invoke_once",
                ) as invoked:
                    with self.assertRaisesRegex(
                        PilotError, "PILOT_IDENTITY_ALREADY_CONSUMED",
                    ):
                        run_synthetic_pilot(
                            run,
                            acknowledge_unqualified_pilot=acknowledged,
                            broker_wheel_sha256="a" * 64,
                            environment={"GH_TOKEN": "must-not-be-read"},
                        )
                self.assertFalse(run.exists())
                environment.assert_not_called()
                preflight.assert_not_called()
                invoked.assert_not_called()

            cli_run = root / "cli-fresh"
            with patch(
                "review_broker.pilot_synthetic.pilot_environment",
            ) as environment, patch(
                "review_broker.pilot_synthetic.preflight_codex_runtime",
            ) as preflight, patch(
                "review_broker.pilot_synthetic.invoke_once",
            ) as invoked:
                result = main([
                    "pilot-synthetic", "--run-dir", str(cli_run),
                    "--broker-wheel-sha256", "a" * 64,
                    "--acknowledge-unqualified-pilot",
                ])
            self.assertEqual(result, 1)
            self.assertFalse(cli_run.exists())
            environment.assert_not_called()
            preflight.assert_not_called()
            invoked.assert_not_called()

    def test_fixed_request_and_attempt_ordinal_one_are_consumed(self):
        def failed(*_args, **_kwargs):
            raise InvocationError("CODEX_NONZERO_EXIT_UNCLASSIFIED")

        digest = hashlib.sha256(PILOT_SOURCE).hexdigest()
        expected_request = request_identity({
            "kind": "RB-PILOT-01", "fixture_sha256": digest, "ordinal": 1,
        })
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as temporary:
            run, _ = self._run(temporary, failed)
            armed = json.loads((run / "pilot-armed.json").read_text(encoding="utf-8"))
            receipt = json.loads((run / "pilot-failure.json").read_text(encoding="utf-8"))
            self.assertEqual(armed["request_id"], expected_request)
            self.assertEqual(armed["attempt_id"], attempt_identity(expected_request, 1))
            self.assertEqual(receipt["attempt_id"], armed["attempt_id"])
            self.assertNotEqual(armed["attempt_id"], attempt_identity(expected_request, 2))
            self.assertEqual(receipt["failure_observation"], "UNDETERMINED")


if __name__ == "__main__":
    unittest.main()
