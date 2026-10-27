"""Offline, no-inference tests for the explicit synthetic pilot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.codex import InvocationError
from review_broker.identity import canonical_bytes
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
    def _valid_output(manifest, *, claim="The eligible boundary incorrectly excludes age 18."):
        return {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
            "packet_id": manifest["packet_id"],
            "verdict": "NO_GO",
            "sources_examined": ["S001"],
            "findings": [{
                "id": "F001",
                "category": "contradiction",
                "claim": claim,
                "consequence": "Applicants aged 18 are rejected despite the stated requirement.",
                "evidence": [{"source_id": "S001", "line": 3, "quote": "return age > 18"}],
            }],
            "remaining_uncertainties": [],
        }

    @staticmethod
    def _write_completed_evidence(evidence, messages, final_message, *, post_terminal=()):
        events = [
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "turn.started"},
            *({"type": "item.completed",
               "item": {"type": "agent_message", "text": message}}
              for message in messages),
            {"type": "turn.completed"},
            *({"type": "item.completed",
               "item": {"type": "agent_message", "text": message}}
              for message in post_terminal),
        ]
        (evidence / "codex-final.json").write_text(final_message, encoding="utf-8")
        (evidence / "codex-events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
        )
        (evidence / "codex-exit-code.txt").write_text("0\n", encoding="ascii")

    @classmethod
    def _synthetic_completed(cls, evidence, *_args, **_kwargs):
        manifest = verify_packet(evidence)
        message = json.dumps(cls._valid_output(manifest))
        cls._write_completed_evidence(evidence, [message], message)

    def _assert_post_invocation_mutation_rejected(self, temp, mutate):
        def completed_then_mutated(evidence, *_args, **_kwargs):
            self._synthetic_completed(evidence)
            mutate(evidence)

        run, result = self._run(temp, completed_then_mutated)
        self.assertEqual(result["pilot_functional"], "FAIL")
        self.assertEqual(result["failure"], "PILOT_POST_INVOCATION_PACKET_INVALID")
        self.assertTrue((run / "pilot-armed.json").is_file())

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

    def test_post_invocation_source_mutation_fails_closed(self):
        def mutate(evidence):
            source = evidence / "sources/S001.bin"
            source.write_bytes(source.read_bytes() + b"# changed after invocation\n")
        with tempfile.TemporaryDirectory() as temp:
            self._assert_post_invocation_mutation_rejected(temp, mutate)

    def test_post_invocation_manifest_mutation_fails_closed(self):
        def mutate(evidence):
            manifest_path = evidence / "input-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["post_invocation_extra"] = "changed"
            manifest_path.write_bytes(canonical_bytes(manifest) + b"\n")
        with tempfile.TemporaryDirectory() as temp:
            self._assert_post_invocation_mutation_rejected(temp, mutate)

    def test_post_invocation_prompt_mutation_fails_closed(self):
        def mutate(evidence):
            prompt = evidence / "input.txt"
            prompt.write_bytes(prompt.read_bytes() + b"changed after invocation\n")
        with tempfile.TemporaryDirectory() as temp:
            self._assert_post_invocation_mutation_rejected(temp, mutate)

    def test_post_invocation_input_symlink_fails_closed(self):
        def completed_then_aliased(evidence, *_args, **_kwargs):
            self._synthetic_completed(evidence)
            prompt = evidence / "input.txt"
            target = evidence.parent / "prompt-alias-target"
            target.write_bytes(prompt.read_bytes())
            prompt.unlink()
            prompt.symlink_to(target)
        with tempfile.TemporaryDirectory() as temp:
            run, result = self._run(temp, completed_then_aliased)
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertEqual(result["failure"], "PILOT_CREDENTIAL_OUTPUT_QUARANTINED")
            self.assertTrue((run / "pilot-armed.json").is_file())

    def test_post_invocation_input_hard_link_fails_closed(self):
        def mutate(evidence):
            prompt = evidence / "input.txt"
            target = evidence.parent / "prompt-hard-link-target"
            target.write_bytes(prompt.read_bytes())
            prompt.unlink()
            os.link(target, prompt)
        with tempfile.TemporaryDirectory() as temp:
            self._assert_post_invocation_mutation_rejected(temp, mutate)

    def test_post_invocation_unexpected_path_fails_closed(self):
        def mutate(evidence):
            (evidence / "unexpected.txt").write_text("unexpected", encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            self._assert_post_invocation_mutation_rejected(temp, mutate)

    def test_intermediate_agent_message_cannot_be_final(self):
        def intermediate_final(evidence, *_args, **_kwargs):
            manifest = verify_packet(evidence)
            first = json.dumps(self._valid_output(manifest))
            second = json.dumps(self._valid_output(manifest, claim="Later valid response."))
            self._write_completed_evidence(evidence, [first, second], first)
        with tempfile.TemporaryDirectory() as temp:
            _, result = self._run(temp, intermediate_final)
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertIn("PILOT_FINAL_MESSAGE_MISMATCH", result["validation_reasons"])

    def test_agent_message_after_terminal_fails_closed(self):
        def post_terminal(evidence, *_args, **_kwargs):
            manifest = verify_packet(evidence)
            first = json.dumps(self._valid_output(manifest))
            second = json.dumps(self._valid_output(manifest, claim="Post-terminal response."))
            self._write_completed_evidence(evidence, [first], first, post_terminal=[second])
        with tempfile.TemporaryDirectory() as temp:
            _, result = self._run(temp, post_terminal)
            self.assertEqual(result["pilot_functional"], "FAIL")
            self.assertIn("PILOT_TERMINAL_EVENTS_INVALID", result["validation_reasons"])

    def test_last_agent_message_matching_final_passes(self):
        def matching_last(evidence, *_args, **_kwargs):
            manifest = verify_packet(evidence)
            first = json.dumps(self._valid_output(manifest, claim="Earlier valid response."))
            last = json.dumps(self._valid_output(manifest))
            self._write_completed_evidence(evidence, [first, last], last)
        with tempfile.TemporaryDirectory() as temp:
            _, result = self._run(temp, matching_last)
            self.assertEqual(result["pilot_functional"], "PASS")

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
