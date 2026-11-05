"""Private atomic retention and cold reconstruction of Reviewer Packet v2."""
from __future__ import annotations
from dataclasses import replace
import hashlib,json,os,re,shutil,tempfile
from pathlib import Path
from typing import Mapping
from .admission_evidence_v3 import validate_journal_admission_v3
from .admission_v3 import PreclaimAdmissionV3
from .github_git_file_v3 import GitHubGitFileObservationV3
from .github_issue_reference_v3 import GitHubIssueReferenceObservationV3
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .github_journal_v3 import GitHubJournalV3
from .identity import artifact_identity,canonical_bytes
from .queue import AttemptState
from .packet_v2 import (SubjectCaptureV2,TechnicalProfileSnapshotV2,build_packet_v2_candidate,
                        subject_capture_evidence_id_v2,verify_packet_v2_candidate)
from .packets import SourceRecord
from .packet_v2_manifest import load_packet_manifest_v2,packet_snapshot_relative_path_v2
from .packet_v2_technical_policy import AuthorizedPolicySnapshotV3, AuthorizedPolicyVerificationV3, PolicySnapshotV2, PolicyVerificationV3
from .pre_model_policy_evidence_retention_v3 import (
 POLICY_EVIDENCE_NAMES, load_policy_evidence_v3, persist_policy_evidence_v3,
 require_private_policy_tree_v3, rename_exclusive_policy_tree_v3,
 observe_path_v3, policy_tree_paths_v3,
)
from .packet_v2_subject_provenance import (SubjectCaptureProvenanceV2Error,
                                         validate_capture_provenance_v2)

class PacketRetentionV3Error(ValueError): pass
_SAFE_ID=re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
def packet_retention_locator_v3(retention_base:Path,claim_ref:str)->Path:
 digest=claim_ref.rsplit("/",1)[-1]
 if re.fullmatch(r"[0-9a-f]{64}",digest) is None: raise PacketRetentionV3Error("RETENTION_CLAIM_REF_INVALID")
 return retention_base/digest
def _exclusive(path:Path,data:bytes,before_effect=None)->None:
 if before_effect is not None: before_effect()
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 if before_effect is not None: before_effect()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,"wb",buffering=0) as stream:
  if before_effect is not None: before_effect()
  stream.write(data)
  if before_effect is not None: before_effect()
  os.fsync(stream.fileno())
def _private_tree(root:Path,before_effect=None)->None:
 for path in policy_tree_paths_v3(root,before_effect):
  if observe_path_v3(path.is_symlink,before_effect): raise PacketRetentionV3Error("RETAINED_SYMLINK_FORBIDDEN")
  mode=0o700 if observe_path_v3(path.is_dir,before_effect) else 0o600
  if before_effect is not None: before_effect()
  os.chmod(path,mode)
def persist_packet_evidence_v3(admission:PreclaimAdmissionV3,capture:SubjectCaptureV2,
 profile:PolicySnapshotV2,retention_base:Path,snapshot:VerifiedJournalSnapshotV3,
 journal:GitHubJournalV3,issue_reference_readers:Mapping|None=None,*,
 policy_verification:AuthorizedPolicyVerificationV3|None=None,
 candidate_directory:Path|None=None)->dict[str,object]:
 """Build and verify the unique ADMITTED claim locator, then expose it atomically."""
 if policy_verification is not None:
  if type(policy_verification) is not AuthorizedPolicyVerificationV3: raise PacketRetentionV3Error("ACTIVE_RETENTION_AUTHORITY_REQUIRED")
  policy_verification.require_profile(profile,admission)
 if (snapshot.record.attempt.state is not AttemptState.ADMITTED
  or snapshot.record.attempt.admission!=admission.journal_admission()):
  raise PacketRetentionV3Error("RETENTION_ADMITTED_SNAPSHOT_REQUIRED")
 current=journal.read(admission.request_id)
 if current.commit_sha!=snapshot.commit_sha or current.record.attempt.state is not AttemptState.ADMITTED:
  raise PacketRetentionV3Error("RETENTION_CURRENT_ADMITTED_SNAPSHOT_REQUIRED")
 authorized=type(profile) is AuthorizedPolicySnapshotV3
 def guard():
  if authorized:
   if type(policy_verification) is not AuthorizedPolicyVerificationV3 or policy_verification.snapshot!=snapshot or policy_verification.journal is not journal:
    raise PacketRetentionV3Error("RETENTION_POLICY_AUTHORITY_REQUIRED")
   policy_verification.before_effect()
 def write(path,data):
  guard();_exclusive(path,data,guard if authorized else None);guard()
 guard()
 retention_root=packet_retention_locator_v3(retention_base,snapshot.claim_ref)
 def inspect(operation): return observe_path_v3(operation,guard if authorized else None)
 if inspect(retention_base.is_symlink) or inspect(retention_root.is_symlink) or inspect(retention_root.exists): raise PacketRetentionV3Error("RETENTION_TARGET_EXISTS")
 guard();retention_base.mkdir(mode=0o700,parents=True,exist_ok=True)
 guard();os.chmod(retention_base,0o700)
 guard();staging=Path(tempfile.mkdtemp(prefix=".retained-v3-",dir=retention_base))
 try:
  if authorized:
   if candidate_directory is None: raise PacketRetentionV3Error("RETENTION_VERIFIED_CANDIDATE_REQUIRED")
   require_private_policy_tree_v3(candidate_directory,guard)
   manifest=verify_packet_v2_candidate(candidate_directory,admission,capture,profile,policy_verification=policy_verification)
   for path in sorted(list(policy_tree_paths_v3(candidate_directory,guard))[1:]):
    if inspect(path.is_file):
     guard();data=path.read_bytes()
     write(staging/"packet"/path.relative_to(candidate_directory),data)
  else:
   manifest=build_packet_v2_candidate(admission,capture,profile,staging/"packet",issue_reference_readers)
   verify_packet_v2_candidate(staging/"packet",admission,capture,profile)
  write(staging/"evidence/origin-body.bin",admission.origin_body_bytes)
  if authorized: persist_policy_evidence_v3(staging/"evidence",profile,policy_verification)
  else: write(staging/"evidence/technical-profile.bin",profile.original_bytes)
  remote={item["id"]:item for item in admission.request["references"] if item["source"]["kind"]!="inline"}
  git=iter(admission.git_file_observations);issues=iter(admission.issue_reference_observations)
  for identifier,reference in remote.items():
   if _SAFE_ID.fullmatch(identifier) is None: raise PacketRetentionV3Error("REFERENCE_ID_PATH_UNSAFE")
   observation=next(git) if reference["source"]["kind"]=="git_file" else next(issues)
   write(staging/f"evidence/admitted-references/{identifier}.bin",observation.original_bytes)
  if authorized:
   guard();(staging/"evidence/admitted-references").mkdir(mode=0o700,exist_ok=True)
   verify_packet_v2_candidate(staging/"packet",admission,capture,profile,policy_verification=policy_verification)
  guard();_private_tree(staging,guard if authorized else None)
  guard()
  if authorized: rename_exclusive_policy_tree_v3(staging,retention_root,before_effect=guard)
  else: os.replace(staging,retention_root)
  return manifest
 except BaseException:
  guard();shutil.rmtree(staging,ignore_errors=True);raise

def _read_private(path:Path,verification=None)->bytes:
 def inspect(operation): return observe_path_v3(operation,None if verification is None else verification.before_effect)
 if (inspect(path.is_symlink) or not inspect(path.is_file) or inspect(path.stat).st_mode & 0o077):
  raise PacketRetentionV3Error("RETAINED_FILE_INVALID")
 if verification is not None: verification.before_effect()
 return path.read_bytes()
def _git_observation(meta:dict[str,object],data:bytes)->GitHubGitFileObservationV3:
 digest=hashlib.sha256(data).hexdigest();header=b"blob "+str(len(data)).encode()+b"\0"+data
 if len(data)!=meta["original_byte_length"] or digest!=meta["sha256"] or hashlib.sha1(header).hexdigest()!=meta["git_blob_oid"]:
  raise PacketRetentionV3Error("RETAINED_GIT_FILE_BYTES_MISMATCH")
 value=GitHubGitFileObservationV3(meta["repository"],meta["repository_id"],meta["commit_sha"],meta["root_tree_sha"],meta["path"],meta["git_blob_oid"],data,len(data),digest,meta["observed_at"],meta["api_source"],meta["qualification"],meta["authority_evidence_id"],meta["installation_id"],meta["evidence_id"])
 if artifact_identity(canonical_bytes(value.provenance_basis())+b"\n")!=value.evidence_id: raise PacketRetentionV3Error("RETAINED_GIT_FILE_EVIDENCE_MISMATCH")
 return value
def _issue_observation(meta:dict[str,object],data:bytes)->GitHubIssueReferenceObservationV3:
 digest=hashlib.sha256(data).hexdigest()
 if len(data)!=meta["original_byte_length"] or digest!=meta["sha256"]: raise PacketRetentionV3Error("RETAINED_ISSUE_BYTES_MISMATCH")
 value=GitHubIssueReferenceObservationV3(meta["source_kind"],meta["repository"],meta["repository_id"],meta["selector_id"],meta["issue_id"],meta["issue_number"],meta["comment_id"],meta["author_id"],data,len(data),digest,meta["observed_at"],meta["updated_at"],meta["api_source"],meta["qualification"],meta["authority_evidence_id"],meta["installation_id"],meta["evidence_id"])
 if artifact_identity(canonical_bytes(value.provenance_basis())+b"\n")!=value.evidence_id: raise PacketRetentionV3Error("RETAINED_ISSUE_EVIDENCE_MISMATCH")
 return value

def load_packet_evidence_v3(retention_root:Path,journal_admission:Mapping[str,object],*,
 policy_verification:PolicyVerificationV3|None=None)->tuple[PreclaimAdmissionV3,SubjectCaptureV2,PolicySnapshotV2,dict[str,object]]:
 """Cold-reconstruct verifier inputs from journal authority and retained bytes only."""
 if policy_verification is not None:
  from .historical_policy_verification_v3 import HistoricalAuthorizedPolicyVerificationV3
  if type(policy_verification) not in {AuthorizedPolicyVerificationV3,HistoricalAuthorizedPolicyVerificationV3}: raise PacketRetentionV3Error("CLOSED_POLICY_READER_REQUIRED")
  policy_verification.require_admission(journal_admission)
 def read(path): return _read_private(path,policy_verification)
 guard=None if policy_verification is None else policy_verification.before_effect
 def inspect(operation): return observe_path_v3(operation,guard)
 def entries(path): return inspect(lambda: tuple(path.iterdir()))
 packet,evidence=retention_root/"packet",retention_root/"evidence"
 if inspect(retention_root.is_symlink) or inspect(packet.is_symlink) or inspect(evidence.is_symlink): raise PacketRetentionV3Error("RETAINED_SYMLINK_FORBIDDEN")
 if ({item.name for item in entries(retention_root)}!={"packet","evidence"}
  or inspect(retention_root.stat).st_mode&0o077 or inspect(packet.stat).st_mode&0o077 or inspect(evidence.stat).st_mode&0o077):
  raise PacketRetentionV3Error("RETAINED_ROOT_INVENTORY_INVALID")
 origin=read(evidence/"origin-body.bin");validated=validate_journal_admission_v3(journal_admission,origin)
 try: manifest=load_packet_manifest_v2(read(packet/"input-manifest.json"))
 except (UnicodeError,json.JSONDecodeError) as exc: raise PacketRetentionV3Error("RETAINED_MANIFEST_INVALID") from exc
 request=validated["canonical_request"];refs={item["id"]:item for item in request["references"] if item["source"]["kind"]!="inline"}
 authorized=manifest["technical_policy"]["qualification"]=="PREMODEL_POLICY_SOURCE_VERIFIED_ONLY"
 if policy_verification is not None and not authorized: raise PacketRetentionV3Error("AUTHORIZED_POLICY_MODE_REQUIRED")
 expected={"origin-body.bin","technical-profile.bin","admitted-references"}
 if authorized:
  require_private_policy_tree_v3(retention_root,guard)
  expected={"origin-body.bin","admitted-references"}|POLICY_EVIDENCE_NAMES
  if {item.name for item in entries(evidence)}!=expected: raise PacketRetentionV3Error("RETAINED_POLICY_INVENTORY_INVALID")
 elif {item.name for item in entries(evidence)}-({"preparation-receipt.json"}|expected): raise PacketRetentionV3Error("RETAINED_EVIDENCE_INVENTORY_INVALID")
 admitted_dir=evidence/"admitted-references";expected_files={f"{key}.bin" for key in refs}
 if (inspect(admitted_dir.is_symlink) or not inspect(admitted_dir.is_dir) or inspect(admitted_dir.stat).st_mode&0o077
  or {item.name for item in entries(admitted_dir)}!=expected_files):
  raise PacketRetentionV3Error("RETAINED_REFERENCE_INVENTORY_INVALID")
 git_meta=iter(validated.get("reference_admissions",[]));issue_meta=iter(validated.get("issue_reference_admissions",[]));git=[];issues=[]
 for identifier,reference in refs.items():
  data=read(admitted_dir/f"{identifier}.bin")
  if reference["source"]["kind"]=="git_file": git.append(_git_observation(next(git_meta),data))
  else: issues.append(_issue_observation(next(issue_meta),data))
 source=validated["source_observation"];origin_meta=validated["origin_observation"]
 admission=PreclaimAdmissionV3(canonical_bytes(request),validated["request_id"],validated["review_intent_id"],validated["broker_issue_id"],validated["requester_id"],origin_meta["requester_login_observed"],source["repository"],source["repository_id"],source["pull_request"],source["pull_request_id"],source["head_sha"],validated["source_admission_id"],tuple(validated["reference_ids"]),origin,canonical_bytes(origin_meta),canonical_bytes(source),canonical_bytes(validated["requester_authorization"]),canonical_bytes(validated["history_observation"]),validated["origin_evidence_id"],validated["requester_authorization_evidence_id"],validated["history_evidence_id"],validated["history_scan_boundary"],validated["admission_evidence_id"],tuple(git),tuple(issues),source_scope_evidence_id=validated.get("source_app_scope_evidence_id"))
 records=[]
 for entry in manifest["subject_sources"]:
  data=read(packet/packet_snapshot_relative_path_v2(entry));record=SourceRecord.from_bytes(entry["repository"],entry["commit"],entry["path"],entry["git_blob_oid"],data)
  if hashlib.sha256(data).hexdigest()!=entry["sha256"]: raise PacketRetentionV3Error("RETAINED_SUBJECT_BYTES_MISMATCH")
  records.append(record)
 subject=manifest["subject"];qualification=subject["capture_qualification"]
 authority_fields=("source_authorization_evidence_id","pr_observation_evidence_id")
 if qualification=="AUTHENTICATED_SOURCE_READ_ONLY":
  if any(type(subject.get(key)) is not str or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",subject[key]) is None for key in authority_fields):
   raise PacketRetentionV3Error("RETAINED_SUBJECT_AUTHORITY_INVALID")
 elif qualification=="SYNTHETIC_OFFLINE_VERIFIED":
  if any(key in subject for key in authority_fields):
   raise PacketRetentionV3Error("RETAINED_SYNTHETIC_AUTHORITY_FORBIDDEN")
 else: raise PacketRetentionV3Error("RETAINED_SUBJECT_QUALIFICATION_INVALID")
 capture=SubjectCaptureV2(subject["repository"],subject["repository_id"],subject["pull_request"],subject["pull_request_id"],subject["head_sha"],subject["base_sha"],subject["merge_base_sha"],tuple({"status":x["status"],"path":x["path"],"previous_path":x["previous_path"]} for x in manifest["change_scope"]["changes"]),tuple(records),read(packet/"changes.patch"),subject["subject_capture_evidence_id"],Path("."),verification=qualification,source_authorization_evidence_id=subject.get("source_authorization_evidence_id"),pr_observation_evidence_id=subject.get("pr_observation_evidence_id"))
 try: validate_capture_provenance_v2(capture,source,admission.source_scope_evidence_id)
 except SubjectCaptureProvenanceV2Error as exc: raise PacketRetentionV3Error(str(exc)) from exc
 if subject_capture_evidence_id_v2(capture)!=capture.evidence_id: raise PacketRetentionV3Error("RETAINED_SUBJECT_EVIDENCE_MISMATCH")
 if authorized:
  profile=load_policy_evidence_v3(evidence,policy_verification,admission)
 else:
  profile_bytes=read(evidence/"technical-profile.bin");name=manifest["technical_policy"]["basis"]["permission_profile_name"]
  profile=TechnicalProfileSnapshotV2(name,name,profile_bytes,artifact_identity(profile_bytes),"SYNTHETIC_OFFLINE_VERIFIED")
 verify_packet_v2_candidate(packet,admission,capture,profile,policy_verification=policy_verification)
 return admission,capture,profile,manifest
