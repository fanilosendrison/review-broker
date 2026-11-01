"""Exact isolated Git-backed subject capture for authenticated v3 PR scope."""
from __future__ import annotations
from dataclasses import replace
import os,subprocess
from pathlib import Path
from typing import Callable,Mapping
from .admission_v3 import SourceRepositoryAuthorizationV3
from .github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3,PullRequestScopeV3
from .packet_v2 import SubjectCaptureV2,subject_capture_evidence_id_v2
from .packets import GitSourceReader,SourceSpec
from .source_authorization import isolated_source_environment,require_private_source_environment

class GitHubSubjectCaptureV3Error(RuntimeError):pass
AcquireRepositoryV3=Callable[[Path,Mapping[str,str]],None]
def _run(arguments:list[str],environment:Mapping[str,str],timeout:int=300)->bytes:
 try:result=subprocess.run(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=timeout,shell=False,env=dict(environment))
 except (OSError,subprocess.TimeoutExpired):raise GitHubSubjectCaptureV3Error("SUBJECT_GIT_COMMAND_FAILED") from None
 if result.returncode!=0:raise GitHubSubjectCaptureV3Error("SUBJECT_GIT_COMMAND_FAILED")
 return result.stdout
def _default_acquire(repository:str,token:str)->AcquireRepositoryV3:
 def acquire(destination:Path,environment:Mapping[str,str])->None:
  remote=f"https://github.com/{repository}.git"
  _run(["gh","repo","clone",remote,str(destination),"--","--filter=blob:none","--no-checkout","--no-tags","--depth=256"],environment)
  if token.encode() in _run(["git","-C",str(destination),"remote","get-url","origin"],environment):raise GitHubSubjectCaptureV3Error("SOURCE_TOKEN_IN_GIT_REMOTE")
 return acquire
def _inventory(reader:GitSourceReader,merge_base:str,head:str)->tuple[dict[str,object],...]:
 raw=reader._git("diff","--name-status","-z","--find-renames","--find-copies-harder",merge_base,head,"--")
 if not raw.endswith(b"\0"):raise GitHubSubjectCaptureV3Error("SUBJECT_CHANGE_INVENTORY_INVALID")
 parts=raw.split(b"\0")[:-1];cursor=0;result=[]
 try:
  while cursor<len(parts):
   status=parts[cursor].decode("ascii");cursor+=1;previous=None
   if not status:raise ValueError
   if status[0] in "RC":previous=parts[cursor].decode("ascii");cursor+=1
   path=parts[cursor].decode("ascii");cursor+=1
   kind={"A":"added","D":"removed","M":"modified","T":"changed","R":"renamed","C":"copied"}.get(status[0])
   if kind is None:raise ValueError
   result.append({"status":kind,"path":path,"previous_path":previous})
 except (UnicodeError,IndexError,ValueError):raise GitHubSubjectCaptureV3Error("SUBJECT_CHANGE_INVENTORY_INVALID") from None
 return tuple(result)
def _read_regular(git:GitSourceReader,spec:SourceSpec):
 raw=git._git("ls-tree",spec.commit,"--",spec.path)
 try:metadata,listed_path=raw.rstrip(b"\n").split(b"\t",1);mode,kind,_=metadata.split(b" ",2)
 except ValueError:raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_METADATA_INVALID") from None
 if listed_path.decode("ascii")!=spec.path or kind!=b"blob" or mode not in {b"100644",b"100755"}:raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_TYPE_UNSUPPORTED")
 return git.read(spec)
def capture_authenticated_subject_v3(scope:PullRequestScopeV3,reader:GitHubPullRequestObservationReaderV3,
 source_authorization:SourceRepositoryAuthorizationV3,source_authority_scope_evidence_id:str,
 source_token:str,private_root:Path,*,acquire_repository:AcquireRepositoryV3|None=None)->SubjectCaptureV2:
 """Acquire exact Git objects without checkout or reviewed-code execution."""
 expected_authorization=reader.source_authority.authorize(scope.repository,scope.repository_id)
 if (source_authorization!=expected_authorization
  or source_authority_scope_evidence_id!=reader.source_authority.scope_observation.evidence_id):
  raise GitHubSubjectCaptureV3Error("SUBJECT_SOURCE_AUTHORITY_MISMATCH")
 environment=require_private_source_environment(scope.repository,frozenset({scope.repository}),source_token)
 if private_root.is_symlink() or private_root.exists() and not private_root.is_dir():raise GitHubSubjectCaptureV3Error("SUBJECT_CAPTURE_ROOT_INVALID")
 private_root.mkdir(mode=0o700,parents=True,exist_ok=True)
 with isolated_source_environment(environment) as isolated:
  assert isolated is not None;repository_root=private_root/"source.git"
  (acquire_repository or _default_acquire(scope.repository,source_token))(repository_root,isolated)
  isolated={**isolated,"GIT_NO_REPLACE_OBJECTS":"1"}
  for commit in (scope.base_sha,scope.head_sha):
   try:_run(["git","-C",str(repository_root),"fetch","origin",commit,"--depth=256"],isolated,180)
   except GitHubSubjectCaptureV3Error:raise GitHubSubjectCaptureV3Error("SUBJECT_COMMIT_FETCH_FAILED") from None
  git=GitSourceReader(repository_root,environment=isolated);merge=None
  for deepen in (0,256,512,1024,2048,4096):
   try:merge=git._git("merge-base",scope.base_sha,scope.head_sha).decode().strip()
   except Exception:
    if deepen==4096:break
    _run(["git","-C",str(repository_root),"fetch","origin",f"--deepen={max(1,deepen)}"],isolated,180);continue
   break
  if merge is None:raise GitHubSubjectCaptureV3Error("SUBJECT_ANCESTRY_UNAVAILABLE")
  if merge!=scope.merge_base_sha:raise GitHubSubjectCaptureV3Error("SUBJECT_MERGE_BASE_MISMATCH")
  inventory=_inventory(git,merge,scope.head_sha)
  if inventory!=scope.changes or git.changed_paths(merge,scope.head_sha)!={item["path"] for item in scope.changes}:raise GitHubSubjectCaptureV3Error("SUBJECT_CHANGE_SCOPE_MISMATCH")
  records=[]
  for change in inventory:
   status,path,previous=change["status"],change["path"],change["previous_path"]
   if status!="added":records.append(_read_regular(git,SourceSpec(scope.repository,merge,previous or path)))
   if status!="removed":records.append(_read_regular(git,SourceSpec(scope.repository,scope.head_sha,path)))
  diff=git.diff(merge,scope.head_sha)
  credential=source_token.encode("utf-8")
  if credential in diff or any(credential in record.original_bytes for record in records):
   raise GitHubSubjectCaptureV3Error("SOURCE_CREDENTIAL_IN_CAPTURED_BYTES")
  provisional=SubjectCaptureV2(scope.repository,scope.repository_id,scope.pull_request,scope.pull_request_id,scope.head_sha,scope.base_sha,merge,inventory,tuple(records),diff,"",repository_root,"AUTHENTICATED_SOURCE_READ_ONLY",source_authorization.evidence_id,scope.evidence_id)
  capture=replace(provisional,evidence_id=subject_capture_evidence_id_v2(provisional));reader.verify_final_identity(scope)
  config=git._git("config","--local","--list")
  if source_token.encode() in config:raise GitHubSubjectCaptureV3Error("SOURCE_TOKEN_RETAINED_IN_GIT_CONFIG")
  return capture
def bind_authenticated_capture_v3(capture:SubjectCaptureV2,source_authorization_evidence_id:str,
 pr_observation_evidence_id:str)->SubjectCaptureV2:
 """Bind the finalized admission authorities without changing captured Git bytes."""
 if capture.verification!="AUTHENTICATED_SOURCE_READ_ONLY":raise GitHubSubjectCaptureV3Error("AUTHENTICATED_CAPTURE_REQUIRED")
 value=replace(capture,evidence_id="",source_authorization_evidence_id=source_authorization_evidence_id,pr_observation_evidence_id=pr_observation_evidence_id)
 return replace(value,evidence_id=subject_capture_evidence_id_v2(value))
