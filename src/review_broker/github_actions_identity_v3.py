"""Authenticated GitHub Actions run/job observations for experimental v3 authority."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Callable, Mapping, Protocol
from urllib.parse import quote
from urllib.request import Request
from .codespace_gate_v3 import (
    CodespaceAccessRequestV3, CodespaceEffectV3, TrustedWorkerContextV3,
)
from .github_http_live_v3 import HttpExecutorV3, HttpResponseV3, urllib_executor
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import WorkerIdentityV3
_API = "https://api.github.com"
_VERSION = "2022-11-28"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_WORKFLOW_PATH = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
_EVENT = re.compile(r"^[a-z_]+$")
_SUPPORTED_EVENTS = {"pull_request", "workflow_dispatch"}
class GitHubActionsIdentityV3Error(RuntimeError):
    """The Actions execution identity could not be authenticated exactly."""
def _positive(value: object, marker: str) -> int:
    if type(value) is not int or value < 1:
        raise GitHubActionsIdentityV3Error(marker)
    return value
def _sha(value: object, marker: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise GitHubActionsIdentityV3Error(marker)
    return value
@dataclass(frozen=True)
class GitHubActionsRuntimeClaimV3:
    repository: str
    repository_id: int
    run_id: int
    run_attempt: int
    job_key: str
    workflow_ref: str
    workflow_sha: str
    checked_out_source_sha: str
    event_name: str
    pull_request_head_sha: str | None = None
    synthetic_merge_sha: str | None = None
    worker_dispatch: bool = False

    def __post_init__(self) -> None:
        numeric = (self.repository_id, self.run_id, self.run_attempt)
        strings = (self.job_key, self.workflow_ref)
        if (_REPOSITORY.fullmatch(self.repository) is None
                or any(type(value) is not int or value < 1 for value in numeric)
                or any(not isinstance(value, str) or not value for value in strings)
                or _SHA.fullmatch(self.workflow_sha) is None
                or _SHA.fullmatch(self.checked_out_source_sha) is None
                or self.event_name not in _SUPPORTED_EVENTS
                or type(self.worker_dispatch) is not bool
                or (self.event_name == "workflow_dispatch") != self.worker_dispatch):
            raise ValueError("GITHUB_ACTIONS_RUNTIME_CLAIM_INVALID")
class TrustedExecutionBoundaryV3(Protocol):
    """Designated harness boundary; ordinary caller values are insufficient."""
    def authenticates(self, claim: GitHubActionsRuntimeClaimV3) -> bool: ...
@dataclass(frozen=True)
class GitHubActionsExpectationV3:
    repository: str
    repository_id: int
    workflow_id: int
    workflow_path: str
    workflow_ref: str
    workflow_execution_ref: str
    event_name: str
    workflow_definition_sha: str
    executing_source_sha: str
    job_key: str
    job_name: str
    worker_dispatch: bool = False
    workflow_name: str | None = None

    def __post_init__(self) -> None:
        numeric = (self.repository_id, self.workflow_id)
        strings = (self.workflow_ref, self.job_key, self.job_name)
        if (_REPOSITORY.fullmatch(self.repository) is None
                or any(type(value) is not int or value < 1 for value in numeric)
                or any(not isinstance(value, str) or not value for value in strings)
                or _WORKFLOW_PATH.fullmatch(self.workflow_path) is None
                or not self.workflow_execution_ref.startswith("refs/heads/")
                or self.event_name not in _SUPPORTED_EVENTS
                or type(self.worker_dispatch) is not bool
                or (self.event_name == "workflow_dispatch") != self.worker_dispatch
                or self.worker_dispatch and (not isinstance(self.workflow_name, str)
                                              or not self.workflow_name)
                or _SHA.fullmatch(self.workflow_definition_sha) is None
                or _SHA.fullmatch(self.executing_source_sha) is None):
            raise ValueError("GITHUB_ACTIONS_EXPECTATION_INVALID")
@dataclass(frozen=True)
class GitHubActionsRunObservationV3:
    repository: str
    repository_id: int
    run_id: int
    run_attempt: int
    workflow_id: int
    workflow_path: str
    workflow_ref: str
    event_name: str
    run_head_sha: str
    source_repository: str
    source_repository_id: int
    actor_id: int
    actor_login: str
    triggering_actor_id: int
    triggering_actor_login: str
    job_id: int
    job_name: str
    runtime_job_key: str
    workflow_definition_sha: str
    executing_source_sha: str
    pull_request_head_sha: str | None
    synthetic_merge_sha: str | None
    observed_at: str
    api_source: str
    evidence_id: str
ClockV3 = Callable[[], datetime]
class TrustedWorkerBindingV3(Protocol):
    """Trusted workflow-input binding, separate from API run existence."""
    def authenticates(self, request: CodespaceAccessRequestV3,
                      observation: GitHubActionsRunObservationV3) -> bool: ...
from .github_actions_jobs_v3 import GitHubActionsJobsReaderV3


class GitHubActionsIdentityReaderV3(GitHubActionsJobsReaderV3):
    """Confront a boundary-authenticated runtime claim with fresh run/job APIs."""
    def __init__(self, token: str, repository: str, repository_id: int, *,
                 executor: HttpExecutorV3 | None = None,
                 clock: ClockV3 | None = None):
        if not token or token.strip() != token or any(c in token for c in "\r\n"):
            raise ValueError("GITHUB_TOKEN_INVALID")
        if _REPOSITORY.fullmatch(repository) is None or ".." in repository:
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        _positive(repository_id, "GITHUB_REPOSITORY_ID_INVALID")
        self._token = token
        self.repository = repository
        self.repository_id = repository_id
        self._executor = executor or urllib_executor
        self.injected_transport = executor is not None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owner, self._name = repository.split("/", 1)
    def _get(self, suffix: str) -> HttpResponseV3:
        if re.fullmatch(
            r"/actions/runs/[1-9][0-9]*(?:/attempts/[1-9][0-9]*/jobs\?per_page=100&page=[1-9][0-9]*)?",
            suffix,
        ) is None:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_ENDPOINT_INVALID")
        root = f"/repos/{quote(self._owner, safe='')}/{quote(self._name, safe='')}"
        request = Request(
            _API + root + suffix,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": _VERSION,
            },
            method="GET",
        )
        try:
            response = self._executor(request)
        except Exception:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_UNAVAILABLE") from None
        if not isinstance(response, HttpResponseV3):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_RESPONSE_INVALID")
        return response
    @staticmethod
    def _json(response: HttpResponseV3) -> Mapping[str, object]:
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JSON_INVALID") from exc
        if not isinstance(value, dict):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JSON_INVALID")
        return value
    def observe(self, claim: GitHubActionsRuntimeClaimV3,
                expected: GitHubActionsExpectationV3,
                boundary: TrustedExecutionBoundaryV3) -> GitHubActionsRunObservationV3:
        diagnostics = getattr(self, 'diagnostics', None)
        if diagnostics is not None: diagnostics.count('WORKER_IDENTITY_COUNT')
        try:
            boundary_verdict = boundary.authenticates(claim)
        except Exception:
            boundary_verdict = False
        if type(boundary_verdict) is not bool or not boundary_verdict:
            raise GitHubActionsIdentityV3Error("TRUSTED_EXECUTION_BOUNDARY_REQUIRED")
        if (claim.repository != self.repository or expected.repository != self.repository
                or claim.repository_id != self.repository_id
                or expected.repository_id != self.repository_id):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_REPOSITORY_MISMATCH")
        run_id = _positive(claim.run_id, "GITHUB_ACTIONS_RUN_ID_INVALID")
        run_attempt = _positive(claim.run_attempt, "GITHUB_ACTIONS_RUN_ATTEMPT_INVALID")
        if (claim.workflow_ref != expected.workflow_ref
                or claim.event_name != expected.event_name
                or claim.job_key != expected.job_key):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_RUNTIME_CLAIM_MISMATCH")
        if (_sha(claim.workflow_sha, "GITHUB_ACTIONS_WORKFLOW_SHA_INVALID")
                != expected.workflow_definition_sha):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_WORKFLOW_SHA_MISMATCH")
        if (_sha(claim.checked_out_source_sha, "GITHUB_ACTIONS_EXECUTABLE_SHA_INVALID")
                != expected.executing_source_sha):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_EXECUTABLE_SHA_MISMATCH")
        if (_WORKFLOW_PATH.fullmatch(expected.workflow_path) is None
                or _EVENT.fullmatch(expected.event_name) is None
                or expected.event_name not in _SUPPORTED_EVENTS
                or not claim.job_key):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_EXPECTATION_INVALID")
        response = self._get(f"/actions/runs/{run_id}")
        if response.status != 200:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_RUN_UNAVAILABLE")
        run = self._json(response)
        repository = run.get("repository")
        head_repository = run.get("head_repository")
        if not isinstance(repository, dict) or not isinstance(head_repository, dict):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_REPOSITORY_INVALID")
        if (repository.get("full_name") != self.repository
                or type(repository.get("id")) is not int
                or repository.get("id") != self.repository_id):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_REPOSITORY_MISMATCH")
        if (type(run.get("id")) is not int or run.get("id") != run_id
                or type(run.get("run_attempt")) is not int
                or run.get("run_attempt") != run_attempt):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_RUN_ATTEMPT_MISMATCH")
        if (type(run.get("workflow_id")) is not int
                or run.get("workflow_id") != expected.workflow_id
                or run.get("event") != expected.event_name):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_WORKFLOW_MISMATCH")
        path = run.get("path")
        if path != expected.workflow_path:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_WORKFLOW_PATH_MISMATCH")
        run_head_sha = _sha(run.get("head_sha"), "GITHUB_ACTIONS_HEAD_SHA_INVALID")
        if (head_repository.get("full_name") != self.repository
                or type(head_repository.get("id")) is not int
                or head_repository.get("id") != self.repository_id):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_SOURCE_REPOSITORY_MISMATCH")
        actor = run.get("actor")
        triggering_actor = run.get("triggering_actor")
        if not isinstance(actor, dict) or not isinstance(triggering_actor, dict):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_ACTOR_INVALID")
        actor_id = _positive(actor.get("id"), "GITHUB_ACTIONS_ACTOR_INVALID")
        triggering_id = _positive(triggering_actor.get("id"), "GITHUB_ACTIONS_TRIGGERING_ACTOR_INVALID")
        actor_login, triggering_login = actor.get("login"), triggering_actor.get("login")
        if not all(isinstance(value, str) and value for value in (actor_login, triggering_login)):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_ACTOR_INVALID")
        pr_head = claim.pull_request_head_sha
        merge_sha = claim.synthetic_merge_sha
        if expected.event_name == "pull_request":
            pr_head = _sha(pr_head, "GITHUB_ACTIONS_PR_HEAD_SHA_INVALID")
            merge_sha = _sha(merge_sha, "GITHUB_ACTIONS_MERGE_SHA_INVALID")
            if run_head_sha != pr_head:
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PR_HEAD_SHA_MISMATCH")
            pull_requests = run.get("pull_requests")
            expected_head_ref = expected.workflow_execution_ref.removeprefix("refs/heads/")
            if (expected.workflow_execution_ref != "refs/heads/" + expected_head_ref
                    or not isinstance(pull_requests, list) or not any(
                        isinstance(item, dict) and isinstance(item.get("head"), dict)
                        and item["head"].get("sha") == pr_head
                        and item["head"].get("ref") == expected_head_ref
                        for item in pull_requests
                    )):
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PR_HEAD_UNVERIFIED")
        elif pr_head is not None or merge_sha is not None:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_EVENT_CONTEXT_INVALID")
        if expected.event_name == "workflow_dispatch":
            from .github_actions_workflow_dispatch_v3 import (
                validate_worker_dispatch_run, validate_controller_dispatch_run,
            )
            if expected.job_key == "controller":
                validate_controller_dispatch_run(run, expected)
            else:
                validate_worker_dispatch_run(run, expected)
        jobs = self._jobs(run_id, run_attempt)
        matches = [job for job in jobs if job.get("name") == expected.job_name]
        if len(matches) != 1:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOB_IDENTITY_AMBIGUOUS")
        job_id = _positive(matches[0].get("id"), "GITHUB_ACTIONS_JOB_ID_INVALID")
        if expected.event_name == "workflow_dispatch":
            from .github_actions_workflow_dispatch_v3 import validate_worker_dispatch_job
            validate_worker_dispatch_job(matches[0], run_id=run_id,
                                        run_attempt=run_attempt, source_sha=run_head_sha)
        observed = self._clock()
        if observed.tzinfo is None:
            raise GitHubActionsIdentityV3Error("GITHUB_OBSERVATION_TIME_INVALID")
        observed_at = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        api_source = f"{_API}/repos/{self.repository}/actions/runs/{run_id}"
        basis = {
            "schema_version": 1,
            "evidence_type": "github-actions-run-observation",
            "repository": self.repository,
            "repository_id": self.repository_id,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "workflow_id": expected.workflow_id,
            "workflow_path": expected.workflow_path,
            "workflow_ref": expected.workflow_ref,
            "workflow_execution_ref": expected.workflow_execution_ref,
            "event_name": expected.event_name,
            "run_head_sha": run_head_sha,
            "source_repository": head_repository["full_name"],
            "source_repository_id": head_repository["id"],
            "actor_id": actor_id,
            "actor_login": actor_login,
            "triggering_actor_id": triggering_id,
            "triggering_actor_login": triggering_login,
            "job_id": job_id,
            "job_name": expected.job_name,
            "runtime_job_key": claim.job_key,
            "workflow_definition_sha": expected.workflow_definition_sha,
            "executing_source_sha": expected.executing_source_sha,
            "pull_request_head_sha": pr_head,
            "synthetic_merge_sha": merge_sha,
            "observed_at": observed_at,
            "api_source": api_source,
        }
        return GitHubActionsRunObservationV3(
            self.repository, self.repository_id, run_id, run_attempt,
            expected.workflow_id, expected.workflow_path, expected.workflow_ref,
            expected.event_name, run_head_sha, head_repository["full_name"],
            head_repository["id"], actor_id, actor_login, triggering_id,
            triggering_login, job_id, expected.job_name, claim.job_key,
            expected.workflow_definition_sha, expected.executing_source_sha,
            pr_head, merge_sha, observed_at,
            api_source, artifact_identity(canonical_bytes(basis) + b"\n"),
        )
@dataclass(frozen=True)
class GitHubActionsTrustedContextProviderV3:
    """Smallest Actions-backed provider for the existing preventive gate."""
    reader: GitHubActionsIdentityReaderV3
    runtime_claim: GitHubActionsRuntimeClaimV3
    expectation: GitHubActionsExpectationV3
    execution_boundary: TrustedExecutionBoundaryV3
    worker_binding: TrustedWorkerBindingV3
    codespace_identity: str
    allowed_operation: CodespaceEffectV3
    def authenticate(self, request: CodespaceAccessRequestV3) -> TrustedWorkerContextV3 | None:
        admission_repository_id = request.expected_admission.get("repository_id")
        if (request.broker_repository != self.reader.repository
                or type(admission_repository_id) is not int
                or admission_repository_id != self.reader.repository_id
                or request.worker != WorkerIdentityV3(
                    self.runtime_claim.run_id, self.runtime_claim.run_attempt)
                or request.codespace_identity != self.codespace_identity
                or request.operation is not self.allowed_operation):
            return None
        try:
            observation = self.reader.observe(
                self.runtime_claim, self.expectation, self.execution_boundary
            )
        except (GitHubActionsIdentityV3Error, ValueError):
            return None
        if (observation.repository != request.broker_repository
                or observation.repository_id != admission_repository_id
                or (observation.run_id, observation.run_attempt)
                != (request.worker.run_id, request.worker.run_attempt)
                or observation.executing_source_sha != self.expectation.executing_source_sha):
            return None
        try:
            bound = self.worker_binding.authenticates(request, observation)
        except Exception:
            bound = False
        if type(bound) is not bool or not bound:
            return None
        return TrustedWorkerContextV3(
            request.broker_repository, request.request_id, request.attempt_id,
            request.claim_ref, request.reservation_id, request.generation,
            request.worker, self.codespace_identity, request.operation,
        )
