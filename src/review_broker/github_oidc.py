"""GitHub workload-identity transport and pinned issuer verification, without execution authority."""
import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping

import jwt

ISSUER = 'https://token.actions.githubusercontent.com'
DISCOVERY = ISSUER + '/.well-known/openid-configuration'
JWKS = ISSUER + '/.well-known/jwks'


class GitHubOIDCError(ValueError):
    """Credential-free failure; callers must not publish chained provider exceptions."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise GitHubOIDCError('GITHUB_OIDC_REDIRECT_REFUSED')


def issuer_json(url: str) -> dict[str, Any]:
    # Any represents heterogeneous, bounded provider JSON, never executable data.
    if url not in {DISCOVERY, JWKS}:
        raise GitHubOIDCError('GITHUB_OIDC_ISSUER_URL_REFUSED')
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
    except Exception:
        raise GitHubOIDCError('GITHUB_OIDC_ISSUER_UNAVAILABLE') from None


def request_identity(audience: str, environment: Mapping[str, str], *,
                     allowed_host: Callable[[str], bool]) -> str:
    """One request, no retries, redirects or proxies; endpoint policy belongs to the caller."""
    try:
        url = environment['ACTIONS_ID_TOKEN_REQUEST_URL']
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or not allowed_host(parsed.hostname)
            or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment):
            raise ValueError
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if any(k == 'audience' for k, _ in query):
            raise ValueError
        query.append(('audience', audience))
        target = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        request = urllib.request.Request(target, headers={
            'Authorization': 'Bearer ' + environment['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=15) as response:
            raw = response.read(65_537)
            if len(raw) > 65_536 or response.geturl() != target:
                raise ValueError
        token = json.loads(raw)['value']
        if not isinstance(token, str) or not token or len(token) > 32_768:
            raise ValueError
        return token
    except Exception:
        raise GitHubOIDCError('GITHUB_OIDC_REQUEST_FAILED') from None


def verify_github_identity(token: str, *, audience: str, expected_claims: Mapping[str, str],
                           issuer_reader: Callable[[str], dict[str, Any]] | None = None,
                           allow_thumbprints: bool = False) -> None:
    """Verify JOSE and exact caller-owned workload bindings; never grant model authority."""
    if issuer_reader is None:
        issuer_reader = issuer_json
    try:
        if not isinstance(token, str) or len(token) > 32_768:
            raise ValueError
        header = jwt.get_unverified_header(token)
        fields = {'alg', 'typ', 'kid'} | ({'x5t', 'x5t#S256'} if allow_thumbprints else set())
        if (set(header) - fields or header.get('alg') != 'RS256'
            or not isinstance(header.get('kid'), str) or not header['kid']):
            raise ValueError
        # Standard JOSE thumbprints are metadata only, never key selectors or trust anchors.
        for name, size in [('x5t', 27), ('x5t#S256', 43)]:
            if name in header and (not isinstance(header[name], str)
                or not re.fullmatch('[A-Za-z0-9_-]{' + str(size) + '}', header[name])):
                raise ValueError
        discovery = issuer_reader(DISCOVERY)
        if discovery.get('issuer') != ISSUER or discovery.get('jwks_uri') != JWKS:
            raise ValueError
        keys = issuer_reader(JWKS).get('keys')
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
        claims = jwt.decode(token, signing, algorithms=['RS256'], issuer=ISSUER, audience=audience,
            options={'strict_aud': True, 'require': ['iss', 'aud', 'iat', 'nbf', 'exp', 'jti',
                                                    *expected_claims]})
        now = time.time()
        if (any(type(claims[k]) is not int for k in ['iat', 'nbf', 'exp'])
            or not claims['iat'] <= now < claims['exp'] or not claims['nbf'] <= now
            or not 0 < claims['exp'] - claims['iat'] <= 600
            or not isinstance(claims['jti'], str) or not claims['jti']
            or any(claims[k] != v for k, v in expected_claims.items())):
            raise ValueError
    except Exception:
        raise GitHubOIDCError('GITHUB_OIDC_VERIFICATION_FAILED') from None
