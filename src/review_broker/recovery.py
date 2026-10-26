"""Crash-recovery decisions that never infer unobserved model execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .queue import AttemptRecord, AttemptState


class PreparationRecoveryAction(str, Enum):
    ADMIT_AND_BUILD = "ADMIT_AND_BUILD"
    BUILD_FROM_ADMITTED = "BUILD_FROM_ADMITTED"
    REBUILD_PREPARED = "REBUILD_PREPARED"
    DUPLICATE_TERMINAL_OR_MODEL_CAPABLE = "DUPLICATE_TERMINAL_OR_MODEL_CAPABLE"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    RESUME_PRE_MODEL = "RESUME_PRE_MODEL"
    MARK_INDETERMINATE_AND_STOP = "MARK_INDETERMINATE_AND_STOP"
    BLOCKED_EVIDENCE_LOCATION = "BLOCKED_EVIDENCE_LOCATION"
    STOP_CODESPACE = "STOP_CODESPACE"
    RECORD_STOPPED = "RECORD_STOPPED"
    INFRASTRUCTURE_INCIDENT = "INFRASTRUCTURE_INCIDENT"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str


def decide_preparation_recovery(
    record: AttemptRecord,
    admission_evidence_id: str,
) -> PreparationRecoveryAction:
    if record.state is AttemptState.REQUESTED:
        return PreparationRecoveryAction.ADMIT_AND_BUILD
    if record.state in {AttemptState.ADMITTED, AttemptState.PREPARED}:
        if admission_evidence_id not in record.evidence_ids:
            raise ValueError("RESOLVED_REQUEST_EVIDENCE_MISMATCH")
        if record.state is AttemptState.ADMITTED:
            return PreparationRecoveryAction.BUILD_FROM_ADMITTED
        return PreparationRecoveryAction.REBUILD_PREPARED
    return PreparationRecoveryAction.DUPLICATE_TERMINAL_OR_MODEL_CAPABLE


def verify_rebuilt_packet(record: AttemptRecord, packet_evidence_id: str) -> None:
    if (
        record.state is AttemptState.PREPARED
        and packet_evidence_id not in record.evidence_ids
    ):
        raise ValueError("PREPARED_PACKET_EVIDENCE_MISMATCH")


def decide_recovery(record: AttemptRecord, *, codespace_state: str) -> RecoveryDecision:
    state = record.state
    if state in {AttemptState.REQUESTED, AttemptState.ADMITTED, AttemptState.PREPARED}:
        return RecoveryDecision(
            RecoveryAction.RESUME_PRE_MODEL,
            "No model-capable transition is recorded; resume the same durable attempt.",
        )
    if state is AttemptState.ARMED:
        return RecoveryDecision(
            RecoveryAction.MARK_INDETERMINATE_AND_STOP,
            "ARMED exists without terminal evidence; actual provider inference is unknown and must not be retried.",
        )
    if state is AttemptState.TERMINAL_CAPTURED:
        return RecoveryDecision(
            RecoveryAction.BLOCKED_EVIDENCE_LOCATION,
            "Validation is authorized, but no durable artifact locator is recorded in the journal.",
        )
    if state is AttemptState.VALIDATED:
        return RecoveryDecision(
            RecoveryAction.BLOCKED_EVIDENCE_LOCATION,
            "Publication is authorized, but no durable artifact locator is recorded in the journal.",
        )
    if state in {AttemptState.REPORTED, AttemptState.INDETERMINATE}:
        if codespace_state in {"Available", "ShuttingDown"}:
            return RecoveryDecision(RecoveryAction.STOP_CODESPACE, "Cleanup remains observable and required.")
        if codespace_state == "Shutdown":
            return RecoveryDecision(
                RecoveryAction.RECORD_STOPPED,
                "Shutdown is observed and must be bound before recording STOPPED.",
            )
        return RecoveryDecision(
            RecoveryAction.INFRASTRUCTURE_INCIDENT,
            "Codespace terminal state cannot be established.",
        )
    if state is AttemptState.STOPPED:
        if codespace_state == "Shutdown":
            return RecoveryDecision(RecoveryAction.NONE, "Attempt and Codespace are terminal.")
        return RecoveryDecision(
            RecoveryAction.INFRASTRUCTURE_INCIDENT,
            "Journal says STOPPED but external Shutdown is not observed.",
        )
    return RecoveryDecision(RecoveryAction.INFRASTRUCTURE_INCIDENT, "Unknown recovery state.")
