from dataclasses import replace
import os,subprocess,tempfile,unittest
from unittest import mock
from pathlib import Path
from tests.issue69_test_support import *
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from review_broker.github_subject_capture_v3 import capture_authenticated_subject_v3,bind_authenticated_capture_v3,GitHubSubjectCaptureV3Error
from review_broker.packet_v2 import subject_capture_evidence_id_v2
from review_broker.packets import GitSourceReader,MAX_SOURCE_BYTES,SourceSpec
class Issue69SubjectCaptureTests(unittest.TestCase):
 def setup_capture(self,root):
  origin,base,head,merge,files=git_graph(root);authority=source_authority();api=PullApi(base,head,merge,files);observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=api);scope=observer.observe_scope();authorization=authority.authorize(REPOSITORY,REPOSITORY_ID);capture=capture_authenticated_subject_v3(scope,observer,authorization,authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin));pr=observer.finalize(scope,capture);capture=bind_authenticated_capture_v3(capture,authorization.evidence_id,pr.evidence_id);return origin,scope,observer,authorization,capture,pr
 def test_I69_N06_N07_N08_real_merge_base_images_diff_and_evidence(self):
  with tempfile.TemporaryDirectory() as temporary:
   _,scope,_,authorization,capture,pr=self.setup_capture(Path(temporary));self.assertEqual(capture.merge_base_sha,scope.merge_base_sha);self.assertEqual([x["status"] for x in capture.changes],["added","modified"]);self.assertEqual(len(capture.records),3);self.assertEqual(capture.evidence_id,subject_capture_evidence_id_v2(capture));self.assertEqual(capture.source_authorization_evidence_id,authorization.evidence_id);self.assertEqual(capture.pr_observation_evidence_id,pr.evidence_id)
 def test_I69_F03_substituted_source_token_rejected_before_git(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,files=git_graph(root);authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"SOURCE_AUTHORITY_MISMATCH"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,"different-token",root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F17_F18_ancestry_and_merge_base_fail_closed(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,files=git_graph(root);authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,"f"*40,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"MERGE_BASE_MISMATCH"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F17_unavailable_ancestry_fails_closed(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin=root/"orphan";origin.mkdir();subprocess.run(["git","init","-q","-b","main",str(origin)],check=True);subprocess.run(["git","-C",str(origin),"config","user.email","test@example.invalid"],check=True);subprocess.run(["git","-C",str(origin),"config","user.name","Test"],check=True);(origin/"base.md").write_text("base");subprocess.run(["git","-C",str(origin),"add","."],check=True);subprocess.run(["git","-C",str(origin),"commit","-q","-m","base"],check=True);base=subprocess.check_output(["git","-C",str(origin),"rev-parse","HEAD"],text=True).strip();subprocess.run(["git","-C",str(origin),"checkout","-q","--orphan","feature"],check=True);subprocess.run(["git","-C",str(origin),"rm","-q","-rf","."],check=True);(origin/"head.md").write_text("head");subprocess.run(["git","-C",str(origin),"add","."],check=True);subprocess.run(["git","-C",str(origin),"commit","-q","-m","head"],check=True);head=subprocess.check_output(["git","-C",str(origin),"rev-parse","HEAD"],text=True).strip();files=[{"status":"added","filename":"head.md"}];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,"f"*40,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"ANCESTRY_UNAVAILABLE"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F22_blob_stream_is_capped_and_process_group_terminated(self):
  from review_broker.github_subject_capture_v3 import _read_regular
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);_,_,_,_,capture,_=self.setup_capture(root);record=capture.records[0];reads=[]
   class Stream:
    def read(self,size):reads.append(size);return b"x"*size
   class Process:
    pid=123;stdout=Stream();returncode=None
    def poll(self):return None
    def communicate(self,timeout=None):self.returncode=-9;return b"",b""
   with mock.patch("review_broker.github_subject_capture_v3._popen",return_value=Process()),mock.patch("review_broker.github_subject_capture_v3.os.killpg") as kill:
    with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"SOURCE_TOO_LARGE"):_read_regular(GitSourceReader(capture.repository_root),SourceSpec(record.repository,record.commit,record.path))
   self.assertEqual(reads,[MAX_SOURCE_BYTES+1]);kill.assert_called_once()
 def test_I69_F19_F21_missing_image_and_change_mismatch(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,files=git_graph(root);files=[{"status":"modified","filename":"missing.md"}];authority=source_authority();observer=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=authority,executor=PullApi(base,head,merge,files));scope=observer.observe_scope()
   with self.assertRaisesRegex(GitHubSubjectCaptureV3Error,"CHANGE_SCOPE_MISMATCH"):capture_authenticated_subject_v3(scope,observer,authority.authorize(REPOSITORY,REPOSITORY_ID),authority.scope_observation.evidence_id,TOKEN,root/"capture",acquire_repository=local_acquirer(origin))
 def test_I69_F20_F27_corrupt_git_object_and_no_token_retention(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);_,_,_,_,capture,_=self.setup_capture(root);config=(capture.repository_root/".git/config").read_bytes();self.assertNotIn(TOKEN.encode(),config)
if __name__=="__main__":unittest.main()
