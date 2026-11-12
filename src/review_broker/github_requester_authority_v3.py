"""Exact configured requester authorization for candidate v3 admission."""
from __future__ import annotations
from .admission_v3 import RequesterAuthorizationV3
from .identity import artifact_identity,canonical_bytes
class GitHubRequesterAuthorityV3:
 """Authorize one numeric requester/Issue/origin tuple from trusted configuration."""
 def __init__(self,*,requester_id:int,broker_issue_id:int,origin_evidence_id:str,authorized:bool):
  if type(requester_id) is not int or requester_id<1 or type(broker_issue_id) is not int or broker_issue_id<1: raise ValueError("REQUESTER_AUTHORITY_IDENTITY_INVALID")
  if not origin_evidence_id.startswith("artifact:sha256:") or len(origin_evidence_id)!=80: raise ValueError("REQUESTER_ORIGIN_EVIDENCE_INVALID")
  if type(authorized) is not bool: raise ValueError("REQUESTER_DECISION_INVALID")
  self.requester_id=requester_id;self.broker_issue_id=broker_issue_id;self.origin_evidence_id=origin_evidence_id;self.authorized=authorized
 def authorize(self,requester_id:int,broker_issue_id:int,origin_evidence_id:str)->RequesterAuthorizationV3|None:
  if (not self.authorized or requester_id!=self.requester_id or broker_issue_id!=self.broker_issue_id or origin_evidence_id!=self.origin_evidence_id):return None
  basis={"schema_version":1,"evidence_type":"v3-requester-authorization","requester_id":requester_id,"broker_issue_id":broker_issue_id,"origin_evidence_id":origin_evidence_id}
  return RequesterAuthorizationV3(requester_id,broker_issue_id,artifact_identity(canonical_bytes(basis)+b"\n"))
