"""Pure preventive authorization gate for experimental v3 Codespace effects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from .github_journal_v3 import VerifiedJournalSnapshotV3
from .identity import canonical_bytes
from .journal_record_v3 import WorkerIdentityV3, decode_journal_v2, encode_journal_v2
from .queue import AttemptState


class CodespaceEffectV3(str, Enum):
    START = "START"
    SSH = "SSH"
    COPY_TO = "COPY_TO"
    COPY_FROM = "COPY_FROM"
    REMOTE_EXECUTE = "REMOTE_EXECUTE"
    RECOVER = "RECOVER"
    STOP = "STOP"


@dataclass(frozen=True)
class CodespaceAccessRequestV3:
    broker_repository: str
    request_id: str
    attempt_id: str
    claim_ref: str
    reservation_id: str
    generation: int
    worker: WorkerIdentityV3
    codespace_identity: str
    operation: CodespaceEffectV3
    expected_admission: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.operation) is not CodespaceEffectV3:
            raise ValueError("CODESPACE_EFFECT_CLASS_INVALID")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("CODESPACE_GENERATION_INVALID")


@dataclass(frozen=True)
class TrustedWorkerContextV3:
    broker_repository: str
    request_id: str
    attempt_id: str
    claim_ref: str
    reservation_id: str
    generation: int
    worker: WorkerIdentityV3
    codespace_identity: str
    operation: CodespaceEffectV3

    def __post_init__(self) -> None:
        if type(self.operation) is not CodespaceEffectV3:
            raise ValueError("CODESPACE_EFFECT_CLASS_INVALID")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("CODESPACE_GENERATION_INVALID")


class CurrentJournalAuthorityV3(Protocol):
    """Injected authenticated proof that the supplied commit still heads the claim."""

    def is_current(self, snapshot: VerifiedJournalSnapshotV3) -> bool: ...


class TrustedContextProviderV3(Protocol):
    """Injected authenticated runtime authority; caller fields are not trusted."""

    def authenticate(self, request: CodespaceAccessRequestV3) -> TrustedWorkerContextV3 | None: ...


class ResourceOwnershipProviderV3(Protocol):
    """Separate injected ownership authority required for physical STOP."""

    def owns_resource(self, context: TrustedWorkerContextV3) -> bool: ...


@dataclass(frozen=True)
class CodespaceGateDecisionV3:
    allowed: bool
    reason: str


_EFFECT_ELIGIBLE_STATES = {
    AttemptState.PREPARED,
    AttemptState.ARMED,
    AttemptState.TERMINAL_CAPTURED,
    AttemptState.VALIDATED,
    AttemptState.REPORTED,
    AttemptState.INDETERMINATE,
}


def _same_context(request: CodespaceAccessRequestV3,
                  trusted: TrustedWorkerContextV3) -> bool:
    return (
        request.broker_repository == trusted.broker_repository
        and request.request_id == trusted.request_id
        and request.attempt_id == trusted.attempt_id
        and request.claim_ref == trusted.claim_ref
        and request.reservation_id == trusted.reservation_id
        and request.generation == trusted.generation
        and request.worker == trusted.worker
        and request.codespace_identity == trusted.codespace_identity
        and request.operation is trusted.operation
    )


def authorize_codespace_effect_v3(
    snapshot: VerifiedJournalSnapshotV3,
    request: CodespaceAccessRequestV3,
    current_journal: CurrentJournalAuthorityV3,
    trusted_contexts: TrustedContextProviderV3,
    resource_ownership: ResourceOwnershipProviderV3 | None = None,
) -> CodespaceGateDecisionV3:
    """Authorize without performing an effect; every uncertain input fails closed."""
    if type(request.operation) is not CodespaceEffectV3:
        return CodespaceGateDecisionV3(False, "CODESPACE_EFFECT_CLASS_INVALID")
    try:
        record = decode_journal_v2(snapshot.journal_bytes)
    except ValueError:
        return CodespaceGateDecisionV3(False, "JOURNAL_UNTRUSTED")
    if encode_journal_v2(snapshot.record) != snapshot.journal_bytes:
        return CodespaceGateDecisionV3(False, "JOURNAL_SNAPSHOT_MISMATCH")
    if snapshot.repository != request.broker_repository:
        return CodespaceGateDecisionV3(False, "BROKER_REPOSITORY_MISMATCH")
    expected_ref = "refs/heads/review-claims-v3/" + request.request_id.rsplit(":", 1)[-1]
    if request.claim_ref != expected_ref:
        return CodespaceGateDecisionV3(False, "V3_CLAIM_NAMESPACE_REQUIRED")
    if snapshot.claim_ref != expected_ref:
        return CodespaceGateDecisionV3(False, "CLAIM_REF_MISMATCH")
    attempt = record.attempt
    control = record.control
    if attempt.request_id != request.request_id or attempt.attempt_id != request.attempt_id:
        return CodespaceGateDecisionV3(False, "ATTEMPT_IDENTITY_MISMATCH")
    if canonical_bytes(attempt.admission) != canonical_bytes(dict(request.expected_admission)):
        return CodespaceGateDecisionV3(False, "ADMISSION_IDENTITY_MISMATCH")
    try:
        current = current_journal.is_current(snapshot)
    except Exception:
        current = False
    if type(current) is not bool or not current:
        return CodespaceGateDecisionV3(False, "CURRENT_JOURNAL_AUTHORITY_UNVERIFIED")
    prepared_committed = any(
        entry.get("state") == AttemptState.PREPARED.value
        for entry in attempt.history
    )
    if attempt.state not in _EFFECT_ELIGIBLE_STATES or not prepared_committed:
        return CodespaceGateDecisionV3(False, "COMMITTED_PREPARED_REQUIRED")
    if control.disposition != "RESERVED" or control.failure_receipt_id is not None:
        return CodespaceGateDecisionV3(False, "PREPARATION_DISPOSITION_DENIED")
    if (control.generation != request.generation
            or control.reservation_id != request.reservation_id
            or control.worker != request.worker):
        return CodespaceGateDecisionV3(False, "WORKER_GENERATION_FENCED")
    try:
        trusted = trusted_contexts.authenticate(request)
    except Exception:
        trusted = None
    if trusted is None or not _same_context(request, trusted):
        return CodespaceGateDecisionV3(False, "WORKER_AUTHORITY_UNTRUSTED")
    if request.operation is CodespaceEffectV3.STOP:
        try:
            owns_resource = (resource_ownership is not None
                             and resource_ownership.owns_resource(trusted))
        except Exception:
            owns_resource = False
        if type(owns_resource) is not bool or not owns_resource:
            return CodespaceGateDecisionV3(False, "RESOURCE_OWNERSHIP_REQUIRED")
    return CodespaceGateDecisionV3(True, "AUTHORIZED")
