"""Deterministic HTTP and real-Git fixtures for Issue #69."""
from __future__ import annotations
import json,os,shutil,subprocess
from pathlib import Path
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_source_authority_v3 import GitHubSourceAuthorityV3
from review_broker.admission_v3 import admit_initial_inline_v3
from tests.request_v3_test_support import HistoryAuthority,origin
from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
REPOSITORY="fanilosendrison/review-broker";REPOSITORY_ID=1433701208;TOKEN="token";INSTALLATION_ID=123
PERMISSIONS=frozenset({"contents:read","pull_requests:read","metadata:read","issues:read"})
class ScopeApi:
 def __init__(self,*,repositories=None,total=None,status=200,links=None):
  self.repositories=repositories or [{"full_name":REPOSITORY,"id":REPOSITORY_ID}];self.total=len(self.repositories) if total is None else total;self.status=status;self.links=links or {};self.calls=[];self.methods=[]
 def __call__(self,request):
  self.calls.append(request.full_url);self.methods.append(request.method);page=int(request.full_url.rsplit("page=",1)[1]);batch=self.repositories[(page-1)*100:page*100];headers={}
  if page in self.links:headers["Link"]=self.links[page]
  return HttpResponseV3(self.status,json.dumps({"total_count":self.total,"repositories":batch}).encode(),headers)
def source_authority(api=None,*,permissions=PERMISSIONS,repository_id=REPOSITORY_ID,installation_id=INSTALLATION_ID):
 value=GitHubSourceAuthorityV3(TOKEN,expected_app_slug="github-app:source",expected_installation_id=installation_id,repository=REPOSITORY,repository_id=repository_id,approved_permissions=permissions,authorized_repositories=frozenset({REPOSITORY}),executor=api or ScopeApi());value.observe_scope();return value
class PullApi:
 def __init__(self,base:str,head:str,merge:str,changes:list[dict],*,pr_id=7001,repo_id=REPOSITORY_ID,drift_head=None,drift_base=None,compare_base=None,files_total=None,status=200):
  self.base,self.head,self.merge,self.changes=base,head,merge,changes;self.pr_id,self.repo_id=pr_id,repo_id;self.drift_head,self.drift_base=drift_head,drift_base;self.compare_base=compare_base or base;self.files_total=files_total or len(changes);self.status=status;self.pr_reads=0;self.calls=[];self.methods=[]
 def __call__(self,request):
  self.calls.append(request.full_url);self.methods.append(request.method);url=request.full_url
  if self.status!=200:return HttpResponseV3(self.status,b"{}",{})
  if url.endswith("/review-broker"):value={"full_name":REPOSITORY,"id":self.repo_id}
  elif "/compare/" in url:value={"base_commit":{"sha":self.compare_base},"merge_base_commit":{"sha":self.merge},"commits":[{"sha":self.head}]}
  elif "/files?" in url:
   page=int(url.rsplit("page=",1)[1]);batch=self.changes[(page-1)*100:page*100];headers={}
   if page*100<len(self.changes):headers["Link"]='<https://api.github.com/next>; rel="next"'
   return HttpResponseV3(200,json.dumps(batch).encode(),headers)
  elif url.endswith("/pulls/71"):
   self.pr_reads+=1;head=self.drift_head if self.pr_reads>1 and self.drift_head else self.head;base=self.drift_base if self.pr_reads>1 and self.drift_base else self.base
   value={"number":71,"id":self.pr_id,"head":{"sha":head},"base":{"sha":base},"changed_files":self.files_total}
  else:raise AssertionError(url)
  return HttpResponseV3(200,json.dumps(value).encode(),{})
def git_graph(root:Path)->tuple[Path,str,str,str,list[dict]]:
 repository=root/"origin";repository.mkdir();subprocess.run(["git","init","-q","-b","main",str(repository)],check=True)
 subprocess.run(["git","-C",str(repository),"config","user.email","test@example.invalid"],check=True);subprocess.run(["git","-C",str(repository),"config","user.name","Test"],check=True)
 env={**os.environ,"GIT_AUTHOR_DATE":"2026-01-01T00:00:00Z","GIT_COMMITTER_DATE":"2026-01-01T00:00:00Z"}
 (repository/"review.md").write_bytes(b"common\n");subprocess.run(["git","-C",str(repository),"add","."],check=True);subprocess.run(["git","-C",str(repository),"commit","-q","-m","merge-base"],check=True,env=env);merge=_sha(repository)
 subprocess.run(["git","-C",str(repository),"checkout","-q","-b","feature"],check=True);(repository/"review.md").write_bytes(b"feature\n");(repository/"added.md").write_bytes(b"added\n");subprocess.run(["git","-C",str(repository),"add","."],check=True);subprocess.run(["git","-C",str(repository),"commit","-q","-m","head"],check=True,env=env);head=_sha(repository)
 subprocess.run(["git","-C",str(repository),"checkout","-q","main"],check=True);(repository/"base-only.md").write_bytes(b"base\n");subprocess.run(["git","-C",str(repository),"add","."],check=True);subprocess.run(["git","-C",str(repository),"commit","-q","-m","base"],check=True,env=env);base=_sha(repository)
 changes=[{"status":"added","filename":"added.md"},{"status":"modified","filename":"review.md"}]
 return repository,base,head,merge,changes
def _sha(repository):return subprocess.check_output(["git","-C",str(repository),"rev-parse","HEAD"],text=True).strip()
def authenticated_admission(request_value,pr_authority,source):
 origin_reader=origin(request_value);observed=origin_reader.observe(51);requester=GitHubRequesterAuthorityV3(requester_id=observed.requester_id,broker_issue_id=observed.issue_id,origin_evidence_id=observed.evidence_id,authorized=True)
 return admit_initial_inline_v3(origin_reader,broker_issue_number=51,expected_broker_issue_id=6106789428,expected_requester_id=30498238,requester_authority=requester,pr_authority=pr_authority,source_authority=source,history_authority=HistoryAuthority())
def local_acquirer(origin:Path):
 def acquire(destination:Path,environment):
  shutil.copytree(origin,destination);subprocess.run(["git","-C",str(destination),"remote","add","origin",str(origin)],check=True)
 return acquire
