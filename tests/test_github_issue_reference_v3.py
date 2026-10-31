import json, hashlib
from datetime import datetime,timezone
import unittest
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_issue_reference_v3 import GitHubIssueReferenceReaderV3,GitHubIssueReferenceV3Error
from tests.test_github_git_file_v3 import AUTHORITY,REPO,REPO_ID
class Api:
 def __init__(self,body="alpha\r\nbeta",status=None,pr=False): self.body,self.status,self.pr=body,status,pr
 def __call__(self,r):
  u=r.full_url
  if self.status and ("/issues/" in u): return HttpResponseV3(self.status,b"{}",{})
  if u.endswith("/installation"): v={"id":123}
  elif u.endswith("/review-broker"): v={"id":REPO_ID,"full_name":REPO}
  elif u.endswith("/issues/comments/99"): v={"id":99,"body":self.body,"updated_at":"2026-01-01Z","issue_url":f"https://api.github.com/repos/{REPO}/issues/51","user":{"id":8}}
  elif u.endswith("/issues/43"): v={"id":430,"number":43,"body":self.body,"updated_at":"2026-01-01Z","user":{"id":7},**({"pull_request":{}} if self.pr else {})}
  elif u.endswith("/issues/51"): v={"id":510,"number":51,"body":"parent","updated_at":"2026-01-01Z","user":{"id":7},**({"pull_request":{}} if self.pr else {})}
  else: raise AssertionError(u)
  return HttpResponseV3(200,json.dumps(v).encode(),{})
def reader(api): return GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,authority_evidence_id=AUTHORITY,expected_installation_id=123,executor=api,clock=lambda:datetime(2026,1,2,tzinfo=timezone.utc))
class Tests(unittest.TestCase):
 def test_issue_and_comment_exact_bytes_identity(self):
  issue=reader(Api()).observe_issue_body(43); comment=reader(Api()).observe_issue_comment(99)
  self.assertEqual(issue.original_bytes,b"alpha\r\nbeta"); self.assertEqual(comment.issue_id,510); self.assertEqual(comment.comment_id,99)
 def test_empty_digest_and_fail_closed_cases(self):
  self.assertEqual(reader(Api(body="")).observe_issue_body(43).original_bytes,b"")
  for api,marker,comment in [(Api(body=None),"BODY_INVALID",False),(Api(status=403),"AMBIGUOUS",False),(Api(status=404),"AMBIGUOUS",True),(Api(pr=True),"PARENT_INVALID",True)]:
   with self.subTest(marker=marker),self.assertRaisesRegex(GitHubIssueReferenceV3Error,marker):
    reader(api).observe_issue_comment(99) if comment else reader(api).observe_issue_body(43)
  with self.assertRaisesRegex(GitHubIssueReferenceV3Error,"EXPECTED_SHA256_MISMATCH"): reader(Api()).observe_issue_body(43,"0"*64)
if __name__=="__main__": unittest.main()
