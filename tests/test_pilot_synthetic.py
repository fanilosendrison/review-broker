"""Offline, no-inference tests for the explicit synthetic pilot."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.codex import InvocationError
from review_broker.packets import verify_packet
from review_broker.pilot_synthetic import (
    PILOT_SOURCE, PilotError, pilot_environment, pilot_fixture, run_synthetic_pilot,
)


class SyntheticPilotTests(unittest.TestCase):
    def test_acknowledgement_required_without_side_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "pilot"
            with self.assertRaisesRegex(PilotError, "PILOT_EXPLICIT_ACK_REQUIRED"):
                run_synthetic_pilot(run, acknowledge_unqualified_pilot=False,
                                    broker_wheel_sha256="a" * 64)
            self.assertFalse(run.exists())

    def test_parent_with_privileged_environment_rejected(self):
        with self.assertRaisesRegex(PilotError, "PILOT_PRIVILEGED_PARENT_ENVIRONMENT"):
            pilot_environment({"HOME": "/tmp/home", "PATH": "/bin", "GH_TOKEN": "synthetic"})
        with self.assertRaisesRegex(PilotError, "PILOT_NONSTANDARD_CODEX_HOME"):
            pilot_environment({"HOME": "/tmp/home", "PATH": "/bin", "CODEX_HOME": "/other"})

    def test_fixture_is_fixed_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = pilot_fixture(root)
            self.assertEqual(verify_packet(root / "evidence"), manifest)
            self.assertEqual((root / "evidence/sources/S001.bin").read_bytes(), PILOT_SOURCE)
            self.assertEqual(len(manifest["sources"]), 1)

    def _run(self, temp, invoke):
        root = Path(temp)
        home = root / "home"
        workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        env = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"),
               "PATH": "/usr/bin", "LANG": "C.UTF-8"}
        with patch("review_broker.pilot_synthetic.preflight_codex_runtime",
                   return_value={"cli_compatibility_verified": True}) as preflight, \
             patch("review_broker.pilot_synthetic.invoke_once", side_effect=invoke) as called:
            result = run_synthetic_pilot(
                root / "pilot",
                acknowledge_unqualified_pilot=True,
                broker_wheel_sha256="a" * 64,
                trusted_workspace=workspace,
                codex_runtime_root=root / "runtime",
                environment=env,
            )
        self.assertEqual(preflight.call_count, 1)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(called.call_args.kwargs["environment"]["HOME"], str(home))
        self.assertNotIn("GITHUB_TOKEN", called.call_args.kwargs["environment"])
        return root / "pilot", result

    @staticmethod
    def _synthetic_completed(evidence, *_args, **_kwargs):
        manifest = verify_packet(evidence)
        output = {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
            "packet_id": manifest["packet_id"],
            "verdict": "NO_GO",
            "sources_examined": ["S001"],
            "findings": [{
                "id": "F001",
                "category": "contradiction",
                "claim": "The eligible boundary incorrectly excludes age 18.",
                "consequence": "Applicants aged 18 are rejected despite the stated requirement.",
                "evidence": [{"source_id": "S001", "line": 3, "quote": "return age > 18"}],
            }],
            "remaining_uncertainties": [],
        }
        message = json.dumps(output)
        (evidence / "codex-final.json").write_text(message, encoding="utf-8")
        (evidence / "codex-events.jsonl").write_text("\n".join(json.dumps(event) for event in [
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
            {"type": "turn.completed"},
        ]) + "\n", encoding="utf-8")
        (evidence / "codex-exit-code.txt").write_text("0\n", encoding="ascii")

    def test_one_successful_mock_invocation_and_no_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            run, result = self._run(temp, self._synthetic_completed)
            self.assertEqual(result["pilot_functional"], "PASS")
            self.assertEqual(result["verdict"], "NO_GO")
            self.assertEqual(result["github_publication"], "NONE")
            self.assertFalse(result["pilot_security_qualified"])
            self.assertFalse(result["codespace_shutdown_observed"])
            self.assertEqual(result["end_to_end_pilot"], "PENDING_INDEPENDENT_SHUTDOWN_OBSERVATION")
            self.assertTrue((run / "pilot-armed.json").exists())
            self.assertEqual(json.loads((run / "pilot-summary.json").read_text()), result)
            with self.assertRaisesRegex(PilotError, "PILOT_FRESH_ABSOLUTE_RUN_DIR_REQUIRED"):
                run_synthetic_pilot(run, acknowledge_unqualified_pilot=True,
                                    broker_wheel_sha256="a" * 64,
                                    environment={"HOME": str(Path(temp) / "home"), "PATH": "/usr/bin"})

    def test_model_failure_consumes_attempt_without_retry(self):
        def unavailable(*_args, **_kwargs):
            raise InvocationError("MODEL_UNAVAILABLE")
        with tempfile.TemporaryDirectory() as temp:
            run, result = self._run(temp, unavailable)
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertEqual(result["failure"], "MODEL_UNAVAILABLE")
            self.assertTrue((run / "pilot-armed.json").exists())

    def test_contaminated_model_output_is_quarantined(self):
        def contaminated(evidence, *_args, **_kwargs):
            (evidence / "codex-final.json").write_text(
                "Bearer SYNTHETIC00000000000000000000", encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            run, result = self._run(temp, contaminated)
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertEqual(result["failure"], "PILOT_CREDENTIAL_OUTPUT_QUARANTINED")
            self.assertFalse((run / "evidence/codex-final.json").exists())
            self.assertTrue((run / "evidence/credential-incident.json").is_file())


if __name__ == "__main__":
    unittest.main()
