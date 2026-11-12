"""One bounded read-only reconciliation of an existing journal operation."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .github_journal_transport_v3 import (
    GraphQLRefUpdateV3, JournalOutcomeV3, OutcomeStatusV3, PendingWriteV3,
    ReadStatusV3, TransportSnapshotV3,
)

if TYPE_CHECKING:
    from .github_journal_v3 import GitHubJournalV3


def reconcile_pending_write_v3(self: GitHubJournalV3, pending: PendingWriteV3) -> JournalOutcomeV3:
    """Validate pending authority, then observe only; never repeat a mutation."""
    from .github_journal_v3 import GitHubJournalV3Error

    if pending.repository != self.repository:
        raise GitHubJournalV3Error("PENDING_REPOSITORY_MISMATCH")
    if pending.claim_ref != self.claim_ref(pending.request_id):
        raise GitHubJournalV3Error("PENDING_CLAIM_REF_MISMATCH")
    if not self._is_sha(pending.intended_sha):
        raise GitHubJournalV3Error("PENDING_INTENDED_SHA_INVALID")
    if pending.mutation_kind not in {"CREATE_REF", "UPDATE_REFS"}:
        raise GitHubJournalV3Error("PENDING_MUTATION_KIND_INVALID")
    if pending.mutation_kind == "CREATE_REF":
        if (pending.creation_evidence_id is None
                or not self.admission_authority.permits_evidence(
                    repository=self.repository, request_id=pending.request_id,
                    admission=pending.admission,
                    evidence_id=pending.creation_evidence_id,
                )):
            raise GitHubJournalV3Error("PENDING_CREATION_EVIDENCE_UNTRUSTED")
    if pending.mutation_kind == "UPDATE_REFS":
        if pending.predecessor_sha is None or not self._is_sha(pending.predecessor_sha):
            raise GitHubJournalV3Error("PENDING_PREDECESSOR_SHA_INVALID")
        update = GraphQLRefUpdateV3(
            self.repository_node_id, pending.claim_ref,
            pending.predecessor_sha, pending.intended_sha, False,
        )
        if (pending.writer_evidence_id is not None
                and not self.mutation_authority.permits(
                    update, pending.writer_evidence_id
                )):
            raise GitHubJournalV3Error("PENDING_WRITER_EVIDENCE_UNTRUSTED")
        if (pending.expected_old_rejected
                and (pending.rejection_evidence_id is None
                     or not self.rejection_authority.permits(
                         update, pending.rejection_evidence_id
                     ))):
            raise GitHubJournalV3Error("PENDING_REJECTION_EVIDENCE_UNTRUSTED")
    try:
        read = self.transport.read_claim(pending.claim_ref)
        if read.status is not ReadStatusV3.FOUND or read.snapshot is None:
            return JournalOutcomeV3(
                OutcomeStatusV3.UNRESOLVED, pending=pending,
                reason="READBACK_UNAVAILABLE",
            )
        snapshot = self._verified(pending.claim_ref, read.snapshot)
    except Exception:
        # A failed observation cannot erase the already known operation identity
        # or its recognized evidence. It grants neither retry nor attribution.
        return JournalOutcomeV3(
            OutcomeStatusV3.UNRESOLVED, pending=pending, reason="READBACK_UNAVAILABLE",
        )
    if not self._matches_claim(snapshot, pending.request_id, pending.admission):
        return JournalOutcomeV3(
            OutcomeStatusV3.REJECTED, snapshot=snapshot, reason="CLAIM_IDENTITY_CONFLICT"
        )
    if pending.mutation_kind == "CREATE_REF":
        if (not pending.creation_may_reuse_existing
                and snapshot.commit_sha != pending.intended_sha):
            return JournalOutcomeV3(
                OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
                reason="CREATED_REF_EXACT_TARGET_UNRESOLVED",
            )
        evidence = (pending.writer_evidence_id
                    if snapshot.commit_sha == pending.intended_sha
                    else snapshot.writer_evidence_id)
        transport_snapshot = TransportSnapshotV3(
            snapshot.commit_sha, snapshot.parent_sha, snapshot.journal_bytes
        )
        if (evidence is None
                or not self.predecessor_authority.permits_evidence(
                    repository=self.repository, claim_ref=pending.claim_ref,
                    snapshot=transport_snapshot, evidence_id=evidence,
                )):
            return JournalOutcomeV3(
                OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
                reason="CREATED_REF_WRITER_UNATTRIBUTED",
            )
        attributed = replace(snapshot, writer_evidence_id=evidence)
        return JournalOutcomeV3(OutcomeStatusV3.COMMITTED, snapshot=attributed)
    if snapshot.commit_sha == pending.intended_sha:
        if pending.writer_evidence_id is None:
            return JournalOutcomeV3(
                OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
                reason="MUTATION_WRITER_UNATTRIBUTED",
            )
        if snapshot.parent_sha != pending.predecessor_sha:
            return JournalOutcomeV3(
                OutcomeStatusV3.REJECTED, snapshot=snapshot,
                reason="SUCCESSOR_PARENT_MISMATCH",
            )
        attributed = replace(snapshot, writer_evidence_id=pending.writer_evidence_id)
        return JournalOutcomeV3(OutcomeStatusV3.COMMITTED, snapshot=attributed)
    if pending.application_errors and pending.expected_old_rejected:
        return JournalOutcomeV3(
            OutcomeStatusV3.REJECTED, snapshot=snapshot,
            reason="GRAPHQL_EXPECTED_OLD_REJECTED",
        )
    if pending.application_errors:
        return JournalOutcomeV3(
            OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
            reason="GRAPHQL_ERROR_APPLICATION_UNRESOLVED",
        )
    reason = ("READ_AFTER_WRITE_MAY_BE_STALE"
              if pending.predecessor_sha == snapshot.commit_sha
              else "COMPETING_OR_LAGGING_READBACK")
    return JournalOutcomeV3(
        OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending, reason=reason
    )
