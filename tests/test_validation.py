"""Ordered Codex event-sequence regressions for production evidence validation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from review_broker.evidence import TERMINAL_CAPTURE_FILES, build_terminal_capture_receipt
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.validation import validate_evidence
from tests import test_evidence


class EventSequenceValidationTests(unittest.TestCase):
    ATTEMPT_ID = "attempt:sha256:" + "3" * 64
    CONTEXT = {"workflow_run_id": "123", "workflow_run_attempt": "1"}

    def _fixture(self, root: Path):
        return test_evidence.EvidenceValidationTests().fixture(root)

    def _rewrite_terminal_evidence(
        self,
        root: Path,
        manifest: dict,
        messages_before_terminal: list[str],
        final_message: str,
        *,
        messages_after_terminal: list[str] | None = None,
    ) -> None:
        events = [
            {"type": "turn.started"},
            *({"type": "item.completed",
               "item": {"type": "agent_message", "text": message}}
              for message in messages_before_terminal),
            {"type": "turn.completed"},
            *({"type": "item.completed",
               "item": {"type": "agent_message", "text": message}}
              for message in messages_after_terminal or []),
        ]
        (root / "codex-events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
        )
        (root / "codex-final.json").write_text(final_message, encoding="utf-8")
        recovery = json.loads((root / "recovery-manifest.json").read_text(encoding="utf-8"))
        for name in TERMINAL_CAPTURE_FILES:
            data = (root / name).read_bytes()
            recovery["artifacts"][name] = {
                "recovered": True,
                "artifact_id": artifact_identity(data),
                "byte_length": len(data),
            }
        (root / "recovery-manifest.json").write_bytes(canonical_bytes(recovery))
        receipt = build_terminal_capture_receipt(
            root,
            request_id=manifest["request_id"],
            attempt_id=self.ATTEMPT_ID,
            packet_id=manifest["packet_id"],
            context=self.CONTEXT,
            observed_at="2026-10-26T00:00:01+00:00",
        )
        (root / "terminal-capture.json").write_bytes(canonical_bytes(receipt) + b"\n")

    @staticmethod
    def _different_valid_message(first_message: str) -> str:
        response = json.loads(first_message)
        response["remaining_uncertainties"] = ["Later response differs."]
        return json.dumps(response, separators=(",", ":"))

    def test_intermediate_agent_message_cannot_be_final(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._fixture(root)
            first = (root / "codex-final.json").read_text(encoding="utf-8")
            last = self._different_valid_message(first)
            self._rewrite_terminal_evidence(root, manifest, [first, last], first)

            result = validate_evidence(root, setup=manifest)

            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")
            self.assertIn("FINAL_MESSAGE_EVENT_MISMATCH", result["validation_reasons"])

    def test_agent_message_after_terminal_is_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._fixture(root)
            first = (root / "codex-final.json").read_text(encoding="utf-8")
            later = self._different_valid_message(first)
            self._rewrite_terminal_evidence(
                root, manifest, [first], first, messages_after_terminal=[later]
            )

            result = validate_evidence(root, setup=manifest)

            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")
            self.assertIn("TERMINAL_EVENT_SEQUENCE_INVALID", result["validation_reasons"])

    def test_final_matching_last_agent_message_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._fixture(root)
            first = (root / "codex-final.json").read_text(encoding="utf-8")
            last = self._different_valid_message(first)
            self._rewrite_terminal_evidence(root, manifest, [first, last], last)

            result = validate_evidence(root, setup=manifest)

            self.assertEqual(result["execution_status"], "COMPLETED")
            self.assertEqual(result["evidence_status"], "VALID")
            self.assertEqual(result["review_verdict"], "GO")


if __name__ == "__main__":
    unittest.main()
