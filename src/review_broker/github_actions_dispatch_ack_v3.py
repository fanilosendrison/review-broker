"""Reconstructible dispatch acknowledgment from authenticated Actions run/job and journal."""
from __future__ import annotations

from dataclasses import replace
import time

from .github_actions_workflow_dispatch_v3 import validate_worker_dispatch_run, validate_worker_dispatch_job
from .github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID, WORKER_PATH, OWNER_ID
from .identity import artifact_identity, canonical_bytes
from .pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3
from .pre_model_dispatch_v3 import InitialDispatchStatusV3


DISPATCH_LINK_FIELDS=(
    'broker_repository','broker_repository_id','request_id','attempt_id','claim_ref',
    'reservation_id','generation','reservation_commit_sha','worker_workflow_path',
    'execution_ref','executable_sha','workflow_run_id',
)


class GitHubActionsDispatchAcknowledgmentAuthorityV3:
    """No Controller-private archive. Historical verification issues no dispatch permit."""
    def __init__(self, api, expected, *, sleeper=time.sleep):
        if expected.workflow_path != WORKER_PATH or expected.repository != REPOSITORY:
            raise ValueError("WORKER_DISPATCH_EXPECTATION_REQUIRED")
        self.api, self.expected, self.sleeper = api, expected, sleeper

    def _controller(self, run_id, *, require_success):
        workflow=self.api.get('/actions/workflows/v3-pre-model-controller.yml')
        run=self.api.get(f'/actions/runs/{run_id}/attempts/1')
        e=self.expected
        if (type(run.get('id')) is not int or run['id']!=run_id
                or type(workflow.get('id')) is not int or workflow['id']<1
                or type(run.get('workflow_id')) is not int or run['workflow_id']!=workflow['id']
                or run.get('path')!='.github/workflows/v3-pre-model-controller.yml'
                or workflow.get('path')!=run['path'] or workflow.get('name')!=run.get('name')
                or run.get('event')!='workflow_dispatch' or type(run.get('run_attempt')) is not int
                or run['run_attempt']!=1 or run.get('head_sha')!=e.executing_source_sha
                or run.get('head_branch')!=e.workflow_execution_ref.removeprefix('refs/heads/')):
            raise ValueError('DISPATCH_CONTROLLER_UNRECOGNIZED')
        for key in ('repository','head_repository'):
            if (type(run.get(key,{}).get('id')) is not int or run[key]['id']!=REPOSITORY_ID
                    or run[key].get('full_name')!=REPOSITORY):
                raise ValueError('DISPATCH_CONTROLLER_REPOSITORY_MISMATCH')
        for key in ('actor','triggering_actor'):
            if type(run.get(key,{}).get('id')) is not int or run[key]['id']!=OWNER_ID:
                raise ValueError('DISPATCH_CONTROLLER_ACTOR_MISMATCH')
        jobs=self.api.metadata.listing(f'/actions/runs/{run_id}/attempts/1/jobs',{},'jobs',self.api.guard)
        matches=[j for j in jobs if j.get('name')=='controller']
        if len(matches)!=1:raise ValueError('DISPATCH_CONTROLLER_JOB_UNRECOGNIZED')
        validate_worker_dispatch_job(matches[0],run_id=run_id,run_attempt=1,source_sha=e.executing_source_sha)
        if type(matches[0].get('id')) is not int or matches[0]['id']<1:
            raise ValueError('DISPATCH_CONTROLLER_JOB_UNRECOGNIZED')
        if require_success and (run.get('status')!='completed' or run.get('conclusion')!='success'
                or matches[0].get('conclusion')!='success'):
            raise ValueError('DISPATCH_CONTROLLER_NOT_TERMINALLY_SUCCESSFUL')
        return {'controller_run_id':run_id,'controller_workflow_id':workflow['id'],
                'controller_job_id':matches[0]['id']}

    def _observation(self, receipt, controller):
        e = self.expected
        if (type(receipt) is not DispatchAcknowledgmentV3
                or receipt.broker_repository != REPOSITORY
                or receipt.broker_repository_id != REPOSITORY_ID
                or receipt.worker_workflow_path != e.workflow_path
                or receipt.execution_ref != e.workflow_execution_ref
                or receipt.executable_sha != e.executing_source_sha):
            raise ValueError("DISPATCH_RECEIPT_BINDING_INVALID")
        run = self.api.get(f"/actions/runs/{receipt.workflow_run_id}/attempts/1")
        if (type(run.get("id")) is not int or run["id"] != receipt.workflow_run_id
                or run.get("workflow_id") != e.workflow_id
                or type(run.get("workflow_id")) is not int
                or run.get("path") != WORKER_PATH or run.get("event") != "workflow_dispatch"):
            raise ValueError("DISPATCH_RUN_UNRECOGNIZED")
        for key in ("repository", "head_repository"):
            obj = run.get(key)
            if (type(obj) is not dict or obj.get("full_name") != REPOSITORY
                    or type(obj.get("id")) is not int or obj["id"] != REPOSITORY_ID):
                raise ValueError("DISPATCH_REPOSITORY_MISMATCH")
        validate_worker_dispatch_run(run, e)
        actor, triggering = run.get("actor", {}), run.get("triggering_actor", {})
        if (type(actor.get("id")) is not int or actor["id"] < 1
                or type(triggering.get("id")) is not int or triggering["id"] != actor["id"]):
            raise ValueError("DISPATCH_PRINCIPAL_UNRECOGNIZED")
        jobs = self.api.metadata.listing(f"/actions/runs/{receipt.workflow_run_id}/attempts/1/jobs",
            {}, "jobs", self.api.guard)
        matches = [job for job in jobs if job.get("name") == "worker"]
        if len(matches) != 1:
            raise ValueError("DISPATCH_JOB_UNRECOGNIZED")
        validate_worker_dispatch_job(matches[0], run_id=receipt.workflow_run_id,
            run_attempt=1, source_sha=e.executing_source_sha)
        if type(matches[0].get("id")) is not int or matches[0]["id"] < 1:
            raise ValueError("DISPATCH_JOB_UNRECOGNIZED")
        fields=receipt.as_dict()
        basis = {name:fields[name] for name in DISPATCH_LINK_FIELDS}
        basis.update(controller)
        basis.update(schema_version=1, evidence_type="github-actions-initial-dispatch-observation",
            workflow_id=e.workflow_id, run_attempt=1, event="workflow_dispatch",
            run_head_sha=run["head_sha"], run_head_branch=run["head_branch"],
            actor_id=actor["id"], triggering_actor_id=triggering["id"])
        return artifact_identity(canonical_bytes(basis) + b"\n"), actor["id"]

    def observe(self, *, request, response, transport, controller_authority, reservation):
        if (transport.authority is not controller_authority
                or transport.observed_request is not request or transport.observed_response is not response
                or response.status is not InitialDispatchStatusV3.OBSERVED
                or reservation.claim_ref != request.claim_ref
                or reservation.record.control.reservation_id != request.reservation_id
                or reservation.record.control.worker is not None):
            return None
        controller_authority.require_current()
        receipt = DispatchAcknowledgmentV3(1, "v3-initial-dispatch-acknowledgment",
            REPOSITORY, REPOSITORY_ID, request.request_id, request.attempt_id, request.claim_ref,
            request.reservation_id, 1, reservation.commit_sha, WORKER_PATH,
            request.execution_ref, request.executable_sha, response.run_id, "artifact:sha256:" + "0" * 64)
        from .pre_model_ack_start_gate_v3 import MAX_ACK_OBSERVATION_ATTEMPTS, ACK_OBSERVATION_INTERVAL_SECONDS
        for index in range(MAX_ACK_OBSERVATION_ATTEMPTS):
            try:
                controller_authority.require_current()
                controller=self._controller(controller_authority.runtime.claim.run_id,require_success=False)
                evidence, _ = self._observation(receipt,controller)
                return replace(receipt, dispatch_response_evidence_id=evidence)
            except (ValueError, RuntimeError):
                if index+1<MAX_ACK_OBSERVATION_ATTEMPTS:self.sleeper(ACK_OBSERVATION_INTERVAL_SECONDS)
        return None

    def _reconstruct(self,receipt,*,require_success):
        runs=self.api.metadata.listing('/actions/workflows/v3-pre-model-controller.yml/runs',
            {'event':'workflow_dispatch','head_sha':self.expected.executing_source_sha},
            'workflow_runs',self.api.guard)
        matches=[]
        for run in runs:
            try:
                controller=self._controller(run['id'],require_success=require_success)
                evidence,principal=self._observation(receipt,controller)
                if evidence==receipt.dispatch_response_evidence_id:matches.append(principal)
            except (ValueError,RuntimeError):continue
        if len(matches)!=1:raise ValueError('DISPATCH_OBSERVATION_OR_CONTROLLER_UNRECOGNIZED')
        return matches[0]

    def principal_id(self, receipt):
        return self._reconstruct(receipt,require_success=True)

    def authenticates(self, receipt, *, dispatch_principal_id):
        try:
            return type(dispatch_principal_id) is int and self.principal_id(receipt) == dispatch_principal_id
        except Exception:
            return False

    def permits_ack(self, snapshot, receipt):
        try:
            return (receipt.reservation_commit_sha == snapshot.commit_sha
                and receipt.claim_ref == snapshot.claim_ref
                and receipt.request_id == snapshot.record.attempt.request_id
                and receipt.reservation_id == snapshot.record.control.reservation_id
                and snapshot.record.control.worker is None
                and self._reconstruct(receipt,require_success=False) > 0)
        except Exception:
            return False
