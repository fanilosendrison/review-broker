"""Pinned GitHub issuer discovery and maintained JWT signature/claim validation."""
import json
import time
import urllib.request
from typing import Any

import jwt

from .arm_authority_contract import (
    ArmAuthorityError, DISCOVERY, ISSUER, JWKS, envelope_audience,
)

# JSON JWT/JWKS claims have schema-dependent types; never expose them in errors.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ArmAuthorityError('ARM_ISSUER_REDIRECT_REFUSED')


def issuer_json(url: str) -> dict[str, Any]:
    if url not in {DISCOVERY, JWKS}:
        raise ArmAuthorityError('ARM_ISSUER_URL_REFUSED')
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(url, timeout=15) as response:
            raw = response.read(131_073)
            if len(raw) > 131_072 or response.geturl() != url:
                raise ValueError
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except Exception as exc:
        raise ArmAuthorityError('ARM_ISSUER_UNAVAILABLE') from exc


def verify_oidc(token: str, envelope: dict[str, Any], trust: dict[str, Any]) -> None:
    """Identity of this pinned job delegates journal authority under the owner decision."""
    try:
        if not isinstance(token, str) or len(token) > 32_768:
            raise ValueError
        header = jwt.get_unverified_header(token)
        if (set(header) - {'alg', 'typ', 'kid'} or header.get('alg') != 'RS256'
            or not isinstance(header.get('kid'), str) or not header['kid']):
            raise ValueError
        discovery = issuer_json(DISCOVERY)
        if discovery.get('issuer') != ISSUER or discovery.get('jwks_uri') != JWKS:
            raise ValueError
        keys = issuer_json(JWKS).get('keys')
        if not isinstance(keys, list):
            raise ValueError
        matches = [k for k in keys if isinstance(k, dict) and k.get('kid') == header['kid']]
        if len(matches) != 1:
            raise ValueError
        key = matches[0]
        if (key.get('kty') != 'RSA' or key.get('alg', 'RS256') != 'RS256'
            or key.get('use', 'sig') != 'sig' or key.get('key_ops', ['verify']) != ['verify']
            or any(k in key for k in ['d', 'p', 'q', 'dp', 'dq', 'qi'])):
            raise ValueError
        signing = jwt.PyJWK.from_dict(key, algorithm='RS256').key
        if signing.key_size < 2048:
            raise ValueError
        claims = jwt.decode(token, signing, algorithms=['RS256'], issuer=ISSUER,
                            audience=envelope_audience(envelope),
                            options={'strict_aud': True, 'require': ['iss', 'aud', 'iat', 'nbf', 'exp',
                                     'repository', 'repository_id', 'workflow_ref', 'workflow_sha',
                                     'ref', 'run_id', 'run_attempt', 'jti', 'sub']})
        now = time.time()
        if (any(type(claims[k]) is not int for k in ['iat', 'nbf', 'exp'])
            or not claims['iat'] <= now < claims['exp']
            or not claims['nbf'] <= now or not 0 < claims['exp'] - claims['iat'] <= 600
            or not isinstance(claims['jti'], str) or not claims['jti']
            or claims['sub'] != 'repo:' + trust['broker_repository'] + ':ref:' + trust['ref']):
            raise ValueError
        bindings = {'repository': 'broker_repository', 'repository_id': 'broker_repository_id',
                    'workflow_ref': 'workflow_ref', 'workflow_sha': 'executing_broker_sha',
                    'ref': 'ref', 'run_id': 'run_id', 'run_attempt': 'run_attempt'}
        for claim, field in bindings.items():
            if claims[claim] != envelope[field]:
                raise ValueError
        for field in ['broker_repository', 'broker_repository_id', 'executing_broker_sha',
                      'workflow_ref', 'ref', 'codespace_name', 'codespace_id']:
            if envelope[field] != trust[field]:
                raise ValueError
    except Exception as exc:
        raise ArmAuthorityError('ARM_OIDC_VERIFICATION_FAILED') from exc
