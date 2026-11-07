"""Exactly one real-form Actions dispatch; its response is only a run candidate."""
from __future__ import annotations

import json
from threading import Lock

from .github_actions_controller_authority_v3 import GitHubActionsControllerAuthorityV3
from .github_live_runtime_v3 import REPOSITORY, WORKER_PATH
from .identity import attempt_identity
from .journal_record_v3 import preparation_dispatch_identity
from .pre_model_dispatch_v3 import InitialDispatchResultV3, InitialDispatchStatusV3


class GitHubActionsInitialDispatchTransportV3:
    original_controller_binding_required = True

    def __init__(self, authority: GitHubActionsControllerAuthorityV3):
        if type(authority) is not GitHubActionsControllerAuthorityV3:
            raise ValueError("CONCRETE_CONTROLLER_AUTHORITY_REQUIRED")
        self.authority = authority
        self._lock, self._attempted = Lock(), False
        self.observed_request = self.observed_response = None
        self._controller = None
        self._permit = None

    def bind_controller(self,controller):
        from .pre_model_controller_v3 import PreModelControllerV3
        if (type(controller) is not PreModelControllerV3 or self._controller is not None
                or controller.authority is not self.authority or controller.dispatch_transport is not self):
            raise ValueError('ORIGINAL_CONTROLLER_REQUIRED')
        self._controller=controller

    def bind_initial_reservation(self,controller,issuer):
        if (controller is not self._controller or issuer is None
                or controller._dispatch_issuance_gate is not issuer
                or controller._dispatch_issuance_outcome is None):
            raise ValueError('ORIGINAL_ATTRIBUTED_RESERVATION_REQUIRED')
        self._permit=(controller,issuer,controller._dispatch_issuance_request,
            controller._dispatch_issuance_outcome.snapshot)

    def dispatch(self, request):
        with self._lock:
            if self._attempted:
                raise ValueError("INITIAL_DISPATCH_ALREADY_ATTEMPTED")
            self._attempted = True
            permit,self._permit=self._permit,None
        if (permit is None or permit[0] is not self._controller
                or permit[0]._dispatch_issuance_gate is not permit[1] or permit[2] is not request):
            raise ValueError('ORIGINAL_CONTROLLER_DISPATCH_OPPORTUNITY_REQUIRED')
        a, target = self.authority, self.authority.target
        if (request.broker_repository != REPOSITORY or request.worker_workflow != WORKER_PATH
                or request.request_id != a.request_id or type(request.generation) is not int
                or request.generation != 1 or request.execution_ref != target.execution_ref
                or request.executable_sha != target.executable_sha
                or request.attempt_id != attempt_identity(request.request_id, 1)
                or request.claim_ref != "refs/heads/review-claims-v3/" + request.request_id[15:]
                or request.reservation_id != preparation_dispatch_identity(
                    request.request_id, request.attempt_id, 1, request.request_id)):
            raise ValueError("INITIAL_DISPATCH_BINDING_INVALID")
        a.require_current()
        ref = a.runtime.api.get('/git/ref/' + target.execution_ref.removeprefix('refs/'))
        if ref.get('ref') != target.execution_ref or ref.get('object',{}).get('sha') != target.executable_sha:
            raise ValueError('DISPATCH_PUBLISHED_REF_MOVED')
        claim=a.runtime.api.get('/git/ref/'+request.claim_ref.removeprefix('refs/'))
        if (claim.get('ref')!=request.claim_ref or claim.get('object',{}).get('sha')!=permit[3].commit_sha):
            raise ValueError('DISPATCH_RESERVATION_NO_LONGER_CURRENT')
        payload = {"ref": target.execution_ref.removeprefix("refs/heads/"), "inputs": {
            "request_id": request.request_id, "reservation_id": request.reservation_id,
            "generation": 1}, "return_run_details": True}
        result = InitialDispatchResultV3(InitialDispatchStatusV3.UNRESOLVED)
        try:
            a.require_current()
            response = a.runtime.api.post_dispatch(payload)
            if response.status == 204:
                result = InitialDispatchResultV3(InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID)
            elif response.status == 200:
                value = a.runtime.api.metadata.object(response)
                run = value.get("workflow_run_id")
                if (type(run) is int and run > 0
                        and value.get("run_url") == f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{run}"
                        and value.get("html_url") == f"https://github.com/{REPOSITORY}/actions/runs/{run}"):
                    result = InitialDispatchResultV3(InitialDispatchStatusV3.OBSERVED, run)
        except Exception:
            pass  # POST may have applied. No retry, no search for a redispatch target.
        self.observed_request, self.observed_response = request, result
        return result
