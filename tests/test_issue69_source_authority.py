import unittest
from tests.issue69_test_support import *
from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
from review_broker.github_source_authority_v3 import GitHubSourceAuthorityV3,GitHubSourceAuthorityV3Error
from review_broker.identity import artifact_identity,canonical_bytes
class Issue69SourceAuthorityTests(unittest.TestCase):
 def test_I69_N01_N02_exact_mint_scope_and_authorization(self):
  authority=source_authority();scope=authority.scope_observation;authorization=authority.authorize(REPOSITORY,REPOSITORY_ID)
  self.assertEqual((scope.installation_id,scope.repository_id),(INSTALLATION_ID,REPOSITORY_ID));self.assertEqual(authorization.installation_id,INSTALLATION_ID);self.assertTrue(authority.permits_token(TOKEN,REPOSITORY,REPOSITORY_ID));self.assertNotIn(TOKEN,canonical_bytes(scope.basis()).decode())
 def test_I69_F05_multi_page_excess_scope_is_fully_read_then_rejected(self):
  repositories=[{"full_name":REPOSITORY,"id":REPOSITORY_ID}]+[{"full_name":f"owner/repo-{i}","id":i+1} for i in range(100)];api=ScopeApi(repositories=repositories,links={1:'<https://api.github.com/installation/repositories?per_page=100&page=2>; rel="next"'});authority=GitHubSourceAuthorityV3(TOKEN,expected_app_slug="github-app:source",expected_installation_id=INSTALLATION_ID,repository=REPOSITORY,repository_id=REPOSITORY_ID,approved_permissions=PERMISSIONS,authorized_repositories=frozenset({REPOSITORY}),executor=api)
  with self.assertRaisesRegex(GitHubSourceAuthorityV3Error,"NOT_EXACT_REPOSITORY"):authority.observe_scope()
  self.assertEqual(api.methods,["GET","GET"])
 def test_I69_N03_exact_requester_authorization(self):
  origin="artifact:sha256:"+"1"*64;authority=GitHubRequesterAuthorityV3(requester_id=7,broker_issue_id=69,origin_evidence_id=origin,authorized=True);value=authority.authorize(7,69,origin)
  self.assertEqual((value.requester_id,value.broker_issue_id),(7,69));self.assertIsNone(authority.authorize(8,69,origin));self.assertIsNone(authority.authorize(7,70,origin))
 def test_I69_F01_F02_F04_repository_identity_and_selection(self):
  with self.assertRaises(GitHubSourceAuthorityV3Error):source_authority(ScopeApi(repositories=[{"full_name":REPOSITORY,"id":9}]))
  with self.assertRaises(GitHubSourceAuthorityV3Error):source_authority(ScopeApi(repositories=[{"full_name":"alias/review-broker","id":REPOSITORY_ID}]))
  with self.assertRaises(ValueError):GitHubSourceAuthorityV3(TOKEN,expected_app_slug="app",expected_installation_id=123,repository=REPOSITORY,repository_id=REPOSITORY_ID,approved_permissions=PERMISSIONS,authorized_repositories=frozenset(),executor=ScopeApi())
 def test_I69_F03_F05_F06_F09_F10_mint_permission_and_pagination_fail_closed(self):
  with self.assertRaises(ValueError):source_authority(permissions=PERMISSIONS-{"issues:read"})
  with self.assertRaises(ValueError):source_authority(permissions=PERMISSIONS|{"contents:write"})
  with self.assertRaises(ValueError):source_authority(installation_id=0)
  with self.assertRaises(GitHubSourceAuthorityV3Error):source_authority(ScopeApi(total=2))
  with self.assertRaises(GitHubSourceAuthorityV3Error):source_authority(ScopeApi(status=403))
  authority=source_authority();self.assertFalse(authority.permits_token("qualification-token",REPOSITORY,REPOSITORY_ID))
 def test_I69_F07_F08_source_read_never_authorizes_requester(self):
  source=source_authority();origin="artifact:sha256:"+"2"*64;requester=GitHubRequesterAuthorityV3(requester_id=7,broker_issue_id=69,origin_evidence_id=origin,authorized=False)
  self.assertIsNotNone(source.authorize(REPOSITORY,REPOSITORY_ID));self.assertIsNone(requester.authorize(7,69,origin))
if __name__=="__main__":unittest.main()
