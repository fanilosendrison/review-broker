"""Remote execution authorization composition, with no controller credentials or JWT to Codex."""
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

from .arm_authority_contract import (
    ArmAuthorityError, TRUST_FILE, canonical_object, execution_metadata, validate_envelope,
)
from .arm_consumption import consume_attempt
from .arm_oidc import verify_oidc
from .fileobservation import read_regular_file_bounded
from .identity import canonical_bytes
from .input_capacity import capacity_receipt

# Any is bounded canonical JSON; trust is root-owned and envelope/receipts are validated.

def load_trust() -> dict[str, Any]:
    """No runtime bootstrap: missing trust or state requires separate owner qualification."""
    try:
        if TRUST_FILE.resolve(strict=True) != TRUST_FILE:
            raise ValueError
        for parent in TRUST_FILE.parents:
            st = parent.lstat()
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
                raise ValueError
        st = TRUST_FILE.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != 0
            or stat.S_IMODE(st.st_mode) != 0o444):
            raise ValueError
        value = canonical_object(read_regular_file_bounded(TRUST_FILE, 16_384))
        fields = {'schema_version', 'broker_repository', 'broker_repository_id', 'executing_broker_sha',
                  'workflow_ref', 'ref', 'codespace_name', 'codespace_id', 'consumption_directory',
                  'consumption_identity', 'consumption_owner'}
        if (set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['consumption_identity'], list) or len(value['consumption_identity']) != 2
            or any(type(n) is not int or n < 0 for n in value['consumption_identity'])
            or type(value['consumption_owner']) is not int or value['consumption_owner'] != os.geteuid()
            or any(not isinstance(value[k], str) or not value[k] for k in fields -
                   {'schema_version', 'consumption_identity', 'consumption_owner'})):
            raise ValueError
        store = Path(value['consumption_directory'])
        if (store.parent != TRUST_FILE.parent.parent or store.name != 'arm-authority-state-v1'
            or store.resolve(strict=True) != store):
            raise ValueError
        return value
    except Exception as exc:
        raise ArmAuthorityError('ARM_TRUST_BOOTSTRAP_UNQUALIFIED_OR_UNAVAILABLE') from exc


def authorize_execution(
    bundle_raw: bytes | None, *, directory: Path, packet_id: str, attempt_id: str,
    input_bytes: bytes, reviewer_home: Path, trusted_workspace: Path,
    request_id: str,
) -> None:
    """No caller boolean grants authority. Consume only after every binding succeeds."""
    try:
        if bundle_raw is None or len(bundle_raw) > 100_000:
            raise ArmAuthorityError('ARM_AUTHORIZATION_MISSING')
        bundle = canonical_object(bundle_raw)
        if set(bundle) != {'envelope', 'jwt'}:
            raise ArmAuthorityError('ARM_AUTHORIZATION_BUNDLE_INVALID')
        envelope = bundle['envelope']
        validate_envelope(envelope)
        metadata, raw_metadata = execution_metadata(directory)
        expected = capacity_receipt(input_bytes, request_id=metadata['request_id'],
            attempt_id=attempt_id, packet_id=packet_id, executing_broker_sha=metadata['executing_broker_sha'])
        capacity_raw = read_regular_file_bounded(directory / 'input-capacity.json', 100_000)
        if metadata['request_id'] != request_id:
            raise ArmAuthorityError('ARM_REQUEST_BINDING_INVALID')
        if (expected['status'] != 'PASS' or capacity_raw != canonical_bytes(expected) + b'\n'
            or envelope['capacity_receipt'] != expected
            or metadata['attempt_id'] != attempt_id
            or envelope['broker_repository'] != metadata['broker_repository']
            or envelope['broker_metadata_sha256'] != hashlib.sha256(raw_metadata).hexdigest()):
            raise ArmAuthorityError('ARM_EXECUTION_BINDING_INVALID')
        trust = load_trust()
        if (os.environ.get('CODESPACE_NAME') != trust['codespace_name']
            or os.environ.get('CODESPACES') != 'true'):
            raise ArmAuthorityError('ARM_RUNTIME_CODESPACE_MISMATCH')
        store = Path(trust['consumption_directory'])
        for forbidden in [directory, reviewer_home, trusted_workspace]:
            forbidden = forbidden.resolve(strict=True)
            if store == forbidden or store.is_relative_to(forbidden) or forbidden.is_relative_to(store):
                raise ArmAuthorityError('ARM_STORE_BOUNDARY_INVALID')
        verify_oidc(bundle['jwt'], envelope, trust)
        consume_attempt(envelope, trust)
    except ArmAuthorityError:
        raise
    except Exception as exc:
        raise ArmAuthorityError('ARM_EXECUTION_AUTHORIZATION_INVALID') from exc
