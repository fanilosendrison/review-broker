"""Nonproduction Actions OIDC issuance qualification; no review orchestration imports."""
import hashlib
import os
import re
import secrets
import sys
from typing import Mapping

from .github_oidc import ISSUER, GitHubOIDCError, request_identity, verify_github_identity
from .identity import canonical_bytes
from .oidc_subject import (
    BROKER_REPOSITORY as REPOSITORY, BROKER_REF as REF,
    BROKER_REPOSITORY_ID, BROKER_OWNER_ID, immutable_repository_subject,
)

NAMESPACE = 'urn:review-broker:qualification:v1'
WORKFLOW = REPOSITORY + '/.github/workflows/review-request.yml@' + REF
POLICY = dict(namespace=NAMESPACE, repository=REPOSITORY, ref=REF, workflow_ref=WORKFLOW,
              issuer=ISSUER, algorithm='RS256', lifetime_seconds=600,
              standard_jose_thumbprints='ignored_metadata_never_key_selection',
              scope='OIDC_JOB_ONLY_NOT_PRODUCTION_ARM_AUTHORITY')


def qualify(environment: Mapping[str, str]) -> dict[str, object]:
    """Bind one fresh, purpose-restricted request to the immutable trusted job context."""
    if (environment.get('GITHUB_ACTIONS') != 'true'
        or environment.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
        or environment.get('QUALIFICATION_ONLY') != 'true'
        or environment.get('QUALIFICATION_DEFAULT_BRANCH') != 'dev'
        or environment.get('QUALIFICATION_SHA') != environment.get('GITHUB_SHA')
        or environment.get('GITHUB_REPOSITORY') != REPOSITORY
        or environment.get('GITHUB_REPOSITORY_ID') != BROKER_REPOSITORY_ID
        or environment.get('GITHUB_REPOSITORY_OWNER') != REPOSITORY.split('/', 1)[0]
        or environment.get('GITHUB_REPOSITORY_OWNER_ID') != BROKER_OWNER_ID
        or environment.get('GITHUB_REF') != REF
        or environment.get('GITHUB_WORKFLOW_REF') != WORKFLOW
        or environment.get('GITHUB_WORKFLOW_SHA') != environment.get('GITHUB_SHA')
        or not re.fullmatch('[0-9a-f]{40}', environment.get('GITHUB_SHA', ''))):
        raise ValueError('QUALIFICATION_CONTEXT_INVALID')
    for name in ['GITHUB_REPOSITORY_ID', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT']:
        if not re.fullmatch('[1-9][0-9]*', environment.get(name, '')):
            raise ValueError('QUALIFICATION_CONTEXT_INVALID')
    source = dict(repository=environment['GITHUB_REPOSITORY'],
        repository_id=environment['GITHUB_REPOSITORY_ID'], sha=environment['GITHUB_SHA'],
        workflow_ref=environment['GITHUB_WORKFLOW_REF'], workflow_sha=environment['GITHUB_WORKFLOW_SHA'],
        ref=environment['GITHUB_REF'], run_id=environment['GITHUB_RUN_ID'],
        run_attempt=environment['GITHUB_RUN_ATTEMPT'])
    identity = secrets.token_hex(32)
    binding = dict(namespace=NAMESPACE, source=source, qualification_id=identity)
    digest = hashlib.sha256(canonical_bytes(binding)).hexdigest()
    audience = NAMESPACE + ':sha256:' + digest
    # Endpoint is the trusted runner's normal injected URL, restricted to GitHub's Actions domain.
    # Unlike production's unchanged strict hostname policy, this qualifies the actual job endpoint.
    token = request_identity(audience, environment,
        allowed_host=lambda host: host.endswith('.actions.githubusercontent.com'))
    sys.stderr.write('OIDC_QUALIFICATION_TOKEN_RESPONSE_OBTAINED\n')
    expected = {key: source[key] for key in ['repository', 'repository_id', 'workflow_ref',
                                            'workflow_sha', 'ref', 'run_id', 'run_attempt']}
    expected['repository_owner_id'] = BROKER_OWNER_ID
    expected['repository_owner'] = REPOSITORY.split('/', 1)[0]
    expected['sub'] = immutable_repository_subject(
        REPOSITORY, BROKER_REPOSITORY_ID, BROKER_OWNER_ID, REF)
    verify_github_identity(token, audience=audience, expected_claims=expected, allow_thumbprints=True)
    return dict(schema_version=1, status='OIDC_JOB_QUALIFIED', source=source,
        qualification_id=identity, audience_sha256=hashlib.sha256(audience.encode()).hexdigest(),
        policy_sha256=hashlib.sha256(canonical_bytes(POLICY)).hexdigest(),
        signature_issuer_audience_time_verified=True, exact_workload_bindings_verified=True,
        production_arm_authority_qualified=False)


def main() -> int:
    """Fixed output filename and sanitized failure only: no provider error or JWT can escape."""
    try:
        receipt = qualify(os.environ)
        raw = canonical_bytes(receipt) + b'\n'
        fd = os.open('oidc-qualification.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        sys.stdout.write(raw.decode())
        return 0
    except GitHubOIDCError as exc:
        # Only these client-owned static codes are reportable; never arbitrary exception text.
        allowed = {'GITHUB_OIDC_REQUEST_FAILED', 'GITHUB_OIDC_VERIFICATION_FAILED',
                   'GITHUB_OIDC_ISSUER_UNAVAILABLE', 'GITHUB_OIDC_ISSUER_URL_REFUSED',
                   'GITHUB_OIDC_REDIRECT_REFUSED'}
        code = str(exc) if str(exc) in allowed else 'UNCLASSIFIED'
        sys.stderr.write('OIDC_QUALIFICATION_FAILED:' + code + '\n')
        return 1
    except Exception:
        sys.stderr.write('OIDC_QUALIFICATION_FAILED\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
