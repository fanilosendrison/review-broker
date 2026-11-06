"""Concrete Git Database HTTP writer with external simulated CAS attribution."""
from review_broker.github_transport_live_v3 import GitHubTransportLiveV3
from review_broker.github_journal_transport_v3 import TransportSnapshotV3
from tests.github_transport_live_v3_support import FakeGitHubApi, PARENT_TREE, git_blob_sha


class ConcreteFailureGitTransport(GitHubTransportLiveV3):
    def __init__(self, original, snapshot, api):
        self.original=original
        api.rest_node=api.graphql_node=snapshot.repository_node_id
        api.commits[snapshot.commit_sha]=(PARENT_TREE,[snapshot.parent_sha])
        blob=git_blob_sha(snapshot.journal_bytes);api.blobs[blob]=snapshot.journal_bytes
        api.trees[PARENT_TREE]=[
            {'path':'README.md','mode':'100644','type':'blob','sha':'3'*40},
            {'path':'.review-broker','mode':'040000','type':'tree','sha':'d'*40},
            {'path':'.review-broker/attempt.json','mode':'100644','type':'blob','sha':blob},
        ]
        api.refs[snapshot.claim_ref]=snapshot.commit_sha
        super().__init__('fixture-git-control-token',snapshot.repository,executor=api)

    def read_claim(self, claim_ref):
        # Same external authoritative ref service used by the live-HTTP adapter's
        # qualified fake backend; no alternate head or predecessor is invented.
        return self.original.read_claim(claim_ref)

    def create_journal_commit(self, parent_sha, raw):
        sha=super().create_journal_commit(parent_sha,raw)
        self.original.commits[sha]=TransportSnapshotV3(sha,parent_sha,raw)
        return sha

    def update_ref(self, update):
        result=super().update_ref(update)
        if result.http_status==200 and not result.errors:
            # The independent service owns the expected-old application and writer
            # receipt. HTTP success alone never supplies synthetic attribution.
            return self.original.update_ref(update)
        return result


def install_concrete_failure_writer(scenario, *, revoke_after=None, permission_status=None):
    server=scenario.real.worker.transport
    a=scenario.authority.snapshot
    api=FakeGitHubApi()
    if permission_status is not None:api.graphql_status=permission_status
    original=api.__call__
    def execute(request):
        response=original(request)
        body=request.data or b''
        path=request.full_url
        trigger=(revoke_after is not None and request.get_method()=='POST' and (
            path.endswith('/git/'+revoke_after) or revoke_after=='identity' and api.mutation_calls==3
            and path.endswith('/graphql') and b'query(' in body))
        if trigger:
            api.revoke_index=len(api.calls)
            sha=server.create_journal_commit(a.commit_sha,a.journal_bytes)
            server.attributed.add(sha);server.refs[a.claim_ref]=sha
        return response
    transport=ConcreteFailureGitTransport(server,a,api)
    transport._executor=execute
    scenario.real.worker.journal.transport=transport
    return api,transport
