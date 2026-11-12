"""Ephemeral exact request plan for one existing journal operation; no durable protocol."""
import base64
import re
from threading import Lock

from .github_journal_commit_writer_v3 import JOURNAL_PATH_V3
from .github_journal_transport_v3 import (
    JOURNAL_COMMIT_MESSAGE_V3,JOURNAL_UPDATE_REFS_QUERY_V3,encode_journal_http_payload_v3,
)
from .github_live_runtime_v3 import REPOSITORY


class JournalOperationPlanV3:
    """Internal request binding, not actor authority, CAS or reconciliation logic.

    Each preparation request is exact and single-use. A ref opportunity exists
    only after the existing writer returned a completely verified successor.
    Consumption precedes provider emission, so response loss never permits retry.
    Invalid requests do not consume the intended request's opportunity.
    """
    def __init__(self,*,expected,claim_ref,parent_sha,parent_tree,node_id,journal_bytes,blob_sha):
        self.expected,self.claim_ref=expected,claim_ref
        self.parent,self.parent_tree,self.node_id=parent_sha,parent_tree,node_id
        self.journal_bytes,self.blob_sha=journal_bytes,blob_sha
        self.tree=self.commit=self.successor=None
        self._phase='blob';self._lock=Lock()

    def ready(self,successor):
        with self._lock:
            if self._phase!='prepared' or self.commit!=successor or self.successor is not None:
                raise ValueError('ORIGINAL_VERIFIED_SUCCESSOR_REQUIRED')
            self.successor=successor;self._phase='ref'

    def before_request(self,request):
        root='https://api.github.com/repos/'+REPOSITORY
        with self._lock:
            if request.get_method()!='POST':raise ValueError('JOURNAL_REQUEST_METHOD_OUTSIDE_PLAN')
            if request.full_url==root+'/git/blobs':
                phase='blob';wanted={'content':base64.b64encode(self.journal_bytes).decode('ascii'),'encoding':'base64'}
            elif request.full_url==root+'/git/trees':
                phase='tree';wanted={'base_tree':self.parent_tree,'tree':[{
                    'path':JOURNAL_PATH_V3,'mode':'100644','type':'blob','sha':self.blob_sha}]}
            elif request.full_url==root+'/git/commits':
                phase='commit';wanted={'message':JOURNAL_COMMIT_MESSAGE_V3,'tree':self.tree,'parents':[self.parent]}
            elif request.full_url==root+'/git/refs' and self.expected is None:
                phase='ref';wanted={'ref':self.claim_ref,'sha':self.successor}
            elif request.full_url=='https://api.github.com/graphql' and self.expected is not None:
                phase='ref';wanted={'query':JOURNAL_UPDATE_REFS_QUERY_V3,'variables':{
                    'repositoryId':self.node_id,'name':self.claim_ref,'beforeOid':self.parent,
                    'afterOid':self.successor,'force':False}}
            else:raise ValueError('JOURNAL_REQUEST_TARGET_OUTSIDE_PLAN')
            if self._phase!=phase or request.data!=encode_journal_http_payload_v3(wanted) or phase=='ref' and self.successor is None:
                raise ValueError('JOURNAL_REQUEST_DOES_NOT_MATCH_ORIGINAL_OPERATION')
            self._phase=phase+'-emitted'

    def observe_preparation_response(self,request,response,decode):
        """Record only provider ACK data; never manufacture a lost response."""
        root='https://api.github.com/repos/'+REPOSITORY
        if request.full_url not in {root+'/git/blobs',root+'/git/trees',root+'/git/commits'}:return
        if response.status!=201:return
        try:sha=decode(response).get('sha')
        except Exception:return
        if type(sha) is not str or re.fullmatch('[0-9a-f]{40}',sha) is None:return
        with self._lock:
            if request.full_url.endswith('/git/blobs') and self._phase=='blob-emitted' and sha==self.blob_sha:
                self._phase='tree'
            elif request.full_url.endswith('/git/trees') and self._phase=='tree-emitted':
                self.tree=sha;self._phase='commit'
            elif request.full_url.endswith('/git/commits') and self._phase=='commit-emitted':
                self.commit=sha;self._phase='prepared'
