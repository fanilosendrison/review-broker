import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from review_broker.bounded_preflight import (
    RUNTIME_EVIDENCE_KEYS,
    build_bounded_preflight,
)
from review_broker.codex import InvocationError
from review_broker.identity import canonical_bytes
from review_broker.packets import PacketError, SourceRecord, build_packet
from review_broker.reviewer_profile import install_reviewer_profile
from review_broker.validation import validate_evidence
from tests.test_codex import verified_runtime
from tests.test_evidence import EvidenceValidationTests


class BoundedPreflightTests(unittest.TestCase):
    def preflight_fixture(self, root: Path, admission_mode="low-sensitivity-v1"):
        root = root.resolve()
        home, workspace, packet = root / "home", root / "workspace", root / "packet"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        packet.mkdir()
        source = b"bounded source\n"
        oid = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        manifest = build_packet(
            [SourceRecord.from_bytes("sample/repo", "a" * 40, "doc.md", oid, source)],
            request_id="request:sha256:" + "1" * 64,
            subject_id="subject:sha256:" + "2" * 64,
            mission_instruction="Review.",
            profile={"id": "code", "version": 1},
            output_directory=packet,
        )
        attempt_id = "attempt:sha256:" + "3" * 64
        broker_sha = "4" * 40
        metadata = {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "attempt_id": attempt_id,
            "admission_mode": admission_mode,
            "executing_broker_sha": broker_sha,
            "requester": "trusted",
            "subject_repository": "sample/repo",
            "admission_checks": (
                {
                    "requester_authorized": True,
                    "repository_authorized": True,
                    "bounded_private_request_admitted": True,
                    "private_repository_verified": True,
                    "private_source_credential_scope_verified": True,
                    "public_repository_verified": False,
                    "executing_sha_admitted": True,
                }
                if admission_mode == "bounded-private-v1" else
                {
                    "requester_authorized": True,
                    "repository_authorized": True,
                    "low_sensitivity_repository_admitted": True,
                    "public_repository_verified": True,
                    "executing_sha_admitted": True,
                }
            ),
        }
        resolved = {
            "schema_version": 1,
            "request_id": manifest["request_id"],
            "subject_id": manifest["subject_id"],
        }
        (packet / "broker-metadata.json").write_bytes(canonical_bytes(metadata) + b"\n")
        (packet / "resolved-request.json").write_bytes(canonical_bytes(resolved) + b"\n")
        schema = root / "schema.json"
        schema.write_text("{}", encoding="utf-8")
        install_reviewer_profile(home, workspace, packet)
        runtime = verified_runtime(root)
        receipt = build_bounded_preflight(
            packet,
            schema,
            attempt_id=attempt_id,
            expected_packet_id=manifest["packet_id"],
            broker_wheel_sha256="5" * 64,
            trusted_workspace=workspace,
            codex_runtime_root=root / "protected",
            executing_broker_sha=broker_sha,
            environment={"HOME": str(home), "PATH": "/trusted", "OPENAI_API_KEY": "synthetic"},
            runtime_verifier=lambda *_: runtime,
        )
        return packet, manifest, receipt

    def test_valid_receipt_binds_exact_verified_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, manifest, receipt = self.preflight_fixture(Path(temporary))
            self.assertEqual(receipt["request_id"], manifest["request_id"])
            self.assertEqual(receipt["assurance_scope"], "LOW_SENSITIVITY_V1")
            self.assertFalse(receipt["direct_sandbox_probe_executed"])
            self.assertFalse(receipt["comprehensive_isolation_qualified"])
            self.assertEqual(receipt["effective_codex_policy_attestation"], "UNAVAILABLE")
            self.assertIn("OPENAI_API_KEY", receipt["environment_keys_removed"])

    def test_private_receipt_is_mode_distinguished_and_never_claims_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, receipt = self.preflight_fixture(
                Path(temporary), admission_mode="bounded-private-v1"
            )
            self.assertEqual(receipt["evidence_type"], "bounded-private-v1-preflight")
            self.assertEqual(receipt["assurance_scope"], "BOUNDED_PRIVATE_V1")
            self.assertFalse(receipt["admission_checks"]["public_repository_verified"])
            forged = dict(receipt)
            forged["admission_mode"] = "low-sensitivity-v1"
            from review_broker.bounded_preflight import validate_bounded_preflight_receipt
            errors = validate_bounded_preflight_receipt(
                forged,
                request_id=receipt["request_id"], attempt_id=receipt["attempt_id"],
                packet_id=receipt["packet_id"], subject_id=receipt["subject_id"],
                executing_broker_sha=receipt["executing_broker_sha"],
                permission_profile=receipt["permission_profile"],
                permission_profile_sha256=receipt["permission_profile_sha256"],
                broker_wheel_sha256=receipt["broker_wheel_sha256"],
                runtime_evidence={key: receipt[key] for key in RUNTIME_EVIDENCE_KEYS},
                admission_mode="bounded-private-v1",
            )
            self.assertIn("BOUNDED_PREFLIGHT_FIELD_INVALID:admission_mode", errors)

    def test_packet_aliases_and_tampering_fail_before_preflight(self):
        for defect in ("symlink", "hardlink", "tamper"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                packet, _, _ = self.preflight_fixture(root)
                source = packet / "sources" / "S001.bin"
                if defect == "symlink":
                    original = source.read_bytes()
                    source.unlink()
                    target = root / "alias.bin"
                    target.write_bytes(original)
                    source.symlink_to(target)
                elif defect == "hardlink":
                    os.link(source, root / "alias.bin")
                else:
                    source.write_bytes(b"tampered\n")
                with self.assertRaises((InvocationError, PacketError)):
                    build_bounded_preflight(
                        packet,
                        root / "schema.json",
                        attempt_id="attempt:sha256:" + "3" * 64,
                        expected_packet_id=json.loads((packet / "input-manifest.json").read_text())["packet_id"],
                        broker_wheel_sha256="5" * 64,
                        trusted_workspace=root / "workspace",
                        codex_runtime_root=root / "protected",
                        executing_broker_sha="4" * 40,
                        environment={"HOME": str(root / "home"), "PATH": "/trusted"},
                        runtime_verifier=lambda *_: verified_runtime(root),
                    )


class BoundedEvidenceValidationTests(unittest.TestCase):
    def fixture(self, root: Path):
        manifest = EvidenceValidationTests().fixture(root, attempt_overrides={
            "model_requested": "gpt-5.6-sol",
            "reasoning_effort_requested": "xhigh",
            "shell_tool_requested": False,
            "effective_policy_attestation": "UNAVAILABLE",
            "api_key_fallback_forbidden": True,
            "environment_keys_removed": [],
            "argv": ["codex", "exec", "features.shell_tool=false"],
        })
        attempt = json.loads((root / "attempt.json").read_text())
        metadata = json.loads((root / "broker-metadata.json").read_text())
        metadata.update({"admission_mode": "low-sensitivity-v1", "executing_broker_sha": "7" * 40})
        (root / "broker-metadata.json").write_bytes(canonical_bytes(metadata) + b"\n")
        (root / "reviewer-security-probe.json").unlink()
        receipt = {
            "schema_version": 1,
            "evidence_type": "bounded-low-sensitivity-v1-preflight",
            "assurance_scope": "LOW_SENSITIVITY_V1",
            "admission_mode": "low-sensitivity-v1",
            "direct_sandbox_probe_executed": False,
            "comprehensive_isolation_qualified": False,
            "runtime_identity": "VERIFIED",
            "profile_identity": "VERIFIED",
            "packet_tree_integrity": "VERIFIED",
            "effective_codex_policy_attestation": "UNAVAILABLE",
            "request_id": manifest["request_id"],
            "attempt_id": attempt["attempt_id"],
            "packet_id": manifest["packet_id"],
            "subject_id": manifest["subject_id"],
            "executing_broker_sha": metadata["executing_broker_sha"],
            "permission_profile": attempt["permission_profile"],
            "permission_profile_sha256": attempt["permission_profile_sha256"],
            "broker_wheel_sha256": attempt["broker_wheel_sha256"],
            "shell_tool_requested": False,
            "model_requested": "gpt-5.6-sol",
            "reasoning_effort_requested": "xhigh",
            "api_key_fallback_forbidden": True,
            "model_substitution_forbidden": True,
            "reviewer_publication_authority": False,
            "trusted_admission": "VERIFIED_PRE_CLAIM",
            "admission_checks": {
                "requester_authorized": True,
                "repository_authorized": True,
                "low_sensitivity_repository_admitted": True,
                "public_repository_verified": True,
                "executing_sha_admitted": True,
            },
            "environment_keys_removed": [],
            **{key: attempt[key] for key in RUNTIME_EVIDENCE_KEYS},
        }
        (root / "bounded-v1-preflight.json").write_bytes(canonical_bytes(receipt) + b"\n")
        return manifest, receipt

    def test_valid_bounded_evidence_is_accepted_without_comprehensive_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _ = self.fixture(root)
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["evidence_status"], "VALID")
            self.assertEqual(result["assurance_scope"], "LOW_SENSITIVITY_V1")
            self.assertFalse(result["comprehensive_isolation_qualified"])

    def test_historical_public_receipt_without_admission_mode_remains_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, receipt = self.fixture(root)
            receipt.pop("admission_mode")
            (root / "bounded-v1-preflight.json").write_bytes(
                canonical_bytes(receipt) + b"\n"
            )
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["evidence_status"], "VALID")
            self.assertEqual(result["assurance_scope"], "LOW_SENSITIVITY_V1")

    def test_comprehensive_mode_still_requires_original_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = EvidenceValidationTests().fixture(root)
            (root / "reviewer-security-probe.json").unlink()
            result = validate_evidence(root, setup=manifest)
            self.assertEqual(result["evidence_status"], "INVALID")
            self.assertIn(
                "MISSING_EVIDENCE:reviewer-security-probe.json",
                result["validation_reasons"],
            )

    def test_workflow_selects_assurance_only_from_trusted_preparation_mode(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/review-request.yml"
        ).read_text(encoding="utf-8")
        bounded = workflow.index("name: Verify bounded low-sensitivity pre-arm evidence")
        comprehensive = workflow.index("name: Run comprehensive reviewer isolation probe")
        arm = workflow.index("name: Durably arm exactly one invocation")
        self.assertLess(bounded, arm)
        self.assertLess(comprehensive, arm)
        self.assertIn("steps.prepare.outputs.admission_mode == 'low-sensitivity-v1'", workflow)
        self.assertIn("steps.prepare.outputs.admission_mode == 'comprehensive-security'", workflow)
        self.assertEqual(workflow.count("internal-probe-reviewer-profile"), 1)
        self.assertEqual(workflow.count("internal-bounded-v1-preflight"), 1)

    def test_missing_forged_cross_mode_and_wrong_identities_are_rejected(self):
        mutations = {
            "missing": lambda root, receipt: (root / "bounded-v1-preflight.json").unlink(),
            "forged": lambda root, receipt: receipt.update({"direct_sandbox_probe_executed": True, "comprehensive_isolation_qualified": True}),
            "cross-mode": lambda root, receipt: (root / "reviewer-security-probe.json").write_text("{}"),
            "request": lambda root, receipt: receipt.update(request_id="request:sha256:" + "9" * 64),
            "attempt": lambda root, receipt: receipt.update(attempt_id="attempt:sha256:" + "9" * 64),
            "packet": lambda root, receipt: receipt.update(packet_id="packet:sha256:" + "9" * 64),
            "broker": lambda root, receipt: receipt.update(executing_broker_sha="9" * 40),
            "profile": lambda root, receipt: receipt.update(permission_profile_sha256="9" * 64),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest, receipt = self.fixture(root)
                mutate(root, receipt)
                if name not in {"missing", "cross-mode"}:
                    (root / "bounded-v1-preflight.json").write_bytes(canonical_bytes(receipt) + b"\n")
                result = validate_evidence(root, setup=manifest)
                self.assertEqual(result["evidence_status"], "INVALID")
                self.assertEqual(result["review_verdict"], "UNDETERMINED")


if __name__ == "__main__":
    unittest.main()
