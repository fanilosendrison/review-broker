"""Authenticated direct A/P history, reusing the journal's transition and authorities."""
from __future__ import annotations

from dataclasses import dataclass

from .github_journal_transport_v3 import (
    GraphQLRefUpdateV3, ReadStatusV3, TransportSnapshotV3, VerifiedJournalSnapshotV3,
)
from .journal_record_v3 import encode_journal_v2
from .pre_model_control_v3 import transition_state
from .pre_model_dispatch_ack_v3 import acknowledgment_from_record
from .queue import AttemptState


def require_snapshot_origin_v3(journal, snapshot: VerifiedJournalSnapshotV3) -> None:
    if (type(snapshot) is not VerifiedJournalSnapshotV3
            or snapshot.repository != journal.repository
            or snapshot.repository_node_id != journal.repository_node_id
            or snapshot.claim_ref != journal.claim_ref(snapshot.record.attempt.request_id)
            or snapshot.journal_bytes != encode_journal_v2(snapshot.record)
            or snapshot.writer_evidence_id is None
            or journal.predecessor_authority.permits_evidence(
                repository=snapshot.repository, claim_ref=snapshot.claim_ref,
                snapshot=TransportSnapshotV3(snapshot.commit_sha, snapshot.parent_sha,
                                             snapshot.journal_bytes),
                evidence_id=snapshot.writer_evidence_id) is not True):
        raise ValueError("HISTORICAL_JOURNAL_ORIGIN_UNTRUSTED")


def read_authenticated_journal_at_v3(journal, request_id: str,
                                      commit_sha: str) -> VerifiedJournalSnapshotV3:
    if not journal._is_sha(commit_sha):
        raise ValueError("HISTORICAL_JOURNAL_SHA_INVALID")
    result = journal.transport.read_journal_commit(commit_sha)
    if (result.status is not ReadStatusV3.FOUND or result.snapshot is None
            or result.snapshot.commit_sha != commit_sha):
        raise ValueError("HISTORICAL_JOURNAL_UNAVAILABLE")
    snapshot = journal._verified(journal.claim_ref(request_id), result.snapshot)
    require_snapshot_origin_v3(journal, snapshot)
    return snapshot


@dataclass(frozen=True)
class PreparedJournalHistoryV3:
    journal: object  # Concrete journal checked below; avoids a circular import.
    admitted: VerifiedJournalSnapshotV3
    prepared: VerifiedJournalSnapshotV3
    remote_receipt_id: str
    expected: object  # Concrete expectation checked below; never archive-derived.
    dispatch_authority: object  # Injected independent provenance protocol.
    dispatch_principal_id: int

    def __post_init__(self) -> None:
        self.verify()

    def verify(self) -> None:
        from .github_journal_v3 import GitHubJournalV3
        from .github_actions_identity_v3 import GitHubActionsExpectationV3
        if type(self.journal) is not GitHubJournalV3 or type(self.expected) is not GitHubActionsExpectationV3:
            raise ValueError("HISTORICAL_CONTEXT_TYPES_INVALID")
        journal, a, p = self.journal, self.admitted, self.prepared
        for snapshot in (a, p):
            require_snapshot_origin_v3(journal, snapshot)
        control, attempt = a.record.control, a.record.attempt
        if (attempt.state is not AttemptState.ADMITTED
                or p.record.attempt.state is not AttemptState.PREPARED
                or p.parent_sha != a.commit_sha
                or p.claim_ref != a.claim_ref
                or control.generation != 1 or control.worker is None
                or control.worker.run_attempt != 1
                or attempt.invocation_count != 0 or p.record.attempt.invocation_count != 0):
            raise ValueError("HISTORICAL_PREPARED_RELATION_INVALID")
        expected = transition_state(a.record, AttemptState.PREPARED, self.remote_receipt_id,
                                    control.reservation_id, 1, control.worker)
        entries = [entry for entry in p.record.attempt.history if entry.get("state") == "PREPARED"]
        if (p.journal_bytes != encode_journal_v2(expected)
                or len(entries) != 1 or entries[0].get("evidence_ids") != [self.remote_receipt_id]
                or journal.mutation_authority.permits(GraphQLRefUpdateV3(
                    journal.repository_node_id, p.claim_ref, a.commit_sha, p.commit_sha, False),
                    p.writer_evidence_id) is not True):
            raise ValueError("HISTORICAL_PREPARED_TRANSITION_UNTRUSTED")
        ack = acknowledgment_from_record(a.record)
        bindings = [e["pre_model"]["receipt"] for e in attempt.history
                    if e.get("event") == "PRE_MODEL_WORKER_BOUND"]
        if (ack is None or len(bindings) != 1
                or type(self.dispatch_principal_id) is not int or self.dispatch_principal_id < 1
                or self.dispatch_authority.authenticates(
                    ack, dispatch_principal_id=self.dispatch_principal_id) is not True):
            raise ValueError("HISTORICAL_WORKER_OR_ACK_UNRECOGNIZED")
        binding = bindings[0]
        if (binding["request_id"] != attempt.request_id
                or binding["attempt_id"] != attempt.attempt_id
                or binding["reservation_id"] != control.reservation_id
                or binding["generation"] != 1 or binding["worker"] != control.worker.as_dict()
                or ack.claim_ref != a.claim_ref or ack.request_id != attempt.request_id
                or ack.reservation_id != control.reservation_id
                or ack.workflow_run_id != control.worker.run_id
                or ack.broker_repository != self.expected.repository
                or a.repository != self.expected.repository
                or ack.broker_repository_id != self.expected.repository_id
                or ack.worker_workflow_path != self.expected.workflow_path
                or ack.execution_ref != self.expected.workflow_execution_ref
                or ack.executable_sha != self.expected.executing_source_sha
                or ack.executable_sha != self.expected.workflow_definition_sha):
            raise ValueError("HISTORICAL_WORKER_LINKS_INVALID")
        # This is independent request admission, not a receipt hash as approval.
        recognized = journal.admission_authority.evidence_id(
            repository=a.repository, request=attempt.admission["canonical_request"],
            admission=attempt.admission)
        if recognized is None or journal.admission_authority.permits_evidence(
                repository=a.repository, request_id=attempt.request_id,
                admission=attempt.admission, evidence_id=recognized) is not True:
            raise ValueError("HISTORICAL_ADMISSION_UNRECOGNIZED")

    @classmethod
    def read(cls, journal, request_id: str, expected, dispatch_authority,
             dispatch_principal_id: int):
        p = journal.read(request_id)
        require_snapshot_origin_v3(journal, p)
        a = journal.read_at(request_id, p.parent_sha)
        if not p.record.attempt.evidence_ids:
            raise ValueError("HISTORICAL_RECEIPT_ID_MISSING")
        return cls(journal, a, p, p.record.attempt.evidence_ids[-1], expected,
                   dispatch_authority, dispatch_principal_id)
