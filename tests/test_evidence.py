import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from review_broker.evidence import REQUIRED_EVIDENCE_FILES, evidence_manifest, scan_for_credentials
from review_broker.identity import canonical_bytes
from review_broker.packets import SourceRecord, build_packet
from review_broker.validation import validate_evidence


class EvidenceValidationTests(unittest.TestCase):
    def fixture(self, root: Path, *, quote="alpha", terminal=True, failure=False):
        source = b"alpha line\r\nbeta line\r\n"
        oid = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        record = SourceRecord.from_bytes("sample/repo", "a" * 40, "doc.md", oid, source)
        manifest = build_packet(
            [record],
            request_id="request:sha256:" + "1" * 64,
            subject_id="subject:sha256:" + "2" * 64,
            mission_instruction="Find falsifiers.",
            profile={"id": "publication", "version": 1},
            output_directory=root,
        )
        final = {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
            "packet_id": manifest["packet_id"],
            "verdict": "GO",
            "sources_examined": ["S001"],
            "findings": [{
                "id": "F001", "category": "evidence-gap",
                "claim": "A conclusion that the validator cannot semantically adjudicate.",
                "consequence": "Consumer review remains required.",
                "evidence": [{"source_id": "S001", "line": 1, "quote": quote}],
            }],
            "remaining_uncertainties": ["Semantic correctness is not machine-validated."],
        }
        final_text = json.dumps(final, separators=(",", ":"))
        events = [{"type": "turn.started"}]
        if failure:
            events.append({"type": "turn.failed", "error": {"message": "failed"}})
        else:
            events.append({"type": "item.completed", "item": {"type": "agent_message", "text": final_text}})
            if terminal:
                events.append({"type": "turn.completed"})
        (root / "attempt.json").write_bytes(canonical_bytes({"attempt_id": "attempt:sha256:" + "3" * 64}))
        (root / "prompt.sha256").write_text(manifest["prompt_sha256"] + "\n")
        (root / "codex-events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        (root / "codex-stderr.txt").write_text("")
        (root / "codex-final.json").write_text(final_text)
        (root / "codex-exit-code.txt").write_text("0\n")
        for name in ("input-before.sha256", "input-after.sha256"):
            (root / name).write_text(manifest["prompt_sha256"] + "\n")
        return manifest

    def test_valid_citations_do_not_validate_conclusions(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = validate_evidence(Path(temporary), setup=self.fixture(Path(temporary)))
            self.assertEqual(result["execution_status"], "COMPLETED")
            self.assertEqual(result["evidence_status"], "VALID")
            self.assertEqual(result["review_verdict"], "GO")
            self.assertFalse(result["semantic_correctness_validated"])

    def test_incorrect_citation_is_invalid_not_no_go(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = validate_evidence(root, setup=self.fixture(root, quote="fabricated"))
            self.assertEqual(result["execution_status"], "COMPLETED")
            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")

    def test_fabricated_source_line_is_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            final = json.loads((root / "codex-final.json").read_text())
            final["findings"][0]["evidence"][0]["line"] = 99
            text = json.dumps(final, separators=(",", ":"))
            (root / "codex-final.json").write_text(text)
            events = [json.loads(x) for x in (root / "codex-events.jsonl").read_text().splitlines()]
            events[1]["item"]["text"] = text
            (root / "codex-events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["evidence_status"], "INVALID")

    def test_lost_terminal_response_is_indeterminate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = validate_evidence(root, setup=self.fixture(root, terminal=False))
            self.assertEqual(result["execution_status"], "INDETERMINATE")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")

    def test_jsonl_failure_event_is_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = validate_evidence(root, setup=self.fixture(root, failure=True))
            self.assertEqual(result["execution_status"], "FAILED")
            self.assertEqual(result["evidence_status"], "INVALID")

    def test_missing_evidence_remains_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / "codex-final.json").unlink()
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["execution_status"], "INDETERMINATE")
            self.assertEqual(result["evidence_status"], "INVALID")

    def test_evidence_manifest_binds_every_required_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            manifest = evidence_manifest(root)
            self.assertTrue(set(REQUIRED_EVIDENCE_FILES) <= set(manifest))

    def test_credential_material_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            credential_key = "access_" + "token"
            (root / "codex-stderr.txt").write_text(
                json.dumps({credential_key: "placeholder-value"})
            )
            self.assertEqual(scan_for_credentials(root), ["codex-stderr.txt"])


if __name__ == "__main__":
    unittest.main()
