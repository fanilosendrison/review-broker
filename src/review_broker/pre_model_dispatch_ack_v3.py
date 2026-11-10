"""Canonical experimental dispatch receipts, not HTTP or Actions attestations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import re
from typing import Mapping, Protocol, TYPE_CHECKING

from .identity import artifact_identity, attempt_identity, canonical_bytes
from .pre_model_dispatch_v3 import InitialDispatchRequestV3, InitialDispatchResultV3

if TYPE_CHECKING:
    from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
    from .journal_record_v3 import JournalRecordV3, PreModelControlV3

ACK_EVENT = "PRE_MODEL_DISPATCH_ACKNOWLEDGED"


@dataclass(frozen=True)
class DispatchAcknowledgmentV3:
    schema_version: int
    evidence_type: str
    broker_repository: str
    broker_repository_id: int
    request_id: str
    attempt_id: str
    claim_ref: str
    reservation_id: str
    generation: int
    reservation_commit_sha: str
    worker_workflow_path: str
    execution_ref: str
    executable_sha: str
    workflow_run_id: int
    dispatch_response_evidence_id: str

    def __post_init__(self) -> None:
        from .journal_record_v3 import preparation_dispatch_identity
        valid = (
            type(self.schema_version) is int and self.schema_version == 1
            and self.evidence_type == "v3-initial-dispatch-acknowledgment"
            and type(self.generation) is int and self.generation == 1
            and type(self.broker_repository_id) is int and self.broker_repository_id > 0
            and type(self.workflow_run_id) is int and self.workflow_run_id > 0
        )
        patterns = {
            "broker_repository": r"[a-z0-9_.-]+/[a-z0-9_.-]+",
            "request_id": r"request:sha256:[0-9a-f]{64}",
            "attempt_id": r"attempt:sha256:[0-9a-f]{64}",
            "reservation_commit_sha": r"[0-9a-f]{40}",
            "worker_workflow_path": r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml",
            "execution_ref": r"refs/heads/[A-Za-z0-9_./-]+",
            "executable_sha": r"[0-9a-f]{40}",
            "dispatch_response_evidence_id": r"artifact:sha256:[0-9a-f]{64}",
        }
        valid = valid and all(
            isinstance(getattr(self, key), str)
            and re.fullmatch(pattern, getattr(self, key)) is not None
            for key, pattern in patterns.items()
        )
        if not valid:
            raise ValueError("DISPATCH_ACK_FIELDS_INVALID")
        if (".." in self.broker_repository or ".." in self.execution_ref
                or self.execution_ref.endswith(("/", ".", ".lock"))
                or "//" in self.execution_ref
                or self.attempt_id != attempt_identity(self.request_id, 1)
                or self.claim_ref != "refs/heads/review-claims-v3/" + self.request_id[15:]
                or self.reservation_id != preparation_dispatch_identity(
                    self.request_id, self.attempt_id, 1, self.request_id)):
            raise ValueError("DISPATCH_ACK_IDENTITY_INVALID")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def evidence_id(self) -> str:
        return artifact_identity(canonical_bytes(self.as_dict()) + b"\n")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "DispatchAcknowledgmentV3":
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("DISPATCH_ACK_CLOSED_FIELDS_REQUIRED")
        return cls(**value)

    def dispatch_request(self) -> InitialDispatchRequestV3:
        return InitialDispatchRequestV3(
            self.broker_repository, self.request_id, self.attempt_id, self.claim_ref,
            self.reservation_id, self.generation, self.worker_workflow_path,
            self.execution_ref, self.executable_sha,
        )


class DispatchAcknowledgmentAuthorityV3(Protocol):
    """Injected provenance boundary. Hash equality alone never implements it.

    observe must correlate a trusted emission and its response with this exact
    authorized Controller, transport and attributed reservation. Cold validation
    requires retained external observations, not private Worker memory.
    """
    def observe(self, *, request: InitialDispatchRequestV3,
                response: InitialDispatchResultV3, transport: object,
                controller_authority: object,
                reservation: "VerifiedJournalSnapshotV3") -> DispatchAcknowledgmentV3 | None: ...

    def permits_ack(self, snapshot: "VerifiedJournalSnapshotV3",
                    receipt: DispatchAcknowledgmentV3) -> bool: ...

    def authenticates(self, receipt: DispatchAcknowledgmentV3, *,
                      dispatch_principal_id: int) -> bool: ...


def acknowledgment_from_record(record: "JournalRecordV3") -> DispatchAcknowledgmentV3 | None:
    entries = [entry for entry in record.attempt.history if entry.get("event") == ACK_EVENT]
    if not entries:
        return None
    if len(entries) != 1:
        raise ValueError("DISPATCH_ACK_NOT_UNIQUE")
    return DispatchAcknowledgmentV3.from_dict(entries[0]["pre_model"]["receipt"])


def validate_ack_history(value: dict[str, object], control: "PreModelControlV3") -> None:
    """Strict additive validation; historical no-ACK records remain unchanged."""
    history = value["history"]
    entries = [(i, e) for i, e in enumerate(history) if e.get("event") == ACK_EVENT]
    if not entries:
        return
    if len(entries) != 1:
        raise ValueError("DISPATCH_ACK_NOT_UNIQUE")
    index, entry = entries[0]
    receipt = DispatchAcknowledgmentV3.from_dict(entry["pre_model"].get("receipt"))
    prior = history[index - 1] if index else {}
    if (receipt.request_id != value["request_id"] or receipt.attempt_id != value["attempt_id"]
            or receipt.reservation_id != control.reservation_id or control.generation != 1
            or entry["pre_model"]["generation"] != 1
            or entry["pre_model"]["reservation_id"] != receipt.reservation_id
            or prior.get("event") != "PRE_MODEL_DISPATCH_RESERVED"
            or any(e.get("event") == "PRE_MODEL_WORKER_BOUND" for e in history[:index])):
        raise ValueError("DISPATCH_ACK_HISTORY_MISMATCH")


def check_worker_ack_authority(snapshot: "VerifiedJournalSnapshotV3", authority: object) -> None:
    """Legacy synthetic bindings cannot be substituted on the new ACK path."""
    from .github_actions_worker_authority_v3 import GitHubActionsWorkerAuthorityV3
    if acknowledgment_from_record(snapshot.record) is not None:
        if (type(authority) is not GitHubActionsWorkerAuthorityV3
                or not authority.permits_snapshot(snapshot)):
            raise ValueError("AUTHENTICATED_WORKER_ACK_AUTHORITY_REQUIRED")
