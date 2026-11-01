from dataclasses import replace
import tempfile,unittest
from pathlib import Path
from tests.issue69_test_support import *
from tests.packet_v2_test_support import inline,profile,request_for_capture
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from review_broker.github_subject_capture_v3 import capture_authenticated_subject_v3,bind_authenticated_capture_v3
from review_broker.packet_v2 import build_packet_v2_candidate,verify_packet_v2_candidate,PacketV2CandidateError,subject_capture_evidence_id_v2
from review_broker.admission_evidence_v3 import validate_journal_admission_v3
from review_broker.admission_v3 import AdmissionV3CandidateError
class Issue69PacketProvenanceTests(unittest.TestCase):
 def integrated(self,root):
  origin_repo,base,head,merge,files=git_graph(root);authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope();authorization=authority.authorize(REPOSITORY,REPOSITORY_ID);capture=capture_authenticated_subject_v3(scope,observer,authorization,authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin_repo));pr=observer.finalize(scope,capture);capture=bind_authenticated_capture_v3(capture,authorization.evidence_id,pr.evidence_id);request=request_for_capture(capture,[inline("context","authenticated capture\n")]);admission=authenticated_admission(request,observer,authority);return capture,admission
 def test_I69_N09_authenticated_packet_and_synthetic_policy_remain_distinct(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission=self.integrated(root);output=root/"packet";manifest=build_packet_v2_candidate(admission,capture,profile(),output);verify_packet_v2_candidate(output,admission,capture,profile());self.assertEqual(manifest["subject"]["capture_qualification"],"AUTHENTICATED_SOURCE_READ_ONLY");self.assertEqual(manifest["technical_policy"]["qualification"],"SYNTHETIC_OFFLINE_ONLY");self.assertNotIn(TOKEN,(output/"input.txt").read_text());self.assertNotIn(TOKEN,(output/"input-manifest.json").read_text())
 def test_I69_F25_F26_forged_qualification_or_authority_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission=self.integrated(root);forged=replace(capture,source_authorization_evidence_id="artifact:sha256:"+"0"*64,evidence_id="");forged=replace(forged,evidence_id=subject_capture_evidence_id_v2(forged))
   with self.assertRaisesRegex(PacketV2CandidateError,"AUTHENTICATED_CAPTURE_AUTHORITY_MISMATCH"):build_packet_v2_candidate(admission,forged,profile(),root/"packet")
   downgraded=replace(capture,verification="SYNTHETIC_OFFLINE_VERIFIED",source_authorization_evidence_id=None,pr_observation_evidence_id=None,evidence_id="");downgraded=replace(downgraded,evidence_id=subject_capture_evidence_id_v2(downgraded))
   with self.assertRaisesRegex(PacketV2CandidateError,"SYNTHETIC_CAPTURE_AUTHORITY_FORBIDDEN"):build_packet_v2_candidate(admission,downgraded,profile(),root/"downgraded")
   stripped=admission.journal_admission();del stripped["source_app_scope_evidence_id"]
   with self.assertRaisesRegex(AdmissionV3CandidateError,"SOURCE_SCOPE_MISMATCH"):validate_journal_admission_v3(stripped,admission.origin_body_bytes)
 def test_I69_F28_technical_policy_not_promoted(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission=self.integrated(root);manifest=build_packet_v2_candidate(admission,capture,profile(),root/"packet");self.assertEqual(manifest["technical_policy"]["qualification"],"SYNTHETIC_OFFLINE_ONLY")
 def test_I69_N10_F29_synthetic_packet_shape_remains_without_authority_fields(self):
  from tests.packet_v2_test_support import admitted,git_capture
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture=git_capture(root);request=request_for_capture(capture,[inline()]);admission=admitted(request,capture=capture);manifest=build_packet_v2_candidate(admission,capture,profile(),root/"packet");self.assertEqual(manifest["subject"]["capture_qualification"],"SYNTHETIC_OFFLINE_VERIFIED");self.assertNotIn("source_authorization_evidence_id",manifest["subject"])
if __name__=="__main__":unittest.main()
