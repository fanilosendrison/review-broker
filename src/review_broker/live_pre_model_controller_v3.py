"""Concrete Controller dependency composition; the existing Controller owns the algorithm."""
from collections.abc import Callable

from .github_actions_dispatch_provider_v3 import GitHubActionsDispatchProviderObservationV3
from .github_actions_controller_authority_v3 import GitHubActionsControllerAuthorityV3
from .github_actions_initial_dispatch_v3 import GitHubActionsInitialDispatchTransportV3
from .github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
from .github_initial_history_v3 import GitHubInitialHistoryAuthorityV3
from .github_live_runtime_v3 import worker_expectation_v3
from .live_journal_composition_v3 import live_journal_v3
from .live_source_admission_v3 import LiveSourceSessionV3
from .pre_model_controller_v3 import PreModelControllerV3


def controller_authority_v3(runtime,issue,request_id,gates):
    authority=GitHubActionsControllerAuthorityV3(runtime,issue=issue,request_id=request_id,gates=gates)
    authority.require_current()
    return authority


def run_live_controller_v3(*,runtime,issue,request_id,gates,source_token,app_slug,
                           installation_id,private_root,source_executor,acquire_repository=None,
                           observation_sink: Callable[[GitHubActionsDispatchProviderObservationV3], None] | None = None):
    authority=controller_authority_v3(runtime,issue,request_id,gates)
    if source_token==runtime.api.token:raise ValueError('CONTROL_TOKEN_IS_NOT_SOURCE_AUTHORITY')
    phase={'source_complete':False}
    def write_guard():
        if not phase['source_complete']:raise ValueError('COMPLETE_PRECLAIM_ADMISSION_REQUIRED')
        authority.require_current()
    journal=live_journal_v3(runtime,authority,write_guard=write_guard)
    history=GitHubInitialHistoryAuthorityV3(runtime.api,journal.transport,runtime.checkout.sha)
    source=LiveSourceSessionV3(source_token,app_slug=app_slug,installation_id=installation_id,
        root=private_root,guard=authority.require_current,executor=source_executor,
        acquire_repository=acquire_repository)
    try:
        admission=source.admit_controller(authority,history)
    finally:
        source.close()
    del source,source_token
    phase['source_complete']=True
    authority.require_current()
    target=authority.target
    dispatch=GitHubActionsInitialDispatchTransportV3(authority,observation_sink=observation_sink)
    expected=worker_expectation_v3(runtime.api,target.execution_ref,target.executable_sha)
    acknowledgment=GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api,expected)
    return PreModelControllerV3(journal,target,dispatch,authority,acknowledgment).run(admission)
