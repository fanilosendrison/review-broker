"""Executable witnesses for the independent RWP-04 NO_GO, not reason-only checks."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import canonical_bytes
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.prepared_packet_readback_v3 import reconstruct_prepared_packet_v3
from review_broker.prepared_artifact_transport_v3 import PreparedMetadataReaderV3
from review_broker.github_http_live_v3 import HttpResponseV3
from tests.issue70_rwp04_test_support import RemoteScenario, PRINCIPAL, BUDGET


class RemoteManifestConfinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.r = RemoteScenario(cls.root)
        cls.result = cls.r.run()
        if cls.result.status.value != "COMMITTED": raise AssertionError(cls.result)
        cls.history = PreparedJournalHistoryV3.read(cls.r.s.worker.journal,
            cls.r.s.worker.admission.request_id, cls.r.s.worker.expected,
            cls.r.s.worker.dispatch_authority, PRINCIPAL)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_R1_active_and_historical_manifest_paths_never_read_outside_canary(self):
        r = self.r
        transport, a, p = r.s.worker.transport, self.history.admitted, self.history.prepared
        for mode in ("active", "historical"):
            for kind in ("absolute", "traversal"):
                root = self.root/f"{mode}-{kind}"
                shutil.copytree(self.root/"downloaded", root)
                canary = self.root/f"outside-{mode}-{kind}.bin"
                canary.write_bytes(b"nonsecret independent outside-read canary")
                canary.chmod(0o600)
                manifest_path = root/"packet/input-manifest.json"
                manifest = json.loads(manifest_path.read_bytes())
                manifest["subject_sources"][0]["snapshot"] = str(canary) if kind == "absolute" else os.path.relpath(canary, root/"packet")
                manifest_path.write_bytes(canonical_bytes(manifest)+b"\n")
                reads, original = [], Path.read_bytes
                def read(path):
                    if path.resolve() == canary.resolve(): reads.append(path)
                    return original(path)
                try:
                    transport.refs[a.claim_ref] = a.commit_sha if mode == "active" else p.commit_sha
                    with patch.object(Path, "read_bytes", read):
                        with self.assertRaises((ValueError, RuntimeError, OSError)):
                            if mode == "active":
                                load_packet_evidence_v3(root, a.record.attempt.admission,
                                                       policy_verification=r.verification)
                            else:
                                reconstruct_prepared_packet_v3(root, history=self.history,
                                    source_authority=r.s.source_authority,
                                    selection_authority=r.s.selection_authority,
                                    authenticated_storage=self.result.remote_receipt.value["storage"])
                    with self.subTest(mode=mode, kind=kind): self.assertEqual(reads, [])
                finally:
                    transport.refs[a.claim_ref] = p.commit_sha
        self.assertEqual(len(r.service.uploads), 1)
        self.assertEqual(transport.events.count("PREPARED"), 1)

    def test_RQ17_coherent_admission_and_worker_changes_are_not_historical_authority(self):
        from tests.issue70_rwp03_test_support import alternate_admission
        from review_broker.pre_model_control_v3 import transition_state, register_worker
        from review_broker.journal_record_v3 import WorkerIdentityV3, encode_journal_v2
        from review_broker.queue import AttemptState
        h, s = self.history, self.r.s.worker
        bound = s.journal.read_at(s.admission.request_id, h.admitted.parent_sha)
        other = alternate_admission(self.r.s)
        changed_admission = replace(bound.record, attempt=replace(bound.record.attempt, admission=other.journal_admission()))
        ack = s.journal.read_at(s.admission.request_id, bound.parent_sha)
        binding = next(e["pre_model"]["receipt"] for e in bound.record.attempt.history if e.get("event") == "PRE_MODEL_WORKER_BOUND")
        changed_worker = register_worker(ack.record, ack.record.control.reservation_id, 1,
                                        WorkerIdentityV3(70002, 1), binding["authority_evidence_id"])
        for record, admission_id in ((changed_admission, other.admission_evidence_id),
                                     (changed_worker, s.admission.admission_evidence_id)):
            control = record.control
            ar = transition_state(record, AttemptState.ADMITTED, admission_id,
                                  control.reservation_id, 1, control.worker)
            pr = transition_state(ar, AttemptState.PREPARED, h.remote_receipt_id,
                                  control.reservation_id, 1, control.worker)
            a = replace(h.admitted, record=ar, journal_bytes=encode_journal_v2(ar))
            p = replace(h.prepared, record=pr, journal_bytes=encode_journal_v2(pr))
            with self.assertRaises(ValueError): replace(h, admitted=a, prepared=p)
        original = s.journal.admission_authority
        from tests.issue68_test_support import ExactAdmissionAuthority
        try:
            s.journal.admission_authority = ExactAdmissionAuthority(other.journal_admission())
            with self.assertRaises(ValueError): h.verify()
        finally:
            s.journal.admission_authority = original
        try:
            s.dispatch_authority.recognized = False
            with self.assertRaises(ValueError): h.verify()
        finally:
            s.dispatch_authority.recognized = True
        h.verify()


class PaginationTerminalTests(unittest.TestCase):
    def listing(self, pages):
        self.calls = []
        def execute(request, *, max_bytes):
            self.calls.append(request.full_url)
            return pages[len(self.calls)-1]
        reader = PreparedMetadataReaderV3(token="fixture", repository="example/broker", executor=execute, budget=BUDGET)
        return reader.listing("/actions/runs/29/artifacts", {"name": "frozen"}, "artifacts", lambda: None)

    def page(self, count, identifier, links):
        return HttpResponseV3(200, json.dumps(dict(total_count=count, artifacts=[{"id": identifier}])).encode(), {"Link": links})

    def link(self, page, rel):
        return f'<https://api.github.com/repos/example/broker/actions/runs/29/artifacts?name=frozen&per_page=100&page={page}>; rel="{rel}"'

    def test_R2_future_last_without_continuation_is_not_complete(self):
        with self.assertRaises(ValueError): self.listing([self.page(1, 1, self.link(2, "last"))])
        self.assertEqual(len(self.calls), 1)

    def test_R2_terminal_page_drift_is_rejected(self):
        with self.assertRaises(ValueError):
            self.listing([self.page(2, 1, self.link(2, "next")+", "+self.link(2, "last")),
                          self.page(2, 2, self.link(1, "prev")+", "+self.link(3, "last"))])
        self.assertEqual(len(self.calls), 2)

    def test_R2_consistent_last_and_complete_prev_first_are_valid(self):
        for final in (self.link(2, "last")+", "+self.link(1, "prev"),
                      self.link(1, "first")+", "+self.link(1, "prev")):
            self.assertEqual(self.listing([self.page(2, 1, self.link(2, "next")+", "+self.link(2, "last")),
                                           self.page(2, 2, final)]), [{"id": 1}, {"id": 2}])
