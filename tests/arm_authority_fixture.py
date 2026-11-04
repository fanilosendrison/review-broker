"""Offline issuer/root-trust fixtures: real RS256 signatures, no live tokens or model."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from review_broker.arm_authority_contract import ISSUER, JWKS, envelope_audience
from review_broker.codex_policy import CodexPolicy
from review_broker.identity import canonical_bytes
from review_broker.input_capacity import capacity_receipt

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key()))
_JWK.update(kid='offline-fixture', alg='RS256', use='sig')


def authorization(directory, manifest, attempt, broker='a' * 40):
    metadata = dict(schema_version=1, broker_repository='sample/broker', issue_number=1,
        request_id=manifest['request_id'], attempt_id=attempt, executing_broker_sha=broker,
        admission_mode='low-sensitivity-v1', requester='fixture', subject_repository='sample/repo',
        admission_checks={'requester_authorized': True, 'repository_authorized': True,
                          'executing_sha_admitted': True, 'low_sensitivity_repository_admitted': True,
                          'public_repository_verified': True})
    raw = canonical_bytes(metadata) + b'\n'
    (directory / 'broker-metadata.json').write_bytes(raw)
    capacity = capacity_receipt((directory / 'input.txt').read_bytes(), request_id=manifest['request_id'],
        packet_id=manifest['packet_id'], attempt_id=attempt, executing_broker_sha=broker)
    (directory / 'input-capacity.json').write_bytes(canonical_bytes(capacity) + b'\n')
    store = directory.parent / 'consumption'
    store.mkdir(mode=0o700, exist_ok=True)
    st = store.stat()
    trust = dict(schema_version=1, broker_repository='sample/broker', broker_repository_id='1',
        executing_broker_sha=broker, workflow_ref='sample/broker/.github/workflows/review-request.yml@refs/heads/dev',
        ref='refs/heads/dev', codespace_name='fixture-space', codespace_id='2',
        consumption_directory=str(store), consumption_identity=[st.st_dev, st.st_ino],
        consumption_owner=os.geteuid())
    envelope = {k: trust[k] for k in ['broker_repository', 'broker_repository_id', 'executing_broker_sha',
                                    'workflow_ref', 'ref', 'codespace_name', 'codespace_id']}
    envelope.update(schema_version=1, authorization_id='3' * 64, workflow_sha=broker,
        run_id='10', run_attempt='1', journal_commit_sha='4' * 40,
        request_id=manifest['request_id'], attempt_id=attempt, packet_id=manifest['packet_id'],
        input_sha256=capacity['input_sha256'], broker_metadata_sha256=hashlib.sha256(raw).hexdigest(),
        capacity_receipt=capacity, reviewer_policy=asdict(CodexPolicy()))
    return {'envelope': envelope, 'jwt': sign(envelope)}, trust


def sign(envelope, overrides=None, key=None, header=None):
    now = int(time.time())
    claims = dict(iss=ISSUER, aud=envelope_audience(envelope), iat=now-1, nbf=now-1, exp=now+120,
        repository=envelope['broker_repository'], repository_id=envelope['broker_repository_id'],
        workflow_ref=envelope['workflow_ref'], workflow_sha=envelope['workflow_sha'],
        ref=envelope['ref'], run_id=envelope['run_id'], run_attempt=envelope['run_attempt'],
        sub='repo:' + envelope['broker_repository'] + ':ref:' + envelope['ref'], jti='fixture-jti')
    claims.update(overrides or {})
    return jwt.encode(claims, key or _KEY, algorithm='RS256', headers=header or {'kid': 'offline-fixture'})


@contextmanager
def trusted_fixture(trust):
    def issuer(url):
        return {'keys': [_JWK]} if url == JWKS else {'issuer': ISSUER, 'jwks_uri': JWKS}
    # Model the separately provisioned root trust at the loader boundary, not signature acceptance.
    # Production loader owner/path checks have independent negative tests; live bootstrap is unqualified.
    with patch('review_broker.arm_execution.load_trust', return_value=trust), \
         patch('review_broker.arm_oidc.issuer_json', side_effect=issuer), \
         patch.dict(os.environ, {'CODESPACE_NAME': trust['codespace_name'], 'CODESPACES': 'true'}):
        yield
