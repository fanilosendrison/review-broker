"""Extra authenticated observations for the initial v3 Worker dispatch only."""
from __future__ import annotations

from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .github_actions_identity_v3 import GitHubActionsExpectationV3

WORKER_WORKFLOW = ".github/workflows/v3-pre-model-worker.yml"


def validate_worker_dispatch_run(run: Mapping[str, object],
                                 expected: "GitHubActionsExpectationV3") -> None:
    from .github_actions_identity_v3 import GitHubActionsIdentityV3Error
    if (not expected.worker_dispatch or expected.workflow_path != WORKER_WORKFLOW
            or expected.job_key != "worker" or expected.job_name != "worker"
            or expected.workflow_ref != (
                f"{expected.repository}/{expected.workflow_path}@{expected.workflow_execution_ref}")
            or not expected.workflow_name
            or run.get("name") != expected.workflow_name
            or type(run.get("run_attempt")) is not int or run["run_attempt"] != 1
            or run.get("head_sha") != expected.executing_source_sha
            or run.get("head_branch") != expected.workflow_execution_ref.removeprefix("refs/heads/")):
        raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_WORKER_DISPATCH_MISMATCH")


def validate_worker_dispatch_job(job: Mapping[str, object], *, run_id: int,
                                 run_attempt: int, source_sha: str) -> None:
    from .github_actions_identity_v3 import GitHubActionsIdentityV3Error
    if (type(job.get("run_id")) is not int or job["run_id"] != run_id
            or type(job.get("run_attempt")) is not int or job["run_attempt"] != run_attempt
            or job.get("head_sha") != source_sha):
        raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_WORKER_JOB_MISMATCH")
