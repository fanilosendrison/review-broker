"""Fail-closed persistent per-attempt reservation on an explicitly provisioned substrate."""
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

from .arm_authority_contract import ArmAuthorityError
from .identity import canonical_bytes

# JSON trust/consumption fields are heterogeneous and validated before use.

def _identity(st: os.stat_result) -> tuple[int, int]:
    return st.st_dev, st.st_ino


def _directory(path: Path, expected: tuple[int, int], owner: int) -> int:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ArmAuthorityError('ARM_STORE_PATH_UNTRUSTED')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(fd)
    if (_identity(st) != expected or st.st_uid != owner or stat.S_IMODE(st.st_mode) != 0o700
        or _identity(path.lstat()) != expected):
        os.close(fd)
        raise ArmAuthorityError('ARM_STORE_IDENTITY_INVALID')
    return fd


def consume_attempt(envelope: dict[str, Any], trust: dict[str, Any]) -> None:
    """Never initialize, clear or repair state. Partial writes permanently refuse replay."""
    path = Path(trust['consumption_directory'])
    expected = tuple(trust['consumption_identity'])
    fd = _directory(path, expected, trust['consumption_owner'])
    name = envelope['attempt_id'].rsplit(':', 1)[-1] + '.json'
    payload = canonical_bytes({'schema_version': 1, 'attempt_id': envelope['attempt_id'],
        'authorization_id': envelope['authorization_id'],
        'authorization_sha256': hashlib.sha256(canonical_bytes(envelope)).hexdigest(),
        'journal_commit_sha': envelope['journal_commit_sha']}) + b'\n'
    try:
        # Refuse ANY existing entry, including corrupt, symlinked or incomplete files.
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
        try:
            with os.fdopen(out, 'wb') as stream:
                if stream.write(payload) != len(payload):
                    raise ArmAuthorityError('ARM_STORE_SHORT_WRITE')
                stream.flush()
                os.fsync(stream.fileno())
                st = os.fstat(stream.fileno())
                named = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid()
                    or stat.S_IMODE(st.st_mode) != 0o600 or _identity(st) != _identity(named)):
                    raise ArmAuthorityError('ARM_CONSUMPTION_REPLACED')
            os.fsync(fd)
            if _identity(path.lstat()) != expected or _identity(os.fstat(fd)) != expected:
                raise ArmAuthorityError('ARM_STORE_REPLACED')
            # Prove final file bytes after persistence; do not remove a failed reservation.
            check = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                observed = os.read(check, len(payload) + 1)
                final = os.fstat(check)
                if (observed != payload or _identity(final) != _identity(st) or final.st_nlink != 1
                    or final.st_uid != os.geteuid() or stat.S_IMODE(final.st_mode) != 0o600):
                    raise ArmAuthorityError('ARM_CONSUMPTION_CHANGED')
            finally:
                os.close(check)
            verified_directory = _directory(path, expected, trust['consumption_owner'])
            os.close(verified_directory)
        except BaseException:
            # The exclusive entry, even empty, is deliberately never rolled back.
            raise
    except OSError as exc:
        raise ArmAuthorityError('ARM_CONSUMPTION_UNAVAILABLE_OR_CONSUMED') from exc
    finally:
        os.close(fd)
