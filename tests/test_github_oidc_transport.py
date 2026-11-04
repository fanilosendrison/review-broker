"""Provider HTTP boundaries and unchanged production endpoint policy, entirely offline."""
import json
import unittest
from unittest.mock import patch

from review_broker.arm_authority_contract import ArmAuthorityError
from review_broker.arm_controller import actions_token
from review_broker.github_oidc import (
    DISCOVERY, ISSUER, JWKS, GitHubOIDCError, _NoRedirect, issuer_json, request_identity,
)


class GitHubOIDCTransportTests(unittest.TestCase):
    def response(self, opener, raw, url):
        response=opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value=raw
        response.geturl.return_value=url
        return response

    def environment(self, url='https://pipelines.actions.githubusercontent.com/fixture?api-version=2.0'):
        return dict(ACTIONS_ID_TOKEN_REQUEST_URL=url,ACTIONS_ID_TOKEN_REQUEST_TOKEN='synthetic-request-credential')

    def test_one_request_uses_bearer_header_and_encoded_audience_without_proxies_or_redirects(self):
        with patch('review_broker.github_oidc.urllib.request.build_opener')as opener:
            target='https://pipelines.actions.githubusercontent.com/fixture?api-version=2.0&audience=urn%3Afixture'
            response=self.response(opener,b'{"value":"synthetic.jwt"}',target)
            value=request_identity('urn:fixture',self.environment(),allowed_host=lambda h:True)
            self.assertEqual(value,'synthetic.jwt')
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,target)
            self.assertEqual(request.get_header('Authorization'),'Bearer synthetic-request-credential')
            self.assertEqual(opener.return_value.open.call_count,1)
            self.assertEqual(opener.return_value.open.call_args.kwargs,{'timeout':15})
            self.assertEqual(opener.call_args.args[0].proxies,{})
            self.assertIsInstance(opener.call_args.args[1],_NoRedirect)
            response.read.assert_called_once_with(65_537)

    def test_production_strict_hostname_is_not_broadened_by_qualification(self):
        for url in ['http://pipelines.actions.githubusercontent.com/fixture',
            'https://run-actions-fixture.actions.githubusercontent.com/fixture',
            'https://attacker.invalid/fixture','https://pipelines.actions.githubusercontent.com:444/fixture',
            'https://user@pipelines.actions.githubusercontent.com/fixture',
            'https://pipelines.actions.githubusercontent.com/fixture#a',
            'https://pipelines.actions.githubusercontent.com/fixture?audience=other']:
            with self.subTest(url=url),patch('review_broker.github_oidc.urllib.request.build_opener')as opener:
                with self.assertRaisesRegex(ArmAuthorityError,'ARM_ACTIONS_OIDC_UNAVAILABLE'):
                    actions_token('fixture',self.environment(url))
                opener.assert_not_called()

    def test_redirects_and_substituted_or_unbounded_responses_refuse_without_retry(self):
        with self.assertRaises(GitHubOIDCError):_NoRedirect().redirect_request(None,None,None,None,None,None)
        for raw in [b'x'*65_537,b'{}',b'{"value":null}',b'{"value":""}',b'invalid']:
            with patch('review_broker.github_oidc.urllib.request.build_opener')as opener:
                self.response(opener,raw,'https://pipelines.actions.githubusercontent.com/fixture?api-version=2.0&audience=fixture')
                with self.assertRaises(GitHubOIDCError):
                    request_identity('fixture',self.environment(),allowed_host=lambda h:True)
                self.assertEqual(opener.return_value.open.call_count,1)

    def test_issuer_endpoints_are_fixed_and_redirect_proxy_and_response_policies_are_shared(self):
        with patch('review_broker.github_oidc.urllib.request.build_opener')as opener:
            with self.assertRaises(GitHubOIDCError):issuer_json('https://attacker.invalid')
            opener.assert_not_called()
            response=self.response(opener,json.dumps({'issuer':ISSUER,'jwks_uri':JWKS}).encode(),DISCOVERY)
            self.assertEqual(issuer_json(DISCOVERY)['issuer'],ISSUER)
            response.read.assert_called_once_with(131_073)
            self.assertEqual(opener.call_args.args[0].proxies,{})
            self.assertIsInstance(opener.call_args.args[1],_NoRedirect)
            response.geturl.return_value='https://attacker.invalid'
            with self.assertRaises(GitHubOIDCError):issuer_json(JWKS)
