"""Final trusted pre-model capacity decision and durable armament use case."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol

# Any denotes the existing JSON evidence object representation, validated by its owner.

from .identity import artifact_identity, canonical_bytes
from .input_capacity import CapacityError, assess_packet_capacity
from .queue import AttemptRecord, AttemptState


class CapacityJournal(Protocol):
    def get(self, request_id: str) -> AttemptRecord: ...
    def record_capacity(self, request_id: str, receipt: Mapping[str, Any]) -> AttemptRecord: ...
    def transition(self, request_id: str, state: AttemptState, evidence: list[str]) -> AttemptRecord: ...
    def record_invocation(self, request_id: str) -> AttemptRecord: ...


class CapacityRejected(CapacityError):
    """A complete, durable pre-model rejection; not a reviewer execution result."""
    def __init__(self, receipt: Mapping[str, Any]):
        self.receipt = dict(receipt)
        super().__init__("INPUT_CAPACITY_REJECTED:" + canonical_bytes(self.receipt).decode("utf-8"))


def check_prepared_capacity(
    *, journal: CapacityJournal, packet_directory: Path, request_id: str,
    packet_id: str, executing_broker_sha: str, arm: bool = False,
) -> dict[str, Any]:
    current = journal.get(request_id)
    if current.input_capacity is not None and current.input_capacity["status"] == "REJECTED":
        raise CapacityRejected(current.input_capacity)
    if current.state is not AttemptState.PREPARED or current.invocation_count != 0:
        raise CapacityError("CAPACITY_REQUIRES_UNCONSUMED_PREPARED")
    manifest, receipt = assess_packet_capacity(
        packet_directory, request_id=request_id, packet_id=packet_id,
        attempt_id=current.attempt_id, executing_broker_sha=executing_broker_sha,
    )
    if artifact_identity(canonical_bytes(manifest)) not in current.evidence_ids:
        raise CapacityError("CAPACITY_PREPARED_PACKET_EVIDENCE_MISMATCH")
    # Same-state bound metadata; immutable, idempotent, and validated by both journals.
    journal.record_capacity(request_id, receipt)
    if receipt["status"] == "REJECTED":
        raise CapacityRejected(receipt)
    if arm:
        # Re-read after journal I/O as well: the earlier receipt is not a fresh input observation.
        final_manifest, final_receipt = assess_packet_capacity(
            packet_directory, request_id=request_id, packet_id=packet_id,
            attempt_id=current.attempt_id, executing_broker_sha=executing_broker_sha,
        )
        if final_manifest != manifest or final_receipt != receipt:
            raise CapacityError("CAPACITY_INPUT_CHANGED_BEFORE_ARM")
        journal.transition(request_id, AttemptState.ARMED, [packet_id])
        journal.record_invocation(request_id)
    return receipt
