"""Real authorized packet -> injected remote ZIP -> existing PREPARED CAS."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import canonical_bytes
from review_broker.packet_preparation_authority_v3 import (
    offline_packet_receipt_v3, retained_inventory_id_v3,
)
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.queue import AttemptState
from tests.issue70_rwp04_test_support import RemoteScenario, PRINCIPAL, JOB_ID


class RemoteContinuationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.r = RemoteScenario(self.root)

    def complete(self):
        result = self.r.run()
        self.assertEqual(result.status.value, "COMMITTED", result)
        self.assertEqual(result.state, "PREPARED")
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)
        return result

    def test_Q01_real_packet_inventory_offline_receipt_and_remote_readback(self):
        r = self.r
        manifest = json.loads((r.handoff.retained_root/"packet/input-manifest.json").read_bytes())
        expected_offline = offline_packet_receipt_v3(r.verification.snapshot, manifest,
            retained_inventory_id_v3(r.handoff.retained_root))
        # Independent field oracle: the schema is fixed, not rebuilt with the SUT.
        self.assertEqual(set(expected_offline), {"schema_version", "evidence_type", "repository",
            "repository_node_id", "claim_ref", "predecessor_commit_sha", "request_id", "review_intent_id",
            "attempt_id", "admission_evidence_id", "reservation_id", "generation", "worker", "packet_id",
            "subject_capture_evidence_id", "technical_policy_id", "retained_inventory_id"})
        result = self.complete()
        back = r.readback(self.root/"observed")
        self.assertEqual(back.remote_reconstruction, "VERIFIED", back)
        self.assertEqual(back.reconstruction.packet_id, r.handoff.packet_id)
        self.assertEqual(back.reconstruction.offline_receipt_bytes, canonical_bytes(expected_offline)+b"\n")
        self.assertEqual(back.reconstruction.remote_receipt, result.remote_receipt)
        self.assertEqual(back.reconstruction.manifest_bytes, canonical_bytes(manifest)+b"\n")
        self.assertEqual(r.service.archive, result.archive_bytes)
        self.assertEqual(r.service.uploads[0][0].retention_days, 30)
        self.assertEqual([entry["source_kind"] for entry in manifest["reference_sources"]],
                         ["inline", "git_file", "github_issue_body", "github_issue_comment"])
        self.assertFalse((r.handoff.retained_root/"evidence/preparation-receipt.json").exists())

    def test_Q04_Q05_new_clock_terminal_job_and_latest_rerun_do_not_change_identity(self):
        original = self.complete()
        r = self.r
        r.service.jobs[0].update(status="completed", conclusion="success", completed_at="2026-11-06T00:00:00Z")
        r.s.worker.api.run["run_attempt"] = 2  # Latest changed; the committed attempt remains independently archived.
        r.service.run["observed_at"] = "2026-11-08T00:00:00Z"
        from datetime import datetime, timezone
        r.adapter = r.make_adapter(clock=lambda: datetime(2026, 11, 8, tzinfo=timezone.utc))
        back = r.readback(self.root/"later")
        self.assertEqual(back.remote_reconstruction, "VERIFIED", back)
        self.assertEqual(back.reconstruction.remote_receipt, original.remote_receipt)
        self.assertTrue(any(f"/attempts/1?" not in url and url.endswith("/attempts/1")
                            for url in r.service.metadata_calls))
        self.assertTrue(all("/attempts/1" in url for url in r.service.metadata_calls if "/jobs?" in url))
        self.assertFalse(any(url.endswith("/actions/runs/70001") for url in r.service.metadata_calls))

    def test_Q06_Q22_committed_prepared_survives_loss_expiry_or_metadata_replacement(self):
        original = self.complete()
        saved = copy.deepcopy(self.r.service.artifacts)
        for change in ("missing", "expired", "new-id", "timestamp", "duplicate"):
            self.r.service.artifacts = copy.deepcopy(saved)
            if change == "missing": self.r.service.artifacts = []
            elif change == "expired": self.r.service.artifacts[0]["expired"] = True
            elif change == "new-id": self.r.service.artifacts[0]["id"] += 1
            elif change == "timestamp": self.r.service.artifacts[0]["created_at"] = "2026-11-05T00:00:01Z"
            else: self.r.service.artifacts.append(copy.deepcopy(saved[0]))
            with self.subTest(change=change):
                back = self.r.readback(self.root/change)
                self.assertEqual((back.journal_transition, back.state, back.remote_reconstruction),
                                 ("COMMITTED", "PREPARED", "UNAVAILABLE"))
                self.assertEqual(self.r.s.worker.journal.read(self.r.s.worker.admission.request_id), original.journal_outcome.snapshot)
                self.assertEqual(len(self.r.service.uploads), 1)
                self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)

    def test_Q19_lost_upload_response_reconciles_without_second_upload(self):
        self.r.service.lost_upload_response = True
        self.complete()
        self.assertNotEqual(self.r.run().status.value, "COMMITTED")
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)

    def test_Q19_established_upload_refusal_permits_no_cas(self):
        self.r.service.refuse_upload = True
        result = self.r.run()
        self.assertEqual(result.status.value, "REJECTED")
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)
        self.assertEqual(len(self.r.service.uploads), 1)

    def test_Q16_upload_journal_movement_leaves_orphan_without_cas(self):
        def move(stage, guard):
            if stage == "after":
                s = self.r.s.worker
                a = s.journal.read(s.admission.request_id)
                sha = s.transport.create_journal_commit(a.commit_sha, a.journal_bytes)
                s.transport.attributed.add(sha)
                s.transport.refs[a.claim_ref] = sha
        self.r.service.upload_hook = move
        result = self.r.run()
        self.assertEqual(result.status.value, "UNRESOLVED")
        self.assertIsNotNone(self.r.service.archive)
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)

    def test_Q22_read_unavailable_after_attributed_cas_preserves_committed(self):
        journal = self.r.s.worker.journal
        original = journal.read
        def read(request_id):
            snapshot = original(request_id)
            if snapshot.record.attempt.state is AttemptState.PREPARED:
                raise OSError("fixture unavailable after attributable CAS readback")
            return snapshot
        with patch.object(journal, "read", read):
            result = self.r.run()
        self.assertEqual((result.status.value, result.state, result.remote_reconstruction),
                         ("COMMITTED", "PREPARED", "UNAVAILABLE"), result)
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)

    def test_Q20_lost_cas_ack_has_visible_prepared_but_no_attributed_success(self):
        self.r.s.worker.transport.lose_update_acknowledgment = True
        result = self.r.run()
        self.assertEqual(result.status.value, "UNRESOLVED", result)
        self.assertEqual(self.r.s.worker.journal.read(self.r.s.worker.admission.request_id).record.attempt.state,
                         AttemptState.PREPARED)
        self.r.run()
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)
        self.assertEqual(len(self.r.service.uploads), 1)

    def test_Q20_divergent_cas_readback_never_retries_mutation(self):
        self.r.s.worker.transport.competing_descendant_after_update = True
        result = self.r.run()
        self.assertEqual(result.status.value, "UNRESOLVED", result)
        self.r.run()
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 1)
        self.assertEqual(len(self.r.service.uploads), 1)

    def test_Q19_unknown_upload_with_ambiguous_objects_never_repeats(self):
        def duplicate(stage, guard):
            if stage == "after":
                item = copy.deepcopy(self.r.service.artifacts[0]); item["id"] += 1
                self.r.service.artifacts.append(item)
        self.r.service.upload_hook = duplicate
        self.r.service.lost_upload_response = True
        result = self.r.run()
        self.assertEqual(result.status.value, "UNRESOLVED", result)
        self.r.run()
        self.assertEqual(len(self.r.service.uploads), 1)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)

    def test_Q18_Q21_new_producer_or_copied_handoff_cannot_upload(self):
        from dataclasses import replace
        result = self.r.continuation.run(self.r.s.worker.context, replace(self.r.handoff))
        self.assertEqual(result.status.value, "REJECTED")
        self.assertEqual(len(self.r.service.uploads), 0)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)

    def test_Q10_storage_request_does_not_receive_github_credentials(self):
        self.complete()
        self.assertTrue(self.r.service.storage_headers)
        self.assertTrue(all(not headers for headers in self.r.service.storage_headers))

    def test_Q08_wrong_job_prevents_prepared(self):
        self.r.service.jobs[0]["id"] = JOB_ID + 1
        result = self.r.run()
        self.assertEqual(result.status.value, "UNRESOLVED")
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)

    def test_Q17_unrecognized_historical_writer_is_rejected(self):
        self.complete()
        p = self.r.s.worker.journal.read(self.r.s.worker.admission.request_id)
        self.r.s.worker.transport.attributed.remove(p.parent_sha)
        with self.assertRaises(ValueError):
            PreparedJournalHistoryV3.read(self.r.s.worker.journal, self.r.s.worker.admission.request_id,
                self.r.s.worker.expected, self.r.s.worker.dispatch_authority, PRINCIPAL)
