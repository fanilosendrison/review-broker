from __future__ import annotations

from dataclasses import replace
import unittest

from review_broker.github_journal_v3 import GitHubJournalV3, GitHubJournalV3Error
from review_broker.github_journal_transport_v3 import OutcomeStatusV3, PendingWriteV3
from tests.journal_v3_test_support import (
    ADMISSION,
    BASE_SHA,
    NODE_ID,
    REPOSITORY,
    REQUEST,
    FakeGitHubTransportV3,
    TrustedAdmissionAuthority,
    TrustedMutationAuthority,
    TrustedPredecessorAuthority,
    TrustedRejectionAuthority,
)


class ReconciliationTrustBoundaryV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeGitHubTransportV3()
        self.journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(),
            TrustedPredecessorAuthority(),
        )
        self.claimed = self.journal.claim(REQUEST, ADMISSION).snapshot

    def test_cached_record_identity_uses_canonical_bytes_not_python_equality(self):
        transport = FakeGitHubTransportV3()
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )
        integer_admission = dict(ADMISSION, trust_marker=1)
        claimed = journal.claim(REQUEST, integer_admission).snapshot
        boolean_admission = dict(ADMISSION, trust_marker=True)
        forged_attempt = replace(claimed.record.attempt, admission=boolean_admission)
        forged = replace(
            claimed, record=replace(claimed.record, attempt=forged_attempt)
        )
        before_updates = len(transport.updates)
        with self.assertRaisesRegex(GitHubJournalV3Error, "SNAPSHOT_RECORD_MISMATCH"):
            journal.reserve_initial(forged)
        self.assertEqual(len(transport.updates), before_updates)

    def test_canonical_admission_identity_distinguishes_integer_and_boolean(self):
        transport = FakeGitHubTransportV3()
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )
        first_admission = dict(ADMISSION, trust_marker=1)
        second_admission = dict(ADMISSION, trust_marker=True)
        first = journal.claim(REQUEST, first_admission)
        second = journal.claim(REQUEST, second_admission)
        self.assertEqual(first.status, OutcomeStatusV3.COMMITTED)
        self.assertEqual(second.status, OutcomeStatusV3.REJECTED)
        self.assertEqual(second.reason, "CLAIM_IDENTITY_CONFLICT")

    def test_created_ref_requires_authenticated_writer_evidence(self):
        transport = FakeGitHubTransportV3()
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(False),
        )
        outcome = journal.claim(REQUEST, ADMISSION)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "CREATED_REF_WRITER_UNATTRIBUTED")

    def test_immediate_created_ref_readback_requires_exact_target(self):
        transport = FakeGitHubTransportV3()
        transport.created_wrong_target = True
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, transport,
            TrustedAdmissionAuthority(), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )
        outcome = journal.claim(REQUEST, ADMISSION)
        self.assertEqual(outcome.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(outcome.reason, "CREATED_REF_EXACT_TARGET_UNRESOLVED")

    def test_forged_snapshot_writer_evidence_cannot_authorize_transition(self):
        forged = replace(
            self.claimed, writer_evidence_id="artifact:sha256:" + "f" * 64
        )
        before_updates = len(self.transport.updates)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PREDECESSOR_WRITER_EVIDENCE_UNTRUSTED"):
            self.journal.reserve_initial(forged)
        self.assertEqual(len(self.transport.updates), before_updates)

    def test_forged_pending_writer_evidence_is_rejected_before_read(self):
        committed = self.journal.reserve_initial(self.claimed).snapshot
        pending = PendingWriteV3(
            REPOSITORY, self.claimed.claim_ref, self.claimed.commit_sha,
            committed.commit_sha, self.claimed.record.attempt.request_id,
            ADMISSION, "UPDATE_REFS",
            writer_evidence_id="artifact:sha256:" + "f" * 64,
        )
        before_reads = len(self.transport.read_calls)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PENDING_WRITER_EVIDENCE_UNTRUSTED"):
            self.journal.reconcile(pending)
        self.assertEqual(len(self.transport.read_calls), before_reads)

    def test_arbitrary_pending_ref_is_rejected_before_transport_read(self):
        pending = PendingWriteV3(
            REPOSITORY, "refs/heads/dev", None, "a" * 40,
            self.claimed.record.attempt.request_id, ADMISSION, "CREATE_REF",
        )
        before_reads = len(self.transport.read_calls)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PENDING_CLAIM_REF_MISMATCH"):
            self.journal.reconcile(pending)
        self.assertEqual(len(self.transport.read_calls), before_reads)

    def test_forged_creation_evidence_is_rejected_before_read(self):
        pending = PendingWriteV3(
            REPOSITORY, self.claimed.claim_ref, None, self.claimed.commit_sha,
            self.claimed.record.attempt.request_id, ADMISSION, "CREATE_REF",
            creation_evidence_id="artifact:sha256:" + "f" * 64,
        )
        before_reads = len(self.transport.read_calls)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PENDING_CREATION_EVIDENCE_UNTRUSTED"):
            self.journal.reconcile(pending)
        self.assertEqual(len(self.transport.read_calls), before_reads)

    def test_created_ref_requires_exact_intended_sha(self):
        pending = PendingWriteV3(
            REPOSITORY, self.claimed.claim_ref, None, "f" * 40,
            self.claimed.record.attempt.request_id, ADMISSION, "CREATE_REF",
            creation_evidence_id="artifact:sha256:" + "3" * 64,
            creation_may_reuse_existing=False,
        )
        outcome = self.journal.reconcile(pending)
        self.assertEqual(outcome.status.value, "UNRESOLVED")
        self.assertEqual(outcome.reason, "CREATED_REF_EXACT_TARGET_UNRESOLVED")

    def test_forged_expected_old_rejection_is_rejected_before_read(self):
        pending = PendingWriteV3(
            REPOSITORY, self.claimed.claim_ref, self.claimed.commit_sha,
            "a" * 40, self.claimed.record.attempt.request_id,
            ADMISSION, "UPDATE_REFS", application_errors=("forged",),
            expected_old_rejected=True,
            rejection_evidence_id="artifact:sha256:" + "f" * 64,
        )
        before_reads = len(self.transport.read_calls)
        with self.assertRaisesRegex(GitHubJournalV3Error, "PENDING_REJECTION_EVIDENCE_UNTRUSTED"):
            self.journal.reconcile(pending)
        self.assertEqual(len(self.transport.read_calls), before_reads)


if __name__ == "__main__":
    unittest.main()
