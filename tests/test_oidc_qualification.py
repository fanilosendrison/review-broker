"""Actual qualification entry point with real synthetic RS256 and issuer boundary fixtures."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from review_broker import oidc_qualification as qualification
from review_broker.github_oidc import ISSUER, JWKS


class OIDCQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = dict(json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key())),
                       kid='qualification-fixture', alg='RS256', use='sig')

    def environment(self):
        return dict(GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='workflow_dispatch',
            QUALIFICATION_ONLY='true', QUALIFICATION_SHA='a'*40, QUALIFICATION_DEFAULT_BRANCH='dev',
            GITHUB_REPOSITORY='fanilosendrison/review-broker', GITHUB_REPOSITORY_ID='1',
            GITHUB_SHA='a'*40, GITHUB_WORKFLOW_SHA='a'*40, GITHUB_REF='refs/heads/dev',
            GITHUB_WORKFLOW_REF='fanilosendrison/review-broker/.github/workflows/review-request.yml@refs/heads/dev',
            GITHUB_RUN_ID='42', GITHUB_RUN_ATTEMPT='1')

    def run_entry(self, *, changed=None, header=None, key=None, keys=None,
                  environment=None, discovery=None, provider_error=False):
        env = environment or self.environment()
        captured = []
        def request(audience, supplied, **kwargs):
            self.assertEqual(dict(supplied), env)
            self.assertTrue(audience.startswith('urn:review-broker:qualification:v1:sha256:'))
            self.assertNotIn('arm-authority', audience)
            self.assertTrue(kwargs['allowed_host']('pipelines.actions.githubusercontent.com'))
            self.assertTrue(kwargs['allowed_host']('run-actions-fixture.actions.githubusercontent.com'))
            self.assertFalse(kwargs['allowed_host']('actions.githubusercontent.com.attacker.invalid'))
            now = int(time.time())
            claims = dict(iss=ISSUER, aud=audience, iat=now-1, nbf=now-1, exp=now+120,
                jti='synthetic-jti', repository=env['GITHUB_REPOSITORY'],
                repository_id=env['GITHUB_REPOSITORY_ID'], workflow_ref=env['GITHUB_WORKFLOW_REF'],
                workflow_sha=env['GITHUB_SHA'], ref=env['GITHUB_REF'], run_id=env['GITHUB_RUN_ID'],
                run_attempt=env['GITHUB_RUN_ATTEMPT'],
                sub='repo:fanilosendrison/review-broker:ref:refs/heads/dev')
            claims.update(changed or {})
            token = jwt.encode(claims, key or self.key, algorithm='RS256',
                headers=header or {'kid': 'qualification-fixture'})
            captured.append(token)
            if provider_error:
                raise RuntimeError(token)
            return token
        def issuer(url):
            return {'keys': keys if keys is not None else [self.jwk]} if url == JWKS else (
                discovery or {'issuer': ISSUER, 'jwks_uri': JWKS})
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            os.chdir(tmp)
            try:
                out, err = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, env, clear=True), \
                     patch('review_broker.oidc_qualification.request_identity', side_effect=request) as req, \
                     patch('review_broker.github_oidc.issuer_json', side_effect=issuer), \
                     contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    status = qualification.main()
                files = {p.name: p.read_text() for p in Path(tmp).iterdir()}
                for token in captured:
                    self.assertNotIn(token, out.getvalue()+err.getvalue()+json.dumps(files))
                self.assertLessEqual(req.call_count, 1)
                return status, out.getvalue(), err.getvalue(), files, req.call_count
            finally:
                os.chdir(previous)

    def test_actual_entry_success_only_reports_sanitized_nonproduction_identity(self):
        status, out, err, files, calls = self.run_entry()
        self.assertEqual((status, err, calls), (0, 'OIDC_QUALIFICATION_TOKEN_RESPONSE_OBTAINED\n', 1))
        self.assertEqual(set(files), {'oidc-qualification.json'})
        value = json.loads(files['oidc-qualification.json'])
        self.assertEqual(json.loads(out), value)
        self.assertEqual(value['status'], 'OIDC_JOB_QUALIFIED')
        self.assertFalse(value['production_arm_authority_qualified'])
        self.assertTrue(value['signature_issuer_audience_time_verified'])
        self.assertTrue(value['exact_workload_bindings_verified'])
        self.assertEqual(value['source']['sha'], 'a'*40)
        self.assertEqual(value['source']['workflow_sha'], 'a'*40)
        self.assertEqual(value['source']['repository_id'], '1')
        self.assertEqual(value['source']['run_id'], '42')
        self.assertEqual(value['source']['run_attempt'], '1')
        self.assertEqual(set(value), {'schema_version', 'status', 'source', 'qualification_id',
            'audience_sha256', 'policy_sha256', 'signature_issuer_audience_time_verified',
            'exact_workload_bindings_verified', 'production_arm_authority_qualified'})
        second = json.loads(self.run_entry()[3]['oidc-qualification.json'])
        self.assertNotEqual(second['qualification_id'], value['qualification_id'])
        self.assertNotEqual(second['audience_sha256'], value['audience_sha256'])

    def test_invalid_issuer_audience_signature_workload_and_time_never_emit_evidence(self):
        variants = [{'iss': 'https://attacker.invalid'}, {'aud': 'urn:review-broker:arm-authority:v1:x'},
            {'repository': 'attacker/repo'}, {'repository_id': '2'}, {'workflow_ref': 'other'},
            {'workflow_sha': 'b'*40}, {'ref': 'refs/heads/feature'}, {'run_id': '43'},
            {'run_attempt': '2'}, {'sub': 'repo:other:ref:refs/heads/dev'},
            {'exp': 1}, {'iat': 9999999999}, {'nbf': 9999999999},
            {'iat': int(time.time())-1, 'exp': int(time.time())+700}, {'jti': ''}]
        for variant in variants:
            with self.subTest(variant=variant):
                status, out, err, files, calls = self.run_entry(changed=variant)
                self.assertEqual((status, out, err, files, calls),
                                 (1, '', 'OIDC_QUALIFICATION_TOKEN_RESPONSE_OBTAINED\n'
                                  'OIDC_QUALIFICATION_FAILED:GITHUB_OIDC_VERIFICATION_FAILED\n', {}, 1))
        self.assertEqual(self.run_entry(key=self.other)[0], 1)
        wrong_algorithm=self.run_entry(key='synthetic-hmac-fixture-'*4,
            header={'kid':'qualification-fixture','alg':'HS256'})
        self.assertEqual((wrong_algorithm[0],wrong_algorithm[4]),(1,1))
        self.assertIn('GITHUB_OIDC_VERIFICATION_FAILED',wrong_algorithm[2])

    def test_unknown_ambiguous_invalid_keys_and_injected_key_urls_fail(self):
        for arguments in [dict(header={'kid': 'unknown'}), dict(keys=[self.jwk, self.jwk]),
            dict(keys=[]), dict(keys=[dict(self.jwk, use='enc')]),
            dict(header={'kid': 'qualification-fixture', 'jku': 'https://attacker.invalid'}),
            dict(discovery={'issuer': ISSUER, 'jwks_uri': 'https://attacker.invalid'})]:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_entry(**arguments)[0], 1)

    def test_standard_thumbprints_are_metadata_only_and_never_key_urls(self):
        for header in [{'kid':'qualification-fixture','x5t':'a'*27},
                       {'kid':'qualification-fixture','x5t#S256':'a'*43}]:
            self.assertEqual(self.run_entry(header=header)[0],0)
        for header in [{'kid':'qualification-fixture','x5t':'https://attacker.invalid'},
                       {'kid':'qualification-fixture','x5u':'https://attacker.invalid'}]:
            self.assertEqual(self.run_entry(header=header)[0],1)

    def test_failure_text_cannot_disclose_even_a_provider_exception_containing_jwt(self):
        self.assertEqual(self.run_entry(provider_error=True)[:4],
                         (1, '', 'OIDC_QUALIFICATION_FAILED\n', {}))

    def test_invalid_context_fails_without_asking_for_a_token(self):
        variants = dict(GITHUB_ACTIONS='false', GITHUB_EVENT_NAME='issues',
            QUALIFICATION_ONLY='false', QUALIFICATION_SHA='b'*40, QUALIFICATION_DEFAULT_BRANCH='main',
            GITHUB_REPOSITORY='attacker/repo', GITHUB_REF='refs/heads/feature',
            GITHUB_WORKFLOW_REF='other', GITHUB_WORKFLOW_SHA='b'*40,
            GITHUB_RUN_ID='0', GITHUB_RUN_ATTEMPT='-1', GITHUB_REPOSITORY_ID='')
        for field, value in variants.items():
            with self.subTest(field=field):
                env = self.environment(); env[field] = value
                self.assertEqual(self.run_entry(environment=env)[0::4], (1, 0))

    def test_module_entry_failure_is_sanitized_and_has_no_orchestration_imports(self):
        root = Path(__file__).parents[1]
        code = """import runpy,sys
forbidden={'review_broker.arm_controller','review_broker.github_journal',
'review_broker.codex','review_broker.orchestration','review_broker.cli','review_broker.arm_execution'}
def audit(event,args):
 if event=='import' and args[0] in forbidden: raise RuntimeError('ORCHESTRATION_IMPORT')
sys.addaudithook(audit)
runpy.run_module('review_broker.oidc_qualification',run_name='__main__')
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, '-c', code], cwd=tmp,
                env=dict(os.environ, GITHUB_ACTIONS='false'), text=True, capture_output=True)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (1, '', 'OIDC_QUALIFICATION_FAILED\n'))
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertNotIn('reviewctl', (root/'src/review_broker/oidc_qualification.py').read_text())
