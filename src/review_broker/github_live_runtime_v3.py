"""Protected Actions checkout/input boundary shared by the pre-model entrypoints."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping
from urllib.request import Request

from .github_actions_identity_v3 import (
    GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3, GitHubActionsRuntimeClaimV3,
)
from .github_actions_worker_authority_v3 import WorkerExecutionContextV3, WorkerInputsV3
from .github_http_live_v3 import HttpResponseV3, urllib_executor
from .identity import artifact_identity, canonical_bytes
from .prepared_artifact_transport_v3 import PreparedArtifactBudgetV3, PreparedMetadataReaderV3

REPOSITORY = "fanilosendrison/review-broker"
REPOSITORY_ID = 1433701208
OWNER_ID = 30498238
CONTROLLER_PATH = ".github/workflows/v3-pre-model-controller.yml"
WORKER_PATH = ".github/workflows/v3-pre-model-worker.yml"
METADATA_BUDGET = PreparedArtifactBudgetV3(32_000_000, 64_000_000, 1000, 100, 4_000_000)


def exact_positive(value: object) -> int:
    if type(value) is not str or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError("LIVE_POSITIVE_DECIMAL_REQUIRED")
    return int(value)


class LiveGitHubApiV3:
    """One fixed repository; every controlled HTTP request has an explicit guard."""
    def __init__(self, token: str, *, guard, executor=urllib_executor):
        if not token or any(c in token for c in "\r\n") or not callable(guard):
            raise ValueError("LIVE_API_CONFIGURATION_INVALID")
        from .github_conditional_reads_v3 import GitHubConditionalReadsV3
        self.token, self.guard, self.executor = token, guard, GitHubConditionalReadsV3(executor)
        self.metadata = PreparedMetadataReaderV3(token=token, repository=REPOSITORY,
            executor=self.metadata_execute, budget=METADATA_BUDGET)

    def execute(self, request):
        self.guard()
        if request.full_url == "https://api.github.com/graphql":
            payload = json.loads(request.data)
            if request.get_method() != "POST" or not payload.get("query", "").startswith("query"):
                raise ValueError("LIVE_API_QUERY_ONLY")
        elif (request.full_url.split("?", 1)[0] != f"https://api.github.com/repos/{REPOSITORY}"
                and not request.full_url.startswith(f"https://api.github.com/repos/{REPOSITORY}/")):
            raise ValueError("LIVE_API_SCOPE_INVALID")
        return self.executor(request)

    def metadata_execute(self, request, *, max_bytes):
        result = self.execute(request)
        if type(result) is not HttpResponseV3 or len(result.body) > max_bytes:
            raise ValueError("LIVE_METADATA_RESPONSE_INVALID")
        return result

    def get(self, suffix):
        return self.metadata.object(self.metadata.get(suffix, self.guard))

    def query(self, query, variables):
        response = self.execute(Request("https://api.github.com/graphql", method="POST",
            data=canonical_bytes({"query":query,"variables":variables}), headers={
                "Authorization":f"Bearer {self.token}","Content-Type":"application/json"}))
        value = self.metadata.object(response)
        if "errors" in value:raise ValueError("LIVE_QUERY_UNAVAILABLE")
        return value["data"]

    def post_dispatch(self, payload):
        self.guard()
        return self.execute(Request(
            f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/v3-pre-model-worker.yml/dispatches",
            method="POST", data=canonical_bytes(payload), headers={
                "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"}))


@dataclass(frozen=True)
class ProtectedCheckoutV3:
    root: Path
    sha: str

    @classmethod
    def observe(cls, root: Path, expected_sha: str):
        environment = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TMPDIR") if k in os.environ}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1")
        def git(*args):
            return subprocess.run(["git", "-C", str(root), *args], env=environment,
                stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=30).stdout
        if (re.fullmatch(r"[0-9a-f]{40}", expected_sha) is None
                or git("rev-parse", "HEAD") != (expected_sha + "\n").encode()
                or git("status", "--porcelain")):
            raise ValueError("PROTECTED_CHECKOUT_MISMATCH")
        return cls(root.resolve(), expected_sha)


def worker_expectation_v3(api,execution_ref,sha):
    workflow=api.get('/actions/workflows/v3-pre-model-worker.yml')
    if (workflow.get('path')!=WORKER_PATH or type(workflow.get('id')) is not int
            or workflow['id']<1):raise ValueError('WORKER_WORKFLOW_UNRECOGNIZED')
    return GitHubActionsExpectationV3(REPOSITORY,REPOSITORY_ID,workflow['id'],WORKER_PATH,
        f'{REPOSITORY}/{WORKER_PATH}@{execution_ref}',execution_ref,'workflow_dispatch',
        sha,sha,'worker','worker',True,workflow['name'])


class GitHubActionsRuntimeBoundaryV3:
    """Trusted protected-workflow assumption, confronted with fresh authenticated APIs.

    Inputs originate in the exact checked-out workflow/local action mapping. A
    same-OS arbitrary-code adversary is not a supported trust boundary. This is
    not OIDC or a cryptographic claim that environment possession authenticates a
    process. No reviewed code executes in this trusted process.
    """
    def __init__(self, *, environment: Mapping[str, str], checkout: ProtectedCheckoutV3,
                 role: str, inputs: Mapping[str, object], token: str, executor=urllib_executor):
        if role not in {"controller", "worker"}:
            raise ValueError("LIVE_RUNTIME_ROLE_INVALID")
        self.env, self.checkout, self.role = dict(environment), checkout, role
        self.inputs = dict(inputs)
        self._worker_context = None
        self.path = CONTROLLER_PATH if role == "controller" else WORKER_PATH
        self.check_locals()
        self.api = LiveGitHubApiV3(token, guard=self.check_locals, executor=executor)
        workflow = self.api.get("/actions/workflows/" + self.path.rsplit("/", 1)[-1])
        if workflow.get("path") != self.path or type(workflow.get("id")) is not int or workflow["id"] < 1:
            raise ValueError("LIVE_WORKFLOW_IDENTITY_INVALID")
        self.expected = GitHubActionsExpectationV3(REPOSITORY, REPOSITORY_ID,
            workflow["id"], self.path, self.env["GITHUB_WORKFLOW_REF"], self.env["GITHUB_REF"],
            "workflow_dispatch", checkout.sha, checkout.sha, role, role, True, workflow["name"])
        self.claim = GitHubActionsRuntimeClaimV3(REPOSITORY, REPOSITORY_ID,
            exact_positive(self.env["GITHUB_RUN_ID"]), 1, role,
            self.env["GITHUB_WORKFLOW_REF"], checkout.sha, checkout.sha,
            "workflow_dispatch", worker_dispatch=True)
        self.reader = GitHubActionsIdentityReaderV3(token, REPOSITORY, REPOSITORY_ID,
            executor=self.active_execute)
        self.boundary_id = artifact_identity(canonical_bytes({"workflow": self.path,
            "ref": self.env["GITHUB_REF"], "sha": checkout.sha, "role": role}) + b"\n")

    def active_execute(self,request):
        response=self.api.execute(request)
        if request.full_url==f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{self.claim.run_id}':
            run=self.api.metadata.object(response)
            if run.get('status') not in {'in_progress','queued','waiting','pending'}:
                raise ValueError('LIVE_EXECUTION_NOT_ACTIVE')
        return response

    def check_locals(self):
        e = self.env
        if (e.get("GITHUB_REPOSITORY") != REPOSITORY
                or e.get("GITHUB_REPOSITORY_ID") != str(REPOSITORY_ID)
                or e.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
                or e.get("GITHUB_RUN_ATTEMPT") != "1"
                or e.get("GITHUB_JOB") != self.role
                or e.get("GITHUB_SHA") != self.checkout.sha
                or e.get("GITHUB_WORKFLOW_SHA") != self.checkout.sha
                or not e.get("GITHUB_REF", "").startswith("refs/heads/")
                or e.get("GITHUB_WORKFLOW_REF") != f"{REPOSITORY}/{self.path}@{e.get('GITHUB_REF')}"):
            raise ValueError("LIVE_RUNTIME_CONTEXT_INVALID")

    def authenticates(self, claim):
        self.check_locals()
        return claim == self.claim

    def observe(self):
        self.check_locals()
        observed = self.reader.observe(self.claim, self.expected, self)
        if (self.env.get('GITHUB_ACTOR_ID')!=str(observed.actor_id)
                or self.env.get('GITHUB_ACTOR')!=observed.actor_login
                or self.env.get('GITHUB_TRIGGERING_ACTOR')!=observed.triggering_actor_login):
            raise ValueError('LIVE_RUNTIME_ACTOR_CONTEXT_MISMATCH')
        repo = self.api.get("")
        if (repo.get("id") != REPOSITORY_ID or repo.get("full_name") != REPOSITORY
                or not isinstance(repo.get("node_id"), str)):
            raise ValueError("LIVE_REPOSITORY_IDENTITY_INVALID")
        return observed

    def worker_context(self):
        if self.role != "worker" or set(self.inputs) != {"request_id", "reservation_id", "generation"}:
            raise ValueError("WORKER_LITERAL_INPUT_MAPPING_REQUIRED")
        from .github_actions_worker_authority_v3 import valid_worker_inputs
        inputs = WorkerInputsV3(**self.inputs)
        if not valid_worker_inputs(inputs):
            raise ValueError("WORKER_INPUTS_INVALID")
        observed = self.observe()
        context = WorkerExecutionContextV3(self.claim, inputs, self.boundary_id, observed.job_id)
        if self._worker_context is None:self._worker_context = context
        if self._worker_context != context:raise ValueError('WORKER_RUNTIME_CONTEXT_CHANGED')
        return self._worker_context

    def authenticates_context(self, context: WorkerExecutionContextV3):
        if self.role != "worker":
            return False
        self.check_locals()
        # Fresh run/job observations are performed by the existing binding/current
        # authority. Reobserving them here recursively multiplies reads, not trust.
        return (context is self._worker_context and context.runtime == self.claim
                and context.boundary_id == self.boundary_id
                and context.inputs == WorkerInputsV3(**self.inputs))
