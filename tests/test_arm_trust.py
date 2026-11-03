"""Protected bootstrap positive/negative oracles under explicit root-metadata simulation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.arm_authority_contract import ArmAuthorityError
from review_broker.arm_execution import load_trust
from review_broker.identity import canonical_bytes


class ArmTrustTests(unittest.TestCase):
    def test_protected_metadata_accepts_valid_bootstrap_but_rejects_owner_mode_and_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            authority = root/'authority'
            authority.mkdir(mode=0o700)
            store = root/'arm-authority-state-v1'
            store.mkdir(mode=0o700)
            st = store.stat()
            path = authority/'trust.json'
            value = dict(schema_version=1, broker_repository='sample/broker', broker_repository_id='1',
                executing_broker_sha='a'*40, workflow_ref='sample/broker/.github/workflows/review-request.yml@refs/heads/dev',
                ref='refs/heads/dev', codespace_name='fixture-space', codespace_id='2',
                consumption_directory=str(store), consumption_identity=[st.st_dev, st.st_ino],
                consumption_owner=os.geteuid())
            path.write_bytes(canonical_bytes(value)+b'\n')
            path.chmod(0o444)
            actual = Path.lstat
            actual_fstat = os.fstat
            condition = {'owner': 0, 'writable': False}
            class Metadata:
                def __init__(self, original, owner, mode):
                    self.original, self.st_uid, self.st_mode = original, owner, mode
                def __getattr__(self, key):
                    return getattr(self.original, key)
            def protected_descriptor(fd):
                observed = actual_fstat(fd)
                if (observed.st_dev, observed.st_ino) == (actual(path).st_dev, actual(path).st_ino):
                    return Metadata(observed, condition['owner'], observed.st_mode | (0o020 if condition['writable'] else 0))
                return observed
            def protected_metadata(candidate):
                observed = actual(candidate)
                if candidate == path or candidate in path.parents:
                    mode = observed.st_mode & ~0o022
                    if candidate == path and condition['writable']:
                        mode |= 0o020
                    return Metadata(observed, condition['owner'] if candidate == path else 0, mode)
                return observed
            # This models a provisioned root filesystem's metadata, not a live substrate proof.
            # The actual file bytes, canonical parser and all production guard branches still run.
            with patch('review_broker.arm_execution.TRUST_FILE', path), \
                 patch.object(Path, 'lstat', protected_metadata), patch('os.fstat', protected_descriptor):
                self.assertEqual(load_trust(), value)
                condition['owner'] = 12345
                with self.assertRaises(ArmAuthorityError):
                    load_trust()
                condition['owner'] = 0
                condition['writable'] = True
                with self.assertRaises(ArmAuthorityError):
                    load_trust()
                condition['writable'] = False
                path.chmod(0o600)
                path.write_bytes(b'{}\n')
                path.chmod(0o444)
                with self.assertRaises(ArmAuthorityError):
                    load_trust()
