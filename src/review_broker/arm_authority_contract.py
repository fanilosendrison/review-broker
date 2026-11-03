"""Versioned, closed workload-identity delegation envelope; never authority alone."""
from dataclasses import asdict
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .codex_policy import CodexPolicy
from .fileobservation import read_regular_file_bounded
from .identity import attempt_identity, canonical_bytes
from .input_capacity import validate_capacity_receipt

# Any denotes JSON contract values, not executable objects; schema and bindings are checked.
ISSUER = 'https://token.actions.githubusercontent.com'
DISCOVERY = ISSUER + '/.well-known/openid-configuration'
JWKS = ISSUER + '/.well-known/jwks'
AUDIENCE_PREFIX = 'urn:review-broker:arm-authority:v1:sha256:'
WORKFLOW_PATH = '.github/workflows/review-request.yml'
TRUSTED_REF = 'refs/heads/dev'
AUTHORITY_ROOT = Path('/var/lib/review-broker/arm-authority-v1')
TRUST_FILE = AUTHORITY_ROOT / 'trust.json'
STATE_DIRECTORY = AUTHORITY_ROOT.parent / 'arm-authority-state-v1'


class ArmAuthorityError(ValueError):
    """Fail closed without including token, claims or credential data in diagnostics."""


_FIELDS = {
    'schema_version': {'const': 1, 'type': 'integer'},
    'authorization_id': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
    'broker_repository': {'type': 'string', 'pattern': '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'},
    'broker_repository_id': {'type': 'string', 'pattern': '^[1-9][0-9]*$'},
    'executing_broker_sha': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
    'workflow_ref': {'type': 'string'}, 'workflow_sha': {'type': 'string'},
    'ref': {'const': TRUSTED_REF},
    'run_id': {'type': 'string', 'pattern': '^[1-9][0-9]*$'},
    'run_attempt': {'type': 'string', 'pattern': '^[1-9][0-9]*$'},
    'journal_commit_sha': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
    'request_id': {'type': 'string', 'pattern': '^request:sha256:[0-9a-f]{64}$'},
    'attempt_id': {'type': 'string', 'pattern': '^attempt:sha256:[0-9a-f]{64}$'},
    'packet_id': {'type': 'string', 'pattern': '^packet:sha256:[0-9a-f]{64}$'},
    'input_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
    'broker_metadata_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
    'capacity_receipt': {'type': 'object'}, 'reviewer_policy': {'type': 'object'},
    'codespace_name': {'type': 'string', 'pattern': '^[a-zA-Z0-9-]+$'},
    'codespace_id': {'type': 'string', 'pattern': '^[1-9][0-9]*$'},
}
ENVELOPE_SCHEMA = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                   'type': 'object', 'properties': _FIELDS, 'required': list(_FIELDS),
                   'additionalProperties': False}
_VALIDATOR = Draft202012Validator(ENVELOPE_SCHEMA)


def validate_envelope(value: dict[str, Any]) -> None:
    try:
        _VALIDATOR.validate(value)
        if any('pattern' in rule and re.fullmatch(rule['pattern'], value[key]) is None
               for key, rule in _FIELDS.items()):
            raise ValueError
        if (value['attempt_id'] != attempt_identity(value['request_id'], 1)
            or value['workflow_sha'] != value['executing_broker_sha']
            or value['workflow_ref'] != value['broker_repository'] + '/' + WORKFLOW_PATH + '@' + TRUSTED_REF
            or value['reviewer_policy'] != asdict(CodexPolicy())):
            raise ValueError
        capacity = value['capacity_receipt']
        validate_capacity_receipt(capacity)
        if capacity['status'] != 'PASS':
            raise ValueError
        for key in ['request_id', 'attempt_id', 'packet_id', 'executing_broker_sha', 'input_sha256']:
            if value[key] != capacity[key]:
                raise ValueError
    except Exception as exc:
        raise ArmAuthorityError('ARM_ENVELOPE_INVALID') from exc


def envelope_audience(envelope: dict[str, Any]) -> str:
    validate_envelope(envelope)
    return AUDIENCE_PREFIX + hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def canonical_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or raw != canonical_bytes(value) + b'\n':
            raise ValueError
        return value
    except Exception as exc:
        raise ArmAuthorityError('ARM_CANONICAL_OBJECT_INVALID') from exc


def execution_metadata(directory: Path) -> tuple[dict[str, Any], bytes]:
    """Current operational metadata is mandatory; historical validation is unchanged."""
    raw = read_regular_file_bounded(directory / 'broker-metadata.json', 100_000)
    value = canonical_object(raw)
    fields = {'schema_version', 'broker_repository', 'issue_number', 'attempt_id', 'request_id',
              'admission_mode', 'executing_broker_sha', 'requester', 'subject_repository', 'admission_checks'}
    if (set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
        or type(value['issue_number']) is not int or value['issue_number'] <= 0
        or any(not isinstance(value[k], str) or not value[k] for k in fields -
               {'schema_version', 'issue_number', 'admission_checks'})
        or value['admission_mode'] not in {'comprehensive-security', 'low-sensitivity-v1', 'bounded-private-v1'}
        or not isinstance(value['admission_checks'], dict)
        or not value['admission_checks']
        or any(type(v) is not bool for v in value['admission_checks'].values())):
        raise ArmAuthorityError('ARM_METADATA_INVALID')
    return value, raw
