"""Injected GitHub Actions PREPARED artifact composition, not TERMINAL_CAPTURED."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
from threading import Lock
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import Request

from .artifact_locator import _timestamp
from .identity import canonical_bytes
from .github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from .prepared_artifact_transport_v3 import (
    BeforeEffectV3, PreparedArtifactBudgetV3, PreparedMetadataReaderV3, PreparedStorageExecutorV3,
)
from .remote_prepared_receipt_v3 import (
    RemotePreparedReceiptV3, api_decimal_v3, positive_json_integer_v3, prepared_artifact_name_v3,
)


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
    """Official Actions artifact mechanism integration; no invented REST POST.

    One logical call, no overwrite, deletion or internal retry. Guard EVERY
    internal external call. A lost response may leave a created object behind.
    """
    def upload_once(self, plan: PreparedUploadPlanV3, archive: bytes, *,
                    before_effect: BeforeEffectV3) -> PreparedUploadResultV3: ...


class PreparedArtifactUploaderV3:
    def __init__(self, boundary: PreparedActionsUploadBoundaryV3):
        self.boundary, self._lock, self._attempted = boundary, Lock(), False

    def upload_once(self, plan: PreparedUploadPlanV3, archive: bytes, *,
                    before_effect: BeforeEffectV3) -> PreparedUploadResultV3:
        with self._lock:
            if self._attempted:
                raise ValueError("PREPARED_UPLOAD_ALREADY_ATTEMPTED")
            self._attempted = True
        before_effect()
        try:
            result = self.boundary.upload_once(plan, archive, before_effect=before_effect)
        except Exception:
            return PreparedUploadResultV3(UploadStatusV3.UNKNOWN)
        if type(result) is not PreparedUploadResultV3 or type(result.status) is not UploadStatusV3:
            return PreparedUploadResultV3(UploadStatusV3.UNKNOWN)
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

    def observe(self, admitted, before_effect: BeforeEffectV3, *, active_context=None):
        expected = self.worker_history.expected
        worker = self.worker_history.observe(admitted, before_effect, active_context=active_context)
        repository = self.metadata.object(self.metadata.get("", before_effect))
        if (repository.get("full_name") != admitted.repository
                or repository.get("node_id") != admitted.repository_node_id
                or positive_json_integer_v3(repository.get("id")) != expected.repository_id):
            raise ValueError("PREPARED_ARTIFACT_REPOSITORY_MISMATCH")
        name = prepared_artifact_name_v3(admitted.claim_ref, worker.run_id, 1)
        artifacts = self.metadata.listing(f"/actions/runs/{worker.run_id}/artifacts",
                                          {"name": name}, "artifacts", before_effect)
        if any(item.get("name") != name for item in artifacts):
            raise ValueError("PREPARED_ARTIFACT_FILTER_MISMATCH")
        if len(artifacts) != 1:
            raise ValueError("PREPARED_ARTIFACT_UNAVAILABLE_OR_AMBIGUOUS")
        item = artifacts[0]
        run = item.get("workflow_run")
        if type(run) is not dict:
            raise ValueError("PREPARED_ARTIFACT_RUN_MISSING")
        if (positive_json_integer_v3(run.get("id")) != worker.run_id
                or positive_json_integer_v3(run.get("repository_id")) != expected.repository_id
                or positive_json_integer_v3(run.get("head_repository_id")) != expected.repository_id
                or run.get("head_sha") != expected.executing_source_sha):
            raise ValueError("PREPARED_ARTIFACT_RUN_MISMATCH")
        size = positive_json_integer_v3(item.get("size_in_bytes"))
        if size > self.budget.max_archive_bytes:
            raise ValueError("PREPARED_ARTIFACT_ARCHIVE_BUDGET")
        created = _timestamp(item.get("created_at"), "PREPARED_CREATED_AT_INVALID")
        expires = _timestamp(item.get("expires_at"), "PREPARED_EXPIRES_AT_INVALID")
        now = self.clock()
        if (type(now) is not datetime or now.tzinfo is None or created >= expires
                or item.get("expired") is not False or now >= expires):
            raise ValueError("PREPARED_ARTIFACT_EXPIRED_OR_TIME_INVALID")
        storage = {
            "backend": "github-actions-artifact", "repository": expected.repository,
            "repository_id": expected.repository_id, "workflow_run_id": worker.run_id,
            "workflow_run_attempt": 1, "workflow_id": expected.workflow_id,
            "workflow_path": expected.workflow_path, "execution_ref": expected.workflow_execution_ref,
            "executable_sha": expected.executing_source_sha, "verified_worker_job_id": worker.job_id,
            "artifact_id": api_decimal_v3(item.get("id")), "artifact_name": name,
            "artifact_digest": item.get("digest"), "artifact_size_in_bytes": size,
            "created_at": item.get("created_at"), "expires_at": item.get("expires_at"),
        }
        return storage

    def download(self, storage: dict[str, object], before_effect: BeforeEffectV3) -> bytes:
        # Validate the exact storage schema before using any endpoint or size.
        RemotePreparedReceiptV3(canonical_bytes({"schema_version": 1,
                "evidence_type": "remote-v3-prepared-packet-binding",
                "offline_preparation_receipt_id": "artifact:sha256:" + "0" * 64,
                "storage": storage}) + b"\n")
        response = self.metadata.get(f"/actions/artifacts/{storage['artifact_id']}/zip", before_effect)
        locations = [v for k, v in response.headers.items() if k.lower() == "location"]
        if response.status != 302 or len(locations) != 1:
            raise ValueError("PREPARED_ARCHIVE_REDIRECT_REQUIRED")
        destination = urlsplit(locations[0])
        host = destination.hostname or ""
        if (destination.scheme != "https" or destination.username or destination.password
                or destination.port not in {None, 443} or destination.fragment
                or not destination.path.startswith("/")
                or not any(host.endswith("." + suffix) and host != suffix for suffix in (
                    "blob.core.windows.net", "actions.githubusercontent.com"))):
            raise ValueError("PREPARED_ARCHIVE_REDIRECT_INVALID")
        # A new Request has no GitHub authorization, cookies or shared opener state.
        request = Request(locations[0], method="GET")
        chunks, count, digest = [], 0, hashlib.sha256()
        try:
            before_effect()
            stream = iter(self.storage_executor(request, max_bytes=self.budget.max_archive_bytes))
            while True:
                before_effect()
                try:
                    chunk = next(stream)
                except StopIteration:
                    break
                if type(chunk) is not bytes:
                    raise ValueError("PREPARED_ARCHIVE_CHUNK_INVALID")
                count += len(chunk)
                if count > self.budget.max_archive_bytes or count > storage["artifact_size_in_bytes"]:
                    raise ValueError("PREPARED_ARCHIVE_SIZE_MISMATCH")
                digest.update(chunk)
                chunks.append(chunk)
        except Exception:
            # Storage exceptions can contain signed URLs. Never surface their text.
            raise ValueError("PREPARED_ARCHIVE_READ_UNAVAILABLE_OR_INVALID") from None
        if count != storage["artifact_size_in_bytes"] or "sha256:" + digest.hexdigest() != storage["artifact_digest"]:
            raise ValueError("PREPARED_ARCHIVE_DIGEST_OR_SIZE_MISMATCH")
        before_effect()
        return b"".join(chunks)
