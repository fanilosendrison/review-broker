"""Injected GitHub Actions PREPARED artifact composition, not TERMINAL_CAPTURED."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Protocol

from .identity import canonical_bytes
from .pre_model_observation_diagnostics_v3 import measured_phase_v3
from .github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from .prepared_artifact_transport_v3 import (
    BeforeEffectV3, PreparedArtifactBudgetV3, PreparedMetadataReaderV3, PreparedStorageExecutorV3,
)
from .remote_prepared_receipt_v3 import RemotePreparedReceiptV3, prepared_artifact_name_v3
from .actions_artifact_readback_v3 import download_artifact_bytes_v3, observe_named_artifact_v3


class UploadStatusV3(str, Enum):
    ACK = "ACK"
    REFUSED = "REFUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PreparedUploadResultV3:
    status: UploadStatusV3


@dataclass(frozen=True)
class PreparedUploadPlanV3:
    artifact_name: str
    inventory_bytes: bytes
    worker_context: object  # Concrete authenticated context, not an archive assertion.
    retention_days: int = 30


class PreparedActionsUploadBoundaryV3(Protocol):
    """One logical official provider operation, without overwrite/delete/broker retry.

    Live adaptation may use one pinned child with opaque provider-internal retries.
    Guards bracket that child; its completion cannot authorize the next effect.
    Historical injected RWP-04 qualification is not retroactively changed.
    """
    def upload_once(self, plan: PreparedUploadPlanV3, archive: bytes, *,
                    before_effect: BeforeEffectV3) -> PreparedUploadResultV3: ...


class PreparedArtifactUploaderV3:
    def __init__(self, boundary: PreparedActionsUploadBoundaryV3):
        self.boundary, self._lock, self._attempted = boundary, Lock(), False

    def upload_once(self, plan: PreparedUploadPlanV3, archive: bytes, *,
                    before_effect: BeforeEffectV3, failure_observer=None) -> PreparedUploadResultV3:
        with self._lock:
            if self._attempted:
                raise ValueError("PREPARED_UPLOAD_ALREADY_ATTEMPTED")
            self._attempted = True
        before_effect()
        try:
            result = self.boundary.upload_once(plan, archive, before_effect=before_effect)
        except Exception:
            result = PreparedUploadResultV3(UploadStatusV3.UNKNOWN)
        if type(result) is not PreparedUploadResultV3 or type(result.status) is not UploadStatusV3:
            result = PreparedUploadResultV3(UploadStatusV3.UNKNOWN)
        if failure_observer is not None: failure_observer.upload(self, plan, result)
        return result


class GitHubPreparedArtifactV3:
    """Read-only adapter; metadata trust is external to downloaded archive bytes."""
    def __init__(self, *, metadata: PreparedMetadataReaderV3,
                 worker_history: GitHubPreparedWorkerHistoryV3,
                 storage_executor: PreparedStorageExecutorV3,
                 budget: PreparedArtifactBudgetV3, clock):
        if (type(budget) is not PreparedArtifactBudgetV3 or metadata.budget != budget
                or worker_history.metadata is not metadata
                or not callable(storage_executor) or not callable(clock)):
            raise ValueError("PREPARED_ARTIFACT_CONFIGURATION_INVALID")
        self.metadata, self.worker_history = metadata, worker_history
        self.storage_executor, self.budget, self.clock = storage_executor, budget, clock
        self.failure_observer = None

    @measured_phase_v3('ARTIFACT_READBACK')
    def observe(self, admitted, before_effect: BeforeEffectV3, *, active_context=None):
        worker = self.worker_history.observe(admitted, before_effect, active_context=active_context)
        name = prepared_artifact_name_v3(admitted.claim_ref, worker.run_id, 1)
        return observe_named_artifact_v3(self, admitted, worker, name, before_effect)

    @measured_phase_v3('ARTIFACT_READBACK')
    def download(self, storage: dict[str, object], before_effect: BeforeEffectV3) -> bytes:
        RemotePreparedReceiptV3(canonical_bytes({"schema_version": 1,
                "evidence_type": "remote-v3-prepared-packet-binding",
                "offline_preparation_receipt_id": "artifact:sha256:" + "0" * 64,
                "storage": storage}) + b"\n")
        return download_artifact_bytes_v3(self, storage, before_effect)
