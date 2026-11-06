"""Actions retention for original RWP-05 canonical observations, not their provenance."""
from __future__ import annotations

from threading import Lock

from .actions_artifact_child_v3 import GitHubActionsArtifactChildV3
from .actions_artifact_readback_v3 import download_artifact_bytes_v3, observe_named_artifact_v3
from .github_prepared_artifact_v3 import GitHubPreparedArtifactV3, UploadStatusV3
from .identity import artifact_identity
from .pre_model_failure_evidence_v3 import FailureRetentionResultV3, FailureRetentionStatusV3
from .pre_model_failure_observation_v3 import (
    FailureObservationV3, valid_failure_observation_identity_v3,
)


def failure_artifact_name_v3(evidence_id: str) -> str:
    if not valid_failure_observation_identity_v3(evidence_id):
        raise ValueError("FAILURE_ARCHIVE_ID_INVALID")
    return "rb-v3-failure-observation-" + evidence_id.removeprefix("artifact:sha256:")


class GitHubActionsFailureObservationArchiveV3:
    """One separate direct-upload lane; no BLOCKED authority, delete or overwrite.

    Metadata is independently authenticated and the exact job/attempt is observed.
    No claim that GitHub attests which job performed the upload is made. RWP-05's
    separate original observation authority and original decision remain required.
    """
    def __init__(self, *, child: GitHubActionsArtifactChildV3,
                 adapter: GitHubPreparedArtifactV3, snapshot, active_context=None,
                 original_packet_id: str | None = None):
        if (type(child) is not GitHubActionsArtifactChildV3
                or type(adapter) is not GitHubPreparedArtifactV3):
            raise ValueError("FAILURE_ARCHIVE_CONFIGURATION_INVALID")
        self.child, self.adapter = child, adapter
        self.snapshot, self.context = snapshot, active_context
        self.original_packet_id = original_packet_id
        self._lock, self._attempted, self._observed = Lock(), False, {}

    def put_once(self, evidence_id: str, raw: bytes, *, before_effect):
        with self._lock:
            if self._attempted:
                raise ValueError("FAILURE_ARCHIVE_ALREADY_ATTEMPTED")
            self._attempted = True
        name = failure_artifact_name_v3(evidence_id)
        if type(raw) is not bytes or artifact_identity(raw) != evidence_id:
            return FailureRetentionResultV3(FailureRetentionStatusV3.REFUSED)
        observation = FailureObservationV3(raw)
        observation.require_links(self.snapshot,
            original_packet_id=self.original_packet_id, budget=self.adapter.budget)
        result = self.child.upload_bytes_once(name, raw, before_effect=before_effect)
        status = {UploadStatusV3.ACK: FailureRetentionStatusV3.ACK,
            UploadStatusV3.UNKNOWN: FailureRetentionStatusV3.UNKNOWN,
            UploadStatusV3.REFUSED: FailureRetentionStatusV3.REFUSED}[result.status]
        return FailureRetentionResultV3(status)

    def read(self, evidence_id: str, *, max_bytes: int, before_effect):
        name = failure_artifact_name_v3(evidence_id)
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("FAILURE_ARCHIVE_BUDGET_INVALID")
        worker = self.adapter.worker_history.observe(self.snapshot, before_effect,
            active_context=self.context)
        storage = observe_named_artifact_v3(self.adapter, self.snapshot, worker, name, before_effect)
        if (storage["artifact_size_in_bytes"] > max_bytes
                or storage["artifact_digest"] != evidence_id.removeprefix("artifact:")):
            raise ValueError("FAILURE_ARCHIVE_METADATA_MISMATCH")
        with self._lock:
            prior = self._observed.get(evidence_id)
            if prior is not None and prior != storage:
                raise ValueError("FAILURE_ARCHIVE_IDENTITY_CHANGED")
            self._observed[evidence_id] = dict(storage)
        raw = download_artifact_bytes_v3(self.adapter, storage, before_effect)
        if artifact_identity(raw) != evidence_id or len(raw) > max_bytes:
            raise ValueError("FAILURE_ARCHIVE_BYTES_MISMATCH")
        observation = FailureObservationV3(raw)
        observation.require_links(self.snapshot,
            original_packet_id=self.original_packet_id, budget=self.adapter.budget)
        before_effect()
        return raw
