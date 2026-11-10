"""Offline INT03: real candidate components, injected external authorities only."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_broker.admission_v3 import AdmissionV3CandidateError
from review_broker.github_journal_v3 import GitHubJournalV3Error
from review_broker.github_journal_transport_v3 import CreateRefStatusV3, OutcomeStatusV3
from review_broker.github_source_authority_v3 import GitHubSourceAuthorityV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.packet_preparation_authority_v3 import (
    RetainedPacketAuthorityV3, prepare_packet_receipt_v3, verify_prepared_readback_v3,
)
from review_broker.packet_retention_v3 import (
    PacketRetentionV3Error, load_packet_evidence_v3, packet_retention_locator_v3,
    persist_packet_evidence_v3,
)
from review_broker.packet_v2 import (
    PacketV2CandidateError, build_packet_v2_candidate, subject_capture_evidence_id_v2,
    verify_packet_v2_candidate,
)
from tests.issue68_test_support import TECHNICAL_POLICY_ID
from tests.issue69_test_support import source_authority
from tests.issue70_test_support import AuthenticatedScenario
from tests.packet_v2_test_support import admitted, git_capture, inline, profile, request_for_capture
from tests.test_github_git_file_v3 import Api as GitApi, reader as git_reader


class Issue70CompositionTests(unittest.TestCase):
    def scenario(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return AuthenticatedScenario(Path(temporary.name))

    def persisted(self):
        scenario = self.scenario()
        scenario.admitted_snapshot = scenario.through_admitted()
        scenario.retention_base = scenario.root / "retained"
        scenario.retention = packet_retention_locator_v3(
            scenario.retention_base, scenario.admitted_snapshot.claim_ref)
        scenario.manifest = persist_packet_evidence_v3(
            scenario.admission, scenario.capture, profile(), scenario.retention_base,
            scenario.admitted_snapshot, scenario.journal, scenario.issue_readers)
        return scenario

    def test_I70_N01_shared_authority_and_four_reference_prepared(self):
        scenario = self.scenario().complete()
        self.assertIs(type(scenario.source), GitHubSourceAuthorityV3)
        authorization = scenario.source.authorize(scenario.capture.repository, scenario.capture.repository_id)
        self.assertEqual(scenario.admission.source_scope_evidence_id, scenario.source.scope_observation.evidence_id)
        self.assertEqual(scenario.capture.source_authorization_evidence_id, authorization.evidence_id)
        self.assertNotEqual(authorization.evidence_id, scenario.source.scope_observation.evidence_id)
        observed = scenario.pr_reader.observe(scenario.capture.repository, scenario.capture.repository_id,
                                             scenario.capture.pull_request)
        self.assertEqual(scenario.capture.pr_observation_evidence_id, observed.evidence_id)
        for reader in [*scenario.git_readers.values(), *scenario.issue_readers.values(), scenario.pr_reader]:
            self.assertIs(reader.source_authority, scenario.source)
        for observation in (*scenario.admission.git_file_observations, *scenario.admission.issue_reference_observations):
            self.assertEqual(observation.authority_evidence_id, authorization.evidence_id)
        self.assertEqual({item["source_kind"] for item in scenario.manifest["reference_sources"]},
                         {"inline", "git_file", "github_issue_body", "github_issue_comment"})
        self.assertEqual([item["status"] for item in scenario.manifest["reference_outcomes"]], ["captured"] * 4)
        self.assertEqual(scenario.manifest["technical_policy"]["qualification"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(scenario.prepared.record.attempt.state.value, "PREPARED")
        self.assertEqual(scenario.prepared.parent_sha, scenario.admitted_snapshot.commit_sha)
        self.assertEqual(scenario.prepared.record.attempt.invocation_count, 0)
        self.assertEqual(scenario.dispatches, 1)  # Local counter, not an Actions dispatch.
        self.assertEqual([item["operation"] for item in scenario.history],
                         ["claim", "reserve_initial", "register_worker", "record_admission", "prepare"])
        self.assertEqual(scenario.prepared.record.attempt.evidence_ids[-1], scenario.packet_evidence_id)
        self.assertEqual(verify_prepared_readback_v3(scenario.retention_base, scenario.prepared), scenario.verified)
        for path in [scenario.retention, *scenario.retention.rglob("*")]:
            self.assertFalse(path.is_symlink())
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)

    def test_I70_N02_cold_interpreter_preserves_all_authority_ids(self):
        scenario = self.scenario().complete()
        transport_path = scenario.root / "transport.json"
        scenario.save_transport(transport_path)
        # Destroy the acquisition checkout; cold verification has retained bytes only.
        shutil.rmtree(scenario.capture.repository_root)
        cwd = scenario.root / "empty-cwd"
        cwd.mkdir()
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "tests.issue70_test_support", str(scenario.retention_base),
             str(transport_path), scenario.admission.request_id], cwd=cwd,
            env={"PATH": os.defpath, "PYTHONPATH": str(project), "PYTHONNOUSERSITE": "1"},
            capture_output=True, text=True, timeout=90, check=True,
        )
        cold = json.loads(result.stdout)
        self.assertEqual(cold["packet_id"], scenario.manifest["packet_id"])
        self.assertEqual(cold["packet_evidence_id"], scenario.packet_evidence_id)
        self.assertEqual(cold["source_scope_evidence_id"], scenario.admission.source_scope_evidence_id)
        self.assertEqual(cold["source_authorization_evidence_id"], scenario.capture.source_authorization_evidence_id)
        self.assertEqual(cold["pr_observation_evidence_id"], scenario.capture.pr_observation_evidence_id)
        self.assertEqual(cold["capture_qualification"], "AUTHENTICATED_SOURCE_READ_ONLY")

    def test_I70_F01_distinct_authority_realms_are_not_substitutable(self):
        scenario = self.scenario()
        other = source_authority(installation_id=124)
        self.assertNotEqual(other.scope_observation.evidence_id, scenario.source.scope_observation.evidence_id)
        reader = git_reader(GitApi(), other)
        with self.assertRaisesRegex(AdmissionV3CandidateError, "^GIT_FILE_SOURCE_AUTHORITY_MISMATCH$"):
            admitted(scenario.request, capture=scenario.capture, source_authority_override=scenario.source,
                     git_file_readers={"contract": reader}, issue_reference_readers=scenario.issue_readers)
        self.assertEqual(scenario.transport.updates, [])
        self.assertEqual(scenario.transport.refs, {})

    def test_I70_F02_synthetic_capture_cannot_use_authenticated_scope(self):
        scenario = self.scenario()
        synthetic = replace(scenario.capture, verification="SYNTHETIC_OFFLINE_VERIFIED",
                            source_authorization_evidence_id=None, pr_observation_evidence_id=None)
        synthetic = replace(synthetic, evidence_id=subject_capture_evidence_id_v2(synthetic))
        with self.assertRaisesRegex(PacketV2CandidateError, "^PACKET_V2_SYNTHETIC_CAPTURE_AUTHORITY_FORBIDDEN$"):
            build_packet_v2_candidate(scenario.admission, synthetic, profile(), scenario.root / "bad")

    def test_I70_F03_authenticated_admission_requires_bound_scope(self):
        scenario = self.persisted()
        for value in (None, scenario.capture.source_authorization_evidence_id):
            admission = dict(scenario.journal_admission)
            if value is None:
                del admission["source_app_scope_evidence_id"]
            else:
                admission["source_app_scope_evidence_id"] = value
            with self.subTest(scope=value), self.assertRaisesRegex(
                    AdmissionV3CandidateError, "^JOURNAL_ADMISSION_SOURCE_SCOPE_MISMATCH$"):
                load_packet_evidence_v3(scenario.retention, admission)

    def test_I70_F04_cold_authority_tampering_is_rejected(self):
        scenario = self.persisted()
        manifest_path = scenario.retention / "packet/input-manifest.json"
        original = manifest_path.read_bytes()
        for field in ("source_authorization_evidence_id", "pr_observation_evidence_id"):
            for value in (None, True, "invalid", "artifact:sha256:" + "f" * 64,
                          scenario.source.scope_observation.evidence_id):
                with self.subTest(field=field, value=value):
                    value_manifest = json.loads(original)
                    value_manifest["subject"][field] = value
                    manifest_path.write_bytes(canonical_bytes(value_manifest) + b"\n")
                    marker = ("RETAINED_SUBJECT_AUTHORITY_INVALID" if value in (None, True, "invalid")
                              else "PACKET_V2_AUTHENTICATED_CAPTURE_AUTHORITY_MISMATCH")
                    with self.assertRaisesRegex(PacketRetentionV3Error, "^" + marker + "$"):
                        load_packet_evidence_v3(scenario.retention, scenario.journal_admission)
        manifest_path.write_bytes(original)
        load_packet_evidence_v3(scenario.retention, scenario.journal_admission)

    def test_I70_F05_cold_qualification_cannot_be_promoted_or_downgraded(self):
        scenario = self.persisted()
        path = scenario.retention / "packet/input-manifest.json"
        original = path.read_bytes()
        cases = [("UNKNOWN", False, "RETAINED_SUBJECT_QUALIFICATION_INVALID"),
                 ("SYNTHETIC_OFFLINE_VERIFIED", False, "RETAINED_SYNTHETIC_AUTHORITY_FORBIDDEN"),
                 ("SYNTHETIC_OFFLINE_VERIFIED", True, "PACKET_V2_SYNTHETIC_CAPTURE_AUTHORITY_FORBIDDEN")]
        for qualification, remove, marker in cases:
            with self.subTest(qualification=qualification, remove=remove):
                manifest = json.loads(original)
                manifest["subject"]["capture_qualification"] = qualification
                if remove:
                    for field in ("source_authorization_evidence_id", "pr_observation_evidence_id"):
                        del manifest["subject"][field]
                path.write_bytes(canonical_bytes(manifest) + b"\n")
                with self.assertRaisesRegex(PacketRetentionV3Error, "^" + marker + "$"):
                    load_packet_evidence_v3(scenario.retention, scenario.journal_admission)
        path.write_bytes(original)

    def test_I70_F06_bad_packet_cannot_authorize_prepared(self):
        scenario = self.persisted()
        evidence = prepare_packet_receipt_v3(
            scenario.retention_base, scenario.admitted_snapshot, TECHNICAL_POLICY_ID,
            scenario.capture.evidence_id, scenario.manifest["packet_id"])
        authority = RetainedPacketAuthorityV3(scenario.retention_base, TECHNICAL_POLICY_ID,
                                             scenario.capture.evidence_id, scenario.manifest["packet_id"])
        snapshot = scenario.admitted_snapshot
        self.assertTrue(authority.permits(snapshot=snapshot, packet_evidence_id=evidence,
                                         reservation_id=snapshot.record.control.reservation_id,
                                         generation=1, worker=scenario.worker))
        path = scenario.retention / "packet/input.txt"
        path.write_bytes(path.read_bytes() + b"tampered\n")
        before = len(scenario.transport.updates)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PACKET"):
            scenario.journal.prepare(snapshot, evidence, snapshot.record.control.reservation_id,
                                     1, scenario.worker, authority)
        self.assertEqual(len(scenario.transport.updates), before)
        self.assertEqual(scenario.journal.read(scenario.admission.request_id).record.attempt.state.value, "ADMITTED")

    def test_I70_F07_atomic_retention_interruption_has_no_prepared_or_retry(self):
        scenario = self.scenario()
        snapshot = scenario.through_admitted()
        base = scenario.root / "retained"
        before = len(scenario.transport.updates)
        with patch("review_broker.packet_retention_v3.os.replace", side_effect=OSError("INTERRUPTED")):
            with self.assertRaisesRegex(OSError, "^INTERRUPTED$"):
                persist_packet_evidence_v3(scenario.admission, scenario.capture, profile(), base,
                                           snapshot, scenario.journal, scenario.issue_readers)
        self.assertEqual(list(base.iterdir()), [])
        self.assertEqual(len(scenario.transport.updates), before)
        self.assertEqual(scenario.journal.read(scenario.admission.request_id).record.attempt.state.value, "ADMITTED")
        self.assertEqual(scenario.dispatches, 1)

    def test_I70_N03_synthetic_identity_and_retained_shape_stay_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = git_capture(root)
            admission = admitted(request_for_capture(capture, [inline()]), capture=capture)
            packet = root / "retained/packet"
            manifest = build_packet_v2_candidate(admission, capture, profile(), packet)
            self.assertIsNone(admission.source_scope_evidence_id)
            self.assertIsNone(capture.source_authorization_evidence_id)
            self.assertIsNone(capture.pr_observation_evidence_id)
            self.assertEqual(capture.verification, "SYNTHETIC_OFFLINE_VERIFIED")
            self.assertNotIn("source_authorization_evidence_id", manifest["subject"])
            self.assertNotIn("pr_observation_evidence_id", manifest["subject"])
            self.assertEqual(verify_packet_v2_candidate(packet, admission, capture, profile()), manifest)
            # A retained-format fixture exercises the legacy loader independently;
            # it does not claim to qualify the producer for an inline-only packet.
            evidence = root / "retained/evidence"
            (evidence / "admitted-references").mkdir(parents=True)
            (evidence / "origin-body.bin").write_bytes(admission.origin_body_bytes)
            (evidence / "technical-profile.bin").write_bytes(profile().original_bytes)
            for path in [root / "retained", *(root / "retained").rglob("*")]:
                path.chmod(0o700 if path.is_dir() else 0o600)
            rebuilt, cold, _, verified = load_packet_evidence_v3(root / "retained", admission.journal_admission())
            self.assertEqual(cold.evidence_id, capture.evidence_id)
            self.assertIsNone(rebuilt.source_scope_evidence_id)
            self.assertEqual(verified["packet_id"], manifest["packet_id"])

    def test_I70_F08_prepared_reverification_never_reacquires_mutable_sources(self):
        scenario = self.scenario().complete()
        before = len(scenario.transport.updates)
        with patch("review_broker.github_issue_reference_v3.GitHubIssueReferenceReaderV3.observe_issue_body",
                   side_effect=AssertionError("REACQUISITION_FORBIDDEN")):
            self.assertEqual(verify_prepared_readback_v3(scenario.retention_base, scenario.prepared), scenario.verified)
        self.assertEqual(len(scenario.transport.updates), before)
        with self.assertRaisesRegex(GitHubJournalV3Error, "^INITIAL_RESERVATION_NOT_PERMITTED$"):
            scenario.journal.reserve_initial(scenario.prepared)
        self.assertEqual(len(scenario.transport.updates), before)
        self.assertEqual(scenario.dispatches, 1)

    def test_I70_F09_permanent_refusal_fences_retained_packet(self):
        from tests.journal_v3_test_support import failure_receipt, TrustedFailureAuthority
        scenario = self.persisted()
        snapshot = scenario.admitted_snapshot
        control = snapshot.record.control
        evidence = prepare_packet_receipt_v3(
            scenario.retention_base, snapshot, TECHNICAL_POLICY_ID,
            scenario.capture.evidence_id, scenario.manifest["packet_id"])
        authority = RetainedPacketAuthorityV3(scenario.retention_base, TECHNICAL_POLICY_ID,
                                             scenario.capture.evidence_id, scenario.manifest["packet_id"])
        _, receipt = failure_receipt(snapshot.record.attempt.attempt_id,
                                     control.reservation_id, scenario.worker)
        receipt.update(request_id=scenario.admission.request_id,
                       admission_evidence_id=scenario.admission.admission_evidence_id)
        refusal_id = artifact_identity(canonical_bytes(receipt) + b"\n")
        refused = scenario._take("refuse", scenario.journal.refuse_permanently(
            snapshot, refusal_id, receipt, control.reservation_id, 1, scenario.worker,
            TrustedFailureAuthority()), snapshot)
        self.assertEqual(refused.record.control.disposition, "REFUSED_PERMANENT")
        before = len(scenario.transport.updates)
        with self.assertRaisesRegex(GitHubJournalV3Error, "^PACKET_AUTHORITY_UNTRUSTED$"):
            scenario.journal.prepare(refused, evidence, control.reservation_id, 1,
                                     scenario.worker, authority)
        self.assertEqual(len(scenario.transport.updates), before)
        self.assertEqual(scenario.journal.read(scenario.admission.request_id).commit_sha, refused.commit_sha)
        self.assertEqual(refused.record.attempt.state.value, "ADMITTED")
        self.assertEqual(refused.record.attempt.invocation_count, 0)
        self.assertEqual(scenario.dispatches, 1)

    def test_I70_F10_concurrent_initial_claim_has_one_creation(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        scenario = self.scenario()
        scenario.transport.create_barrier = threading.Barrier(2, timeout=30)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: scenario.journal.claim(
                scenario.request, scenario.journal_admission), range(2)))
        self.assertEqual([outcome.status for outcome in outcomes], [OutcomeStatusV3.COMMITTED] * 2)
        self.assertEqual(scenario.transport.create_statuses.count(CreateRefStatusV3.CREATED), 1)
        self.assertEqual(scenario.transport.create_statuses.count(CreateRefStatusV3.ALREADY_EXISTS), 1)
        self.assertEqual(len(scenario.transport.refs), 1)
        self.assertEqual(scenario.transport.updates, [])
        self.assertEqual(scenario.dispatches, 0)


if __name__ == "__main__":
    unittest.main()
