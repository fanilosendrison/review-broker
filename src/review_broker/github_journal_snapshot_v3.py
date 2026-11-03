"""Strict authenticated journal snapshot decoding, mechanically extracted."""
from __future__ import annotations

from .github_journal_transport_v3 import TransportSnapshotV3, VerifiedJournalSnapshotV3
from .journal_record_v3 import JournalRecordV3Error, decode_journal_v2

def verify_journal_snapshot(self, claim_ref: str, transport: TransportSnapshotV3) -> VerifiedJournalSnapshotV3:
    from .github_journal_v3 import GitHubJournalV3Error
    if not self._is_sha(transport.commit_sha) or not self._is_sha(transport.parent_sha):
        raise GitHubJournalV3Error("JOURNAL_COMMIT_IDENTITY_INVALID")
    try:
        record = decode_journal_v2(transport.journal_bytes)
    except JournalRecordV3Error as exc:
        raise GitHubJournalV3Error(str(exc)) from exc
    expected_ref = self.claim_ref(record.attempt.request_id)
    if claim_ref != expected_ref:
        raise GitHubJournalV3Error("JOURNAL_CLAIM_REF_MISMATCH")
    evidence = self.predecessor_authority.evidence_id(
        repository=self.repository, claim_ref=claim_ref, snapshot=transport
    )
    if evidence is not None and not (
        evidence.startswith("artifact:sha256:") and len(evidence) == 80
        and all(character in "0123456789abcdef" for character in evidence[16:])
    ):
        raise GitHubJournalV3Error("PREDECESSOR_WRITER_EVIDENCE_INVALID")
    return VerifiedJournalSnapshotV3(
        self.repository, self.repository_node_id, claim_ref,
        transport.commit_sha, transport.parent_sha,
        transport.journal_bytes, record, evidence,
    )
