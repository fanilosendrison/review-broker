"""Deterministic retained-packet authority for the v3 PREPARED transition."""
from __future__ import annotations
import hashlib,json,os,re
from pathlib import Path
from typing import Mapping
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .identity import artifact_identity,canonical_bytes
from .journal_record_v3 import WorkerIdentityV3
from .packet_retention_v3 import load_packet_evidence_v3,packet_retention_locator_v3
from .packet_v2 import verify_packet_v2_candidate
from .queue import AttemptState

class PacketPreparationAuthorityV3Error(ValueError): pass
_RECEIPT_FIELDS={"schema_version","evidence_type","repository","repository_node_id","claim_ref","predecessor_commit_sha","request_id","review_intent_id","attempt_id","admission_evidence_id","reservation_id","generation","worker","packet_id","subject_capture_evidence_id","technical_policy_id","retained_inventory_id"}
_ID=re.compile(r"(?:artifact|packet):sha256:[0-9a-f]{64}\Z")
_REQUEST_ID=re.compile(r"request:sha256:[0-9a-f]{64}\Z")
_INTENT_ID=re.compile(r"review-intent:sha256:[0-9a-f]{64}\Z")
_ATTEMPT_ID=re.compile(r"attempt:sha256:[0-9a-f]{64}\Z")
_RESERVATION_ID=re.compile(r"preparation-dispatch:sha256:[0-9a-f]{64}\Z")
_SHA=re.compile(r"[0-9a-f]{40}\Z")
def _files(root:Path):
 for path in sorted(root.rglob("*"),key=lambda item:item.relative_to(root).as_posix()):
  if path.is_symlink(): raise PacketPreparationAuthorityV3Error("RETAINED_SYMLINK_FORBIDDEN")
  if path.stat().st_mode&0o077: raise PacketPreparationAuthorityV3Error("RETAINED_MODE_NOT_PRIVATE")
  if path.is_file() and path.relative_to(root).as_posix()!="evidence/preparation-receipt.json": yield path
def retained_inventory_id_v3(root:Path)->str:
 entries=[];seen=set()
 for path in _files(root):
  relative=path.relative_to(root).as_posix()
  if relative in seen: raise PacketPreparationAuthorityV3Error("RETAINED_INVENTORY_DUPLICATE")
  seen.add(relative);data=path.read_bytes();entries.append({"path":relative,"byte_length":len(data),"sha256":hashlib.sha256(data).hexdigest()})
 if not entries: raise PacketPreparationAuthorityV3Error("RETAINED_INVENTORY_EMPTY")
 return artifact_identity(canonical_bytes({"schema_version":1,"files":entries})+b"\n")
def _receipt(snapshot:VerifiedJournalSnapshotV3,manifest:Mapping[str,object],inventory_id:str)->dict[str,object]:
 attempt=snapshot.record.attempt;control=snapshot.record.control
 return {"schema_version":1,"evidence_type":"offline-v3-prepared-packet-binding",
  "repository":snapshot.repository,"repository_node_id":snapshot.repository_node_id,
  "claim_ref":snapshot.claim_ref,"predecessor_commit_sha":snapshot.commit_sha,
  "request_id":attempt.request_id,"review_intent_id":attempt.admission["review_intent_id"],
  "attempt_id":attempt.attempt_id,"admission_evidence_id":attempt.admission["admission_evidence_id"],
  "reservation_id":control.reservation_id,"generation":control.generation,
  "worker":control.worker.as_dict() if control.worker else None,"packet_id":manifest["packet_id"],
  "subject_capture_evidence_id":manifest["subject"]["subject_capture_evidence_id"],
  "technical_policy_id":manifest["technical_policy"]["technical_policy_id"],
  "retained_inventory_id":inventory_id}
def prepare_packet_receipt_v3(retention_base:Path,snapshot:VerifiedJournalSnapshotV3,
 expected_technical_policy_id:str,expected_subject_capture_evidence_id:str,
 expected_packet_id:str)->str:
 """Verify retained evidence and exclusively persist its ADMITTED transition receipt."""
 if snapshot.record.attempt.state is not AttemptState.ADMITTED: raise PacketPreparationAuthorityV3Error("ADMITTED_SNAPSHOT_REQUIRED")
 retention_root=packet_retention_locator_v3(retention_base,snapshot.claim_ref)
 admission,capture,profile,manifest=load_packet_evidence_v3(retention_root,snapshot.record.attempt.admission)
 if manifest["technical_policy"]["technical_policy_id"]!=expected_technical_policy_id: raise PacketPreparationAuthorityV3Error("TECHNICAL_POLICY_IDENTITY_MISMATCH")
 if manifest["subject"]["subject_capture_evidence_id"]!=expected_subject_capture_evidence_id: raise PacketPreparationAuthorityV3Error("SUBJECT_CAPTURE_IDENTITY_MISMATCH")
 if manifest["packet_id"]!=expected_packet_id: raise PacketPreparationAuthorityV3Error("PACKET_IDENTITY_MISMATCH")
 verify_packet_v2_candidate(retention_root/"packet",admission,capture,profile)
 receipt=_receipt(snapshot,manifest,retained_inventory_id_v3(retention_root));raw=canonical_bytes(receipt)+b"\n"
 path=retention_root/"evidence/preparation-receipt.json"
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,"wb") as stream: stream.write(raw);stream.flush();os.fsync(stream.fileno())
 except FileExistsError as exc: raise PacketPreparationAuthorityV3Error("PREPARATION_RECEIPT_EXISTS") from exc
 return artifact_identity(raw)
def _load_receipt(root:Path)->tuple[dict[str,object],bytes]:
 path=root/"evidence/preparation-receipt.json"
 if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077: raise PacketPreparationAuthorityV3Error("PREPARATION_RECEIPT_MISSING")
 raw=path.read_bytes()
 try: value=json.loads(raw)
 except (UnicodeError,json.JSONDecodeError) as exc: raise PacketPreparationAuthorityV3Error("PREPARATION_RECEIPT_INVALID") from exc
 worker=value.get("worker") if isinstance(value,dict) else None
 valid=(isinstance(value,dict) and set(value)==_RECEIPT_FIELDS
  and type(value.get("schema_version")) is int and value["schema_version"]==1
  and value.get("evidence_type")=="offline-v3-prepared-packet-binding"
  and all(isinstance(value.get(field),str) and value[field] for field in ("repository","repository_node_id","claim_ref","technical_policy_id"))
  and _SHA.fullmatch(str(value.get("predecessor_commit_sha"))) is not None
  and _REQUEST_ID.fullmatch(str(value.get("request_id"))) is not None
  and _INTENT_ID.fullmatch(str(value.get("review_intent_id"))) is not None
  and _ATTEMPT_ID.fullmatch(str(value.get("attempt_id"))) is not None
  and _RESERVATION_ID.fullmatch(str(value.get("reservation_id"))) is not None
  and type(value.get("generation")) is int and value["generation"]==1
  and isinstance(worker,dict) and set(worker)=={"run_id","run_attempt"}
  and all(type(worker[field]) is int and worker[field]>0 for field in worker)
  and all(isinstance(value.get(field),str) and _ID.fullmatch(value[field]) is not None for field in ("admission_evidence_id","packet_id","subject_capture_evidence_id","retained_inventory_id"))
  and raw==canonical_bytes(value)+b"\n")
 if not valid: raise PacketPreparationAuthorityV3Error("PREPARATION_RECEIPT_INVALID")
 return value,raw
class RetainedPacketAuthorityV3:
 """Reload and confront exact retained evidence before allowing journal prepare."""
 def __init__(self,retention_base:Path,expected_technical_policy_id:str,expected_subject_capture_evidence_id:str,expected_packet_id:str): self.retention_base=retention_base;self.expected_technical_policy_id=expected_technical_policy_id;self.expected_subject_capture_evidence_id=expected_subject_capture_evidence_id;self.expected_packet_id=expected_packet_id
 def permits(self,*,snapshot:VerifiedJournalSnapshotV3,packet_evidence_id:str,reservation_id:str,generation:int,worker:WorkerIdentityV3)->bool:
  try:
   if snapshot.record.attempt.state is not AttemptState.ADMITTED: return False
   retention_root=packet_retention_locator_v3(self.retention_base,snapshot.claim_ref)
   admission,capture,profile,manifest=load_packet_evidence_v3(retention_root,snapshot.record.attempt.admission)
   receipt,raw=_load_receipt(retention_root);control=snapshot.record.control
   expected=_receipt(snapshot,manifest,retained_inventory_id_v3(retention_root))
   return (raw==canonical_bytes(expected)+b"\n" and artifact_identity(raw)==packet_evidence_id and packet_evidence_id.startswith("artifact:sha256:")
    and control.reservation_id==reservation_id and control.generation==generation and control.worker==worker
    and admission.request_id==snapshot.record.attempt.request_id
    and receipt["technical_policy_id"]==self.expected_technical_policy_id
    and receipt["subject_capture_evidence_id"]==self.expected_subject_capture_evidence_id
    and receipt["packet_id"]==self.expected_packet_id
    and verify_packet_v2_candidate(retention_root/"packet",admission,capture,profile)["packet_id"]==receipt["packet_id"])
  except Exception: return False
def verify_prepared_readback_v3(retention_base:Path,snapshot:VerifiedJournalSnapshotV3)->dict[str,object]:
 """Read-only cold verification of one committed direct PREPARED successor."""
 if snapshot.record.attempt.state is not AttemptState.PREPARED: raise PacketPreparationAuthorityV3Error("PREPARED_READBACK_REQUIRED")
 retention_root=packet_retention_locator_v3(retention_base,snapshot.claim_ref)
 receipt,raw=_load_receipt(retention_root);evidence_id=artifact_identity(raw)
 prepared_entries=[entry for entry in snapshot.record.attempt.history if entry.get("state")=="PREPARED"]
 if (receipt["predecessor_commit_sha"]!=snapshot.parent_sha
  or snapshot.record.attempt.evidence_ids[-1]!=evidence_id
  or len(prepared_entries)!=1 or prepared_entries[0].get("evidence_ids")!=[evidence_id]):
  raise PacketPreparationAuthorityV3Error("PREPARED_JOURNAL_BINDING_MISMATCH")
 admission,capture,profile,manifest=load_packet_evidence_v3(retention_root,snapshot.record.attempt.admission)
 inventory=retained_inventory_id_v3(retention_root)
 expected=dict(receipt);expected["retained_inventory_id"]=inventory
 control=snapshot.record.control
 if (receipt!=expected or receipt["repository"]!=snapshot.repository or receipt["repository_node_id"]!=snapshot.repository_node_id
  or receipt["claim_ref"]!=snapshot.claim_ref or receipt["request_id"]!=snapshot.record.attempt.request_id
  or receipt["review_intent_id"]!=snapshot.record.attempt.admission["review_intent_id"]
  or receipt["admission_evidence_id"]!=snapshot.record.attempt.admission["admission_evidence_id"]
  or receipt["attempt_id"]!=snapshot.record.attempt.attempt_id or receipt["reservation_id"]!=control.reservation_id
  or receipt["generation"]!=1 or control.generation!=1 or control.worker is None or receipt["worker"]!=control.worker.as_dict()
  or receipt["packet_id"]!=manifest["packet_id"]
  or receipt["subject_capture_evidence_id"]!=manifest["subject"]["subject_capture_evidence_id"]
  or receipt["technical_policy_id"]!=manifest["technical_policy"]["technical_policy_id"]):
  raise PacketPreparationAuthorityV3Error("PREPARED_READBACK_IDENTITY_MISMATCH")
 verify_packet_v2_candidate(retention_root/"packet",admission,capture,profile)
 return {"outcome":"PASS","packet_id":manifest["packet_id"],"packet_evidence_id":evidence_id,"request_id":receipt["request_id"],"attempt_id":receipt["attempt_id"],"retained_inventory_id":inventory}
