"""External Actions/Issue service double; never an admission, journal or decision double."""
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_live_runtime_v3 import (
    REPOSITORY, REPOSITORY_ID, CONTROLLER_PATH, WORKER_PATH, ProtectedCheckoutV3,
    GitHubActionsRuntimeBoundaryV3,
)
from review_broker.github_actions_controller_authority_v3 import GATES
from review_broker.request_v3 import build_issue_envelope_v3
from tests.request_v3_test_support import request
import hashlib

SHA = "c" * 40
REF = "refs/heads/qualification-branch"
PRINCIPAL = 41898282


def response(value, status=200):
    return HttpResponseV3(status, json.dumps(value).encode(), {})


def environment(role):
    path = CONTROLLER_PATH if role == "controller" else WORKER_PATH
    return dict(GITHUB_REPOSITORY=REPOSITORY, GITHUB_REPOSITORY_ID=str(REPOSITORY_ID),
        GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_RUN_ATTEMPT="1", GITHUB_JOB=role,
        GITHUB_SHA=SHA, GITHUB_WORKFLOW_SHA=SHA, GITHUB_REF=REF,
        GITHUB_WORKFLOW_REF=f"{REPOSITORY}/{path}@{REF}", GITHUB_RUN_ID="60001" if role=="controller" else "70001",
        GITHUB_ACTOR_ID="30498238" if role=="controller" else str(PRINCIPAL),
        GITHUB_ACTOR="owner" if role=="controller" else "github-actions[bot]",
        GITHUB_TRIGGERING_ACTOR="owner" if role=="controller" else "github-actions[bot]")


class ActionsService:
    def __init__(self, request_value=None):
        self.request = request_value or request()
        self.body = build_issue_envelope_v3(self.request)
        self.calls = []
        self.dispatch_result = None
        self.dispatch_status = 200
        self.dispatch_loss = False
        self.run_overrides, self.job_overrides = {}, {}
        self.node_id = "R_repo_node"
        self.controller_running = False

    def workflow(self, role):
        return {"id":77 if role=="worker" else 76,"path":WORKER_PATH if role=="worker" else CONTROLLER_PATH,
                "name":"v3 pre-model Worker" if role=="worker" else "v3 pre-model Controller"}

    def run(self, role):
        workflow=self.workflow(role)
        actor={"id":30498238,"login":"owner"} if role=="controller" else {"id":PRINCIPAL,"login":"github-actions[bot]"}
        value={"id":60001 if role=="controller" else 70001,"run_attempt":1,
            "repository":{"id":REPOSITORY_ID,"full_name":REPOSITORY},
            "head_repository":{"id":REPOSITORY_ID,"full_name":REPOSITORY},
            "workflow_id":workflow['id'],"path":workflow['path'],"name":workflow['name'],
            "status":"completed","conclusion":"success",
            "event":"workflow_dispatch","head_sha":SHA,"head_branch":REF.removeprefix('refs/heads/'),
            "actor":actor,"triggering_actor":copy.deepcopy(actor)}
        if role=='worker' or self.controller_running:value.update(status='in_progress',conclusion=None)
        value.update(self.run_overrides.get(role,{}))
        return value

    def jobs(self, role):
        value={"id":501 if role=="worker" else 500,"name":role,"conclusion":"success",
            "run_id":70001 if role=="worker" else 60001,"run_attempt":1,"head_sha":SHA}
        if role=='worker' or self.controller_running:value['conclusion']=None
        value.update(self.job_overrides.get(role,{}))
        return [value]

    def __call__(self, req):
        path=urlsplit(req.full_url).path
        self.calls.append((req.get_method(),path,req.data,req.get_header('Authorization')))
        root='/repos/'+REPOSITORY
        if req.get_method()=='POST':
            assert path==root+'/actions/workflows/v3-pre-model-worker.yml/dispatches'
            if self.dispatch_loss: raise TimeoutError('provider response lost')
            value=self.dispatch_result
            if value is None:value={"workflow_run_id":70001,
                "run_url":f"https://api.github.com/repos/{REPOSITORY}/actions/runs/70001",
                "html_url":f"https://github.com/{REPOSITORY}/actions/runs/70001"}
            return response(value,self.dispatch_status)
        if path==root:return response({"id":REPOSITORY_ID,"node_id":self.node_id,"full_name":REPOSITORY})
        if path==root+'/git/ref/'+REF.removeprefix('refs/'):
            return response({'ref':REF,'object':{'type':'commit','sha':SHA}})
        if path==root+'/issues/51':return response({"id":6106789428,"number":51,"body":self.body,"user":{"id":30498238,"login":"owner"}})
        if path.endswith('/actions/workflows/v3-pre-model-controller.yml/runs'):
            return response({'total_count':1,'workflow_runs':[self.run('controller')]})
        if '/actions/workflows/' in path:
            return response(self.workflow('controller' if 'controller' in path else 'worker'))
        if '/actions/runs/' in path:
            role='controller' if '/60001' in path else 'worker'
            if path.endswith('/jobs'):return response({"total_count":len(self.jobs(role)),"jobs":self.jobs(role)})
            return response(self.run(role))
        raise AssertionError(path)

    def runtime(self, role, inputs):
        return GitHubActionsRuntimeBoundaryV3(environment=environment(role),
            checkout=ProtectedCheckoutV3(Path('.'),SHA),role=role,inputs=inputs,
            token='fixture-control',executor=self)

    def gates(self, request_id):
        return dict(zip(GATES,(SHA,request_id,'51',hashlib.sha256(self.body.encode()).hexdigest())))
