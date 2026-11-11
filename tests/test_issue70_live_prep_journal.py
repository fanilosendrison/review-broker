"""Concrete HTTP mutation evidence versus historical target continuity and lost ACKs."""
import hashlib
import json
import unittest

from tests.github_transport_live_v3_support import FakeGitHubApi, NODE_ID, PARENT, response
from tests.request_v3_test_support import (
    origin, RequesterAuthority, PrAuthority, SourceAuthority, HistoryAuthority,
)
from review_broker.admission_v3 import admit_initial_inline_v3
from review_broker.github_journal_transport_v3 import (
    GraphQLRefUpdateV3, PendingWriteV3, OutcomeStatusV3,
)
from review_broker.github_transport_live_v3 import GitHubJournalEvidenceTransportV3
from review_broker.github_journal_transition_authority_v3 import (
    GitHubJournalTransitionAuthorityV3, transition_target_identity_v3,
)
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.journal_record_v3 import initial_record, encode_journal_v2
from review_broker.pre_model_control_v3 import reserve_initial


class JournalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.admission = admit_initial_inline_v3(origin(), broker_issue_number=51,
            expected_broker_issue_id=6106789428, expected_requester_id=30498238,
            requester_authority=RequesterAuthority(), pr_authority=PrAuthority(),
            source_authority=SourceAuthority(), history_authority=HistoryAuthority())
        self.record = initial_record(self.admission.request_id, self.admission.journal_admission())
        self.ref = GitHubJournalV3.claim_ref(self.admission.request_id)
        self.api = FakeGitHubApi()
        self.before, _ = self.api.install_journal(self.ref, encode_journal_v2(self.record))
        self.after = self.api.install_successor(self.before, content=encode_journal_v2(reserve_initial(self.record)))
        self.guard_calls = 0
        def guard(): self.guard_calls += 1
        self.transport = GitHubJournalEvidenceTransportV3("fake-token", before_effect=guard, executor=self.api)
        self.authority = GitHubJournalTransitionAuthorityV3(self.transport)
        self.update = GraphQLRefUpdateV3(NODE_ID, self.ref, self.before, self.after, False)

    def target(self, before=None, after=None):
        return transition_target_identity_v3(repository=self.transport.repository,
            repository_node_id=NODE_ID, claim_ref=self.ref,
            predecessor_sha=before or self.before, successor_sha=after or self.after)

    def test_exact_closed_identity_independent_oracle(self):
        basis = {"schema_version": 1, "evidence_type": "github-v3-journal-transition-target",
            "repository": "fanilosendrison/review-broker", "repository_node_id": NODE_ID,
            "claim_ref": self.ref, "predecessor_sha": self.before, "successor_sha": self.after}
        expected = "artifact:sha256:" + hashlib.sha256(
            json.dumps(basis, sort_keys=True, separators=(",", ":")).encode() + b"\n").hexdigest()
        self.assertEqual(self.target(), expected)

    def test_J01_J02_exact_create_ack_only(self):
        result = self.transport.create_ref(self.ref, self.before)
        self.assertEqual(result.writer_evidence_id, self.target(PARENT, self.before))
        self.api.raise_on = ("POST", "https://api.github.com/repos/fanilosendrison/review-broker/git/refs")
        self.assertIsNone(self.transport.create_ref(self.ref, self.before).writer_evidence_id)
        self.api.raise_on = None
        self.api.create_ref_body = {"ref": self.ref, "object": {"type": "commit", "sha": "f" * 40}}
        self.assertIsNone(self.transport.create_ref(self.ref, self.before).writer_evidence_id)

    def test_J03_J04_J05_exact_graphql_ack_only(self):
        result = self.transport.update_ref(self.update)
        self.assertEqual(result.writer_evidence_id, self.target())
        self.assertTrue(self.authority.permits(self.update, result.writer_evidence_id))
        self.assertGreater(self.guard_calls, 0)
        self.api.graphql_body = {"data": {"updateRefs": None}, "errors": [{"message": "failed"}]}
        self.assertIsNone(self.transport.update_ref(self.update).writer_evidence_id)
        self.api.raise_graphql_mutation = True
        self.assertIsNone(self.transport.update_ref(self.update).writer_evidence_id)

    def test_J06_J12_J13_equal_target_after_lost_ack_stays_unresolved(self):
        self.api.raise_graphql_mutation = True
        outcome = self.transport.update_ref(self.update)
        self.assertIsNone(outcome.writer_evidence_id)
        # Independent provider oracle: applied by this/another actor while response was lost.
        self.api.refs[self.ref] = self.after
        class DenyAdmission:
            def permits_evidence(self, **kwargs): return False
        journal = GitHubJournalV3(self.transport.repository, NODE_ID, PARENT, self.transport,
            DenyAdmission(), self.authority, self.authority, self.authority)
        pending = PendingWriteV3(self.transport.repository, self.ref, self.before,
            self.after, self.admission.request_id, self.admission.journal_admission(), "UPDATE_REFS")
        before = self.api.mutation_calls
        result = journal.reconcile(pending)
        self.assertEqual(result.status, OutcomeStatusV3.UNRESOLVED)
        self.assertEqual(result.pending, pending)
        self.assertIsNone(result.pending.writer_evidence_id)
        self.assertEqual(self.api.mutation_calls, before)
        self.assertEqual(result.snapshot.commit_sha, self.after)
        self.assertIsNotNone(result.snapshot.writer_evidence_id)  # continuity is NOT writer ACK

    def test_J07_J09_wrong_parent_or_force_rejected(self):
        for update in (GraphQLRefUpdateV3(NODE_ID, self.ref, PARENT, self.after),
                GraphQLRefUpdateV3(NODE_ID, self.ref, self.before, self.after, True)):
            before = self.api.mutation_calls
            with self.assertRaises(RuntimeError): self.transport.update_ref(update)
            self.assertEqual(self.api.mutation_calls, before)

    def test_J10_history_recomputes_and_compares_exact_authenticated_bytes(self):
        snapshot = self.transport.read_journal_commit(self.after).snapshot
        self.assertEqual(self.authority.evidence_id(repository=self.transport.repository,
            claim_ref=self.ref, snapshot=snapshot), self.target())
        from dataclasses import replace
        wrong = replace(snapshot, journal_bytes=encode_journal_v2(self.record))
        self.assertIsNone(self.authority.evidence_id(repository=self.transport.repository,
            claim_ref=self.ref, snapshot=wrong))

    def test_J11_identity_never_substitutes_for_actor_guard(self):
        self.target()
        def refuse(): raise ValueError("no current actor permission")
        self.transport.before_effect = refuse
        before = self.api.mutation_calls
        with self.assertRaises(RuntimeError): self.transport.update_ref(self.update)
        self.assertEqual(self.api.mutation_calls, before)
