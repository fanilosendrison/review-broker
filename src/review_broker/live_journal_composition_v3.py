"""Live Git Database composition with separate read-observer and fresh write guards."""
from threading import Lock

from .admission_evidence_v3 import validate_journal_admission_v3
from .github_observed_journal_transport_v3 import GitHubObservedJournalTransportV3
from .github_journal_transition_authority_v3 import GitHubJournalTransitionAuthorityV3
from .github_journal_v3 import GitHubJournalV3
from .github_issue_origin_v3 import GitHubIssueOriginReaderV3
from .github_live_runtime_v3 import REPOSITORY,REPOSITORY_ID,OWNER_ID
from .identity import artifact_identity,canonical_bytes


class GitHubOriginalAdmissionAuthorityV3:
    """Read-only recognition of the original journal/Issue tuple, not new admission."""
    def __init__(self,api):self.api=api

    def origin(self,value):
        reader=GitHubIssueOriginReaderV3(self.api.token,REPOSITORY,REPOSITORY_ID,executor=self.api.execute)
        original=reader.observe(value['origin_observation']['issue_number'])
        if (original.requester_id!=OWNER_ID or original.issue_id!=value['broker_issue_id']
                or original.body is None):raise ValueError('ORIGINAL_REQUESTER_UNRECOGNIZED')
        validate_journal_admission_v3(value,original.body.encode())
        return original.body.encode()

    def evidence_id(self,*,repository,request,admission):
        if repository!=REPOSITORY or request!=admission['canonical_request']:return None
        self.origin(admission)
        return artifact_identity(canonical_bytes(admission)+b'\n')

    def permits_evidence(self,*,repository,request_id,admission,evidence_id):
        return (request_id==admission['request_id'] and evidence_id is not None
            and evidence_id==self.evidence_id(repository=repository,request=admission['canonical_request'],admission=admission))


class NoRejectionAttributionV3:
    def permits(self,update,evidence_id):return False


def live_journal_v3(runtime,admission_authority,*,write_guard):
    """Observation remains possible after effects; only fresh original writes are permitted.

    Every request checks the protected runtime locally. Mutating requests additionally
    reconfront current runtime/journal. Observer reads grant no effect permission and
    avoid recursively authorizing a journal read through itself.
    """
    from .journal_operation_plan_v3 import JournalOperationPlanV3
    from .github_journal_transport_v3 import (
        ReadStatusV3,decode_journal_http_payload_v3,encode_journal_http_payload_v3,JOURNAL_REPOSITORY_QUERY_V3,
    )
    active=[None];lock=Lock()
    def begin_operation(expected,claim_ref,journal_bytes):
        parent=runtime.checkout.sha if expected is None else expected.commit_sha
        parent_tree=transport._get_commit(parent)['tree']['sha']
        plan=JournalOperationPlanV3(expected=expected,claim_ref=claim_ref,parent_sha=parent,
            parent_tree=parent_tree,node_id=transport.repository_node_id,journal_bytes=journal_bytes,
            blob_sha=transport._git_blob_sha(journal_bytes))
        with lock:active[0]=plan
        return plan
    def operation_ready(successor,plan):
        with lock:
            if plan is None or active[0] is not plan:raise ValueError('ORIGINAL_JOURNAL_OPERATION_CHANGED')
        plan.ready(successor)
    def execute(request):
        runtime.check_locals()
        if request.data:decode_journal_http_payload_v3(request.data)
        method=request.get_method()
        read_query=(method=='POST' and request.full_url=='https://api.github.com/graphql'
            and request.data==encode_journal_http_payload_v3({'query':JOURNAL_REPOSITORY_QUERY_V3,
                'variables':{'owner':'fanilosendrison','name':'review-broker'}}))
        if method=='GET' and request.data is not None:raise ValueError('JOURNAL_READ_BODY_FORBIDDEN')
        mutation=method!='GET' and not read_query
        plan=None
        if mutation:
            with lock:plan=active[0]
            if plan is None:raise ValueError('ORIGINAL_JOURNAL_OPERATION_REQUIRED')
            write_guard()
            with lock:
                if active[0] is not plan:raise ValueError('ORIGINAL_JOURNAL_OPERATION_CHANGED')
            plan.before_request(request)
            read=transport.read_claim(plan.claim_ref);expected=plan.expected
            if expected is None:
                if read.status is not ReadStatusV3.MISSING:raise ValueError('CLAIM_ALREADY_EXISTS')
            elif (read.status is not ReadStatusV3.FOUND or read.snapshot is None
                    or read.snapshot.commit_sha!=expected.commit_sha
                    or read.snapshot.parent_sha!=expected.parent_sha
                    or read.snapshot.journal_bytes!=expected.journal_bytes):
                raise ValueError('LIVE_JOURNAL_PREDECESSOR_MOVED')
        response=runtime.api.executor(request)
        if plan is not None:plan.observe_preparation_response(request,response,transport._json)
        return response
    transport=GitHubObservedJournalTransportV3(runtime.api.token,
        before_effect=runtime.check_locals,executor=execute)
    node=transport.verify_repository_identity()
    authority=GitHubJournalTransitionAuthorityV3(transport)
    return GitHubJournalV3(REPOSITORY,node,runtime.checkout.sha,transport,admission_authority,
        authority,NoRejectionAttributionV3(),authority,operation_guard=begin_operation,operation_ready=operation_ready)
