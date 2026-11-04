"""Production delegation bindings over the shared pinned GitHub issuer mechanism."""
from typing import Any

from . import github_oidc
from .arm_authority_contract import ArmAuthorityError, envelope_audience


def issuer_json(url: str) -> dict[str, Any]:
    # Any is provider JSON, validated by the shared cryptographic mechanism.
    if url not in {github_oidc.DISCOVERY, github_oidc.JWKS}:
        raise ArmAuthorityError('ARM_ISSUER_URL_REFUSED')
    try:
        return github_oidc.issuer_json(url)
    except Exception:
        raise ArmAuthorityError('ARM_ISSUER_UNAVAILABLE') from None


def verify_oidc(token: str, envelope: dict[str, Any], trust: dict[str, Any]) -> None:
    """Identity of this pinned job delegates journal authority under the owner decision."""
    try:
        bindings = {'repository': 'broker_repository', 'repository_id': 'broker_repository_id',
                    'workflow_ref': 'workflow_ref', 'workflow_sha': 'executing_broker_sha',
                    'ref': 'ref', 'run_id': 'run_id', 'run_attempt': 'run_attempt'}
        expected = {claim: envelope[field] for claim, field in bindings.items()}
        expected['sub'] = 'repo:' + trust['broker_repository'] + ':ref:' + trust['ref']
        github_oidc.verify_github_identity(token, audience=envelope_audience(envelope),
            expected_claims=expected, issuer_reader=issuer_json)
        for field in ['broker_repository', 'broker_repository_id', 'executing_broker_sha',
                      'workflow_ref', 'ref', 'codespace_name', 'codespace_id']:
            if envelope[field] != trust[field]:
                raise ValueError
    except Exception:
        raise ArmAuthorityError('ARM_OIDC_VERIFICATION_FAILED') from None
