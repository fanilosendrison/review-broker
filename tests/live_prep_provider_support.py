"""External provider HTTP/Git fixture. All admission/transition/packet code is real."""
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from tests.github_transport_live_v3_support import FakeGitHubApi, PARENT_TREE, NODE_ID
from tests.issue69_test_support import git_graph, PullApi, ScopeApi
from tests.live_prep_actions_support import ActionsService, response, SHA, REF
from tests.test_github_git_file_v3 import Api as GitFileApi, COMMIT, DATA
from tests.request_v3_test_support import request
from review_broker.github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID

TOKEN_A='fixture-controller-source-ephemeral-credential'
TOKEN_B='fixture-worker-source-different-ephemeral-credential'
BODY='qualification reference body\n'
COMMENT='qualification reference comment\n'


def controller_scenario(root,service,token=None):
    from review_broker.request_v3 import request_identity_v3
    from review_broker.live_pre_model_controller_v3 import run_live_controller_v3
    identifier=request_identity_v3(service.request)
    runtime=service.runtime('controller',{'request_issue_number':51,'request_id':identifier})
    return run_live_controller_v3(runtime=runtime,issue=51,request_id=identifier,
        gates=service.gates(identifier),source_token=token or service.minted('controller'),
        app_slug='review-broker-app',installation_id=123,private_root=root/'controller-source',
        source_executor=service.source,acquire_repository=service.acquire)


class GitDatabaseService(FakeGitHubApi):
    def __init__(self):
        super().__init__();self.counter=100;self.lost_update=False;self.lose_ack=False
        self.commits[SHA]=(PARENT_TREE,['0'*40]);self.refs[REF]=SHA
        self.after_mutation=None

    def __call__(self,req):
        path=urlsplit(req.full_url).path;data=json.loads(req.data) if req.data else None
        root='/repos/'+REPOSITORY
        write=req.method=='POST' and (path!='/graphql' or data['query'].startswith('mutation'))
        if write and self.after_mutation:self.after_mutation(path)
        if req.method=='POST' and path==root+'/git/trees':
            self._record(req);self.mutation_calls+=1;self.counter+=1
            sha=f'{self.counter:040x}';base=self.trees[data['base_tree']]
            rows=[e for e in base if e['path'] not in {'.review-broker/attempt.json','.review-broker'}]
            self.trees[sha]=rows+[{'path':'.review-broker','mode':'040000','type':'tree','sha':'d'*40}]+data['tree']
            return response({'sha':sha},201)
        if req.method=='POST' and path==root+'/git/commits':
            self._record(req);self.mutation_calls+=1;self.counter+=1
            sha=f'{self.counter:040x}';self.commits[sha]=(data['tree'],data['parents'])
            return response({'sha':sha},201)
        if req.method=='POST' and path=='/graphql' and data['query'].startswith('mutation'):
            self._record(req);self.mutation_calls+=1;v=data['variables']
            if self.refs.get(v['name'])!=v['beforeOid']:
                return response({'data':{'updateRefs':None},'errors':[{'type':'UNPROCESSABLE'}]})
            self.refs[v['name']]=v['afterOid']
            tree=self.trees[self.commits[v['afterOid']][0]]
            blob=next(e['sha'] for e in tree if e['path']=='.review-broker/attempt.json')
            event=json.loads(self.blobs[blob])['history'][-1].get('event')
            if self.lost_update or self.lose_ack and event=='PRE_MODEL_DISPATCH_ACKNOWLEDGED':
                raise TimeoutError('response lost after provider CAS')
            return response({'data':{'updateRefs':{'clientMutationId':None}}})
        return super().__call__(req)


class LiveProviderService(ActionsService):
    def __init__(self,root):
        self.origin,self.base,self.head,self.merge,self.changes=git_graph(root)
        references=[{'id':'inline-fixture','required':True,'source':{'kind':'inline','text':'qualification inline\n'}},
            {'id':'contract','required':True,'source':{'kind':'git_file','repository':REPOSITORY,
                'commit':COMMIT,'path':'contract.md','expected_sha256':hashlib.sha256(DATA).hexdigest()}},
            {'id':'body','required':True,'source':{'kind':'github_issue_body','repository':REPOSITORY,
                'issue':43,'expected_sha256':hashlib.sha256(BODY.encode()).hexdigest()}},
            {'id':'comment','required':True,'source':{'kind':'github_issue_comment','repository':REPOSITORY,
                'comment_id':99,'expected_sha256':hashlib.sha256(COMMENT.encode()).hexdigest()}}]
        super().__init__(request(subject={'kind':'github_pr','repository':REPOSITORY,'repository_id':REPOSITORY_ID,
            'pull_request':71,'expected_head_commit':self.head},references=references))
        self.controller_running=True
        self.git=GitDatabaseService();self.source_calls=[];self.first_mutation=False
        self.source_after_mutation=0;self.source_with_control=0;self.journal_with_source=0
        self.body_reference=BODY;self.comment_reference=COMMENT;self.scope=ScopeApi()
        self.reference_failure=None
        self.pull=PullApi(self.base,self.head,self.merge,self.changes)
        self.git_file=GitFileApi();self.acquisitions=[];self.mints=[]
        self.git.after_mutation=self.mutated

    def minted(self,phase,*,proposed=None):
        if phase=='worker' and proposed==TOKEN_A:raise ValueError('fixture prohibits Controller credential reuse')
        if phase in self.mints:raise ValueError('fixture prohibits token reuse across runs')
        self.mints.append(phase)
        return TOKEN_A if phase=='controller' else TOKEN_B

    def mutated(self,path):self.first_mutation=True

    def claim_count(self):return len([r for r in self.git.refs if r.startswith('refs/heads/review-claims-v3/')])

    def acquire(self,destination,environment):
        token=environment.get('GH_TOKEN')
        assert token in {TOKEN_A,TOKEN_B} and 'GITHUB_TOKEN' not in environment
        if token==TOKEN_A:assert self.claim_count()==0 and not self.first_mutation
        self.acquisitions.append(token)
        subprocess.run(['git','clone','-q','--no-checkout','--no-hardlinks',str(self.origin),str(destination)],
            env=environment,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def source(self,req):
        credential=req.get_header('Authorization')
        if credential not in {'Bearer '+TOKEN_A,'Bearer '+TOKEN_B}:
            self.source_with_control+=1;raise AssertionError('source request without source credential')
        if credential=='Bearer '+TOKEN_A:
            if self.first_mutation:self.source_after_mutation+=1
            assert self.claim_count()==0 and not self.first_mutation
        self.source_calls.append((req.full_url,credential))
        path=urlsplit(req.full_url).path
        if path=='/installation/repositories':return self.scope(req)
        if '/pulls/' in path or '/compare/' in path:return self.pull(req)
        if path.endswith('/issues/43'):
            if self.reference_failure is not None:return response({},self.reference_failure)
            return response({'id':430,'number':43,'body':self.body_reference,'updated_at':'2026-01-01Z','user':{'id':7}})
        if path.endswith('/issues/comments/99'):
            return response({'id':99,'body':self.comment_reference,'updated_at':'2026-01-01Z',
                'issue_url':f'https://api.github.com/repos/{REPOSITORY}/issues/43','user':{'id':8}})
        return self.git_file(req)

    def __call__(self,req):
        credential=req.get_header('Authorization')
        if credential!='Bearer fixture-control':
            self.journal_with_source+=1;raise AssertionError('journal/control request with source credential')
        path=urlsplit(req.full_url).path
        data=json.loads(req.data) if req.data else None
        if path=='/graphql' and data['query'].startswith('query') and 'refs(' in data['query']:
            rows=[{'name':r.removeprefix('refs/heads/'),'target':{'oid':s,'__typename':'Commit'}}
                  for r,s in sorted(self.git.refs.items()) if r.startswith('refs/heads/review-claims-v3/')]
            return response({'data':{'repository':{'databaseId':REPOSITORY_ID,'nameWithOwner':REPOSITORY,
                'refs':{'totalCount':len(rows),'nodes':rows,'pageInfo':{'hasNextPage':False,'endCursor':None}}}}})
        if '/git/' in path or path=='/graphql':return self.git(req)
        return super().__call__(req)
