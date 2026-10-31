"""Deterministic instrumentation for Issue #68 integrated qualification."""
from __future__ import annotations
import base64,json,tempfile
from pathlib import Path
from tests.journal_v3_test_support import (BASE_SHA,NODE_ID,WRITER_EVIDENCE_ID,FakeGitHubTransportV3,
 TrustedMutationAuthority,TrustedPredecessorAuthority,TrustedRejectionAuthority,TrustedWorkerAuthority)
from tests.packet_v2_test_support import admitted,git_capture,inline,profile,request_for_capture
from tests.test_git_file_packet_v3 import git_ref
from tests.test_github_git_file_v3 import Api as GitApi,reader as git_reader
from tests.test_github_issue_reference_v3 import Api as IssueApi,reader as issue_reader
from review_broker.github_journal_transport_v3 import OutcomeStatusV3,TransportSnapshotV3
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.identity import artifact_identity,canonical_bytes
from review_broker.journal_record_v3 import WorkerIdentityV3
from review_broker.packet_preparation_authority_v3 import RetainedPacketAuthorityV3,prepare_packet_receipt_v3,verify_prepared_readback_v3
from review_broker.packet_retention_v3 import persist_packet_evidence_v3

REPOSITORY="fanilosendrison/review-broker"
def issue_ref(): return {"id":"requirement","required":True,"source":{"kind":"github_issue_body","repository":REPOSITORY,"issue":43}}
def comment_ref(): return {"id":"decision","required":True,"source":{"kind":"github_issue_comment","repository":REPOSITORY,"comment_id":99}}
class ExactAdmissionAuthority:
 def __init__(self,admission): self.admission=admission;self.identity=artifact_identity(canonical_bytes(admission)+b"\n")
 def evidence_id(self,**values): return self.identity if values["repository"]==REPOSITORY and values["admission"]==self.admission else None
 def permits_evidence(self,**values): return values["repository"]==REPOSITORY and values["admission"]==self.admission and values["evidence_id"]==self.identity
class IntegratedScenario:
 def __init__(self,root:Path,*,body="old body",comment="old comment"):
  self.root=root;self.capture=git_capture(root);self.references=[inline("note","inline\n"),git_ref(),issue_ref(),comment_ref()]
  self.request=request_for_capture(self.capture,self.references,atomicity=False)
  self.git_readers={"contract":git_reader(GitApi())};self.issue_readers={"requirement":issue_reader(IssueApi(body=body)),"decision":issue_reader(IssueApi(body=comment))}
  self.admission=admitted(self.request,capture=self.capture,git_file_readers=self.git_readers,issue_reference_readers=self.issue_readers)
  self.transport=FakeGitHubTransportV3();self.journal_admission=self.admission.journal_admission();self.worker=WorkerIdentityV3(68001,1)
  self.journal=GitHubJournalV3(REPOSITORY,NODE_ID,BASE_SHA,self.transport,ExactAdmissionAuthority(self.journal_admission),TrustedMutationAuthority(),TrustedRejectionAuthority(),TrustedPredecessorAuthority())
  self.history=[];self.dispatches=0
 def _take(self,name,outcome,start=None):
  self.history.append({"operation":name,"starting_commit":None if start is None else start.commit_sha,"expected_old":None if start is None else start.commit_sha,"intended_successor":None if outcome.pending is None else outcome.pending.intended_sha,"outcome":outcome.status.value,"committed_commit":None if outcome.snapshot is None else outcome.snapshot.commit_sha,"readback":None if outcome.snapshot is None else outcome.snapshot.record.attempt.state.value})
  if outcome.status is not OutcomeStatusV3.COMMITTED: raise AssertionError((name,outcome.status,outcome.reason))
  return outcome.snapshot
 def through_admitted(self):
  current=self._take("claim",self.journal.claim(self.request,self.journal_admission));current=self._take("reserve_initial",self.journal.reserve_initial(current),current);self.dispatches+=1
  current=self._take("register_worker",self.journal.register_worker(current,current.record.control.reservation_id,1,self.worker,TrustedWorkerAuthority(self.worker)),current)
  current=self._take("record_admission",self.journal.record_admission(current,self.admission.admission_evidence_id,current.record.control.reservation_id,1,self.worker),current)
  return current
 def complete(self,*,preparation_body="new body",preparation_comment="new comment"):
  admitted_snapshot=self.through_admitted();self.admitted_snapshot=admitted_snapshot;fresh={"requirement":issue_reader(IssueApi(body=preparation_body)),"decision":issue_reader(IssueApi(body=preparation_comment))}
  self.retention=self.root/"retained";self.manifest=persist_packet_evidence_v3(self.admission,self.capture,profile(),self.retention,fresh)
  self.packet_evidence_id=prepare_packet_receipt_v3(self.retention,admitted_snapshot)
  prepared=self._take("prepare",self.journal.prepare(admitted_snapshot,self.packet_evidence_id,admitted_snapshot.record.control.reservation_id,1,self.worker,RetainedPacketAuthorityV3(self.retention)),admitted_snapshot)
  self.prepared=self.journal.read(self.admission.request_id);assert self.prepared.commit_sha==prepared.commit_sha
  self.verified=verify_prepared_readback_v3(self.retention,self.prepared);return self
 def save_transport(self,path:Path):
  value={"refs":self.transport.refs,"commits":{sha:{"commit_sha":x.commit_sha,"parent_sha":x.parent_sha,"journal_bytes":base64.b64encode(x.journal_bytes).decode()} for sha,x in self.transport.commits.items()}}
  path.write_bytes(canonical_bytes(value)+b"\n")
def restore_transport(path:Path):
 value=json.loads(path.read_bytes());transport=FakeGitHubTransportV3();transport.refs=value["refs"]
 transport.commits={sha:TransportSnapshotV3(x["commit_sha"],x["parent_sha"],base64.b64decode(x["journal_bytes"])) for sha,x in value["commits"].items()};return transport
