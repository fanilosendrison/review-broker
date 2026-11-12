"""LP-01 complete preclaim source phase, distinct credentials and stable logical authority."""
from pathlib import Path
import tempfile
import unittest

from review_broker.github_source_authority_v3 import GitHubSourceAuthorityV3
from review_broker.live_source_admission_v3 import LiveSourceSessionV3,SOURCE_PERMISSIONS
from review_broker.live_pre_model_controller_v3 import run_live_controller_v3
from review_broker.request_v3 import request_identity_v3
from tests.issue69_test_support import ScopeApi
from tests.live_prep_provider_support import LiveProviderService,TOKEN_A,TOKEN_B,controller_scenario
from review_broker.github_live_runtime_v3 import REPOSITORY,REPOSITORY_ID


class DualSourceTests(unittest.TestCase):
    def test_LP01_05_same_logical_evidence_does_not_make_secrets_interchangeable(self):
        authorities=[]
        for token in (TOKEN_A,TOKEN_B):
            a=GitHubSourceAuthorityV3(token,expected_app_slug='review-broker-app',expected_installation_id=123,
                repository=REPOSITORY,repository_id=REPOSITORY_ID,approved_permissions=SOURCE_PERMISSIONS,
                authorized_repositories=frozenset({REPOSITORY}),executor=ScopeApi())
            a.observe_scope();authorities.append(a)
        a,b=authorities
        self.assertNotEqual(TOKEN_A,TOKEN_B)
        self.assertEqual(a.scope_observation.evidence_id,b.scope_observation.evidence_id)
        self.assertEqual(a.authorize(REPOSITORY,REPOSITORY_ID),b.authorize(REPOSITORY,REPOSITORY_ID))
        self.assertTrue(a.permits_token(TOKEN_A,REPOSITORY,REPOSITORY_ID))
        self.assertFalse(a.permits_token(TOKEN_B,REPOSITORY,REPOSITORY_ID))
        self.assertTrue(b.permits_token(TOKEN_B,REPOSITORY,REPOSITORY_ID))
        self.assertFalse(b.permits_token(TOKEN_A,REPOSITORY,REPOSITORY_ID))

    def controller(self,root,service,token=None):
        return controller_scenario(root,service,token)

    def test_LP01_01_02_03_04_16_actual_controller_admits_then_claims_and_dispatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);service=LiveProviderService(root)
            self.assertEqual(service.claim_count(),0)
            result=self.controller(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertEqual(service.claim_count(),1)
            self.assertEqual(service.mints,['controller'])
            self.assertEqual(service.acquisitions,[TOKEN_A])
            self.assertEqual(service.source_after_mutation,0)
            self.assertEqual(service.source_with_control,0)
            self.assertEqual(service.journal_with_source,0)
            self.assertEqual(len([c for c in service.calls if c[0]=='POST']),1)
            original=result.claim_outcome.snapshot.record.attempt.admission
            self.assertEqual(len(original['reference_admissions']),1)
            self.assertEqual(len(original['issue_reference_admissions']),2)
            # Provider independently rejects source-token use at the journal HTTP boundary.
            from urllib.request import Request
            with self.assertRaises(AssertionError):
                service(Request('https://api.github.com/repos/'+REPOSITORY+'/git/refs',
                    data=b'{}',method='POST',headers={'Authorization':'Bearer '+TOKEN_A}))
            self.assertEqual(service.journal_with_source,1)

    def test_LP01_04_control_token_substitution_refuses_before_source_or_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);service=LiveProviderService(root)
            with self.assertRaisesRegex(ValueError,'CONTROL_TOKEN_IS_NOT_SOURCE_AUTHORITY'):
                self.controller(root,service,token='fixture-control')
            self.assertEqual(service.source_calls,[]);self.assertEqual(service.claim_count(),0)

    def test_LP01_06_07_08_09_different_scope_cannot_match_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);service=LiveProviderService(root)
            result=self.controller(root,service);admission=result.claim_outcome.snapshot.record.attempt.admission
            with self.assertRaises(ValueError):
                LiveSourceSessionV3(TOKEN_B,app_slug='other-app',installation_id=123,
                    root=root/'wrong',guard=lambda:None,executor=service.source)
            different=LiveSourceSessionV3(TOKEN_B,app_slug='review-broker-app',installation_id=124,
                root=root/'wrong',guard=lambda:None,executor=service.source)
            with self.assertRaisesRegex(ValueError,'WORKER_SOURCE_AUTHORITY_NOT_ORIGINAL'):
                different.require_original_scope(admission)
            with self.assertRaises(ValueError):
                GitHubSourceAuthorityV3(TOKEN_B,expected_app_slug='review-broker-app',expected_installation_id=123,
                    repository=REPOSITORY,repository_id=REPOSITORY_ID,
                    approved_permissions=SOURCE_PERMISSIONS|{'actions:write'},
                    authorized_repositories=frozenset({REPOSITORY}),executor=ScopeApi())
            wrong=GitHubSourceAuthorityV3(TOKEN_B,expected_app_slug='review-broker-app',expected_installation_id=123,
                repository=REPOSITORY,repository_id=REPOSITORY_ID,approved_permissions=SOURCE_PERMISSIONS,
                authorized_repositories=frozenset({REPOSITORY}),
                executor=ScopeApi(repositories=[{'full_name':'other/repo','id':99}]))
            with self.assertRaises(RuntimeError):wrong.observe_scope()
            self.assertEqual(service.acquisitions,[TOKEN_A])
