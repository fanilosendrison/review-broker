"""Observer-only PREPARED readback and independent reconstruction; no packet builder."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .historical_policy_verification_v3 import HistoricalAuthorizedPolicyVerificationV3
from .identity import canonical_bytes
from .packet_preparation_authority_v3 import offline_packet_receipt_v3, retained_inventory_v3
from .packet_retention_v3 import load_packet_evidence_v3
from .prepared_journal_history_v3 import PreparedJournalHistoryV3
from .prepared_packet_archive_v3 import extract_prepared_packet_v3, inventory_identity_v3
from .remote_prepared_receipt_v3 import RemotePreparedReceiptV3


@dataclass(frozen=True)
class PreparedPacketReconstructionV3:
    manifest_bytes: bytes
    inventory_bytes: bytes
    offline_receipt_bytes: bytes
    remote_receipt: RemotePreparedReceiptV3

    @property
    def packet_id(self):
        import json
        return json.loads(self.manifest_bytes)["packet_id"]


def reconstruct_prepared_packet_v3(root: Path, *, history: PreparedJournalHistoryV3,
                                    source_authority, selection_authority,
                                    authenticated_storage: dict[str, object]):
    """Trust dependencies and storage observations must arrive outside the archive.

    Loading calls the actual complete Packet v2 verifier. No new source reads,
    capture, approval, construction, upload, or journal mutation are exposed.
    """
    if type(history) is not PreparedJournalHistoryV3:
        raise ValueError("CLOSED_PREPARED_HISTORY_REQUIRED")
    verification = HistoricalAuthorizedPolicyVerificationV3(
        history, source_authority, selection_authority)
    a = history.admitted
    admission, _, _, manifest = load_packet_evidence_v3(
        root, a.record.attempt.admission, policy_verification=verification)
    inventory = retained_inventory_v3(root, before_effect=verification.before_effect)
    offline = offline_packet_receipt_v3(a, manifest, inventory_identity_v3(inventory))
    receipt = RemotePreparedReceiptV3.build(offline, authenticated_storage)
    receipt.require_links(offline, history.expected,
                          authenticated_storage["verified_worker_job_id"], a.claim_ref)
    if (admission.journal_admission() != a.record.attempt.admission
            or receipt.evidence_id != history.remote_receipt_id):
        raise ValueError("HISTORICAL_REMOTE_COMMITMENT_MISMATCH")
    return PreparedPacketReconstructionV3(canonical_bytes(manifest) + b"\n",
        canonical_bytes(inventory) + b"\n", canonical_bytes(offline) + b"\n", receipt)


@dataclass(frozen=True)
class PreparedReadbackResultV3:
    journal_transition: str
    state: str
    remote_reconstruction: str
    reason: str
    reconstruction: PreparedPacketReconstructionV3 | None = None


def readback_prepared_packet_v3(*, journal, request_id: str, adapter,
                                source_authority, selection_authority,
                                destination: Path) -> PreparedReadbackResultV3:
    """A restarted observer never acquires an ADMITTED effect permit."""
    try:
        worker = adapter.worker_history
        history = PreparedJournalHistoryV3.read(journal, request_id, worker.expected,
                                               worker.dispatch_authority, worker.principal)
    except Exception:
        return PreparedReadbackResultV3("UNRESOLVED", "UNCONFIRMED", "UNAVAILABLE",
                                        "PREPARED_HISTORY_UNCONFIRMED")
    try:
        storage = adapter.observe(history.admitted, history.verify)
        raw = adapter.download(storage, history.verify)
        extract_prepared_packet_v3(raw, destination, adapter.budget, history.require_local_integrity)
        reconstruction = reconstruct_prepared_packet_v3(destination, history=history,
            source_authority=source_authority, selection_authority=selection_authority,
            authenticated_storage=storage)
        return PreparedReadbackResultV3("COMMITTED", "PREPARED", "VERIFIED",
                                        "HISTORICAL_REMOTE_RECONSTRUCTION_COMPLETE", reconstruction)
    except Exception:
        return PreparedReadbackResultV3("COMMITTED", "PREPARED", "UNAVAILABLE",
                                        "REMOTE_RECONSTRUCTION_UNAVAILABLE_OR_INVALID")
