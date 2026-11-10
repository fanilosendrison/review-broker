from dataclasses import replace
import json,shutil,tempfile,unittest
from pathlib import Path
from tests.issue68_test_support import IntegratedScenario,TECHNICAL_POLICY_ID
from tests.issue69_test_support import source_authority
from tests.packet_v2_test_support import admitted,git_capture,profile,request_for_capture
from tests.test_git_file_packet_v3 import git_ref
from tests.test_github_git_file_v3 import Api as GitApi,reader as git_reader
from tests.test_github_issue_reference_v3 import Api as IssueApi,reader as issue_reader
from review_broker.admission_v3 import AdmissionV3CandidateError
from review_broker.github_journal_transport_v3 import CreateRefStatusV3,OutcomeStatusV3
from review_broker.github_journal_v3 import GitHubJournalV3Error
from review_broker.identity import canonical_bytes
from review_broker.journal_record_v3 import WorkerIdentityV3
from review_broker.packet_preparation_authority_v3 import RetainedPacketAuthorityV3,PacketPreparationAuthorityV3Error,verify_prepared_readback_v3
from review_broker.packet_retention_v3 import PacketRetentionV3Error,load_packet_evidence_v3,persist_packet_evidence_v3

class Issue68FailureTests(unittest.TestCase):
 def scenario(self):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);return IntegratedScenario(Path(temporary.name))
 def test_I68_F01_F02_invalid_admission_and_identity(self):
  scenario=self.scenario().complete();value=dict(scenario.journal_admission);value["request_id"]="request:sha256:"+"0"*64
  with self.assertRaises(AdmissionV3CandidateError): load_packet_evidence_v3(scenario.retention,value)
  claimed=scenario.admitted_snapshot;forged=dict(claimed.record.attempt.admission);forged["review_intent_id"]="review-intent:sha256:"+"0"*64
  before=len(scenario.transport.updates)
  with self.assertRaises(Exception): scenario.journal.claim(scenario.request,forged)
  self.assertEqual(len(scenario.transport.updates),before)
 def test_I68_F03_F04_wrong_repository_and_stable_object(self):
  with tempfile.TemporaryDirectory() as temporary:
   source=source_authority();cap=git_capture(Path(temporary),source_authority_override=source);req=request_for_capture(cap,[git_ref()])
   bad=git_reader(GitApi(),source)
   admitted(req,capture=cap,source_authority_override=source,git_file_readers={"contract":bad})
   bad.repository_id+=1
   with self.assertRaisesRegex(AdmissionV3CandidateError,"^GIT_FILE_OBSERVATION_UNAVAILABLE$"): admitted(req,capture=cap,source_authority_override=source,git_file_readers={"contract":bad})
  with tempfile.TemporaryDirectory() as temporary:
   source=source_authority();cap=git_capture(Path(temporary),source_authority_override=source);ref={"id":"requirement","required":True,"source":{"kind":"github_issue_body","repository":cap.repository,"issue":43}};req=request_for_capture(cap,[ref])
   api=IssueApi();reader=issue_reader(api,source)
   admitted(req,capture=cap,source_authority_override=source,issue_reference_readers={"requirement":reader})
   reader.repository_id+=1
   with self.assertRaisesRegex(AdmissionV3CandidateError,"^ISSUE_REFERENCE_AUTHORITY_MISMATCH$"): admitted(req,capture=cap,source_authority_override=source,issue_reference_readers={"requirement":reader})
 def test_I68_F05_F06_F07_required_optional_and_digest_fail_closed(self):
  for required,status in ((True,404),(False,403)):
   with self.subTest(required=required),tempfile.TemporaryDirectory() as temporary:
    source=source_authority();cap=git_capture(Path(temporary),source_authority_override=source);ref=git_ref(required=required);req=request_for_capture(cap,[ref]);api=GitApi();reader=git_reader(api,source)
    admitted(req,capture=cap,source_authority_override=source,git_file_readers={"contract":reader})
    api.status=status
    with self.assertRaisesRegex(AdmissionV3CandidateError,"^GIT_FILE_OBSERVATION_UNAVAILABLE$"): admitted(req,capture=cap,source_authority_override=source,git_file_readers={"contract":reader})
  with tempfile.TemporaryDirectory() as temporary:
   source=source_authority();cap=git_capture(Path(temporary),source_authority_override=source);reader=git_reader(GitApi(),source)
   admitted(request_for_capture(cap,[git_ref()]),capture=cap,source_authority_override=source,git_file_readers={"contract":reader})
   req=request_for_capture(cap,[git_ref(expected="0"*64)])
   with self.assertRaisesRegex(AdmissionV3CandidateError,"^GIT_FILE_OBSERVATION_UNAVAILABLE$"): admitted(req,capture=cap,source_authority_override=source,git_file_readers={"contract":reader})
 def test_I68_F08_F09_F10_F12_retained_byte_tampering_refuses_authority(self):
  scenario=self.scenario().complete();targets=["evidence/admitted-references/contract.bin","packet/sources/S001.bin","packet/changes.patch","packet/input.txt","packet/input-manifest.json","evidence/technical-profile.bin"]
  for relative in targets:
   with self.subTest(relative=relative):
    base=scenario.root/("tamper-"+relative.replace("/","-"));copy=base/scenario.retention.name;shutil.copytree(scenario.retention,copy);path=copy/relative;path.write_bytes(path.read_bytes()+b"x")
    authority=RetainedPacketAuthorityV3(base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]);self.assertFalse(authority.permits(snapshot=scenario.admitted_snapshot,packet_evidence_id=scenario.packet_evidence_id,reservation_id=scenario.admitted_snapshot.record.control.reservation_id,generation=1,worker=scenario.worker))
 def test_I68_F11_forged_receipt_or_evidence_refuses_before_mutation(self):
  from review_broker.packet_preparation_authority_v3 import prepare_packet_receipt_v3
  unbound=self.scenario();admitted=unbound.through_admitted();base=unbound.root/"retained";manifest=persist_packet_evidence_v3(unbound.admission,unbound.capture,profile(),base,admitted,unbound.journal,unbound.issue_readers)
  with self.assertRaisesRegex(PacketPreparationAuthorityV3Error,"SUBJECT_CAPTURE_IDENTITY_MISMATCH"): prepare_packet_receipt_v3(base,admitted,TECHNICAL_POLICY_ID,"artifact:sha256:"+"0"*64,manifest["packet_id"])
  with self.assertRaisesRegex(PacketPreparationAuthorityV3Error,"PACKET_IDENTITY_MISMATCH"): prepare_packet_receipt_v3(base,admitted,TECHNICAL_POLICY_ID,unbound.capture.evidence_id,"packet:sha256:"+"0"*64)
  scenario=self.scenario().complete();before=len(scenario.transport.updates)
  receipt_path=scenario.retention/"evidence/preparation-receipt.json";original=receipt_path.read_bytes();forged=json.loads(original);forged["generation"]=True;receipt_path.write_bytes(canonical_bytes(forged)+b"\n")
  forged_id=__import__("review_broker.identity",fromlist=["artifact_identity"]).artifact_identity(receipt_path.read_bytes())
  self.assertFalse(RetainedPacketAuthorityV3(scenario.retention_base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]).permits(snapshot=scenario.admitted_snapshot,packet_evidence_id=forged_id,reservation_id=scenario.admitted_snapshot.record.control.reservation_id,generation=1,worker=scenario.worker));receipt_path.write_bytes(original)
  with self.assertRaises(GitHubJournalV3Error): scenario.journal.prepare(scenario.admitted_snapshot,"artifact:sha256:"+"0"*64,scenario.admitted_snapshot.record.control.reservation_id,1,scenario.worker,RetainedPacketAuthorityV3(scenario.retention_base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]))
  self.assertEqual(len(scenario.transport.updates),before)
 def test_I68_F13_F14_stale_and_wrong_worker_are_fenced(self):
  scenario=self.scenario().complete();before=len(scenario.transport.updates)
  stale=scenario.journal.prepare(scenario.admitted_snapshot,scenario.packet_evidence_id,scenario.admitted_snapshot.record.control.reservation_id,1,scenario.worker,RetainedPacketAuthorityV3(scenario.retention_base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]))
  self.assertEqual(stale.status,OutcomeStatusV3.REJECTED)
  wrong=[("preparation-dispatch:sha256:"+"0"*64,1,scenario.worker),(scenario.admitted_snapshot.record.control.reservation_id,2,scenario.worker),(scenario.admitted_snapshot.record.control.reservation_id,1,WorkerIdentityV3(9,1))]
  for reservation,generation,worker in wrong:
   with self.assertRaises(GitHubJournalV3Error): scenario.journal.prepare(scenario.admitted_snapshot,scenario.packet_evidence_id,reservation,generation,worker,RetainedPacketAuthorityV3(scenario.retention_base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]))
  self.assertEqual(len(scenario.transport.updates),before+1)
 def test_I68_F15_F16_duplicate_reservation_and_discovery(self):
  from concurrent.futures import ThreadPoolExecutor
  scenario=self.scenario();claim=scenario._take("claim",scenario.journal.claim(scenario.request,scenario.journal_admission))
  with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(lambda _:scenario.reserve_and_dispatch_outcome(claim),range(2)))
  self.assertEqual([x.status for x in outcomes].count(OutcomeStatusV3.COMMITTED),1);self.assertEqual([x.status for x in outcomes].count(OutcomeStatusV3.REJECTED),1);self.assertEqual(scenario.dispatches,1)
  duplicate=scenario.journal.claim(scenario.request,scenario.journal_admission);self.assertEqual(duplicate.status,OutcomeStatusV3.COMMITTED)
  self.assertEqual(scenario.transport.create_statuses.count(CreateRefStatusV3.CREATED),1);self.assertEqual(len(scenario.transport.updates),2)
 def test_I68_F17_F18_interruptions_do_not_report_prepared(self):
  scenario=self.scenario();admitted=scenario.through_admitted();self.assertEqual(scenario.journal.read(scenario.admission.request_id).record.attempt.state.value,"ADMITTED")
  persist_packet_evidence_v3(scenario.admission,scenario.capture,profile(),scenario.root/"retained",admitted,scenario.journal,scenario.issue_readers)
  self.assertEqual(scenario.journal.read(scenario.admission.request_id).record.attempt.state.value,"ADMITTED")
 def test_I68_F19_F20_ambiguous_CAS_never_blindly_retries(self):
  from review_broker.packet_preparation_authority_v3 import prepare_packet_receipt_v3
  for after_apply in (True,False):
   scenario=self.scenario();current=scenario.through_admitted();scenario.retention_base=scenario.root/"retained";scenario.manifest=persist_packet_evidence_v3(scenario.admission,scenario.capture,profile(),scenario.retention_base,current,scenario.journal,scenario.issue_readers);evidence=prepare_packet_receipt_v3(scenario.retention_base,current,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"])
   scenario.transport.graphql_error_after_apply=after_apply;scenario.transport.graphql_application_error=not after_apply
   before=len(scenario.transport.updates);outcome=scenario.journal.prepare(current,evidence,current.record.control.reservation_id,1,scenario.worker,RetainedPacketAuthorityV3(scenario.retention_base,TECHNICAL_POLICY_ID,scenario.capture.evidence_id,scenario.manifest["packet_id"]))
   self.assertEqual(outcome.status,OutcomeStatusV3.UNRESOLVED);self.assertEqual(len(scenario.transport.updates),before+1)
   self.assertEqual(scenario.journal.read(scenario.admission.request_id).record.attempt.state.value,"PREPARED" if after_apply else "ADMITTED")
 def test_I68_F21_F22_F23_F24_competing_recovery_and_postprepared_immutability(self):
  from review_broker.packet_preparation_authority_v3 import prepare_packet_receipt_v3
  competing=self.scenario();current=competing.through_admitted();competing.retention_base=competing.root/"retained";competing.manifest=persist_packet_evidence_v3(competing.admission,competing.capture,profile(),competing.retention_base,current,competing.journal,competing.issue_readers);evidence=prepare_packet_receipt_v3(competing.retention_base,current,TECHNICAL_POLICY_ID,competing.capture.evidence_id,competing.manifest["packet_id"]);competing.transport.competing_descendant_after_update=True
  outcome=competing.journal.prepare(current,evidence,current.record.control.reservation_id,1,competing.worker,RetainedPacketAuthorityV3(competing.retention_base,TECHNICAL_POLICY_ID,competing.capture.evidence_id,competing.manifest["packet_id"]));self.assertEqual(outcome.status,OutcomeStatusV3.UNRESOLVED)
  scenario=self.scenario().complete();before=len(scenario.transport.updates);first=verify_prepared_readback_v3(scenario.retention_base,scenario.prepared);second=verify_prepared_readback_v3(scenario.retention_base,scenario.prepared)
  self.assertEqual(first,second);self.assertEqual(len(scenario.transport.updates),before)
  backup=scenario.root/"retained-backup";shutil.move(scenario.retention,backup)
  with self.assertRaisesRegex(PacketRetentionV3Error,"CURRENT_ADMITTED"): persist_packet_evidence_v3(scenario.admission,scenario.capture,profile(),scenario.retention_base,scenario.admitted_snapshot,scenario.journal,scenario.issue_readers)
  shutil.move(backup,scenario.retention)
  self.assertEqual(verify_prepared_readback_v3(scenario.retention_base,scenario.prepared)["packet_id"],scenario.manifest["packet_id"])
 def test_I68_F25_historical_namespaces_and_v1_identity_unchanged(self):
  import inspect
  legacy=__import__("review_broker.github_journal",fromlist=["GitHubRefJournal"]).GitHubRefJournal
  self.assertIn('refs/heads/review-claims/{digest}',inspect.getsource(legacy._claim_ref))
  self.assertEqual(__import__("review_broker.github_journal_v3",fromlist=["GitHubJournalV3"]).GitHubJournalV3.CLAIM_PREFIX,"refs/heads/review-claims-v3/")
if __name__=="__main__":unittest.main()
