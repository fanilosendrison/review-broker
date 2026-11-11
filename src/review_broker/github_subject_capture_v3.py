"""Exact isolated Git-backed subject capture for authenticated v3 PR scope."""
from __future__ import annotations
from dataclasses import replace
from functools import partial
import hashlib,os,selectors,signal,subprocess,time
from pathlib import Path
from typing import Callable,Mapping
from .admission_v3 import SourceRepositoryAuthorizationV3
from .github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3,PullRequestScopeV3
from .packet_v2 import SubjectCaptureV2,subject_capture_evidence_id_v2
from .packets import GitSourceReader,MAX_PACKET_BYTES,MAX_SOURCE_BYTES,MAX_SOURCE_COUNT,SourceRecord,SourceSpec
from .source_authorization import isolated_source_environment,require_private_source_environment

class GitHubSubjectCaptureV3Error(RuntimeError):pass
_popen=subprocess.Popen
AcquireRepositoryV3=Callable[[Path,Mapping[str,str]],None]
def _close_pipes(process)->None:
 for stream in (process.stdout,process.stderr):
  if stream is not None:stream.close()
def _terminate(process)->None:
 try:os.killpg(process.pid,signal.SIGKILL)
 except OSError:
  if process.poll() is None:process.kill()
 process.communicate();_close_pipes(process)
def _run(arguments:list[str],environment:Mapping[str,str],timeout:int=300,*,failure_observer=None,repository=None,operation=None,before_effect=None,transfer_observer=None)->bytes:
 if before_effect is not None:before_effect()
 try:
  process=_popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(environment),start_new_session=True)
  if transfer_observer is not None and operation in {'GIT_CLONE','GIT_FETCH'}:
   transfer_observer.transfer_started(repository,operation,tuple(arguments),process)
  stdout,_=process.communicate(timeout=timeout);_close_pipes(process)
 except subprocess.TimeoutExpired:
  if 'process' in locals():
   _terminate(process)
   if transfer_observer is not None and process.poll() is not None:
    transfer_observer.transfer_terminated(process)
   if failure_observer is not None and process.poll() is not None and operation in {"GIT_CLONE","GIT_FETCH"}:
    failure_observer.transfer_timeout(repository,operation,arguments,process)
  raise GitHubSubjectCaptureV3Error("SUBJECT_GIT_COMMAND_TIMEOUT") from None
 except OSError:raise GitHubSubjectCaptureV3Error("SUBJECT_GIT_COMMAND_FAILED") from None
 if process.returncode!=0:raise GitHubSubjectCaptureV3Error("SUBJECT_GIT_COMMAND_FAILED")
 return stdout
def _default_acquire(repository:str,token:str,failure_observer=None,before_effect=None,transfer_observer=None)->AcquireRepositoryV3:
 def acquire(destination:Path,environment:Mapping[str,str])->None:
  remote=f"https://github.com/{repository}.git"
  run=partial(_run,before_effect=before_effect,failure_observer=failure_observer,repository=repository,operation="GIT_CLONE",transfer_observer=transfer_observer)
  run(["gh","repo","clone",remote,str(destination),"--","--filter=blob:none","--no-checkout","--no-tags","--depth=256"],environment)
  if token.encode() in _run(["git","-C",str(destination),"remote","get-url","origin"],environment,before_effect=before_effect):raise GitHubSubjectCaptureV3Error("SOURCE_TOKEN_IN_GIT_REMOTE")
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
def _read_regular(git:GitSourceReader,spec:SourceSpec,before_effect=None):
 raw=git._git("ls-tree",spec.commit,"--",spec.path)
 try:metadata,listed_path=raw.rstrip(b"\n").split(b"\t",1);mode,kind,oid_bytes=metadata.split(b" ",2);oid=oid_bytes.decode("ascii")
 except (ValueError,UnicodeError):raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_METADATA_INVALID") from None
 if listed_path.decode("ascii")!=spec.path or kind!=b"blob" or mode not in {b"100644",b"100755"}:raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_TYPE_UNSUPPORTED")
 if before_effect is not None:before_effect()
 try:
  process=_popen(["git","-C",str(git.repository_root),"cat-file","blob",oid],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=git.environment,start_new_session=True)
  assert process.stdout is not None and process.stderr is not None;selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ,"stdout");selector.register(process.stderr,selectors.EVENT_READ,"stderr");data=bytearray();deadline=time.monotonic()+git.timeout_seconds
  while selector.get_map():
   remaining=deadline-time.monotonic()
   if remaining<=0:raise subprocess.TimeoutExpired(process.args,git.timeout_seconds)
   events=selector.select(remaining)
   if not events:raise subprocess.TimeoutExpired(process.args,git.timeout_seconds)
   for key,_ in events:
    chunk=os.read(key.fileobj.fileno(),65536)
    if not chunk:selector.unregister(key.fileobj);continue
    if key.data=="stdout":
     data.extend(chunk)
     if len(data)>MAX_SOURCE_BYTES:raise GitHubSubjectCaptureV3Error("SUBJECT_SOURCE_TOO_LARGE")
  process.wait(timeout=max(0.01,deadline-time.monotonic()));data=bytes(data);_close_pipes(process)
 except GitHubSubjectCaptureV3Error:
  _terminate(process);raise
 except (OSError,subprocess.TimeoutExpired):
  if 'process' in locals():_terminate(process)
  raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_READ_FAILED") from None
 if process.returncode!=0:raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_READ_FAILED")
 header=b"blob "+str(len(data)).encode()+b"\0"+data;algorithm=hashlib.sha1 if len(oid)==40 else hashlib.sha256
 if algorithm(header).hexdigest()!=oid:raise GitHubSubjectCaptureV3Error("SUBJECT_IMAGE_BLOB_MISMATCH")
 return SourceRecord.from_bytes(spec.repository,spec.commit,spec.path,oid,data)
def capture_authenticated_subject_v3(scope:PullRequestScopeV3,reader:GitHubPullRequestObservationReaderV3,
 source_authorization:SourceRepositoryAuthorizationV3,source_authority_scope_evidence_id:str,
 source_token:str,private_root:Path,*,acquire_repository:AcquireRepositoryV3|None=None,failure_observer=None,before_effect=None,transfer_observer=None)->SubjectCaptureV2:
 """Acquire exact Git objects without checkout or reviewed-code execution."""
 expected_authorization=reader.source_authority.authorize(scope.repository,scope.repository_id)
 if (not reader.source_authority.permits_token(source_token,scope.repository,scope.repository_id)
  or source_authorization!=expected_authorization
  or source_authority_scope_evidence_id!=reader.source_authority.scope_observation.evidence_id):
  raise GitHubSubjectCaptureV3Error("SUBJECT_SOURCE_AUTHORITY_MISMATCH")
 image_count=sum(1 if change["status"] in {"added","removed"} else 2 for change in scope.changes)
 if image_count>MAX_SOURCE_COUNT:raise GitHubSubjectCaptureV3Error("SUBJECT_SOURCE_COUNT_EXCEEDED")
 environment=require_private_source_environment(scope.repository,frozenset({scope.repository}),source_token)
 if private_root.is_symlink() or private_root.exists() and not private_root.is_dir():raise GitHubSubjectCaptureV3Error("SUBJECT_CAPTURE_ROOT_INVALID")
 if before_effect is not None:before_effect()
 private_root.mkdir(mode=0o700,parents=True,exist_ok=True)
 with isolated_source_environment(environment) as isolated:
  assert isolated is not None;repository_root=private_root/"source.git"
  acquire=acquire_repository or _default_acquire(scope.repository,source_token,failure_observer,before_effect,transfer_observer)
  acquire(repository_root,isolated)
  source_environment=isolated
  run_transfer=partial(_run,failure_observer=failure_observer,repository=scope.repository,operation="GIT_FETCH",before_effect=before_effect,transfer_observer=transfer_observer)
  for commit in (scope.base_sha,scope.head_sha):
   try:run_transfer(["git","-C",str(repository_root),"fetch","origin",commit,"--depth=256"],source_environment,180)
   except GitHubSubjectCaptureV3Error:raise GitHubSubjectCaptureV3Error("SUBJECT_COMMIT_FETCH_FAILED") from None
  authenticated_environment={**source_environment,"GIT_NO_REPLACE_OBJECTS":"1"}
  from .packet_v2 import GuardedPacketGitReaderV3
  git_reader=GitSourceReader if before_effect is None else partial(GuardedPacketGitReaderV3,before_effect=before_effect)
  authenticated_git=git_reader(repository_root,environment=authenticated_environment);merge=None
  for deepen in (0,256,512,1024,2048,4096):
   try:merge=authenticated_git._git("merge-base",scope.base_sha,scope.head_sha).decode().strip()
   except Exception:
    if deepen==4096:break
    run_transfer(["git","-C",str(repository_root),"fetch","origin",f"--deepen={max(1,deepen)}"],source_environment,180);continue
   break
  if merge is None:raise GitHubSubjectCaptureV3Error("SUBJECT_ANCESTRY_UNAVAILABLE")
  if merge!=scope.merge_base_sha:raise GitHubSubjectCaptureV3Error("SUBJECT_MERGE_BASE_MISMATCH")
  inventory=_inventory(authenticated_git,merge,scope.head_sha)
  if inventory!=scope.changes or authenticated_git.changed_paths(merge,scope.head_sha)!={item["path"] for item in scope.changes}:raise GitHubSubjectCaptureV3Error("SUBJECT_CHANGE_SCOPE_MISMATCH")
  records=[];rendered_bytes=0
  for change in inventory:
   status,path,previous=change["status"],change["path"],change["previous_path"];start=len(records)
   if status!="added":records.append(_read_regular(authenticated_git,SourceSpec(scope.repository,merge,previous or path),before_effect))
   if status!="removed":records.append(_read_regular(authenticated_git,SourceSpec(scope.repository,scope.head_sha,path),before_effect))
   rendered_bytes+=sum(sum(len(line.encode("utf-8"))+9 for line in record.lines) for record in records[start:])
   if rendered_bytes>MAX_PACKET_BYTES:raise GitHubSubjectCaptureV3Error("SUBJECT_RENDERED_BYTES_EXCEEDED")
  local_environment={key:value for key,value in isolated.items() if key not in {"GH_TOKEN","GIT_CONFIG_COUNT","GIT_CONFIG_KEY_0","GIT_CONFIG_KEY_1","GIT_CONFIG_VALUE_0","GIT_CONFIG_VALUE_1"}}
  local_environment.update({"GIT_NO_REPLACE_OBJECTS":"1","GIT_NO_LAZY_FETCH":"1","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":os.devnull,"GIT_TERMINAL_PROMPT":"0"})
  local_git=git_reader(repository_root,environment=local_environment)
  diff=local_git.diff(merge,scope.head_sha)
  credential=source_token.encode("utf-8")
  if credential in diff or any(credential in record.original_bytes for record in records):
   raise GitHubSubjectCaptureV3Error("SOURCE_CREDENTIAL_IN_CAPTURED_BYTES")
  provisional=SubjectCaptureV2(scope.repository,scope.repository_id,scope.pull_request,scope.pull_request_id,scope.head_sha,scope.base_sha,merge,inventory,tuple(records),diff,"",repository_root,"AUTHENTICATED_SOURCE_READ_ONLY",source_authorization.evidence_id,scope.evidence_id)
  capture=replace(provisional,evidence_id=subject_capture_evidence_id_v2(provisional));reader.verify_final_identity(scope)
  config=local_git._git("config","--local","--list")
  if source_token.encode() in config:raise GitHubSubjectCaptureV3Error("SOURCE_TOKEN_RETAINED_IN_GIT_CONFIG")
  return capture
def bind_authenticated_capture_v3(capture:SubjectCaptureV2,source_authorization_evidence_id:str,
 pr_observation_evidence_id:str)->SubjectCaptureV2:
 """Bind the finalized admission authorities without changing captured Git bytes."""
 if capture.verification!="AUTHENTICATED_SOURCE_READ_ONLY":raise GitHubSubjectCaptureV3Error("AUTHENTICATED_CAPTURE_REQUIRED")
 value=replace(capture,evidence_id="",source_authorization_evidence_id=source_authorization_evidence_id,pr_observation_evidence_id=pr_observation_evidence_id)
 return replace(value,evidence_id=subject_capture_evidence_id_v2(value))
