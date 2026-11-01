"""Discriminate synthetic and authenticated Packet v2 subject provenance."""
from __future__ import annotations
from typing import TYPE_CHECKING,Mapping
if TYPE_CHECKING:
 from .packet_v2 import SubjectCaptureV2
class SubjectCaptureProvenanceV2Error(ValueError):pass
def evidence_basis_v2(capture:"SubjectCaptureV2")->dict[str,object]:
 if capture.verification!="AUTHENTICATED_SOURCE_READ_ONLY":return {}
 return {"source_authorization_evidence_id":capture.source_authorization_evidence_id,
         "pr_observation_evidence_id":capture.pr_observation_evidence_id}
def manifest_fields_v2(capture:"SubjectCaptureV2")->dict[str,object]:
 return evidence_basis_v2(capture)
def validate_capture_provenance_v2(capture:"SubjectCaptureV2",admitted_source:Mapping[str,object])->None:
 if capture.verification=="SYNTHETIC_OFFLINE_VERIFIED":
  if capture.source_authorization_evidence_id is not None or capture.pr_observation_evidence_id is not None:
   raise SubjectCaptureProvenanceV2Error("PACKET_V2_SYNTHETIC_CAPTURE_AUTHORITY_FORBIDDEN")
  return
 if (capture.verification!="AUTHENTICATED_SOURCE_READ_ONLY"
  or not isinstance(capture.source_authorization_evidence_id,str)
  or not isinstance(capture.pr_observation_evidence_id,str)
  or capture.source_authorization_evidence_id!=admitted_source.get("source_authorization_evidence_id")
  or capture.pr_observation_evidence_id!=admitted_source.get("pr_observation_evidence_id")):
  raise SubjectCaptureProvenanceV2Error("PACKET_V2_AUTHENTICATED_CAPTURE_AUTHORITY_MISMATCH")
