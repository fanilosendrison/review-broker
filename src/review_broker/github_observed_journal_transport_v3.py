"""Fresh ref observations with bounded reuse of already authenticated immutable Git objects."""
from collections import OrderedDict
from urllib.parse import quote

from .github_git_database_transport_v3 import GitHubJournalEvidenceTransportV3
from .github_journal_transport_v3 import ReadResultV3,ReadStatusV3


class GitHubObservedJournalTransportV3(GitHubJournalEvidenceTransportV3):
    """Cache DATA by commit SHA, never ref state, actor permission or writer acknowledgment.

    Only a successful full provider read populates the bounded corpus. Mutable refs
    are read anew on every read_claim. The existing current-Worker authority still
    reobserves run/job and exact predecessor before effects. This relies on Git's
    immutable object identity, not a timeout or producer-provided content hash.
    """
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._observed=OrderedDict()

    def _remember(self,result):
        if result.status is ReadStatusV3.FOUND and result.snapshot is not None:
            sha=result.snapshot.commit_sha;self._observed[sha]=result.snapshot
            self._observed.move_to_end(sha)
            while len(self._observed)>8:self._observed.popitem(last=False)
        return result

    def read_claim(self,claim_ref):
        ref=self._ref(claim_ref)
        if self._observed:
            response=self._rest('GET','/git/ref/'+quote(ref.removeprefix('refs/'),safe='/'))
            if response.status==200:
                value=self._json(response);obj=value.get('object',{})
                if value.get('ref')!=ref or obj.get('type')!='commit':
                    return ReadResultV3(ReadStatusV3.UNAVAILABLE)
                sha=self._sha(obj.get('sha'))
                if sha in self._observed:
                    self._observed.move_to_end(sha)
                    return ReadResultV3(ReadStatusV3.FOUND,self._observed[sha])
        return self._remember(super().read_claim(ref))

    def read_journal_commit(self,commit_sha):
        sha=self._sha(commit_sha)
        if sha in self._observed:
            self._observed.move_to_end(sha)
            return ReadResultV3(ReadStatusV3.FOUND,self._observed[sha])
        return self._remember(super().read_journal_commit(sha))
