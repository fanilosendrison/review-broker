"""Bounded injected original-observation retention and independent provenance contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol

from .github_actions_worker_authority_v3 import WorkerExecutionContextV3
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .identity import artifact_identity
from .pre_model_failure_observation_v3 import FailureObservationV3, valid_failure_observation_identity_v3
from .prepared_artifact_transport_v3 import PreparedArtifactBudgetV3

BeforeEffectV3 = Callable[[], None]


class FailureEvidenceUnavailableV3(RuntimeError):
    pass


class FailureEvidenceRejectedV3(ValueError):
    pass


class FailureRetentionStatusV3(str, Enum):
    ACK = "ACK"
    REFUSED = "REFUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FailureRetentionResultV3:
    status: FailureRetentionStatusV3


@dataclass(frozen=True)
class FailureObservationBindingV3:
    snapshot: VerifiedJournalSnapshotV3
    context: WorkerExecutionContextV3 | None = field(default=None, repr=False)
    original_packet_id: str | None = None
    budget: PreparedArtifactBudgetV3 | None = None

    def require(self, observation: FailureObservationV3):
        if type(observation) is not FailureObservationV3:
            raise FailureEvidenceRejectedV3("CLOSED_FAILURE_OBSERVATION_REQUIRED")
        observation.require_links(self.snapshot, original_packet_id=self.original_packet_id, budget=self.budget)


class FailureObservationAuthorityV3(Protocol):
    """External execution corpus, NOT packet-owned or populated by an archive put.

    observe must confront the actual emitted operation, endpoint/repository/object
    or plan and original timestamp against independently owned facts. verify must
    recognize the same original facts after restart. Both guard every internal
    external read. The transient boundary event may contain opaque execution
    references; never serialize/log headers, signed URLs or full commands.
    """
    def observe(self, event, binding: FailureObservationBindingV3, *,
                before_effect: BeforeEffectV3) -> FailureObservationV3 | None: ...

    def verify(self, observation: FailureObservationV3, binding: FailureObservationBindingV3, *,
               before_effect: BeforeEffectV3) -> None: ...

    def historical_binding(self, snapshot: VerifiedJournalSnapshotV3, evidence_id: str, *,
                           before_effect: BeforeEffectV3) -> FailureObservationBindingV3:
        """Recover original packet/transport bounds from external provenance, not payload."""
        ...


class FailureObservationArchiveV3(Protocol):
    """Explicit immutable external store; no live implementation or fallback here."""
    def put_once(self, evidence_id: str, raw: bytes, *,
                 before_effect: BeforeEffectV3) -> FailureRetentionResultV3: ...

    def read(self, evidence_id: str, *, max_bytes: int,
             before_effect: BeforeEffectV3) -> bytes | None: ...


@dataclass(frozen=True)
class PreModelFailureEvidenceV3:
    authority: FailureObservationAuthorityV3
    archive: FailureObservationArchiveV3
    max_observation_bytes: int

    def __post_init__(self):
        if (type(self.max_observation_bytes) is not int or self.max_observation_bytes < 1
                or self.authority is None or self.archive is None):
            raise ValueError("FAILURE_EVIDENCE_CONFIGURATION_INVALID")

    def verify_origin(self, observation, binding, before_effect):
        binding.require(observation)
        if len(observation.canonical_bytes) > self.max_observation_bytes:
            raise FailureEvidenceRejectedV3("FAILURE_OBSERVATION_BUDGET_EXCEEDED")
        before_effect()
        if self.authority.verify(observation, binding, before_effect=before_effect) is not None:
            raise FailureEvidenceRejectedV3("FAILURE_OBSERVATION_RECOGNITION_CONTRACT_INVALID")
        before_effect()

    def read_original(self, evidence_id, binding, before_effect):
        if not valid_failure_observation_identity_v3(evidence_id):
            raise FailureEvidenceRejectedV3("FAILURE_OBSERVATION_ID_INVALID")
        before_effect()
        raw = self.archive.read(evidence_id, max_bytes=self.max_observation_bytes, before_effect=before_effect)
        before_effect()
        if raw is None:
            raise FailureEvidenceUnavailableV3("ORIGINAL_FAILURE_OBSERVATION_UNAVAILABLE")
        if (type(raw) is not bytes or len(raw) > self.max_observation_bytes
                or artifact_identity(raw) != evidence_id):
            raise FailureEvidenceRejectedV3("ORIGINAL_FAILURE_OBSERVATION_BYTES_REJECTED")
        try:
            observation = FailureObservationV3(raw)
            self.verify_origin(observation, binding, before_effect)
        except FailureEvidenceUnavailableV3:
            raise
        except ValueError as exc:
            raise FailureEvidenceRejectedV3("ORIGINAL_FAILURE_OBSERVATION_REJECTED") from exc
        return observation

    def retain_original(self, observation, binding, before_effect):
        self.verify_origin(observation, binding, before_effect)
        before_effect()
        try:
            result = self.archive.put_once(observation.evidence_id, observation.canonical_bytes,
                                            before_effect=before_effect)
        except Exception:
            result = FailureRetentionResultV3(FailureRetentionStatusV3.UNKNOWN)
        if type(result) is FailureRetentionResultV3 and result.status is FailureRetentionStatusV3.REFUSED:
            raise FailureEvidenceUnavailableV3("FAILURE_OBSERVATION_RETENTION_REFUSED")
        # ACK loss grants only this bounded read, never another put.
        restored = self.read_original(observation.evidence_id, binding, before_effect)
        if restored.canonical_bytes != observation.canonical_bytes:
            raise FailureEvidenceRejectedV3("FAILURE_OBSERVATION_RETENTION_CHANGED")
        self.verify_origin(restored, binding, before_effect)
        return restored
