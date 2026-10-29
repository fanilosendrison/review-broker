import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from review_broker.evidence import (
    EvidenceCaptureError,
    REQUIRED_EVIDENCE_FILES,
    TERMINAL_CAPTURE_FILES,
    build_terminal_capture_receipt,
    evidence_manifest,
    scan_for_credentials,
    quarantine_contaminated_evidence,
)
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.packets import SourceRecord, build_packet
from review_broker.publication import PublicationError, build_review_result
from review_broker.validation import validate_evidence


class EvidenceValidationTests(unittest.TestCase):
    def fixture(self, root: Path, *, quote="alpha", terminal=True, failure=False,
                claim="A conclusion that the validator cannot semantically adjudicate.",
                uncertainty="Semantic correctness is not machine-validated.", attempt_overrides=None):
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
                "claim": claim,
                "consequence": "Consumer review remains required.",
                "evidence": [{"source_id": "S001", "line": 1, "quote": quote}],
            }],
            "remaining_uncertainties": [uncertainty],
        }
        final_text = json.dumps(final, separators=(",", ":"))
        events = [{"type": "turn.started"}]
        if failure:
            events.append({"type": "turn.failed", "error": {"message": "failed"}})
        else:
            events.append({"type": "item.completed", "item": {"type": "agent_message", "text": final_text}})
            if terminal:
                events.append({"type": "turn.completed"})
        profile_sha256 = "4" * 64
        (root / "broker-metadata.json").write_bytes(canonical_bytes({
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "attempt_id": "attempt:sha256:" + "3" * 64,
            "admission_mode": "comprehensive-security",
            "executing_broker_sha": "7" * 40,
        }) + b"\n")
        (root / "attempt.json").write_bytes(canonical_bytes({
            "attempt_id": "attempt:sha256:" + "3" * 64,
            "broker_wheel_sha256": "6" * 64,
            "runtime_identity_verification": "VERIFIED_OFFICIAL_NPM_ARTIFACT",
            "distribution": "@openai/codex",
            "distribution_version": "0.164.0",
            "platform_alias": "@openai/codex-linux-x64",
            "platform_version": "0.164.0-linux-x64",
            "codex_launcher_sha256": "61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70",
            "codex_native_sha256": "b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306",
            "root_dist_integrity": "sha512-TWj7UGyPRe3Pj/A3ddNAxs1te3a/W/xAd+J0LHrrFTmsSfahGMOLF/vn88D3QCIgAT3B1rm1y/Z3NYE0rx6cZQ==",
            "platform_dist_integrity": "sha512-XLAoaWsGOT2khzl+P4FYDPTkzAr9W0VFXFaVkqlFdkM0soa1gH/4S0wSD57Ek3HHwkirAEGz2/Mwehseh+l5Mg==",
            "node_interpreter_used": False,
            "execution_stability": "ROOT_OWNED_NON_WRITABLE_PACKAGE_LAYOUT",
            "protected_runtime_root": "/var/lib/review-broker/codex-0.164.0-linux-x64",
            "execution_native": "/var/lib/review-broker/codex-0.164.0-linux-x64/bin/codex",
            "permission_profile": "review-broker-" + "0" * 64,
            "permission_profile_sha256": profile_sha256,
            "credential_paths_denied": True,
            "trusted_workspace_denied": True,
            "network_access": False, **(attempt_overrides or {}),
        }) + b"\n")
        security_observations = {
            "packet_canary_readable": True,
            "auth_parent_canary_readable": False,
            "trusted_workspace_readable": False,
            "packet_directory_writable": False,
            "unauthorized_network_connect": False,
            "sensitive_environment_visible": False,
            "process_canary_visible": False,
            "outside_packet_canary_readable": False,
            "symlink_to_auth_parent_canary_readable": False,
            "hardlink_to_auth_parent_canary_readable": False,
            "hardlink_created": True,
        }
        (root / "reviewer-security-probe.json").write_bytes(canonical_bytes({
            "qualified": True,
            "permission_profile": "review-broker-" + "0" * 64,
            "permission_profile_sha256": profile_sha256,
            "mismatches": [],
            "observations": security_observations,
        }))
        (root / "prompt.sha256").write_text(manifest["prompt_sha256"] + "\n")
        (root / "codex-events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        (root / "codex-stderr.txt").write_text("")
        (root / "codex-final.json").write_text(final_text)
        (root / "codex-exit-code.txt").write_text("1\n" if failure else "0\n")
        for name in ("input-before.sha256", "input-after.sha256"):
            (root / name).write_text(manifest["prompt_sha256"] + "\n")
        recovered = {}
        for name in TERMINAL_CAPTURE_FILES:
            data = (root / name).read_bytes()
            recovered[name] = {
                "recovered": True,
                "artifact_id": artifact_identity(data),
                "byte_length": len(data),
            }
        context = {"workflow_run_id": "123", "workflow_run_attempt": "1"}
        (root / "recovery-manifest.json").write_bytes(canonical_bytes({
            "schema_version": 1,
            "evidence_type": "runtime-evidence-recovery",
            "codespace_name": "review-broker-safe",
            "remote_directory": "/tmp/evidence",
            "request_id": manifest["request_id"],
            "attempt_id": "attempt:sha256:" + "3" * 64,
            "observed_at": "2026-10-26T00:00:00+00:00",
            "context": context,
            "artifacts": recovered,
            "complete": True,
        }))
        if terminal or failure:
            receipt = build_terminal_capture_receipt(
                root,
                request_id=manifest["request_id"],
                attempt_id="attempt:sha256:" + "3" * 64,
                packet_id=manifest["packet_id"],
                context=context,
                observed_at="2026-10-26T00:00:01+00:00",
            )
            (root / "terminal-capture.json").write_bytes(
                canonical_bytes(receipt) + b"\n"
            )
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

    def test_complete_terminal_artifacts_produce_bound_capture_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            receipt = build_terminal_capture_receipt(
                root,
                request_id=manifest["request_id"],
                attempt_id="attempt:sha256:" + "3" * 64,
                packet_id=manifest["packet_id"],
                context={"workflow_run_id": "123", "workflow_run_attempt": "1"},
            )
            self.assertEqual(receipt["terminal_event"], "turn.completed")
            self.assertEqual(
                receipt["artifacts"]["codex-events.jsonl"]["sha256"],
                hashlib.sha256((root / "codex-events.jsonl").read_bytes()).hexdigest(),
            )

    def test_missing_terminal_artifact_cannot_be_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / "codex-final.json").unlink()
            with self.assertRaisesRegex(EvidenceCaptureError, "TERMINAL_ARTIFACT_MISSING"):
                build_terminal_capture_receipt(
                    root,
                    request_id=manifest["request_id"],
                    attempt_id="attempt:sha256:" + "3" * 64,
                    packet_id=manifest["packet_id"],
                    context={},
                )

    def test_truncated_terminal_event_stream_cannot_be_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / "codex-events.jsonl").write_text('{"type":"turn.started"}\n{"type":')
            with self.assertRaisesRegex(EvidenceCaptureError, "TERMINAL_EVENTS_JSON_INVALID"):
                build_terminal_capture_receipt(
                    root,
                    request_id=manifest["request_id"],
                    attempt_id="attempt:sha256:" + "3" * 64,
                    packet_id=manifest["packet_id"],
                    context={},
                )

    def test_malformed_terminal_event_stream_cannot_be_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / "codex-events.jsonl").write_text('{"not_type":"turn.started"}\n')
            with self.assertRaisesRegex(EvidenceCaptureError, "TERMINAL_EVENT_INVALID"):
                build_terminal_capture_receipt(
                    root,
                    request_id=manifest["request_id"],
                    attempt_id="attempt:sha256:" + "3" * 64,
                    packet_id=manifest["packet_id"],
                    context={},
                )

    def test_contradictory_terminal_events_cannot_be_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            with (root / "codex-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write('{"type":"turn.failed"}\n')
            with self.assertRaisesRegex(EvidenceCaptureError, "TERMINAL_EVENT_SEQUENCE_INVALID"):
                build_terminal_capture_receipt(
                    root,
                    request_id=manifest["request_id"],
                    attempt_id="attempt:sha256:" + "3" * 64,
                    packet_id=manifest["packet_id"],
                    context={},
                )

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

    def test_security_probe_must_bind_the_exact_permission_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            receipt = json.loads((root / "reviewer-security-probe.json").read_text())
            receipt["permission_profile_sha256"] = "5" * 64
            (root / "reviewer-security-probe.json").write_text(json.dumps(receipt))
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertIn(
                "SECURITY_PROBE_PROFILE_SHA256_MISMATCH",
                result["validation_reasons"],
            )

    def test_evidence_manifest_binds_every_required_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            manifest = evidence_manifest(root)
            self.assertTrue(set(REQUIRED_EVIDENCE_FILES) <= set(manifest))

    def test_contaminated_reviewer_claim_is_not_retained_in_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canary = "sk-" + "A" * 24  # Synthetic token-shaped data, never a credential.
            result = validate_evidence(root, setup=self.fixture(root, claim=canary))
            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")
            self.assertNotIn(canary, (root / "validation.json").read_text())
            self.assertEqual(result["findings"], [])

    def test_contaminated_uncertainty_is_not_retained_in_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canary = "sk-" + "B" * 24
            result = validate_evidence(root, setup=self.fixture(root, uncertainty=canary))
            self.assertNotIn(canary, (root / "validation.json").read_text())
            self.assertEqual(result["remaining_uncertainties"], [])

    def test_contaminated_diagnostic_is_not_retained_in_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            canary = "sk-" + "F" * 24
            (root / "codex-exit-code.txt").write_text(canary + "\n")
            result = validate_evidence(root)
            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertEqual(result["review_verdict"], "UNDETERMINED")
            self.assertNotIn(canary, (root / "validation.json").read_text())
            self.assertTrue(all(entry["sha256"] is None
                                for entry in result["artifact_inventory"].values()))

    def test_contaminated_jsonl_is_reduced_to_non_secret_upload_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            self.fixture(root)
            canary = "sk-" + "C" * 24
            with (root / "codex-events.jsonl").open("a", encoding="utf-8") as events:
                events.write(json.dumps({"type": "item.completed", "item": {"text": canary}}) + "\n")
            outcome = quarantine_contaminated_evidence(
                root, request_id="request:sha256:" + "1" * 64,
                attempt_id="attempt:sha256:" + "3" * 64,
            )
            self.assertEqual(outcome, {"contaminated": True})
            self.assertEqual({path.name for path in root.iterdir()},
                             {"credential-incident.json", "recovery-manifest.json"})
            self.assertNotIn(canary, "".join(path.read_text() for path in root.iterdir()))
            self.assertFalse(json.loads((root / "credential-incident.json").read_text())[
                "raw_runner_evidence_retained"])
            validation = validate_evidence(root)
            self.assertIn("CREDENTIAL_MATERIAL_DETECTED_QUARANTINED",
                          validation["validation_reasons"])
            self.assertEqual(validation["review_verdict"], "UNDETERMINED")
            with self.assertRaisesRegex(PublicationError, "CONTAMINATED"):
                build_review_result({}, {}, {}, validation, current_head=None)

    def test_contaminated_validation_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root, claim="sk-" + "D" * 24)
            validation = validate_evidence(root)
            with self.assertRaisesRegex(PublicationError, "CONTAMINATED"):
                build_review_result(
                    {"request_id": manifest["request_id"],
                     "subject_id": manifest["subject_id"],
                     "policy_id": "policy:sha256:" + "4" * 64,
                     "subject": {"head_commit": "a" * 40}},
                    manifest,
                    {"attempt_id": "attempt:sha256:" + "3" * 64,
                     "model_requested": "gpt-5.6-sol",
                     "reasoning_effort_requested": "xhigh"},
                    validation, current_head="a" * 40,
                )

    def test_actions_qualification_workflow_has_no_write_or_codespace_credential(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
                    "qualify-quarantine.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("codespace", workflow.lower())
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("synthetic-negative-", workflow)
        self.assertIn("synthetic-clean-", workflow)

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
