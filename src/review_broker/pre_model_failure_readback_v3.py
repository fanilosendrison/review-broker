"""Read-only authenticated A/B failure history and original-cause reconstruction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .github_journal_transport_v3 import GraphQLRefUpdateV3, OutcomeStatusV3, VerifiedJournalSnapshotV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import encode_journal_v2
from .pre_model_control_v3 import block_pre_model
from .pre_model_failure_domain_v3 import require_failure_predecessor_v3
from .pre_model_failure_evidence_v3 import (
    PreModelFailureEvidenceV3, FailureObservationBindingV3, FailureEvidenceRejectedV3,
)
from .pre_model_failure_v3 import blocked_failure_receipt_v3
from .prepared_journal_history_v3 import require_snapshot_origin_v3, require_journal_admission_origin_v3
from .queue import AttemptState

if TYPE_CHECKING:
    from .github_journal_v3 import GitHubJournalV3


@dataclass(frozen=True)
class HistoricalPreModelFailureV3:
    journal: GitHubJournalV3
    admitted: VerifiedJournalSnapshotV3
    blocked: VerifiedJournalSnapshotV3

    def __post_init__(self):
        self.verify()

    @property
    def receipt(self):
        return self.blocked.record.attempt.history[-1]['pre_model']['receipt']

    def verify(self):
        from .github_journal_v3 import GitHubJournalV3
        if type(self.journal) is not GitHubJournalV3:
            raise ValueError("CLOSED_HISTORICAL_FAILURE_JOURNAL_REQUIRED")
        a, b = self.admitted, self.blocked
        require_snapshot_origin_v3(self.journal, a)
        require_snapshot_origin_v3(self.journal, b)
        require_journal_admission_origin_v3(self.journal, a)
        require_failure_predecessor_v3(a.record)
        if (b.parent_sha != a.commit_sha or b.claim_ref != a.claim_ref
                or b.record.attempt.state is not AttemptState.ADMITTED
                or b.record.control.disposition != 'BLOCKED'):
            raise ValueError("HISTORICAL_BLOCKED_RELATION_INVALID")
        receipt_id = b.record.control.failure_receipt_id
        expected = block_pre_model(a.record, receipt_id, self.receipt,
            a.record.control.reservation_id, 1, a.record.control.worker)
        if (b.journal_bytes != encode_journal_v2(expected)
                or self.journal.mutation_authority.permits(GraphQLRefUpdateV3(
                    a.repository_node_id, a.claim_ref, a.commit_sha, b.commit_sha, False),
                    b.writer_evidence_id) is not True):
            raise ValueError("HISTORICAL_BLOCKED_TRANSITION_UNTRUSTED")

    @classmethod
    def read(cls, journal, request_id, *, blocked_commit_sha=None):
        b = journal.read(request_id) if blocked_commit_sha is None else journal.read_at(request_id, blocked_commit_sha)
        require_snapshot_origin_v3(journal, b)
        if b.record.control.disposition != 'BLOCKED':
            raise ValueError("HISTORICAL_BLOCKED_REQUIRED")
        return cls(journal, journal.read_at(request_id, b.parent_sha), b)


@dataclass(frozen=True)
class PreModelFailureReadbackV3:
    status: OutcomeStatusV3
    state: str
    disposition: str
    failure_observation: str
    reason: str
    receipt_id: str | None = None
    observation_id: str | None = None
    observed_at: str | None = None
    classification: str | None = None
    reason_code: str | None = None


def read_pre_model_failure_v3(*, journal, request_id: str, evidence: PreModelFailureEvidenceV3,
                              blocked_commit_sha=None) -> PreModelFailureReadbackV3:
    """No ticket/capture/selection/upload/persistence/mutation entry is called."""
    try:
        history = HistoricalPreModelFailureV3.read(journal, request_id, blocked_commit_sha=blocked_commit_sha)
    except Exception:
        return PreModelFailureReadbackV3(OutcomeStatusV3.UNRESOLVED, 'UNCONFIRMED', 'UNCONFIRMED',
                                         'UNAVAILABLE', 'HISTORICAL_BLOCKED_NOT_AUTHENTICATED')
    a, b, receipt = history.admitted, history.blocked, history.receipt
    proof, reason = 'UNAVAILABLE', 'BLOCKED_COMMITTED_CAUSE_UNAVAILABLE'
    try:
        if type(evidence) is not PreModelFailureEvidenceV3:
            raise ValueError('CLOSED_FAILURE_EVIDENCE_REQUIRED')
        binding = evidence.authority.historical_binding(a, receipt['observation_evidence_id'], before_effect=history.verify)
        if type(binding) is not FailureObservationBindingV3 or binding.snapshot != a:
            raise FailureEvidenceRejectedV3('HISTORICAL_FAILURE_BINDING_INVALID')
        observation = evidence.read_original(receipt['observation_evidence_id'], binding, history.verify)
        rebuilt = blocked_failure_receipt_v3(a, observation)
        if (canonical_bytes(rebuilt) != canonical_bytes(receipt)
                or artifact_identity(canonical_bytes(rebuilt)+b'\n') != b.record.control.failure_receipt_id):
            raise FailureEvidenceRejectedV3('HISTORICAL_FAILURE_RECEIPT_DIVERGED')
        proof, reason = 'VERIFIED', 'HISTORICAL_BLOCKED_AND_ORIGINAL_CAUSE_VERIFIED'
    except ValueError:
        proof, reason = 'REJECTED', 'BLOCKED_COMMITTED_CAUSE_REJECTED'
    except Exception:
        proof, reason = 'UNAVAILABLE', 'BLOCKED_COMMITTED_CAUSE_UNAVAILABLE'
    return PreModelFailureReadbackV3(OutcomeStatusV3.COMMITTED, 'ADMITTED', 'BLOCKED', proof, reason,
        b.record.control.failure_receipt_id, receipt['observation_evidence_id'], receipt['observed_at'],
        receipt['classification'], receipt['reason_code'])
