"""Deterministic authenticated Git transition targets; NOT GitHub author signatures."""
from __future__ import annotations

import re
from typing import Protocol

from .github_journal_transport_v3 import (
    GraphQLRefUpdateV3, ReadResultV3, ReadStatusV3, TransportSnapshotV3,
)
from .github_journal_v3 import GitHubJournalV3
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


class TransitionTargetReaderV3(Protocol):
    """Injected authenticated Git reader; provides continuity, not actor permission."""
    repository: str
    repository_node_id: str

    def before_effect(self) -> None: ...
    def read_journal_commit(self, commit_sha: str) -> ReadResultV3: ...


class GitHubJournalTransitionAuthorityV3:
    """Authenticate target continuity via exact-SHA Git reads, never historical actor identity."""
    def __init__(self, transport: TransitionTargetReaderV3):
        if (transport.repository != REPOSITORY or not callable(transport.before_effect)
                or not callable(transport.read_journal_commit)):
            raise ValueError("AUTHENTICATED_TARGET_READER_REQUIRED")
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
