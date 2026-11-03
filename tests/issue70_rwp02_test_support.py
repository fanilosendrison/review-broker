"""Synthetic trust roots and measured external transports; never live authority."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json

from review_broker.github_actions_identity_v3 import (
    GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3, GitHubActionsRuntimeClaimV3,
)
from review_broker.github_actions_worker_authority_v3 import WorkerExecutionContextV3, WorkerInputsV3
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import decode_journal_v2
from review_broker.pre_model_controller_v3 import ControllerAuthorizationV3, PreModelControllerV3
from review_broker.pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3
from review_broker.pre_model_dispatch_v3 import (
    InitialDispatchResultV3, InitialDispatchStatusV3, InitialDispatchTargetV3,
)
from review_broker.pre_model_worker_v3 import PreModelWorkerV3
from tests.issue68_test_support import ExactAdmissionAuthority, REPOSITORY
from tests.issue70_rwp01_test_support import MeasuredTransport
from tests.journal_v3_test_support import (
    BASE_SHA, NODE_ID, TrustedMutationAuthority, TrustedRejectionAuthority, WRITER_EVIDENCE_ID,
)

REPO_ID, RUN_ID, PRINCIPAL, JOB_ID = 1433701208, 70001, 90001, 501
PATH = ".github/workflows/v3-pre-model-worker.yml"
REF, SHA = "refs/heads/experimental-worker", "c" * 40
NAME = "Experimental v3 pre-model Worker (disarmed)"
TARGET = InitialDispatchTargetV3(PATH, REF, SHA)
BOUNDARY = "synthetic-rwp02-execution-boundary"


class MeasuredWorkerTransport(MeasuredTransport):
    def __init__(self):
        super().__init__()
        self.events, self.applied, self.attributed = [], [], set()
        self.crash_event = None
        self.crash_after_apply = False
        self.event_hook = None

    def create_ref(self, claim_ref, commit_sha):
        result = super().create_ref(claim_ref, commit_sha)
        if result.writer_evidence_id:
            self.attributed.add(commit_sha)
        return result

    def update_ref(self, update):
        event = decode_journal_v2(self.commits[update.after_oid].journal_bytes).attempt.history[-1]['event']
        self.events.append(event)
        if self.event_hook:
            self.event_hook(event)
        if self.crash_event == event and not self.crash_after_apply:
            raise RuntimeError("synthetic interruption before application")
        result = super().update_ref(update)
        with self.lock:
            if self.refs[update.name] == update.after_oid and update.after_oid not in self.applied:
                self.applied.append(update.after_oid)
            if self.crash_event == event:
                raise RuntimeError("synthetic interruption after application")
            if result.writer_evidence_id:
                self.attributed.add(update.after_oid)
        return result


class ScopedPredecessor:
    def __init__(self, transport):
        self.transport = transport

    def evidence_id(self, *, snapshot, **values):
        return WRITER_EVIDENCE_ID if snapshot.commit_sha in self.transport.attributed else None

    def permits_evidence(self, *, snapshot, evidence_id, **values):
        return snapshot.commit_sha in self.transport.attributed and evidence_id == WRITER_EVIDENCE_ID


class AuthorizedController:
    def __init__(self, admission):
        self.decision = ControllerAuthorizationV3(
            True, REPOSITORY, NODE_ID, TARGET,
            canonical_bytes(admission.journal_admission()), admission.origin_body_bytes,
        )

    def authorize(self, **values):
        return self.decision


class SyntheticDispatch:
    """The simulated HTTP side owns emission/response observations, not the caller."""
    def __init__(self):
        self.calls = []
        self.status, self.run_id, self.ambiguous = 200, RUN_ID, False
        self.response = None
        self.observation = None
        self.on_dispatch = None

    def dispatch(self, request):
        self.calls.append(request)
        if self.on_dispatch:
            self.on_dispatch()
        status = InitialDispatchStatusV3.UNRESOLVED if self.ambiguous else (
            InitialDispatchStatusV3.OBSERVED if self.run_id else InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID)
        self.response = InitialDispatchResultV3(status, self.run_id)
        self.observation = dict(request=asdict(request), http_status=self.status,
                                run_id=self.run_id, ambiguous=self.ambiguous,
                                repository_id=REPO_ID, dispatch_principal_id=PRINCIPAL,
                                emission_number=len(self.calls))
        return self.response


class SyntheticDispatchAuthority:
    """Offline trust root with external retained HTTP observations, NOT signatures.

    The retained archive is supplied as trusted fixture provenance after restart.
    A caller's receipt/hash by itself is never inserted or admitted here.
    """
    def __init__(self, transport, controller_authority):
        self.transport, self.controller_authority = transport, controller_authority
        self.archive = {}
        self.recognized = True

    def observe(self, *, request, response, transport, controller_authority, reservation):
        obs = self.transport.observation
        if (not self.recognized or transport is not self.transport
                or controller_authority is not self.controller_authority
                or not self.transport.calls or request is not self.transport.calls[-1]
                or response is not self.transport.response or obs is None
                or obs['request'] != asdict(request) or obs['http_status'] != 200
                or obs['ambiguous'] or type(obs['run_id']) is not int or obs['run_id'] < 1
                or response.run_id != obs['run_id']
                or response.status is not InitialDispatchStatusV3.OBSERVED):
            return None
        receipt = DispatchAcknowledgmentV3(
            1, "v3-initial-dispatch-acknowledgment", request.broker_repository,
            REPO_ID, request.request_id, request.attempt_id, request.claim_ref,
            request.reservation_id, 1, reservation.commit_sha, request.worker_workflow,
            request.execution_ref, request.executable_sha, obs['run_id'],
            artifact_identity(canonical_bytes(obs) + b"\n"),
        )
        self.archive[receipt.evidence_id] = dict(receipt=receipt.as_dict(), observation=obs)
        return receipt

    def authenticates(self, receipt, *, dispatch_principal_id):
        stored = self.archive.get(receipt.evidence_id)
        return (self.recognized and stored is not None
                and stored['receipt'] == receipt.as_dict()
                and stored['observation']['dispatch_principal_id'] == dispatch_principal_id
                and receipt.dispatch_response_evidence_id == artifact_identity(
                    canonical_bytes(stored['observation']) + b"\n"))

    def permits_ack(self, snapshot, receipt):
        return (self.authenticates(receipt, dispatch_principal_id=PRINCIPAL)
                and snapshot.commit_sha == receipt.reservation_commit_sha
                and snapshot.claim_ref == receipt.claim_ref
                and snapshot.writer_evidence_id is not None)

    def cold(self):
        clone = SyntheticDispatchAuthority(None, None)
        clone.archive = json.loads(canonical_bytes(self.archive))
        return clone


class SyntheticExecutionBoundary:
    def __init__(self, context):
        self.context, self.trusted = context, True

    def authenticates_context(self, context):
        return self.trusted and context == self.context


class WorkerActionsApi:
    def __init__(self):
        repo = dict(id=REPO_ID, full_name=REPOSITORY)
        self.run = dict(id=RUN_ID, run_attempt=1, workflow_id=77, name=NAME, path=PATH,
                        event="workflow_dispatch", head_sha=SHA, head_branch=REF[11:],
                        repository=repo, head_repository=dict(repo),
                        actor=dict(id=PRINCIPAL, login="dispatch-app"),
                        triggering_actor=dict(id=PRINCIPAL, login="dispatch-app"))
        self.jobs = [dict(id=JOB_ID, name="worker", run_id=RUN_ID, run_attempt=1, head_sha=SHA)]
        self.total, self.headers, self.calls = 1, {}, []

    def __call__(self, request):
        assert request.get_method() == "GET"
        self.calls.append(request.full_url)
        body = self.run if request.full_url.endswith(f"/actions/runs/{self.run['id']}") else dict(
            total_count=self.total, jobs=self.jobs)
        return HttpResponseV3(200, canonical_bytes(body), self.headers)


class WorkerScenario:
    def __init__(self, admission):
        self.admission = admission
        self.transport = MeasuredWorkerTransport()
        self.controller_authority = AuthorizedController(admission)
        self.dispatch = SyntheticDispatch()
        self.dispatch_authority = SyntheticDispatchAuthority(self.dispatch, self.controller_authority)
        self.journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            ExactAdmissionAuthority(admission.journal_admission()), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), ScopedPredecessor(self.transport),
        )
        self.controller = PreModelControllerV3(self.journal, TARGET, self.dispatch,
                                             self.controller_authority, self.dispatch_authority)
        self.expected = GitHubActionsExpectationV3(
            REPOSITORY, REPO_ID, 77, PATH, f"{REPOSITORY}/{PATH}@{REF}", REF,
            "workflow_dispatch", SHA, SHA, "worker", "worker", True, NAME,
        )
        runtime = GitHubActionsRuntimeClaimV3(
            REPOSITORY, REPO_ID, RUN_ID, 1, "worker", self.expected.workflow_ref,
            SHA, SHA, "workflow_dispatch", worker_dispatch=True,
        )
        from review_broker.journal_record_v3 import preparation_dispatch_identity
        from review_broker.identity import attempt_identity
        rid = preparation_dispatch_identity(admission.request_id,
                    attempt_identity(admission.request_id, 1), 1, admission.request_id)
        self.context = WorkerExecutionContextV3(runtime, WorkerInputsV3(admission.request_id, rid, 1),
                                                BOUNDARY, JOB_ID)
        self.boundary = SyntheticExecutionBoundary(self.context)
        self.api = WorkerActionsApi()
        self.source_acquisitions = self.real_github_effects = 0

    def worker(self, **overrides):
        values = dict(journal=self.journal, actions_reader=GitHubActionsIdentityReaderV3(
            "synthetic-token", REPOSITORY, REPO_ID, executor=self.api,
            clock=lambda: datetime(2026, 11, 3, tzinfo=timezone.utc)),
            expected=self.expected, execution_boundary=self.boundary,
            execution_boundary_id=BOUNDARY, dispatch_authority=self.dispatch_authority,
            dispatch_principal_id=PRINCIPAL)
        values.update(overrides)
        return PreModelWorkerV3(**values)

    def run(self):
        return self.worker().run(self.context)

    def seed(self):
        self.controller_result = self.controller.run(self.admission)
        return self.controller_result

    def measure(self, result):
        snapshot = self.journal.read(self.admission.request_id)
        outcome = getattr(result, 'journal_outcome', None)
        return dict(dispatches=len(self.dispatch.calls),
                    ack_attempts=self.transport.events.count('PRE_MODEL_DISPATCH_ACKNOWLEDGED'),
                    worker_attempts=self.transport.events.count('PRE_MODEL_WORKER_BOUND'),
                    committed_mutations=1+len(self.transport.applied),
                    winner=(None if outcome is None or outcome.snapshot is None
                            or result.status.value != 'COMMITTED' else dict(
                                commit_sha=outcome.snapshot.commit_sha,
                                writer_evidence_id=outcome.snapshot.writer_evidence_id,
                                worker=outcome.snapshot.record.control.worker.as_dict())),
                    journal=snapshot.record.as_dict(), status=result.status.value,
                    source_acquisitions=self.source_acquisitions, real_github_effects=self.real_github_effects)
