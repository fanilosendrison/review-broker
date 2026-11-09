"""Synthetic-key conformance for the proposed distinct execution workload domain."""
from copy import deepcopy
import json
import time
import unittest
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from review_broker.github_oidc import DISCOVERY, JWKS, ISSUER, GitHubOIDCError
from jch_normative_fixtures import workload
from jch_normative_schemas import arm_audience, workload_claims, verify_workload_claims


class WorkloadClaimsTests(unittest.TestCase):
    def setUp(self):
        self.envelope,_,_,self.deployment,_=workload()
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        public.update(kid='synthetic-jch',alg='RS256',use='sig');self.jwks=dict(keys=[public])

    def issuer(self,url):
        if url==DISCOVERY:return dict(issuer=ISSUER,jwks_uri=JWKS)
        if url==JWKS:return deepcopy(self.jwks)
        raise AssertionError('unadmitted issuer URL')

    def token(self,**changed):
        now=int(time.time())
        value=dict(iss=ISSUER,aud=arm_audience(self.envelope),iat=now,nbf=now,exp=now+300,jti='synthetic',
                   **workload_claims(self.envelope,self.deployment))
        value.update(changed)
        return jwt.encode(value,self.key,algorithm='RS256',headers=dict(kid='synthetic-jch'))

    def test_exact_workload_accepts_but_conveys_no_runtime_operation(self):
        self.assertIsNone(verify_workload_claims(self.token(),self.envelope,self.deployment,self.issuer))

    def test_legacy_storage_and_wrong_workload_domains_refuse(self):
        for changed in [dict(aud='urn:review-broker:arm-authority:v1:sha256:'+'0'*64),
                        dict(aud='urn:review-broker:result-retention:v1:sha256:'+'0'*64),
                        dict(run_id='999'),dict(repository_id='999'),dict(workflow_sha='0'*40),dict(exp=1)]:
            with self.subTest(changed=changed),self.assertRaises(GitHubOIDCError):
                verify_workload_claims(self.token(**changed),self.envelope,self.deployment,self.issuer)

    def test_changed_complete_binding_changes_audience_and_refuses_prior_token(self):
        token=self.token();self.envelope['binding']['challenge']='0'*64
        with self.assertRaises(GitHubOIDCError):verify_workload_claims(token,self.envelope,self.deployment,self.issuer)
