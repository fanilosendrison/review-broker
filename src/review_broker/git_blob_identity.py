"""Git SHA-1 blob identity through the official isolated, filter-free primitive."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile


class GitBlobIdentityError(ValueError):
    """The local identity computation is unavailable, never an absent object."""


def sha1_oid(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{40}', value) is None:
        raise ValueError
    return value


def blob_identity(raw: bytes) -> str:
    """Compute bytes already held, without filters, caller Git state or -w.

    An isolated empty SHA-1 context prevents an ambient SHA-256 repository,
    templates, attributes, global configuration or GIT_* overrides from changing
    the result. Git versions before GIT_DEFAULT_HASH support only SHA-1.
    The temporary repository is computation context, not claim/consumption state.
    """
    try:
        with tempfile.TemporaryDirectory(prefix='review-broker-blob-identity-') as directory:
            repository = str(Path(directory) / 'objects.git')
            environment = {k: v for k, v in os.environ.items() if k in {'PATH', 'SYSTEMROOT', 'WINDIR'}}
            environment.update(
                HOME=directory, XDG_CONFIG_HOME=directory, TMPDIR=directory,
                TEMP=directory, TMP=directory, GIT_CONFIG_NOSYSTEM='1',
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                GIT_ATTR_NOSYSTEM='1', GIT_DEFAULT_HASH='sha1', GIT_TERMINAL_PROMPT='0',
            )
            initialized = subprocess.run(
                ['git', 'init', '--bare', '--quiet', '--template=', repository],
                cwd=directory, env=environment, capture_output=True, check=False,
                timeout=30, shell=False,
            )
            if initialized.returncode:
                raise ValueError
            result = subprocess.run(
                ['git', '--git-dir=' + repository, 'hash-object', '-t', 'blob', '--stdin', '--no-filters'],
                input=raw, cwd=directory, env=environment, capture_output=True,
                check=False, timeout=30, shell=False,
            )
            if result.returncode or not result.stdout.endswith(b'\n'):
                raise ValueError
            return sha1_oid(result.stdout[:-1].decode('ascii'))
    except Exception:
        raise GitBlobIdentityError('GIT_BLOB_IDENTITY_UNKNOWN') from None
