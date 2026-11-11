"""Historical observations and tampering adversaries; the only doubles are transports."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from review_broker.historical_policy_verification_v3 import HistoricalAuthorizedPolicyVerificationV3
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.remote_prepared_receipt_v3 import RemotePreparedReceiptV3
from tests.issue70_rwp04_test_support import RemoteScenario, PRINCIPAL, BUDGET


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.r = RemoteScenario(cls.root)
        cls.result = cls.r.run()
        if cls.result.status.value != "COMMITTED": raise AssertionError(cls.result)
        cls.saved_artifacts = copy.deepcopy(cls.r.service.artifacts)
        cls.saved_run, cls.saved_jobs = copy.deepcopy(cls.r.service.run), copy.deepcopy(cls.r.service.jobs)
        cls.history = PreparedJournalHistoryV3.read(cls.r.s.worker.journal,
            cls.r.s.worker.admission.request_id, cls.r.s.worker.expected,
            cls.r.s.worker.dispatch_authority, PRINCIPAL)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        service = self.r.service
        service.artifacts = copy.deepcopy(self.saved_artifacts)
        service.run, service.jobs = copy.deepcopy(self.saved_run), copy.deepcopy(self.saved_jobs)
        service.archive = self.result.archive_bytes
        service.redirect = "https://fixture.blob.core.windows.net/private/archive?sig=fixture"
        service.metadata_calls.clear(); service.downloads.clear(); service.storage_headers.clear()
        self.verification = HistoricalAuthorizedPolicyVerificationV3(self.history,
            self.r.s.source_authority, self.r.s.selection_authority)

    def observe(self):
        return self.r.adapter.observe(self.history.admitted, self.history.verify)

    def no_new_effects(self):
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)

    def test_Q08_each_run_attempt_workflow_sha_and_job_binding(self):
        for key, bad in (("id", 70002), ("run_attempt", 2), ("workflow_id", 78),
                         ("head_sha", "f"*40), ("path", ".github/workflows/other.yml"),
                         ("head_branch", "other"), ("event", "push")):
            self.r.service.run = copy.deepcopy(self.saved_run)
            self.r.service.run[key] = bad
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)): self.observe()
        self.r.service.run = copy.deepcopy(self.saved_run)
        for jobs in ([], self.saved_jobs*2, [{**self.saved_jobs[0], "run_attempt": 2}],
                     [{**self.saved_jobs[0], "head_sha": "f"*40}], [{**self.saved_jobs[0], "run_id": 2}]):
            self.r.service.jobs = copy.deepcopy(jobs)
            with self.subTest(jobs=jobs), self.assertRaises((ValueError, RuntimeError)): self.observe()
        self.no_new_effects()
        self.assertEqual(self.r.service.downloads, [])

    def test_Q06_Q08_artifact_filter_repository_run_digest_size_dates(self):
        mutations = (("name", "wrong"), ("size_in_bytes", True), ("size_in_bytes", BUDGET.max_archive_bytes+1),
                     ("created_at", "bad"), ("expired", True))
        for key, bad in mutations:
            self.r.service.artifacts = copy.deepcopy(self.saved_artifacts)
            self.r.service.artifacts[0][key] = bad
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)): self.observe()
        for key, bad in (("id", 9), ("repository_id", 9), ("head_repository_id", 9), ("head_sha", "e"*40)):
            self.r.service.artifacts = copy.deepcopy(self.saved_artifacts)
            self.r.service.artifacts[0]["workflow_run"][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.observe()
        self.no_new_effects()

    def test_Q09_exact_remote_zip_digest_truncation_extra_bytes(self):
        storage = self.observe()
        for raw in (self.result.archive_bytes[:-1], self.result.archive_bytes+b"extra",
                    b"X"+self.result.archive_bytes[1:]):
            self.r.service.archive = raw
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                self.r.adapter.download(storage, self.history.verify)
        self.assertEqual(len(self.r.service.downloads), 3)
        self.no_new_effects()

    def test_Q10_invalid_redirects_never_reach_storage(self):
        storage = self.observe()
        for url in ("http://fixture.blob.core.windows.net/x", "https://evil.invalid/x",
                    "https://blob.core.windows.net/x", "https://user@fixture.blob.core.windows.net/x",
                    "https://fixture.blob.core.windows.net:444/x", "https://fixture.blob.core.windows.net/x#fragment"):
            self.r.service.redirect = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.r.adapter.download(storage, self.history.verify)
        self.assertEqual(self.r.service.downloads, [])
        self.no_new_effects()

    def test_Q13_each_retained_source_reference_policy_manifest_prompt_tampering(self):
        root = self.root/"downloaded"
        names = ["packet/input.txt", "packet/input-manifest.json", "packet/changes.patch",
                 "packet/sources/S001.bin", "packet/sources/S004.bin", "evidence/expected-policy.bin",
                 "evidence/policy-source-observation.json", "evidence/policy-selection-receipt.json",
                 "evidence/admitted-references/requirement.bin", "evidence/origin-body.bin"]
        for name in names:
            path = root/name
            original = path.read_bytes()
            for mode in ("changed", "missing"):
                if mode == "changed": path.write_bytes(original+b"tampered")
                else: path.unlink()
                with self.subTest(name=name, mode=mode), self.assertRaises((ValueError, RuntimeError, OSError)):
                    load_packet_evidence_v3(root, self.history.admitted.record.attempt.admission,
                                           policy_verification=self.verification)
                path.write_bytes(original); path.chmod(0o600)
        self.no_new_effects()

    def test_Q15_coherent_synthetic_downgrade_is_refused_by_historical_reader(self):
        from review_broker.packet_v2 import build_packet_v2_candidate
        from tests.packet_v2_test_support import profile
        root = self.root/"coherent-synthetic"
        root.mkdir(mode=0o700)
        shutil.copytree(self.root/"downloaded/evidence", root/"evidence")
        for name in ("expected-policy.bin", "policy-source-observation.json", "policy-selection-receipt.json"):
            (root/"evidence"/name).unlink()
        (root/"evidence/technical-profile.bin").write_bytes(profile().original_bytes)
        (root/"evidence/technical-profile.bin").chmod(0o600)
        inputs = self.r.s.inputs
        build_packet_v2_candidate(inputs.admission, inputs.capture, profile(), root/"packet", inputs.issue_readers)
        load_packet_evidence_v3(root, inputs.admission.journal_admission())
        with self.assertRaisesRegex(ValueError, "AUTHORIZED_POLICY_MODE_REQUIRED"):
            load_packet_evidence_v3(root, inputs.admission.journal_admission(), policy_verification=self.verification)
        self.no_new_effects()

    def test_Q17_changed_parent_unrecognized_writer_admission_or_binding(self):
        for field, value in (("parent_sha", "f"*40), ("writer_evidence_id", "artifact:sha256:"+"e"*64),
                             ("repository_node_id", "OTHER")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(self.history, prepared=replace(self.history.prepared, **{field: value}))
        self.no_new_effects()

    def test_Q23_remote_source_mutation_does_not_recapture_original_snapshots(self):
        before = self.r.s.capture_calls
        self.r.s.inputs.issue_readers["requirement"]._executor.body = "changed remote body after PREPARED"
        result = self.r.readback(self.root/"mutable-source-readback")
        self.assertEqual(result.remote_reconstruction, "VERIFIED")
        self.assertEqual(result.reconstruction.packet_id, self.r.handoff.packet_id)
        self.assertEqual(self.r.s.capture_calls, before)
        self.no_new_effects()
