import json, hashlib
from dataclasses import replace
from unittest.mock import patch
from datetime import datetime,timezone
import unittest
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_issue_reference_v3 import GitHubIssueReferenceReaderV3,GitHubIssueReferenceV3Error
from tests.test_github_git_file_v3 import REPO,REPO_ID,SwapOnSecondComparison,PlainString,TrapString
from review_broker.identity import artifact_identity,canonical_bytes
from tests.issue69_test_support import source_authority
class Api:
 def __init__(self,body="alpha\r\nbeta",status=None,pr=False): self.body,self.status,self.pr=body,status,pr; self.calls=[]
 def __call__(self,r):
  self.calls.append(r.full_url); u=r.full_url
  if self.status and ("/issues/" in u): return HttpResponseV3(self.status,b"{}",{})
  if u.endswith("/installation"): v={"id":123}
  elif u.endswith("/review-broker"): v={"id":REPO_ID,"full_name":REPO}
  elif u.endswith("/issues/comments/99"): v={"id":99,"body":self.body,"updated_at":"2026-01-01Z","issue_url":f"https://api.github.com/repos/{REPO}/issues/51","user":{"id":8}}
  elif u.endswith("/issues/43"): v={"id":430,"number":43,"body":self.body,"updated_at":"2026-01-01Z","user":{"id":7},**({"pull_request":{}} if self.pr else {})}
  elif u.endswith("/issues/51"): v={"id":510,"number":51,"body":"parent","updated_at":"2026-01-01Z","user":{"id":7},**({"pull_request":{}} if self.pr else {})}
  else: raise AssertionError(u)
  return HttpResponseV3(200,json.dumps(v).encode(),{})
def reader(api,source=None):
 source=source_authority() if source is None else source
 authorization=source.authorize(REPO,REPO_ID)
 return GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,authority_evidence_id=authorization.evidence_id,source_authority=source,executor=api,clock=lambda:datetime(2026,1,2,tzinfo=timezone.utc))
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
  with self.assertRaisesRegex(GitHubIssueReferenceV3Error,"SOURCE_CREDENTIAL_IN_CONTENT"): reader(Api(body="token")).observe_issue_body(43)
class IssueAuthorizationBindingTests(unittest.TestCase):
 marker="ISSUE_REFERENCE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH"
 def observe(self,value,operation):
  return value.observe_issue_body(43) if operation=="body" else value.observe_issue_comment(99)
 def test_body_and_comment_same_real_authority_positive(self):
  source=source_authority(); value=reader(Api(),source)
  for operation in ("body","comment"):
   observed=self.observe(value,operation)
   self.assertEqual(observed.qualification,"AUTHENTICATED_READ_ONLY")
   self.assertEqual(observed.authority_evidence_id,source.authorize(REPO,REPO_ID).evidence_id)
   self.assertEqual(observed.installation_id,source.installation_id)
 def test_body_and_comment_substitution_rejected_before_first_get(self):
  for operation in ("body","comment"):
   for use_scope_id in (False,True):
    with self.subTest(operation=operation,use_scope_id=use_scope_id):
     source=source_authority(); api=Api()
     bad=source.scope_observation.evidence_id if use_scope_id else "artifact:sha256:"+"0"*64
     value=GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,
      authority_evidence_id=bad,source_authority=source,executor=api)
     with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
     self.assertEqual(api.calls,[])
 def test_invalid_current_authorization_rejected_before_get(self):
  source=source_authority(); authorization=source.authorize(REPO,REPO_ID)
  for operation in ("body","comment"):
   for current in (None,{},replace(authorization,repository="other/repository"),
                   replace(authorization,repository_id=REPO_ID+1),
                   replace(authorization,installation_id=124),
                   replace(authorization,evidence_id="artifact:sha256:"+"f"*64)):
    with self.subTest(operation=operation,current=current):
     api=Api(); value=reader(api,source)
     with patch.object(source,"authorize",return_value=current):
      with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
     self.assertEqual(api.calls,[])
 def test_wrong_token_repository_installation_scope_and_changed_evidence(self):
  for operation in ("body","comment"):
   for mutation in ("token","repository","scope","installation","evidence","reader_id"):
    with self.subTest(operation=operation,mutation=mutation):
     source=source_authority(); api=Api(); value=reader(api,source)
     if mutation=="token":value._token="different-token"
     if mutation=="repository":value.repository_id+=1
     if mutation=="scope":source._scope=None
     if mutation=="installation":source.installation_id+=1
     if mutation=="evidence":source.app_slug="changed-source-app"
     if mutation=="reader_id":value.authority_evidence_id="artifact:sha256:"+"0"*64
     marker="ISSUE_REFERENCE_SOURCE_AUTHORITY_MISMATCH" if mutation in {"token","repository","scope"} else self.marker
     with self.assertRaisesRegex(GitHubIssueReferenceV3Error,marker):self.observe(value,operation)
     self.assertEqual(api.calls,[])
 def test_recheck_before_final_emission(self):
  for operation in ("body","comment"):
   with self.subTest(operation=operation):
    source=source_authority(); api=Api(); value=reader(api,source)
    def clock():
     source.app_slug="changed-during-acquisition"
     return datetime(2026,1,2,tzinfo=timezone.utc)
    value._clock=clock
    with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
    self.assertEqual(len(api.calls),3 if operation=="body" else 4)
 def test_historical_qualification_mode_not_promoted(self):
  for operation in ("body","comment"):
   with self.subTest(operation=operation):
    value=GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,
     authority_evidence_id="artifact:sha256:"+"0"*64,qualification_only=True,executor=Api())
    observed=self.observe(value,operation)
    self.assertEqual(observed.qualification,"SAME_REPOSITORY_ACTIONS_QUALIFICATION")
    self.assertIsNone(observed.installation_id)

class IssueStringSubclassTests(unittest.TestCase):
 marker="ISSUE_REFERENCE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH"
 def observe(self,value,operation):
  return value.observe_issue_body(43) if operation=="body" else value.observe_issue_comment(99)
 def test_constructor_rejects_all_subclasses_without_methods(self):
  source=source_authority(); actual=source.authorize(REPO,REPO_ID).evidence_id
  for kind in (PlainString,TrapString):
   for qualification in (False,True):
    with self.subTest(kind=kind.__name__,qualification=qualification):
     api=Api()
     with self.assertRaisesRegex(ValueError,"GITHUB_SOURCE_AUTHORITY_INVALID"):
      GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,authority_evidence_id=kind(actual),
       source_authority=source,qualification_only=qualification,executor=api)
     self.assertEqual(api.calls,[])
 def test_post_construction_subclass_rejected_before_get(self):
  for operation in ("body","comment"):
   for kind in (PlainString,TrapString,SwapOnSecondComparison):
    with self.subTest(operation=operation,kind=kind.__name__):
     source=source_authority(); api=Api(); value=reader(api,source)
     value.authority_evidence_id=kind(value.authority_evidence_id)
     with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
     self.assertEqual(api.calls,[])
 def test_actual_authorization_subclass_rejected_before_get(self):
  for operation in ("body","comment"):
   for kind in (PlainString,TrapString,SwapOnSecondComparison):
    with self.subTest(operation=operation,kind=kind.__name__):
     source=source_authority(); api=Api(); value=reader(api,source)
     actual=source.authorize(REPO,REPO_ID)
     with patch.object(source,"authorize",return_value=replace(actual,evidence_id=kind(actual.evidence_id))):
      with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
     self.assertEqual(api.calls,[])
 def test_field_mutation_during_acquisition_rejected(self):
  for operation in ("body","comment"):
   for kind in (str,PlainString,TrapString):
    with self.subTest(operation=operation,kind=kind.__name__):
     source=source_authority(); api=Api(); value=reader(api,source)
     def clock():
      value.authority_evidence_id=kind("artifact:sha256:"+"0"*64)
      return datetime(2026,1,2,tzinfo=timezone.utc)
     value._clock=clock
     with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
     self.assertEqual(len(api.calls),3 if operation=="body" else 4)
 def test_actual_authorization_subclass_at_final_check_rejected(self):
  for operation in ("body","comment"):
   with self.subTest(operation=operation):
    source=source_authority(); api=Api(); value=reader(api,source)
    actual=source.authorize(REPO,REPO_ID)
    with patch.object(source,"authorize",side_effect=[actual,replace(actual,evidence_id=TrapString(actual.evidence_id))]):
     with self.assertRaisesRegex(GitHubIssueReferenceV3Error,self.marker):self.observe(value,operation)
    self.assertEqual(len(api.calls),3 if operation=="body" else 4)
 def test_emission_uses_verified_local_id_not_mutated_field(self):
  for operation in ("body","comment"):
   with self.subTest(operation=operation):
    source=source_authority(); value=reader(Api(),source)
    actual=source.authorize(REPO,REPO_ID).evidence_id
    original=value._authority; calls=[]
    def verify_then_mutate():
     verified=original(); calls.append(verified)
     if len(calls)==2:value.authority_evidence_id="artifact:sha256:"+"0"*64
     return verified
    value._authority=verify_then_mutate
    observed=self.observe(value,operation)
    self.assertEqual(len(calls),2)
    self.assertNotEqual(value.authority_evidence_id,actual)
    self.assertIs(type(observed.authority_evidence_id),str)
    self.assertEqual(observed.authority_evidence_id,actual)
    basis=observed.provenance_basis(); self.assertEqual(basis["authority_evidence_id"],actual)
    encoded=canonical_bytes(basis)+b"\n"
    self.assertEqual(observed.evidence_id,artifact_identity(encoded))
    self.assertNotIn(b"token",encoded)
 def test_canonical_native_id_and_historical_emission(self):
  source=source_authority(); actual=source.authorize(REPO,REPO_ID).evidence_id
  for operation in ("body","comment"):
   for qualification in (False,True):
    value=GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,authority_evidence_id=actual,
     source_authority=source,qualification_only=qualification,executor=Api())
    observed=self.observe(value,operation)
    self.assertIs(type(observed.authority_evidence_id),str)
    self.assertEqual(observed.authority_evidence_id,actual)
    self.assertEqual(observed.qualification,"SAME_REPOSITORY_ACTIONS_QUALIFICATION" if qualification else "AUTHENTICATED_READ_ONLY")
  for invalid in ("artifact:sha256:"+"g"*64,"artifact:sha256:0"):
   with self.assertRaisesRegex(ValueError,"GITHUB_SOURCE_AUTHORITY_INVALID"):
    GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,authority_evidence_id=invalid,source_authority=source,executor=Api())
 def test_exact_reviewer_witness_body_and_comment_rejected(self):
  for operation in ("body","comment"):
   with self.subTest(operation=operation):
    source=source_authority(); api=Api()
    actual=source.authorize(REPO,REPO_ID).evidence_id
    bad_text="artifact:sha256:"+"0"*64
    self.assertNotEqual(actual,bad_text)
    supplied=SwapOnSecondComparison(bad_text)
    with self.assertRaisesRegex(ValueError,"GITHUB_SOURCE_AUTHORITY_INVALID"):
     value=GitHubIssueReferenceReaderV3("token",REPO,REPO_ID,
      authority_evidence_id=supplied,source_authority=source,executor=api)
     supplied.arm(value)
     observed=value.observe_issue_body(43) if operation=="body" else value.observe_issue_comment(99)
     self.assertEqual(observed.qualification,"AUTHENTICATED_READ_ONLY")
     self.assertIs(type(observed.authority_evidence_id),str)
     self.assertEqual(observed.authority_evidence_id,bad_text)
     self.assertNotEqual(observed.authority_evidence_id,actual)
    self.assertEqual(api.calls,[])

if __name__=="__main__": unittest.main()
