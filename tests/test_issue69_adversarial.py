from dataclasses import replace
import os,subprocess,tempfile,unittest
from pathlib import Path
from tests.issue69_test_support import *
from tests.packet_v2_test_support import inline,profile,request_for_capture
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from review_broker.github_subject_capture_v3 import capture_authenticated_subject_v3,bind_authenticated_capture_v3,GitHubSubjectCaptureV3Error
from review_broker.packet_v2 import build_packet_v2_candidate,PacketV2CandidateError,subject_capture_evidence_id_v2
from review_broker.packets import SourceRecord
class Issue69AdversarialTests(unittest.TestCase):
 def integrated(self,root):
  origin,base,head,merge,files=git_graph(root);authority=source_authority();api=PullApi(base,head,merge,files);observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=api);scope=observer.observe_scope();authorization=authority.authorize(REPOSITORY,REPOSITORY_ID);capture=capture_authenticated_subject_v3(scope,observer,authorization,authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin));pr=observer.finalize(scope,capture);capture=bind_authenticated_capture_v3(capture,authorization.evidence_id,pr.evidence_id);admission=authenticated_admission(request_for_capture(capture,[inline()]),observer,authority);return capture,admission,api
 def test_I69_F16_unsupported_git_object_type(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,_,merge,_=git_graph(root);subprocess.run(["git","-C",str(origin),"checkout","-q","feature"],check=True);os.symlink("review.md",origin/"link.md");subprocess.run(["git","-C",str(origin),"add","link.md"],check=True);subprocess.run(["git","-C",str(origin),"commit","-q","-m","symlink"],check=True);head=subprocess.check_output(["git","-C",str(origin),"rev-parse","HEAD"],text=True).strip();files=[{"status":"added","filename":"added.md"},{"status":"added","filename":"link.md"},{"status":"modified","filename":"review.md"}];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"IMAGE_TYPE_UNSUPPORTED"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F24_subject_reference_role_confusion(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission,_=self.integrated(root);record=capture.records[0];forged_record=replace(record,path="reference.md");forged=replace(capture,records=(forged_record,*capture.records[1:]),evidence_id="");forged=replace(forged,evidence_id=subject_capture_evidence_id_v2(forged))
   with self.assertRaises(PacketV2CandidateError):build_packet_v2_candidate(admission,forged,profile(),root/"packet")
 def test_I69_F20_wrong_git_blob_object_fails_local_proof(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission,_=self.integrated(root);oid=capture.records[-1].git_blob_oid;object_path=capture.repository_root/".git/objects"/oid[:2]/oid[2:];self.assertTrue(object_path.exists());object_path.chmod(0o600);object_path.write_bytes(b"corrupt")
   with self.assertRaisesRegex(PacketV2CandidateError,"LOCAL_GIT_PROOF_INVALID"):build_packet_v2_candidate(admission,capture,profile(),root/"packet")
 def test_I69_F22_source_count_rejected_before_acquisition(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,_=git_graph(root);files=[{"status":"modified","filename":f"path-{i}.md"} for i in range(500)];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope();calls=[]
   def forbidden(destination,environment):calls.append(destination)
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"SOURCE_COUNT_EXCEEDED"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=forbidden)
   self.assertEqual(calls,[])
 def test_I69_F22_oversized_subject_image_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,_,merge,_=git_graph(root);subprocess.run(["git","-C",str(origin),"checkout","-q","feature"],check=True);(origin/"huge.md").write_bytes(b"x"*2_000_001);subprocess.run(["git","-C",str(origin),"add","huge.md"],check=True);subprocess.run(["git","-C",str(origin),"commit","-q","-m","huge"],check=True);head=subprocess.check_output(["git","-C",str(origin),"rev-parse","HEAD"],text=True).strip();files=[{"status":"added","filename":"added.md"},{"status":"added","filename":"huge.md"},{"status":"modified","filename":"review.md"}];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(Exception,"SOURCE_TOO_LARGE"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F27_source_token_in_changed_blob_is_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,_,merge,_=git_graph(root);subprocess.run(["git","-C",str(origin),"checkout","-q","feature"],check=True);(origin/"credential.md").write_text(TOKEN);subprocess.run(["git","-C",str(origin),"add","credential.md"],check=True);subprocess.run(["git","-C",str(origin),"commit","-q","-m","credential"],check=True);head=subprocess.check_output(["git","-C",str(origin),"rev-parse","HEAD"],text=True).strip();files=[{"status":"added","filename":"added.md"},{"status":"added","filename":"credential.md"},{"status":"modified","filename":"review.md"}];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"SOURCE_CREDENTIAL_IN_CAPTURED_BYTES"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F27_token_absent_from_errors_packet_and_config(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);capture,admission,_=self.integrated(root);manifest=build_packet_v2_candidate(admission,capture,profile(),root/"packet");material=(root/"packet/input.txt").read_bytes()+(root/"packet/input-manifest.json").read_bytes()+(capture.repository_root/".git/config").read_bytes();self.assertNotIn(TOKEN.encode(),material)
 def test_I69_live_candidate_stops_before_credentials_on_authority_conflict(self):
  workflow=(Path(__file__).parents[1]/".github/workflows/v3-source-authority-qualification.yml").read_text();self.assertIn('test "$GITHUB_SHA" = "$APPROVED_CODE_SHA"',workflow);self.assertIn("BLOCKED_AUTHORITY_CONFLICT",workflow);self.assertNotIn("create-github-app-token",workflow);self.assertNotIn("GH_TOKEN",workflow)
 def test_I69_F30_all_injected_github_operations_are_read_only(self):
  with tempfile.TemporaryDirectory() as temporary:
   _,_,api=self.integrated(Path(temporary));self.assertTrue(api.calls);self.assertEqual(set(api.methods),{"GET"});self.assertFalse(any(term in call for call in api.calls for term in ("/git/refs","/dispatches","/codespaces")))
if __name__=="__main__":unittest.main()
