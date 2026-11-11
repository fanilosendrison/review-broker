"""Historical exact-attempt Actions observations, never a reconstructed binding receipt."""
from __future__ import annotations

from dataclasses import dataclass

from .github_actions_workflow_dispatch_v3 import (
    validate_worker_dispatch_job, validate_worker_dispatch_run,
)
from .pre_model_dispatch_ack_v3 import acknowledgment_from_record
from .prepared_artifact_transport_v3 import BeforeEffectV3, PreparedMetadataReaderV3
from .remote_prepared_receipt_v3 import api_decimal_v3, positive_json_integer_v3


@dataclass(frozen=True)
class PreparedWorkerObservationV3:
    run_id: int
    run_attempt: int
    job_id: str


class GitHubPreparedWorkerHistoryV3:
    def __init__(self, metadata: PreparedMetadataReaderV3, expected,
                 dispatch_authority, dispatch_principal_id: int):
        self.metadata, self.expected = metadata, expected
        self.dispatch_authority, self.principal = dispatch_authority, dispatch_principal_id

    def observe(self, admitted, before_effect: BeforeEffectV3, *, active_context=None):
        expected, worker = self.expected, admitted.record.control.worker
        ack = acknowledgment_from_record(admitted.record)
        bindings = [e["pre_model"]["receipt"] for e in admitted.record.attempt.history
                    if e.get("event") == "PRE_MODEL_WORKER_BOUND"]
        if (worker is None or worker.run_attempt != 1 or ack is None or len(bindings) != 1
                or ack.workflow_run_id != worker.run_id
                or ack.broker_repository != self.metadata.repository
                or ack.broker_repository != expected.repository
                or ack.broker_repository_id != expected.repository_id
                or ack.executable_sha != expected.executing_source_sha
                or ack.execution_ref != expected.workflow_execution_ref
                or ack.worker_workflow_path != expected.workflow_path
                or bindings[0]["worker"] != worker.as_dict()
                or self.dispatch_authority.authenticates(
                    ack, dispatch_principal_id=self.principal) is not True):
            raise ValueError("PREPARED_HISTORICAL_WORKER_UNTRUSTED")
        run_id = positive_json_integer_v3(worker.run_id)
        path = f"/actions/runs/{run_id}/attempts/1"
        run = self.metadata.object(self.metadata.get(path, before_effect))
        for key in ("id", "run_attempt", "workflow_id"):
            positive_json_integer_v3(run.get(key))
        for key in ("repository", "head_repository"):
            repository = run.get(key)
            if (type(repository) is not dict
                    or repository.get("full_name") != expected.repository
                    or positive_json_integer_v3(repository.get("id")) != expected.repository_id):
                raise ValueError("PREPARED_WORKER_REPOSITORY_MISMATCH")
        if (run["id"] != run_id or run["run_attempt"] != 1
                or run["workflow_id"] != expected.workflow_id
                or run.get("path") != expected.workflow_path
                or run.get("event") != expected.event_name):
            raise ValueError("PREPARED_WORKER_WORKFLOW_MISMATCH")
        for key in ("actor", "triggering_actor"):
            actor = run.get(key)
            if (type(actor) is not dict
                    or positive_json_integer_v3(actor.get("id")) != self.principal):
                raise ValueError("PREPARED_WORKER_PRINCIPAL_MISMATCH")
        validate_worker_dispatch_run(run, expected)
        jobs = self.metadata.listing(path + "/jobs", {}, "jobs", before_effect)
        for job in jobs:
            validate_worker_dispatch_job(job, run_id=run_id, run_attempt=1,
                                         source_sha=expected.executing_source_sha)
        matches = [job for job in jobs if job.get("name") == expected.job_name]
        if len(matches) != 1:
            raise ValueError("PREPARED_WORKER_JOB_AMBIGUOUS")
        job_id = api_decimal_v3(matches[0]["id"])
        if active_context is not None and (
                active_context.runtime.run_id != run_id
                or active_context.runtime.run_attempt != 1
                or api_decimal_v3(active_context.job_id) != job_id):
            raise ValueError("PREPARED_WORKER_RUNTIME_JOB_MISMATCH")
        before_effect()
        return PreparedWorkerObservationV3(run_id, 1, job_id)
