"""Fresh continuation authority; never a registration or perpetual Worker permit."""
from __future__ import annotations

import copy

from .github_actions_identity_v3 import (
    GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3,
)
from .github_actions_worker_authority_v3 import (
    WorkerExecutionBoundaryV3, WorkerExecutionContextV3,
    authenticate_worker_context, valid_worker_inputs,
)
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .github_journal_v3 import GitHubJournalV3
from .identity import attempt_identity
from .journal_record_v3 import WorkerIdentityV3, decode_journal_v2, encode_journal_v2
from .pre_model_dispatch_ack_v3 import (
    DispatchAcknowledgmentAuthorityV3, acknowledgment_from_record,
)
from .queue import AttemptState


class _CurrentRuntimeBoundary:
    def __init__(self, context: WorkerExecutionContextV3,
                 boundary: WorkerExecutionBoundaryV3, boundary_id: str):
        self.context, self.boundary, self.boundary_id = context, boundary, boundary_id

    def authenticates(self, claim: object) -> bool:
        return claim == self.context.runtime and authenticate_worker_context(
            self.context, self.boundary, self.boundary_id)


class CurrentBoundWorkerAuthorityV3:
    """Every call reads current authenticated journal and current Actions run/job.

    The original dispatch archive is independently recognized through the injected
    authority. This does not cryptographically attest an RWP-02 observation archive.
    """

    def __init__(self, *, journal: GitHubJournalV3,
                 actions_reader: GitHubActionsIdentityReaderV3,
                 expected: GitHubActionsExpectationV3,
                 execution_boundary: WorkerExecutionBoundaryV3,
                 execution_boundary_id: str,
                 dispatch_authority: DispatchAcknowledgmentAuthorityV3,
                 dispatch_principal_id: int):
        self.journal, self.reader, self.expected = journal, actions_reader, expected
        self.boundary, self.boundary_id = execution_boundary, execution_boundary_id
        self.dispatch_authority, self.principal = dispatch_authority, dispatch_principal_id

    def authenticate_context(self, context: WorkerExecutionContextV3) -> None:
        if (not authenticate_worker_context(context, self.boundary, self.boundary_id)
                or not valid_worker_inputs(context.inputs)):
            raise ValueError("CURRENT_WORKER_CONTEXT_UNAUTHENTICATED")
        if not self.reader.injected_transport:
            raise ValueError("CURRENT_WORKER_INJECTED_TRANSPORT_REQUIRED")

    def require_current(self, context: WorkerExecutionContextV3,
                        snapshot: VerifiedJournalSnapshotV3,
                        state: AttemptState) -> WorkerIdentityV3:
        self.authenticate_context(context)
        if state not in {AttemptState.REQUESTED, AttemptState.ADMITTED}:
            raise ValueError("CURRENT_WORKER_BOUNDARY_NOT_QUALIFIED")
        current = self.journal.read(context.inputs.request_id)
        if current != snapshot:
            raise ValueError("CURRENT_WORKER_STALE_JOURNAL")
        record = decode_journal_v2(snapshot.journal_bytes)
        if record.as_dict() != snapshot.record.as_dict():
            raise ValueError("CURRENT_WORKER_JOURNAL_DECODING_MISMATCH")
        control, attempt, runtime = record.control, record.attempt, context.runtime
        ack = acknowledgment_from_record(record)
        bindings = [entry["pre_model"]["receipt"] for entry in attempt.history
                    if entry.get("event") == "PRE_MODEL_WORKER_BOUND"]
        expected = self.expected
        worker = WorkerIdentityV3(runtime.run_id, runtime.run_attempt)
        if (encode_journal_v2(record) != snapshot.journal_bytes
                or snapshot.writer_evidence_id is None
                or attempt.state is not state
                or control.generation != 1 or control.disposition != "RESERVED"
                or control.failure_receipt_id is not None
                or control.worker != worker or worker.run_attempt != 1
                or attempt.request_id != context.inputs.request_id
                or attempt.attempt_id != attempt_identity(context.inputs.request_id, 1)
                or control.reservation_id != context.inputs.reservation_id
                or len(bindings) != 1 or ack is None
                or bindings[0]["worker"] != worker.as_dict()
                or bindings[0]["generation"] != 1
                or bindings[0]["reservation_id"] != control.reservation_id
                or bindings[0]["request_id"] != attempt.request_id
                or bindings[0]["attempt_id"] != attempt.attempt_id
                or ack.claim_ref != snapshot.claim_ref
                or ack.broker_repository != snapshot.repository
                or ack.broker_repository != expected.repository
                or ack.broker_repository_id != expected.repository_id
                or ack.worker_workflow_path != expected.workflow_path
                or ack.execution_ref != expected.workflow_execution_ref
                or ack.executable_sha != expected.executing_source_sha
                or ack.executable_sha != expected.workflow_definition_sha
                or ack.workflow_run_id != worker.run_id
                or type(self.principal) is not int or self.principal < 1
                or self.dispatch_authority.authenticates(
                    ack, dispatch_principal_id=self.principal) is not True
                or runtime.event_name != "workflow_dispatch" or not runtime.worker_dispatch
                or expected.event_name != "workflow_dispatch" or not expected.worker_dispatch):
            raise ValueError("CURRENT_WORKER_BINDING_OR_ACK_UNTRUSTED")
        def require_observation_boundary() -> None:
            self.authenticate_context(context)
            if self.journal.read(attempt.request_id) != snapshot:
                raise ValueError("CURRENT_WORKER_JOURNAL_MOVED")
            self.authenticate_context(context)

        reader = copy.copy(self.reader)
        executor = self.reader._executor
        def execute(request):
            require_observation_boundary()
            return executor(request)
        reader._executor = execute
        observation = reader.observe(runtime, expected, _CurrentRuntimeBoundary(
            context, self.boundary, self.boundary_id))
        if (observation.actor_id != self.principal
                or observation.triggering_actor_id != self.principal
                or observation.job_id != context.job_id
                or observation.run_id != worker.run_id or observation.run_attempt != 1):
            raise ValueError("CURRENT_WORKER_RUN_JOB_UNTRUSTED")
        # The REST observation can take time: reject journal movement during it.
        require_observation_boundary()
        return worker
