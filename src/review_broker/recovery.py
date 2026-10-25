"""Crash-recovery decisions that never infer unobserved model execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .queue import AttemptRecord, AttemptState


class RecoveryAction(str, Enum):
    NONE = "NONE"
    RESUME_PRE_MODEL = "RESUME_PRE_MODEL"
    MARK_INDETERMINATE_AND_STOP = "MARK_INDETERMINATE_AND_STOP"
    VALIDATE_EXISTING = "VALIDATE_EXISTING"
    PUBLISH_EXISTING = "PUBLISH_EXISTING"
    STOP_CODESPACE = "STOP_CODESPACE"
    INFRASTRUCTURE_INCIDENT = "INFRASTRUCTURE_INCIDENT"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str


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
            RecoveryAction.VALIDATE_EXISTING,
            "Validate captured evidence without another inference.",
        )
    if state is AttemptState.VALIDATED:
        return RecoveryDecision(
            RecoveryAction.PUBLISH_EXISTING,
            "Publish the already validated bounded result.",
        )
    if state in {AttemptState.REPORTED, AttemptState.INDETERMINATE}:
        if codespace_state in {"Available", "ShuttingDown"}:
            return RecoveryDecision(RecoveryAction.STOP_CODESPACE, "Cleanup remains observable and required.")
        if codespace_state == "Shutdown":
            return RecoveryDecision(RecoveryAction.NONE, "Terminal result and Shutdown are already observed.")
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
