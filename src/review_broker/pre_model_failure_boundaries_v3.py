"""Narrow original-execution hooks; raw execution references never become receipt fields."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
import json
from threading import RLock
from urllib.parse import urlsplit

from .identity import canonical_bytes
from .pre_model_failure_evidence_v3 import FailureObservationBindingV3
from .pre_model_failure_observation_v3 import FailureObservationV3, classify_failure_fact_v3, CHECK_OPERATIONS


@dataclass(frozen=True)
class FailureBoundaryEventV3:
    phase: str
    operation: str
    fact_bytes: bytes
    source: object = field(repr=False)  # Opaque actual boundary, never serialized.
    subject: object = field(repr=False)  # Actual Request/process/plan/check inputs; may contain credentials.
    reference_id: str | None = None
    artifact_id: str | None = None
    prior_events: tuple = field(default=(), repr=False)

    @property
    def fact(self):
        return json.loads(self.fact_bytes)


class PreModelFailureCollectorV3:
    """Only independently recognized facts are candidates; no exception classifier."""
    def __init__(self, *, decision, owner, evidence, before_effect,
                 original_packet_id=None, budget=None):
        decision.require_active(owner)
        self.decision, self.owner, self.evidence, self.guard = decision, owner, evidence, before_effect
        self.binding = FailureObservationBindingV3(decision.snapshot, decision.context, original_packet_id, budget)
        self._events, self._latest, self._upload_pending = [], None, None
        self._artifact_id, self._lock = None, RLock()

    def _event(self, phase, operation, fact, source, subject, *, reference_id=None, artifact_id=None):
        event = FailureBoundaryEventV3(phase, operation, canonical_bytes(fact), source, subject,
                                      reference_id, artifact_id)
        with self._lock:
            self.decision.require_active(self.owner)
            event = replace(event, prior_events=tuple(self._events))
            self._events.append(event)
            return event

    def _recognize(self, event):
        try:
            classify_failure_fact_v3(event.phase, event.operation, event.fact)
        except ValueError:
            return None  # An outside-catalog observation is not promoted.
        self.guard()
        observation = self.evidence.authority.observe(event, self.binding, before_effect=self.guard)
        if observation is None:
            return None
        if type(observation) is not FailureObservationV3:
            raise ValueError("CLOSED_ORIGINAL_FAILURE_OBSERVATION_REQUIRED")
        self.evidence.verify_origin(observation, self.binding, self.guard)
        expected = observation.value
        if (expected["phase"] != event.phase or expected["operation"] != event.operation
                or expected["fact"] != event.fact or expected["reference_id"] != event.reference_id
                or expected["artifact_id"] != event.artifact_id):
            raise ValueError("RECOGNIZED_FAILURE_FACT_MISMATCH")
        with self._lock:
            self._latest = observation
        return observation

    def bind_reference_readers(self, readers):
        result = {}
        for reference_id, reader in readers.items():
            clone = copy.copy(reader)
            collector = self
            class ReferenceHook:
                def http(self, source, request, response, reference_id=reference_id):
                    path = urlsplit(request.full_url).path
                    if "/issues/" not in path:
                        return
                    operation = "GITHUB_ISSUE_COMMENT_GET" if "/issues/comments/" in path else "GITHUB_ISSUE_GET"
                    event = collector._event("REFERENCE_READ", operation,
                        {"kind": "HTTP_STATUS", "status": response.status}, source, request, reference_id=reference_id)
                    collector._recognize(event)
            clone.failure_observer = ReferenceHook()
            result[reference_id] = clone
        return result

    def bind_artifact_adapter(self, adapter):
        clone = copy.copy(adapter)
        clone.metadata = copy.copy(adapter.metadata)
        clone.metadata.failure_observer = self
        clone.worker_history = copy.copy(adapter.worker_history)
        clone.worker_history.metadata = clone.metadata
        clone.failure_observer = self
        return clone

    def transfer_timeout(self, repository, operation, arguments, process):
        event = self._event("SOURCE_ACQUISITION", operation,
            {"kind": "TRANSFER_TIMEOUT", "process_terminated": True}, process,
            (repository, tuple(arguments), process))
        self._recognize(event)

    def upload(self, source, plan, result):
        event = self._event("REMOTE_UPLOAD", "ACTIONS_ARTIFACT_UPLOAD",
            {"kind": "UPLOAD_RESULT", "status": result.status.value}, source, plan)
        if result.status.value == "UNKNOWN":
            with self._lock:
                self._upload_pending = event

    def _artifact_operation(self, request):
        path = urlsplit(request.full_url).path
        if "/actions/artifacts/" in path and path.endswith("/zip"):
            return "ACTIONS_ARTIFACT_DOWNLOAD"
        if path.endswith("/artifacts") or "/actions/artifacts/" in path:
            return "ACTIONS_ARTIFACT_METADATA_GET"
        return None  # Execution/job/repository authority reads are NOT artifact failures.

    def http(self, source, request, response):
        operation = self._artifact_operation(request)
        if operation:
            self._recognize(self._event("REMOTE_READ", operation,
                {"kind": "HTTP_STATUS", "status": response.status}, source, request,
                artifact_id=self._artifact_id))

    def read_timeout(self, source, request, storage=None):
        operation = "ACTIONS_ARTIFACT_DOWNLOAD" if storage is not None else self._artifact_operation(request)
        if operation:
            self._recognize(self._event("REMOTE_READ", operation, {"kind": "READ_TIMEOUT"},
                source, (request, storage), artifact_id=self._artifact_id))

    def established_artifact(self, storage):
        with self._lock:
            self._artifact_id = storage["artifact_id"]

    def verification_failed(self, check, expected_id, observed_id, source, subject,
                            expected_size=None, observed_size=None):
        self._recognize(self._event("REMOTE_RECONSTRUCTION", CHECK_OPERATIONS[check],
            {"kind": "VERIFICATION_FAILED", "check": check,
             "expected_id": expected_id, "observed_id": observed_id,
             "expected_size": expected_size, "observed_size": observed_size},
            source, subject, artifact_id=self._artifact_id))

    def packet_identity_failed(self, source, subject, calculated_id):
        original = self.binding.original_packet_id
        if original is not None and original != calculated_id:
            self.verification_failed("PACKET_ID", original, calculated_id, source, subject)

    def remote_reconstruction_complete(self):
        """Only after actual metadata/ZIP/extraction/inventory/original-packet success."""
        with self._lock:
            self._upload_pending = None

    def original_failure(self):
        with self._lock:
            pending, latest = self._upload_pending, self._latest
        if pending is not None:
            # No fallback to a read/check reason while the upload is unconfirmed.
            composite = self._event("REMOTE_UPLOAD", "ACTIONS_ARTIFACT_UPLOAD",
                {"kind": "UPLOAD_OUTCOME_UNKNOWN", "emitted": True, "reconciliation": "UNCONFIRMED"},
                pending.source, (pending, tuple(self._events)), artifact_id=self._artifact_id)
            return self._recognize(composite)
        return latest
