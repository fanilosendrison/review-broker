"""Snapshot-bound initial Worker authority combining three independent proofs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .github_actions_identity_v3 import (
    GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3,
    GitHubActionsRuntimeClaimV3,
)
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .identity import artifact_identity, attempt_identity, canonical_bytes
from .journal_record_v3 import WorkerIdentityV3, encode_journal_v2
from .pre_model_dispatch_ack_v3 import (
    DispatchAcknowledgmentAuthorityV3, acknowledgment_from_record,
)
from .queue import AttemptState


@dataclass(frozen=True)
class WorkerInputsV3:
    request_id: str
    reservation_id: str
    generation: int


@dataclass(frozen=True)
class WorkerExecutionContextV3:
    runtime: GitHubActionsRuntimeClaimV3
    inputs: WorkerInputsV3
    boundary_id: str
    job_id: int


class WorkerExecutionBoundaryV3(Protocol):
    """Authenticates the entire execution AND original inputs, not just a run ID.

    REST GET workflow run does not attest original dispatch inputs. A real
    boundary implementation remains separately required for operational use.
    """
    def authenticates_context(self, context: WorkerExecutionContextV3) -> bool: ...


def valid_worker_inputs(inputs: WorkerInputsV3) -> bool:
    from .github_journal_v3 import GitHubJournalV3
    from .journal_record_v3 import preparation_dispatch_identity
    try:
        GitHubJournalV3.claim_ref(inputs.request_id)
        return (type(inputs.generation) is int and inputs.generation == 1
                and inputs.reservation_id == preparation_dispatch_identity(
                    inputs.request_id, attempt_identity(inputs.request_id, 1),
                    1, inputs.request_id))
    except (TypeError, ValueError, AttributeError, RuntimeError):
        return False


def authenticate_worker_context(context: WorkerExecutionContextV3,
                                boundary: WorkerExecutionBoundaryV3,
                                expected_boundary_id: str) -> bool:
    try:
        return (type(context) is WorkerExecutionContextV3
                and type(context.inputs) is WorkerInputsV3
                and type(context.runtime) is GitHubActionsRuntimeClaimV3
                and type(context.job_id) is int and context.job_id > 0
                and isinstance(expected_boundary_id, str) and bool(expected_boundary_id)
                and context.boundary_id == expected_boundary_id
                and boundary.authenticates_context(context) is True)
    except Exception:
        return False


class _RuntimeBoundary:
    def __init__(self, context: WorkerExecutionContextV3,
                 boundary: WorkerExecutionBoundaryV3, expected_id: str):
        self.context, self.boundary, self.expected_id = context, boundary, expected_id

    def authenticates(self, claim: GitHubActionsRuntimeClaimV3) -> bool:
        return (claim == self.context.runtime and authenticate_worker_context(
            self.context, self.boundary, self.expected_id))


class GitHubActionsWorkerAuthorityV3:
    """No self-issued attestation: construction performs all injected checks."""
    def __init__(self, *, snapshot: VerifiedJournalSnapshotV3,
                 context: WorkerExecutionContextV3,
                 boundary: WorkerExecutionBoundaryV3, expected_boundary_id: str,
                 reader: GitHubActionsIdentityReaderV3,
                 expected: GitHubActionsExpectationV3,
                 dispatch_authority: DispatchAcknowledgmentAuthorityV3,
                 dispatch_principal_id: int):
        if (not authenticate_worker_context(context, boundary, expected_boundary_id)
                or not valid_worker_inputs(context.inputs)):
            raise ValueError("WORKER_EXECUTION_CONTEXT_UNAUTHENTICATED")
        if not reader.injected_transport:
            raise ValueError("WORKER_INJECTED_ACTIONS_TRANSPORT_REQUIRED")
        record, control, inputs = snapshot.record, snapshot.record.control, context.inputs
        ack = acknowledgment_from_record(record)
        if (encode_journal_v2(record) != snapshot.journal_bytes
                or snapshot.writer_evidence_id is None
                or record.attempt.state is not AttemptState.REQUESTED
                or control.generation != 1 or control.disposition != "RESERVED"
                or control.worker is not None or ack is None
                or type(inputs.generation) is not int or inputs.generation != 1
                or inputs.request_id != record.attempt.request_id
                or inputs.reservation_id != control.reservation_id
                or record.attempt.attempt_id != attempt_identity(inputs.request_id, 1)
                or ack.reservation_commit_sha != snapshot.parent_sha
                or snapshot.record.attempt.history[-1].get("event")
                != "PRE_MODEL_DISPATCH_ACKNOWLEDGED"
                or ack.claim_ref != snapshot.claim_ref
                or ack.broker_repository != snapshot.repository
                or ack.broker_repository != expected.repository
                or ack.broker_repository_id != expected.repository_id
                or ack.worker_workflow_path != expected.workflow_path
                or ack.execution_ref != expected.workflow_execution_ref
                or ack.executable_sha != expected.executing_source_sha
                or ack.executable_sha != expected.workflow_definition_sha
                or type(dispatch_principal_id) is not int or dispatch_principal_id < 1
                or dispatch_authority.authenticates(
                    ack, dispatch_principal_id=dispatch_principal_id) is not True):
            raise ValueError("WORKER_DISPATCH_ACK_OR_RESERVATION_UNTRUSTED")
        runtime = context.runtime
        if (runtime.event_name != "workflow_dispatch" or not runtime.worker_dispatch
                or expected.event_name != "workflow_dispatch" or not expected.worker_dispatch
                or runtime.run_id != ack.workflow_run_id or runtime.run_attempt != 1):
            raise ValueError("WORKER_ACKNOWLEDGED_INITIAL_RUN_REQUIRED")
        observation = reader.observe(runtime, expected, _RuntimeBoundary(
            context, boundary, expected_boundary_id,
        ))
        if (observation.actor_id != dispatch_principal_id
                or observation.triggering_actor_id != dispatch_principal_id
                or observation.job_id != context.job_id):
            raise ValueError("WORKER_PRINCIPAL_OR_JOB_UNAUTHORIZED")
        self._snapshot = snapshot
        self._worker = WorkerIdentityV3(observation.run_id, observation.run_attempt)
        self._values = dict(
            repository=snapshot.repository, request_id=record.attempt.request_id,
            attempt_id=record.attempt.attempt_id, reservation_id=control.reservation_id,
            generation=1, worker=self._worker,
        )
        self._evidence_id = artifact_identity(canonical_bytes({
            "schema_version": 1, "evidence_type": "v3-authenticated-worker-binding",
            "claim_commit_sha": snapshot.commit_sha, "claim_ref": snapshot.claim_ref,
            "ack_receipt_id": ack.evidence_id,
            "journal_bytes_id": artifact_identity(snapshot.journal_bytes),
            "actions_observation_id": observation.evidence_id,
            "context": asdict(context), "dispatch_principal_id": dispatch_principal_id,
        }) + b"\n")

    @property
    def worker(self) -> WorkerIdentityV3:
        return self._worker

    def permits_snapshot(self, snapshot: VerifiedJournalSnapshotV3) -> bool:
        return snapshot == self._snapshot

    def evidence_id(self, *, repository: str, request_id: str, attempt_id: str,
                    reservation_id: str, generation: int,
                    worker: WorkerIdentityV3) -> str | None:
        values = dict(repository=repository, request_id=request_id, attempt_id=attempt_id,
                      reservation_id=reservation_id, generation=generation, worker=worker)
        if type(generation) is int and values == self._values:
            return self._evidence_id
        return None
