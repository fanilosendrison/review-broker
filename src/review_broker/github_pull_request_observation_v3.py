"""Authenticated GitHub Pull Request scope observation for candidate v3."""
from __future__ import annotations
from dataclasses import dataclass,replace
import json,re
from typing import Mapping
from urllib.parse import quote
from urllib.request import Request
from .admission_v3 import PullRequestObservationV3,SubjectSourceFeasibilityV3
from .github_http_live_v3 import HttpExecutorV3,HttpResponseV3,urllib_executor_bounded
from .identity import artifact_identity,canonical_bytes
from .packet_v2 import SubjectCaptureV2
from .packets import PATH_PATTERN

_API="https://api.github.com";_VERSION="2022-11-28";_MAX=8_000_000;_SHA=re.compile(r"[0-9a-f]{40}\Z")
_STATUSES={"added","removed","modified","renamed","copied","changed"}
def _safe_path(value:object)->bool:
 return isinstance(value,str) and PATH_PATTERN.fullmatch(value) is not None and all(part not in {".",".."} for part in value.split("/"))
class GitHubPullRequestObservationV3Error(RuntimeError): pass
@dataclass(frozen=True)
class PullRequestScopeV3:
 repository:str;repository_id:int;pull_request:int;pull_request_id:int
 base_sha:str;head_sha:str;merge_base_sha:str
 changes:tuple[dict[str,object],...];changed_files:int
 repository_before_evidence_id:str;repository_after_evidence_id:str;evidence_id:str
 def basis(self)->dict[str,object]:
  return {"schema_version":1,"evidence_type":"github-pull-request-scope-observation",
   "repository":self.repository,"repository_id":self.repository_id,
   "pull_request":self.pull_request,"pull_request_id":self.pull_request_id,
   "base_sha":self.base_sha,"head_sha":self.head_sha,"merge_base_sha":self.merge_base_sha,
   "changes":list(self.changes),"changed_files":self.changed_files,
   "repository_before_evidence_id":self.repository_before_evidence_id,
   "repository_after_evidence_id":self.repository_after_evidence_id}
class GitHubPullRequestObservationReaderV3:
 def __init__(self,token:str,repository:str,repository_id:int,pull_request:int,expected_head_sha:str,
              *,source_authority:object,executor:HttpExecutorV3|None=None):
  if not token or any(c in token for c in "\r\n"): raise ValueError("PR_TOKEN_INVALID")
  if type(repository_id) is not int or repository_id<1 or type(pull_request) is not int or pull_request<1 or _SHA.fullmatch(expected_head_sha) is None: raise ValueError("PR_EXPECTED_IDENTITY_INVALID")
  from .github_source_authority_v3 import GitHubSourceAuthorityV3
  if type(source_authority) is not GitHubSourceAuthorityV3:raise ValueError("PR_SOURCE_AUTHORITY_REQUIRED")
  permits=getattr(source_authority,"permits_token",None)
  if not callable(permits) or not permits(token,repository,repository_id): raise ValueError("PR_SOURCE_AUTHORITY_REQUIRED")
  self.token,self.repository,self.repository_id,self.pull_request,self.expected_head_sha=token,repository,repository_id,pull_request,expected_head_sha
  self.source_authority=source_authority;self._owner,self._name=repository.split("/",1);self._executor=executor or (lambda request:urllib_executor_bounded(request,_MAX));self._scope:PullRequestScopeV3|None=None;self._final:PullRequestObservationV3|None=None
 def _get(self,suffix:str)->HttpResponseV3:
  root=f"{_API}/repos/{quote(self._owner,safe='')}/{quote(self._name,safe='')}"
  request=Request(root+suffix,headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {self.token}","X-GitHub-Api-Version":_VERSION},method="GET")
  try:response=self._executor(request)
  except Exception:raise GitHubPullRequestObservationV3Error("PR_OBSERVATION_UNAVAILABLE") from None
  if not isinstance(response,HttpResponseV3):raise GitHubPullRequestObservationV3Error("PR_RESPONSE_INVALID")
  if response.status in {403,404}:raise GitHubPullRequestObservationV3Error("PR_AUTHORITY_AMBIGUOUS")
  if response.status!=200:raise GitHubPullRequestObservationV3Error("PR_OBSERVATION_UNAVAILABLE")
  return response
 def _object(self,suffix:str)->tuple[dict[str,object],Mapping[str,str]]:
  response=self._get(suffix)
  try:value=json.loads(response.body)
  except (UnicodeError,json.JSONDecodeError):raise GitHubPullRequestObservationV3Error("PR_RESPONSE_INVALID") from None
  if not isinstance(value,dict):raise GitHubPullRequestObservationV3Error("PR_RESPONSE_INVALID")
  return value,response.headers
 def _repository(self)->str:
  value,_=self._object("")
  if value.get("full_name")!=self.repository or value.get("id")!=self.repository_id:raise GitHubPullRequestObservationV3Error("PR_REPOSITORY_IDENTITY_MISMATCH")
  basis={"schema_version":1,"evidence_type":"github-repository-observation","repository":self.repository,"repository_id":self.repository_id}
  return artifact_identity(canonical_bytes(basis)+b"\n")
 @staticmethod
 def _has_next(headers:Mapping[str,str])->bool:
  link=next((v for k,v in headers.items() if k.lower()=="link"),"");return any('rel="next"' in part for part in link.split(","))
 def observe_scope(self)->PullRequestScopeV3:
  before=self._repository();pr,_=self._object(f"/pulls/{self.pull_request}")
  head,base=pr.get("head"),pr.get("base")
  if (pr.get("number")!=self.pull_request or type(pr.get("id")) is not int or pr["id"]<1
   or not isinstance(head,dict) or not isinstance(base,dict) or head.get("sha")!=self.expected_head_sha
   or _SHA.fullmatch(str(base.get("sha"))) is None or type(pr.get("changed_files")) is not int
   or pr["changed_files"]<1 or pr["changed_files"]>=3000):raise GitHubPullRequestObservationV3Error("PR_IDENTITY_INVALID")
  base_sha=str(base["sha"]);compare,_=self._object(f"/compare/{base_sha}...{self.expected_head_sha}");merge=compare.get("merge_base_commit");compare_base=compare.get("base_commit");commits=compare.get("commits")
  if (not isinstance(merge,dict) or _SHA.fullmatch(str(merge.get("sha"))) is None
   or not isinstance(compare_base,dict) or compare_base.get("sha")!=base_sha
   or not isinstance(commits,list) or not commits or not isinstance(commits[-1],dict)
   or commits[-1].get("sha")!=self.expected_head_sha):raise GitHubPullRequestObservationV3Error("PR_COMPARE_INVALID")
  changes=[];page=1
  while True:
   response=self._get(f"/pulls/{self.pull_request}/files?per_page=100&page={page}")
   try:batch=json.loads(response.body)
   except (UnicodeError,json.JSONDecodeError):raise GitHubPullRequestObservationV3Error("PR_FILES_RESPONSE_INVALID") from None
   if not isinstance(batch,list) or len(batch)>100:raise GitHubPullRequestObservationV3Error("PR_FILES_RESPONSE_INVALID")
   for item in batch:
    if not isinstance(item,dict):raise GitHubPullRequestObservationV3Error("PR_FILE_INVALID")
    status,path=item.get("status"),item.get("filename");previous=item.get("previous_filename") if status in {"renamed","copied"} else None
    if (status not in _STATUSES or not _safe_path(path)
     or status in {"renamed","copied"} and not _safe_path(previous)):
     raise GitHubPullRequestObservationV3Error("PR_FILE_INVALID")
    changes.append({"status":status,"path":path,"previous_path":previous})
   has_next=self._has_next(response.headers)
   if has_next and not batch:raise GitHubPullRequestObservationV3Error("PR_FILES_PAGINATION_INCOMPLETE")
   if not has_next:break
   page+=1
   if page>30:raise GitHubPullRequestObservationV3Error("PR_FILES_PAGINATION_EXCEEDED")
  paths=[item["path"] for item in changes]
  if len(changes)!=pr["changed_files"] or len(paths)!=len(set(paths)):raise GitHubPullRequestObservationV3Error("PR_FILES_INCOMPLETE_OR_DUPLICATE")
  after=self._repository();provisional=PullRequestScopeV3(self.repository,self.repository_id,self.pull_request,pr["id"],base_sha,self.expected_head_sha,str(merge["sha"]),tuple(changes),len(changes),before,after,"")
  self._scope=replace(provisional,evidence_id=artifact_identity(canonical_bytes(provisional.basis())+b"\n"));return self._scope
 def verify_final_identity(self,scope:PullRequestScopeV3)->None:
  self._repository();pr,_=self._object(f"/pulls/{self.pull_request}");head,base=pr.get("head"),pr.get("base")
  if pr.get("id")!=scope.pull_request_id or not isinstance(head,dict) or not isinstance(base,dict) or head.get("sha")!=scope.head_sha or base.get("sha")!=scope.base_sha:raise GitHubPullRequestObservationV3Error("PR_FINAL_IDENTITY_DRIFT")
  self._repository()
 def finalize(self,scope:PullRequestScopeV3,capture:SubjectCaptureV2)->PullRequestObservationV3:
  if scope!=self._scope or (capture.repository,capture.repository_id,capture.pull_request,capture.pull_request_id,capture.head_sha,capture.base_sha,capture.merge_base_sha)!=(scope.repository,scope.repository_id,scope.pull_request,scope.pull_request_id,scope.head_sha,scope.base_sha,scope.merge_base_sha):raise GitHubPullRequestObservationV3Error("PR_CAPTURE_IDENTITY_MISMATCH")
  self.verify_final_identity(scope)
  sources=tuple(SubjectSourceFeasibilityV3(f"S{i:03d}",len(record.original_bytes),sum(len(line.encode("utf-8"))+9 for line in record.lines)) for i,record in enumerate(capture.records,1))
  basis={"schema_version":1,"evidence_type":"v3-pull-request-observation","repository":scope.repository,"repository_id":scope.repository_id,"pull_request":scope.pull_request,"pull_request_id":scope.pull_request_id,"head_sha":scope.head_sha,"base_sha":scope.base_sha,"subject_sources":[{"source_id":x.source_id,"original_bytes":x.original_bytes,"rendered_bytes":x.rendered_bytes} for x in sources]}
  self._final=PullRequestObservationV3(scope.repository,scope.repository_id,scope.pull_request,scope.pull_request_id,scope.head_sha,scope.base_sha,sources,artifact_identity(canonical_bytes(basis)+b"\n"));return self._final
 def observe(self,repository:str,repository_id:int,pull_request:int)->PullRequestObservationV3|None:
  if (repository,repository_id,pull_request)!=(self.repository,self.repository_id,self.pull_request):return None
  return self._final
