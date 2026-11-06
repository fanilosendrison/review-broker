"""Deterministic authenticated Git transition targets; NOT GitHub author signatures."""
from __future__ import annotations

from dataclasses import replace
import re

from .github_journal_transport_v3 import (
    CreateRefStatusV3, GraphQLRefUpdateV3, ReadStatusV3, TransportSnapshotV3,
)
from .github_journal_v3 import GitHubJournalV3
from .github_transport_live_v3 import GitHubTransportLiveV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import decode_journal_v2

REPOSITORY = "fanilosendrison/review-broker"


def transition_target_identity_v3(*, repository: str, repository_node_id: str,
                                  claim_ref: str, predecessor_sha: str,
                                  successor_sha: str) -> str:
    if (repository != REPOSITORY or type(repository_node_id) is not str
            or not repository_node_id
            or type(claim_ref) is not str
            or re.fullmatch(r"refs/heads/review-claims-v3/[0-9a-f]{64}", claim_ref) is None
            or any(type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}", sha) is None
                   for sha in (predecessor_sha, successor_sha))):
        raise ValueError("JOURNAL_TRANSITION_TARGET_INVALID")
    return artifact_identity(canonical_bytes({
        "schema_version": 1, "evidence_type": "github-v3-journal-transition-target",
        "repository": repository, "repository_node_id": repository_node_id,
        "claim_ref": claim_ref, "predecessor_sha": predecessor_sha,
        "successor_sha": successor_sha,
    }) + b"\n")


class GitHubJournalEvidenceTransportV3(GitHubTransportLiveV3):
    """Only acknowledged operations receive evidence. Guard required on EVERY HTTP call.

    Readback equality never fills a lost result. Actor permission belongs to the
    caller's current Actions/journal guard, not the target digest or this token.
    """
    def __init__(self, token: str, *, before_effect, executor=None):
        if not callable(before_effect):
            raise ValueError("LIVE_JOURNAL_GUARD_REQUIRED")
        super().__init__(token, REPOSITORY, executor=executor)
        self.before_effect = before_effect

    def create_ref(self, claim_ref, commit_sha):
        predecessor = self._get_commit(commit_sha, require_one_parent=True)["parents"][0]["sha"]
        result = super().create_ref(claim_ref, commit_sha)
        if result.status is not CreateRefStatusV3.CREATED:
            return result
        evidence = transition_target_identity_v3(repository=self.repository,
            repository_node_id=self.repository_node_id, claim_ref=claim_ref,
            predecessor_sha=predecessor, successor_sha=commit_sha)
        return replace(result, writer_evidence_id=evidence)

    def update_ref(self, update):
        result = super().update_ref(update)
        if result.http_status != 200 or result.errors:
            return result
        evidence = transition_target_identity_v3(repository=self.repository,
            repository_node_id=update.repository_id, claim_ref=update.name,
            predecessor_sha=update.before_oid, successor_sha=update.after_oid)
        return replace(result, writer_evidence_id=evidence)


class GitHubJournalTransitionAuthorityV3:
    """Authenticate target continuity via exact-SHA Git reads, never historical actor identity."""
    def __init__(self, transport: GitHubJournalEvidenceTransportV3):
        if type(transport) is not GitHubJournalEvidenceTransportV3:
            raise ValueError("LIVE_EVIDENCE_TRANSPORT_REQUIRED")
        self.transport = transport

    def evidence_id(self, *, repository: str, claim_ref: str,
                    snapshot: TransportSnapshotV3) -> str | None:
        if repository != self.transport.repository or type(snapshot) is not TransportSnapshotV3:
            return None
        observed = self.transport.read_journal_commit(snapshot.commit_sha)
        if observed.status is not ReadStatusV3.FOUND or observed.snapshot != snapshot:
            return None
        record = decode_journal_v2(snapshot.journal_bytes)
        if claim_ref != GitHubJournalV3.claim_ref(record.attempt.request_id):
            return None
        return transition_target_identity_v3(repository=repository,
            repository_node_id=self.transport.repository_node_id, claim_ref=claim_ref,
            predecessor_sha=snapshot.parent_sha, successor_sha=snapshot.commit_sha)

    def permits_evidence(self, *, repository, claim_ref, snapshot, evidence_id):
        return (evidence_id is not None and evidence_id == self.evidence_id(
            repository=repository, claim_ref=claim_ref, snapshot=snapshot))

    def permits(self, update: GraphQLRefUpdateV3, evidence_id: str) -> bool:
        if (type(update) is not GraphQLRefUpdateV3 or update.force is not False
                or update.repository_id != self.transport.repository_node_id):
            return False
        observed = self.transport.read_journal_commit(update.after_oid)
        if (observed.status is not ReadStatusV3.FOUND or observed.snapshot is None
                or observed.snapshot.parent_sha != update.before_oid):
            return False
        return self.permits_evidence(repository=self.transport.repository,
            claim_ref=update.name, snapshot=observed.snapshot, evidence_id=evidence_id)
