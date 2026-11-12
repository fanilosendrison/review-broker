"""Complete twice-confronted GitHub claim inventory for the bounded initial owner request."""
import re
import unicodedata

from .admission_v3 import InitialHistoryDecisionV3
from .github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID
from .github_journal_transport_v3 import ReadStatusV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import decode_journal_v2


INITIAL_CLAIM_NAMESPACE = 'refs/heads/review-claims-v3/'
_INITIAL_CLAIM_REF = re.compile(re.escape(INITIAL_CLAIM_NAMESPACE) + r'[0-9a-f]{64}')


def _valid_relative_name(name):
    """Git ref restrictions, without executing Git or accepting alternate bases.

    GitHub's deep refPrefix query returns a name relative to that exact prefix.
    Never strip a namespace-looking prefix or reinterpret a full ref as relative.
    """
    if (type(name) is not str or not name or name.startswith('refs/')
            or '..' in name or '@{' in name or name.endswith('.')
            or re.search(r'[ ~^:?*\[\\\\]', name)
            or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in name)):
        return False
    return all(part and not part.startswith('.') and not part.endswith('.lock')
               for part in name.split('/'))


class GitHubInitialHistoryAuthorityV3:
    def __init__(self, api, transport, scan_boundary):
        self.api,self.transport,self.scan_boundary=api,transport,scan_boundary

    def inventory(self):
        cursor=None;seen=set();rows=[];total=None
        query=('query($cursor:String){repository(owner:"fanilosendrison",name:"review-broker"){'
            'databaseId nameWithOwner refs(refPrefix:"' + INITIAL_CLAIM_NAMESPACE + '",'
            'first:100,after:$cursor){totalCount nodes{name target{oid __typename}} '
            'pageInfo{hasNextPage endCursor}}}}')
        for _ in range(100):
            repository=self.api.query(query,{'cursor':cursor})['repository']
            if repository['databaseId']!=REPOSITORY_ID or repository['nameWithOwner']!=REPOSITORY:
                raise ValueError('INITIAL_HISTORY_REPOSITORY_MISMATCH')
            refs=repository['refs'];count=refs['totalCount'];nodes=refs['nodes'];page=refs['pageInfo']
            if (type(count) is not int or count<0 or total is not None and count!=total
                    or type(nodes) is not list or len(nodes)>100):raise ValueError('INITIAL_HISTORY_INCOMPLETE')
            total=count
            for node in nodes:
                name=node['name'];target=node['target']
                if (not _valid_relative_name(name) or name in seen
                        or target['__typename']!='Commit' or type(target['oid']) is not str
                        or re.fullmatch('[0-9a-f]{40}',target['oid']) is None):
                    raise ValueError('INITIAL_HISTORY_REF_INVALID')
                seen.add(name);rows.append((INITIAL_CLAIM_NAMESPACE+name,target['oid']))
            if page['hasNextPage'] is False:
                if len(rows)!=total:raise ValueError('INITIAL_HISTORY_INCOMPLETE')
                return sorted(rows)
            next_cursor=page['endCursor']
            if page['hasNextPage'] is not True or not nodes or not next_cursor or next_cursor==cursor:
                raise ValueError('INITIAL_HISTORY_INCOMPLETE')
            cursor=next_cursor
        raise ValueError('INITIAL_HISTORY_PAGE_BUDGET')

    def decide(self,request_id,review_intent_id,namespace):
        if namespace!=INITIAL_CLAIM_NAMESPACE:raise ValueError('INITIAL_HISTORY_NAMESPACE_INVALID')
        before=self.inventory();matches=[]
        for ref,sha in before:
            if _INITIAL_CLAIM_REF.fullmatch(ref) is None:continue
            read=self.transport.read_journal_commit(sha)
            if read.status is not ReadStatusV3.FOUND:raise ValueError('INITIAL_HISTORY_UNAVAILABLE')
            record=decode_journal_v2(read.snapshot.journal_bytes)
            if record.attempt.admission['review_intent_id']==review_intent_id:
                matches.append(record.attempt.request_id)
        if self.inventory()!=before:raise ValueError('INITIAL_HISTORY_CHANGED')
        basis=dict(schema_version=1,evidence_type='v3-initial-history-observation',
            request_id=request_id,review_intent_id=review_intent_id,namespace=namespace,
            scan_boundary=self.scan_boundary,complete=True,matching_request_ids=sorted(matches))
        return InitialHistoryDecisionV3(request_id,review_intent_id,namespace,self.scan_boundary,
            True,tuple(sorted(matches)),artifact_identity(canonical_bytes(basis)+b'\n'))
