from dataclasses import replace
import tempfile,unittest
from pathlib import Path
from tests.issue69_test_support import *
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3,GitHubPullRequestObservationV3Error
class Issue69PullRequestObservationTests(unittest.TestCase):
 def scope(self,root,**changes):
  origin,base,head,merge,files=git_graph(root);api=PullApi(base,head,merge,files,**changes);reader=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=source_authority(),executor=api);return reader,reader.observe_scope(),api
 def test_I69_N04_N05_exact_pr_and_complete_files(self):
  with tempfile.TemporaryDirectory() as temporary:
   _,scope,api=self.scope(Path(temporary));self.assertEqual((scope.pull_request_id,scope.changed_files),(7001,2));self.assertEqual([x["path"] for x in scope.changes],["added.md","review.md"]);self.assertTrue(scope.evidence_id.startswith("artifact:sha256:"));self.assertTrue(all("per_page=100" in call for call in api.calls if "/files?" in call))
 def test_I69_F11_F12_F13_pr_identity_and_drift(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,files=git_graph(root)
   reader=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=source_authority(),executor=PullApi(base,head,merge,files,pr_id=0))
   with self.assertRaisesRegex(GitHubPullRequestObservationV3Error,"IDENTITY_INVALID"):reader.observe_scope()
   reader=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=source_authority(),executor=PullApi(base,head,merge,files,drift_head="f"*40));scope=reader.observe_scope()
   with self.assertRaisesRegex(GitHubPullRequestObservationV3Error,"FINAL_IDENTITY_DRIFT"):reader.verify_final_identity(scope)
 def test_I69_F14_F15_incomplete_duplicate_and_unsafe_files(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);origin,base,head,merge,files=git_graph(root)
   for changed,total,marker in [([files[0]],2,"INCOMPLETE"),([files[0],files[0]],2,"DUPLICATE"),([{"status":"modified","filename":"../bad"}],1,"FILE_INVALID"),([{"status":"mystery","filename":"x"}],1,"FILE_INVALID")]:
    with self.subTest(marker=marker):
     reader=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=source_authority(),executor=PullApi(base,head,merge,changed,files_total=total))
     with self.assertRaisesRegex(GitHubPullRequestObservationV3Error,marker):reader.observe_scope()
 def test_I69_F23_ambiguous_access_is_not_absence(self):
  with tempfile.TemporaryDirectory() as temporary:
   origin,base,head,merge,files=git_graph(Path(temporary));reader=GitHubPullRequestObservationReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,71,head,source_authority=source_authority(),executor=PullApi(base,head,merge,files,status=404))
   with self.assertRaisesRegex(GitHubPullRequestObservationV3Error,"AUTHORITY_AMBIGUOUS"):reader.observe_scope()
if __name__=="__main__":unittest.main()
