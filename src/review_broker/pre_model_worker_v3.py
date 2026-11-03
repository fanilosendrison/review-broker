"""One offline initial Worker binding operation; deliberately no business continuation."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from .github_actions_identity_v3 import GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3
from .github_actions_worker_authority_v3 import (
    GitHubActionsWorkerAuthorityV3, WorkerExecutionBoundaryV3,
    WorkerExecutionContextV3, authenticate_worker_context, valid_worker_inputs,
)
from .github_journal_transport_v3 import GraphQLRefUpdateV3, JournalOutcomeV3, OutcomeStatusV3
from .github_journal_v3 import GitHubJournalV3
from .journal_record_v3 import encode_journal_v2
from .pre_model_control_v3 import register_worker
from .pre_model_dispatch_ack_v3 import (
    DispatchAcknowledgmentAuthorityV3, acknowledgment_from_record,
)


@dataclass(frozen=True)
class WorkerResultV3:
    status: OutcomeStatusV3
    reason: str
    journal_outcome: JournalOutcomeV3 | None = None


class PreModelWorkerV3:
    """Injected dependencies only. A bound Worker must stop at this return value.

    No source/packet/artifact/Codespace/model interface is accepted. The local
    attempted flag only denies retry and cannot confer durable authority.
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
        self.dispatch_authority = dispatch_authority
        self.dispatch_principal_id = dispatch_principal_id
        self._lock = Lock()
        self._attempted = False

    def run(self, context: WorkerExecutionContextV3) -> WorkerResultV3:
        with self._lock:
            if self._attempted:
                return WorkerResultV3(OutcomeStatusV3.UNRESOLVED, "OBSERVER_ONLY_NO_RETRY")
            self._attempted = True
        if not authenticate_worker_context(context, self.boundary, self.boundary_id):
            return WorkerResultV3(OutcomeStatusV3.REJECTED, "EXECUTION_CONTEXT_UNAUTHENTICATED")
        if not valid_worker_inputs(context.inputs):
            return WorkerResultV3(OutcomeStatusV3.REJECTED, "WORKER_INPUTS_INVALID")
        mutating = False
        try:
            current = self.journal.read(context.inputs.request_id)
            if current.record.control.worker is not None:
                return WorkerResultV3(OutcomeStatusV3.REJECTED, "EXISTING_WORKER_OBSERVER_ONLY")
            if acknowledgment_from_record(current.record) is None:
                return WorkerResultV3(OutcomeStatusV3.UNRESOLVED, "NO_CONFIRMED_ACK_AUTHORITY")
            authority = GitHubActionsWorkerAuthorityV3(
                snapshot=current, context=context, boundary=self.boundary,
                expected_boundary_id=self.boundary_id, reader=self.reader,
                expected=self.expected, dispatch_authority=self.dispatch_authority,
                dispatch_principal_id=self.dispatch_principal_id,
            )
            inputs, worker = context.inputs, authority.worker
            evidence = authority.evidence_id(
                repository=current.repository, request_id=inputs.request_id,
                attempt_id=current.record.attempt.attempt_id,
                reservation_id=inputs.reservation_id, generation=inputs.generation, worker=worker,
            )
            successor = register_worker(current.record, inputs.reservation_id,
                                        inputs.generation, worker, evidence)
            mutating = True
            outcome = self.journal.register_worker(current, inputs.reservation_id,
                                                   inputs.generation, worker, authority)
            after = outcome.snapshot
            if (outcome.status is OutcomeStatusV3.COMMITTED and outcome.pending is None
                    and after is not None and after.parent_sha == current.commit_sha
                    and after.journal_bytes == encode_journal_v2(successor)
                    and after.writer_evidence_id is not None
                    and self.journal.mutation_authority.permits(GraphQLRefUpdateV3(
                        current.repository_node_id, current.claim_ref,
                        current.commit_sha, after.commit_sha, False,
                    ), after.writer_evidence_id) is True):
                return WorkerResultV3(OutcomeStatusV3.COMMITTED,
                                      "RWP02_OFFLINE_WORKER_BOUND=PASS", outcome)
            status = (OutcomeStatusV3.REJECTED if outcome.status is OutcomeStatusV3.REJECTED
                      else OutcomeStatusV3.UNRESOLVED)
            return WorkerResultV3(status, "WORKER_BINDING_NOT_ATTRIBUTED", outcome)
        except Exception:
            return WorkerResultV3(OutcomeStatusV3.UNRESOLVED if mutating
                                  else OutcomeStatusV3.REJECTED,
                                  "WORKER_OPERATION_UNCONFIRMED_NO_RETRY")
