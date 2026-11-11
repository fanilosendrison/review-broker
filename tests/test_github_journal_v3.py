from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import threading
import unittest
from jsonschema import Draft202012Validator

from review_broker.github_journal_v3 import (
    CreateRefStatusV3,
    GitHubJournalV3,
    GitHubJournalV3Error,
    OutcomeStatusV3,
)
from review_broker.identity import canonical_bytes
from review_broker.journal_record_v3 import JournalRecordV3Error, WorkerIdentityV3, decode_journal_v2
from review_broker.queue import AttemptRecord, AttemptState
from tests.journal_v3_test_support import (
    ADMISSION,
    ADMISSION_ID,
    BASE_SHA,
    NODE_ID,
    PACKET_ID,
    REPOSITORY,
    REQUEST,
    REQUEST_ID,
    FakeGitHubTransportV3,
    TrustedAdmissionAuthority,
    TrustedFailureAuthority,
    TrustedMutationAuthority,
    TrustedPacketAuthority,
    TrustedPredecessorAuthority,
    TrustedRejectionAuthority,
    TrustedWorkerAuthority,
    failure_receipt,
)


class GitHubJournalV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeGitHubTransportV3()
        self.journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )

    def claim(self):
        outcome = self.journal.claim(REQUEST, ADMISSION)
        self.assertEqual(outcome.status, OutcomeStatusV3.COMMITTED)
        return outcome.snapshot

    def commit(self, outcome):
        for _ in range(5):
            if outcome.status is not OutcomeStatusV3.UNRESOLVED:
                break
            outcome = self.journal.reconcile(outcome.pending)
        self.assertEqual(outcome.status, OutcomeStatusV3.COMMITTED)
        return outcome.snapshot

    def reserved(self):
        return self.commit(self.journal.reserve_initial(self.claim()))

    def worker_bound(self, worker: WorkerIdentityV3 | None = None):
        worker = worker or WorkerIdentityV3(101, 1)
        reserved = self.reserved()
        control = reserved.record.control
        outcome = self.journal.register_worker(
            reserved, control.reservation_id, 1, worker, TrustedWorkerAuthority(worker)
        )
        return self.commit(outcome), worker

    def admitted(self):
        bound, worker = self.worker_bound()
        control = bound.record.control
        return self.commit(self.journal.record_admission(
            bound, ADMISSION_ID, control.reservation_id, 1, worker
        )), worker

    def test_initial_claim_uses_v3_sibling_namespace(self):
        snapshot = self.claim()
        self.assertTrue(snapshot.claim_ref.startswith("refs/heads/review-claims-v3/"))
        self.assertFalse(snapshot.claim_ref.startswith("refs/heads/review-claims/"))

    def test_two_concurrent_initial_creators_have_one_rest_winner(self):
        self.transport.create_barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(
                lambda _: self.journal.claim(REQUEST, ADMISSION), range(2)
            ))
        self.assertEqual(self.transport.create_statuses.count(CreateRefStatusV3.CREATED), 1)
        self.assertEqual(self.transport.create_statuses.count(CreateRefStatusV3.ALREADY_EXISTS), 1)
        self.assertTrue(all(item.status is OutcomeStatusV3.COMMITTED for item in outcomes))
        self.assertEqual(outcomes[0].snapshot.commit_sha, outcomes[1].snapshot.commit_sha)

    def test_definite_already_exists_validates_admission(self):
        self.claim()
        conflicting = dict(ADMISSION, resolved_subject="different")
        outcome = self.journal.claim(REQUEST, conflicting)
        self.assertEqual(outcome.status, OutcomeStatusV3.REJECTED)
        self.assertEqual(outcome.reason, "CLAIM_IDENTITY_CONFLICT")

    def test_ambiguous_creation_does_not_retry_and_can_reconcile(self):
        self.transport.read_unavailable = 1
        outcome = self.journal.claim(REQUEST, ADMISSION)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(len(self.transport.create_statuses), 1)
        self.assertEqual(self.journal.reconcile(outcome.pending).status,
                         OutcomeStatusV3.COMMITTED)
        self.assertEqual(len(self.transport.create_statuses), 1)

    def test_two_concurrent_reservations_have_one_graphql_winner(self):
        claimed = self.claim()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(
                lambda _: self.journal.reserve_initial(claimed), range(2)
            ))
        self.assertEqual(sum(item.status is OutcomeStatusV3.COMMITTED for item in outcomes), 1)
        self.assertEqual(sum(item.status is OutcomeStatusV3.REJECTED for item in outcomes), 1)
        self.assertEqual(self.journal.read(REQUEST_ID).record.control.generation, 1)

    def test_forged_claim_ref_is_rejected_before_transport_mutation(self):
        claimed = self.claim()
        before_commits = len(self.transport.commits)
        before_updates = len(self.transport.updates)
        forged = replace(claimed, claim_ref="refs/heads/dev")
        with self.assertRaisesRegex(GitHubJournalV3Error, "SNAPSHOT_CLAIM_REF_MISMATCH"):
            self.journal.reserve_initial(forged)
        self.assertEqual(len(self.transport.commits), before_commits)
        self.assertEqual(len(self.transport.updates), before_updates)

    def test_graphql_update_has_exact_expected_old_shape_and_direct_parent(self):
        claimed = self.claim()
        committed = self.commit(self.journal.reserve_initial(claimed))
        update = self.transport.updates[-1]
        self.assertEqual(update.repository_id, NODE_ID)
        self.assertEqual(update.name, claimed.claim_ref)
        self.assertEqual(update.before_oid, claimed.commit_sha)
        self.assertEqual(update.after_oid, committed.commit_sha)
        self.assertFalse(update.force)
        self.assertEqual(self.transport.commits[update.after_oid].parent_sha, update.before_oid)

    def test_stale_graphql_before_oid_is_rejected(self):
        claimed = self.claim()
        self.commit(self.journal.reserve_initial(claimed))
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.REJECTED)
        self.assertEqual(outcome.reason, "GRAPHQL_EXPECTED_OLD_REJECTED")

    def test_http_200_graphql_application_error_is_rejected(self):
        claimed = self.claim()
        self.transport.graphql_application_error = True
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "GRAPHQL_ERROR_APPLICATION_UNRESOLVED")
        self.assertEqual(self.transport.refs[claimed.claim_ref], claimed.commit_sha)

    def test_graphql_error_after_apply_remains_unresolved_without_writer_evidence(self):
        claimed = self.claim()
        self.transport.graphql_error_after_apply = True
        self.transport.stale_reads[claimed.claim_ref] = (claimed.commit_sha, 1)
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "GRAPHQL_ERROR_APPLICATION_UNRESOLVED")
        outcome = self.journal.reconcile(outcome.pending)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "MUTATION_WRITER_UNATTRIBUTED")
        self.assertEqual(len(self.transport.updates), 1)

    def test_ambiguous_expected_old_claim_with_lag_is_not_definite_rejection(self):
        claimed = self.claim()
        self.transport.ambiguous_expected_old_after_apply = True
        self.transport.stale_reads[claimed.claim_ref] = (claimed.commit_sha, 1)
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "GRAPHQL_ERROR_APPLICATION_UNRESOLVED")
        self.assertEqual(len(self.transport.updates), 1)

    def test_competing_descendant_does_not_inherit_writer_evidence(self):
        claimed = self.claim()
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(),
            TrustedPredecessorAuthority(True, readback=False),
        )
        self.transport.competing_descendant_after_update = True
        outcome = journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "COMPETING_OR_LAGGING_READBACK")
        self.assertIsNone(outcome.snapshot.writer_evidence_id)

    def test_successful_mutation_with_stale_readback_reconciles_read_only(self):
        claimed = self.claim()
        self.transport.stale_reads[claimed.claim_ref] = (claimed.commit_sha, 1)
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(len(self.transport.updates), 1)
        outcome = self.journal.reconcile(outcome.pending)
        self.assertEqual(outcome.status, OutcomeStatusV3.COMMITTED)
        self.assertEqual(len(self.transport.updates), 1)

    def test_lost_mutation_acknowledgment_never_retries_mutation(self):
        claimed = self.claim()
        self.transport.lose_update_acknowledgment = True
        self.transport.read_unavailable = 1
        outcome = self.journal.reserve_initial(claimed)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(len(self.transport.updates), 1)
        reconciled = self.journal.reconcile(outcome.pending)
        self.assertEqual(reconciled.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(reconciled.reason, "MUTATION_WRITER_UNATTRIBUTED")
        self.assertEqual(len(self.transport.updates), 1)

    def test_untrusted_admission_cannot_create_commit_or_ref(self):
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            TrustedAdmissionAuthority(False), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )
        with self.assertRaisesRegex(GitHubJournalV3Error, "ADMISSION_AUTHORITY_UNTRUSTED"):
            journal.claim(REQUEST, ADMISSION)
        self.assertEqual(self.transport.commits, {})
        self.assertEqual(self.transport.refs, {})

    def test_reread_reconstructs_authenticated_predecessor_writer_evidence(self):
        self.commit(self.journal.reserve_initial(self.claim()))
        reread = self.journal.read(REQUEST_ID)
        worker = WorkerIdentityV3(101, 1)
        outcome = self.journal.register_worker(
            reread, reread.record.control.reservation_id, 1, worker,
            TrustedWorkerAuthority(worker),
        )
        self.assertEqual(outcome.status, OutcomeStatusV3.COMMITTED)

    def test_duplicate_worker_registration_is_rejected(self):
        bound, worker = self.worker_bound()
        control = bound.record.control
        with self.assertRaisesRegex(GitHubJournalV3Error, "WORKER_REGISTRATION_REJECTED"):
            self.journal.register_worker(
                bound, control.reservation_id, 1, worker, TrustedWorkerAuthority(worker)
            )

    def test_worker_with_wrong_run_attempt_is_untrusted(self):
        reserved = self.reserved()
        wrong = WorkerIdentityV3(101, 2)
        with self.assertRaisesRegex(GitHubJournalV3Error, "WORKER_AUTHORITY_UNTRUSTED"):
            self.journal.register_worker(
                reserved, reserved.record.control.reservation_id, 1, wrong,
                TrustedWorkerAuthority(WorkerIdentityV3(101, 1)),
            )

    def test_wrong_generation_or_reservation_is_rejected(self):
        bound, worker = self.worker_bound()
        for reservation, generation in (("preparation-dispatch:sha256:" + "1" * 64, 1),
                                        (bound.record.control.reservation_id, 2)):
            with self.subTest(generation=generation), self.assertRaisesRegex(
                GitHubJournalV3Error, "WORKER_GENERATION_FENCED"
            ):
                self.journal.record_admission(
                    bound, ADMISSION_ID, reservation, generation, worker
                )

    def test_untrusted_or_malformed_packet_cannot_reach_prepared(self):
        admitted, worker = self.admitted()
        control = admitted.record.control
        before_updates = len(self.transport.updates)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PACKET_AUTHORITY_UNTRUSTED"):
            self.journal.prepare(
                admitted, PACKET_ID, control.reservation_id, 1, worker,
                TrustedPacketAuthority(False),
            )
        with self.assertRaisesRegex(GitHubJournalV3Error, "PACKET_AUTHORITY_UNTRUSTED"):
            self.journal.prepare(
                admitted, "not-an-artifact", control.reservation_id, 1, worker,
                TrustedPacketAuthority(True),
            )
        self.assertEqual(len(self.transport.updates), before_updates)

    def test_committed_prepared_preserves_packet_evidence_in_history(self):
        admitted, worker = self.admitted()
        control = admitted.record.control
        prepared = self.commit(self.journal.prepare(
            admitted, PACKET_ID, control.reservation_id, 1, worker,
            TrustedPacketAuthority(),
        ))
        self.assertEqual(prepared.record.attempt.state, AttemptState.PREPARED)
        self.assertIn(PACKET_ID, prepared.record.attempt.evidence_ids)
        self.assertEqual(prepared.record.attempt.history[-1]["evidence_ids"], [PACKET_ID])
        self.assertNotIn("packet_evidence_id", prepared.record.as_dict())

    def test_permanent_refusal_before_prepared_blocks_prepare(self):
        admitted, worker = self.admitted()
        control = admitted.record.control
        failure_id, receipt = failure_receipt(
            admitted.record.attempt.attempt_id, control.reservation_id, worker
        )
        refused = self.commit(self.journal.refuse_permanently(
            admitted, failure_id, receipt, control.reservation_id, 1, worker,
            TrustedFailureAuthority(),
        ))
        self.assertEqual(refused.record.control.disposition, "REFUSED_PERMANENT")
        with self.assertRaisesRegex(GitHubJournalV3Error, "WORKER_GENERATION_FENCED"):
            self.journal.prepare(
                refused, PACKET_ID, control.reservation_id, 1, worker,
                TrustedPacketAuthority(),
            )

    def test_permanent_refusal_rejects_untrusted_classifier(self):
        admitted, worker = self.admitted()
        control = admitted.record.control
        failure_id, receipt = failure_receipt(
            admitted.record.attempt.attempt_id, control.reservation_id, worker
        )
        with self.assertRaisesRegex(GitHubJournalV3Error, "FAILURE_AUTHORITY_UNTRUSTED"):
            self.journal.refuse_permanently(
                admitted, failure_id, receipt, control.reservation_id, 1, worker,
                TrustedFailureAuthority(False),
            )

    def test_permanent_refusal_rejects_unbound_receipt(self):
        admitted, worker = self.admitted()
        control = admitted.record.control
        failure_id, receipt = failure_receipt(
            admitted.record.attempt.attempt_id, control.reservation_id, worker
        )
        receipt["workflow_run_attempt"] = 2
        with self.assertRaisesRegex(GitHubJournalV3Error, "FAILURE_RECEIPT_IDENTITY_INVALID"):
            self.journal.refuse_permanently(
                admitted, failure_id, receipt, control.reservation_id, 1, worker,
                TrustedFailureAuthority(),
            )

    def test_strict_v2_decoder_matches_candidate_fixture_and_rejects_changes(self):
        snapshot = self.claim()
        schema_path = Path(__file__).parent / "fixtures/pre_model_v3/journal-v2.compat.candidate.schema.json"
        validator = Draft202012Validator(json.loads(schema_path.read_text()))
        self.assertEqual(list(validator.iter_errors(json.loads(snapshot.journal_bytes))), [])
        value = json.loads(snapshot.journal_bytes)
        for change in (
            lambda item: item.__setitem__("schema_version", 3),
            lambda item: item.__setitem__("unknown", True),
            lambda item: item.pop("pre_model_control"),
        ):
            candidate = deepcopy(value)
            change(candidate)
            raw = json.dumps(candidate, separators=(",", ":"), sort_keys=True).encode() + b"\n"
            with self.assertRaises(JournalRecordV3Error):
                decode_journal_v2(raw)

    def test_strict_decoder_rejects_control_worker_forged_against_history(self):
        bound, _ = self.worker_bound()
        value = json.loads(bound.journal_bytes)
        value["pre_model_control"]["worker"] = {"run_id": 999, "run_attempt": 1}
        with self.assertRaisesRegex(JournalRecordV3Error, "CURRENT_WORKER_HISTORY_MISMATCH"):
            decode_journal_v2(canonical_bytes(value) + b"\n")

    def test_noncanonical_v2_and_armed_zero_boundary(self):
        value = json.loads(self.claim().journal_bytes)
        with self.assertRaisesRegex(JournalRecordV3Error, "NONCANONICAL"):
            decode_journal_v2(json.dumps(value, indent=2).encode() + b"\n")
        admitted, worker = self.admitted()
        prepared = self.commit(self.journal.prepare(
            admitted, PACKET_ID, admitted.record.control.reservation_id, 1, worker,
            TrustedPacketAuthority(),
        ))
        value = json.loads(prepared.journal_bytes)
        arm_evidence = "artifact:sha256:" + "5" * 64
        value["state"] = "ARMED"
        value["invocation_count"] = 0
        value["evidence_ids"].append(arm_evidence)
        value["history"].append({"state": "ARMED", "evidence_ids": [arm_evidence]})
        self.assertEqual(
            decode_journal_v2(canonical_bytes(value) + b"\n").attempt.invocation_count, 0
        )

    def test_legacy_attempt_record_and_namespace_are_unchanged(self):
        legacy = AttemptRecord.from_dict({
            "schema_version": 1, "request_id": REQUEST_ID,
            "attempt_id": self.claim().record.attempt.attempt_id,
            "state": "REQUESTED", "evidence_ids": [], "invocation_count": 0,
            "evidence_locator_plan": None, "evidence_locator": None,
            "publication_intent": None, "publication_receipt": None,
            "history": [{"state": "REQUESTED", "evidence_ids": []}],
        })
        self.assertEqual(legacy.as_dict()["schema_version"], 1)
        self.assertNotIn("pre_model_control", legacy.as_dict())
        self.assertEqual(GitHubJournalV3.claim_ref(REQUEST_ID).split("/")[2],
                         "review-claims-v3")

    def test_future_operations_fail_explicitly(self):
        with self.assertRaisesRegex(GitHubJournalV3Error, "V3_OPERATION_UNSUPPORTED:ARM"):
            self.journal.unsupported("ARM")


if __name__ == "__main__":
    unittest.main()
