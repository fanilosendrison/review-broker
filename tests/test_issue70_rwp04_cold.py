"""A genuinely new process reconstructs after the entire Worker root is deleted."""
from dataclasses import asdict, replace
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.historical_policy_verification_v3 import HistoricalAuthorizedPolicyVerificationV3
from review_broker.packet_retention_v3 import load_packet_evidence_v3, persist_packet_evidence_v3
from review_broker.packet_v2 import build_packet_v2_candidate, verify_packet_v2_candidate
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from tests.issue68_test_support import IntegratedScenario
from tests.issue70_rwp03_linux_cold_isolation import minimal_environment
from tests.issue70_rwp04_test_support import RemoteScenario, PRINCIPAL


class RemoteColdTests(unittest.TestCase):
    def test_Q01_Q21_full_worker_disappearance_and_fresh_isolated_process(self):
        self.cold_roundtrip(no_remote=False)

    def test_Q02_no_remote_references_cold_reconstruction(self):
        self.cold_roundtrip(no_remote=True)

    def cold_roundtrip(self, *, no_remote):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker_root, cold = root/"worker", root/"external-observer"
            worker_root.mkdir(mode=0o700); cold.mkdir(mode=0o700)
            r = RemoteScenario(worker_root, no_remote=no_remote)
            result = r.run()
            self.assertEqual(result.status.value, "COMMITTED", result)
            expected = r.readback(root/"expected-readback").reconstruction
            self.assertIsNotNone(expected)
            s = r.s.worker
            IntegratedScenario.save_transport(s, cold/"journal.json")
            p, a = result.journal_outcome.snapshot, r.verification.snapshot
            # Independent simulated service archives: no trust read from the ZIP.
            origins = [dict(repository=x.repository, claim_ref=x.claim_ref, commit_sha=x.commit_sha,
                parent_sha=x.parent_sha, journal_bytes_id=artifact_identity(x.journal_bytes)) for x in (a, p)]
            for name, data in {
                "server-origin.json": canonical_bytes(origins)+b"\n",
                "server-mutation.json": canonical_bytes([asdict(u) for u in s.transport.updates])+b"\n",
                "dispatch.json": canonical_bytes(s.dispatch_authority.archive)+b"\n",
                "admission.json": canonical_bytes(s.admission.journal_admission())+b"\n",
                "authenticated-storage.json": canonical_bytes(result.remote_receipt.value["storage"])+b"\n",
                "independent-selection.json": r.s.archive.read_bytes(),
                "downloaded.zip": result.archive_bytes,
                "request-id.txt": s.admission.request_id.encode(),
            }.items():
                path = cold/name; path.write_bytes(data); path.chmod(0o600)
            original_id = r.handoff.packet_id
            # All producer source clones, packet roots, archives and Python objects vanish.
            expected_offline = expected.offline_receipt_bytes
            del expected  # Parent keeps only byte oracles below, not verifier inputs.
            expected_manifest = (root/"expected-readback/packet/input-manifest.json").read_bytes()
            expected_inventory = r.service.uploads[0][0].inventory_bytes
            expected_receipt = result.remote_receipt.canonical_receipt_bytes
            del result, a, p, s, r
            gc.collect()
            shutil.rmtree(worker_root)
            shutil.rmtree(root/"expected-readback")
            self.assertFalse(worker_root.exists())
            home = root/"cold-home"; home.mkdir(mode=0o700)
            process = subprocess.run([sys.executable, "-m", "tests.issue70_rwp04_cold_probe", str(cold)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                env=minimal_environment(home), close_fds=True, pass_fds=(), timeout=90)
            self.assertEqual(process.returncode, 0, process.stderr)
            observed = json.loads(process.stdout)
            self.assertEqual(canonical_bytes(observed["manifest"])+b"\n", expected_manifest)
            self.assertEqual(canonical_bytes(observed["inventory"])+b"\n", expected_inventory)
            self.assertEqual(canonical_bytes(observed["remote"])+b"\n", expected_receipt)
            self.assertEqual(canonical_bytes(observed["offline"])+b"\n", expected_offline)
            if no_remote:
                self.assertEqual(list((cold/"cold-packet/evidence/admitted-references").iterdir()), [])
            self.assertEqual(observed["manifest"]["packet_id"], original_id)
            self.assertEqual([observed[key] for key in ("capture_calls", "selections", "uploads", "journal_mutations")], [0]*4)

    def test_Q14_Q18_historical_verification_cannot_build_persist_or_authorize_new_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            r = RemoteScenario(root)
            result = r.run()
            self.assertEqual(result.status.value, "COMMITTED", result)
            s = r.s.worker
            history = PreparedJournalHistoryV3.read(s.journal, s.admission.request_id, s.expected,
                                                      s.dispatch_authority, PRINCIPAL)
            verification = HistoricalAuthorizedPolicyVerificationV3(history, r.s.source_authority, r.s.selection_authority)
            admission, capture, profile, manifest = load_packet_evidence_v3(root/"downloaded",
                history.admitted.record.attempt.admission, policy_verification=verification)
            self.assertEqual(verification.selection_context(admission.request).admitted_commit_sha,
                             history.admitted.commit_sha)
            self.assertNotEqual(history.admitted.commit_sha, history.prepared.commit_sha)
            with patch("os.open", side_effect=AssertionError("unexpected filesystem effect")) as writes:
                with self.assertRaises(ValueError):
                    build_packet_v2_candidate(admission, capture, profile, root/"illegal-build", policy_verification=verification)
                with self.assertRaises(ValueError):
                    persist_packet_evidence_v3(admission, capture, profile, root/"illegal-retain", history.admitted,
                                               s.journal, policy_verification=verification)
                writes.assert_not_called()
            for field in ("source_authority", "selection_authority"):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    load_packet_evidence_v3(root/"downloaded", admission.journal_admission(),
                                           policy_verification=replace(verification, **{field: None}))
            self.assertEqual(len(r.service.uploads), 1)
            self.assertEqual(s.transport.events.count("PREPARED"), 1)
