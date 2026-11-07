"""Live Git Database composition with separate read-observer and fresh write guards."""
import json

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
    scope={'expected':None,'claim_ref':None}
    def begin_operation(expected,claim_ref):
        scope['expected'],scope['claim_ref']=expected,claim_ref
    def execute(request):
        runtime.check_locals()
        payload=json.loads(request.data) if request.data else None
        query=payload.get('query','') if isinstance(payload,dict) else ''
        mutation=request.get_method()=='POST' and not query.startswith('query')
        if mutation:
            write_guard()
            from .github_journal_transport_v3 import ReadStatusV3
            if scope['claim_ref'] is None:raise ValueError('ORIGINAL_JOURNAL_OPERATION_REQUIRED')
            read=transport.read_claim(scope['claim_ref']);expected=scope['expected']
            if expected is None:
                if read.status is not ReadStatusV3.MISSING:raise ValueError('CLAIM_ALREADY_EXISTS')
            elif (read.status is not ReadStatusV3.FOUND or read.snapshot is None
                    or read.snapshot.commit_sha!=expected.commit_sha
                    or read.snapshot.parent_sha!=expected.parent_sha
                    or read.snapshot.journal_bytes!=expected.journal_bytes):
                raise ValueError('LIVE_JOURNAL_PREDECESSOR_MOVED')
        return runtime.api.executor(request)
    transport=GitHubObservedJournalTransportV3(runtime.api.token,
        before_effect=runtime.check_locals,executor=execute)
    node=transport.verify_repository_identity()
    authority=GitHubJournalTransitionAuthorityV3(transport)
    return GitHubJournalV3(REPOSITORY,node,runtime.checkout.sha,transport,admission_authority,
        authority,NoRejectionAttributionV3(),authority,operation_guard=begin_operation)
