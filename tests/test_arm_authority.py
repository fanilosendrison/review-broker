"""Offline hostile signature/binding/replay/persistence oracles; no provider invocation."""
import contextlib
import copy
import io
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa

from review_broker.arm_authority_contract import ArmAuthorityError, canonical_object, envelope_audience
from review_broker.arm_consumption import consume_attempt
from review_broker.arm_execution import authorize_execution, load_trust
from review_broker.arm_oidc import issuer_json, verify_oidc
from review_broker.identity import canonical_bytes
from tests import test_capacity_boundaries as fixtures
from tests import arm_authority_fixture as auth
from tests.test_input_capacity import ATTEMPT


class ArmAuthorityTests(unittest.TestCase):
    def setUp(self):
        factory = fixtures.CapacityBoundaryTests()
        factory.setUp()
        self.addCleanup(factory.doCleanups)
        self.directory, self.manifest, _, self.schema, self.arguments = factory.invocation_fixture()
        self.bundle, self.trust = auth.authorization(self.directory, self.manifest, ATTEMPT)

    def authorize(self, bundle=None):
        return authorize_execution(canonical_bytes(bundle or self.bundle) + b'\n',
            directory=self.directory, packet_id=self.manifest['packet_id'], attempt_id=ATTEMPT,
            request_id=self.manifest['request_id'],
            input_bytes=(self.directory / 'input.txt').read_bytes(),
            reviewer_home=self.arguments['trusted_workspace'].parent / 'home',
            trusted_workspace=self.arguments['trusted_workspace'])

    def test_valid_signature_consumes_once_across_new_runs_and_authorizations(self):
        with auth.trusted_fixture(self.trust):
            self.authorize()
            for changed in [False, True]:
                bundle = copy.deepcopy(self.bundle)
                if changed:
                    bundle['envelope'].update(run_id='11', authorization_id='9' * 64)
                    bundle['jwt'] = auth.sign(bundle['envelope'])
                with self.assertRaises(ArmAuthorityError):
                    self.authorize(bundle)
        self.assertEqual(len(list(Path(self.trust['consumption_directory']).iterdir())), 1)

    def test_signature_and_claim_failures_cannot_consume(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        variants = [{'iss': 'https://attacker.invalid'}, {'aud': 'wrong'},
                    {'aud': 'urn:review-broker:qualification:v1:sha256:' + 'a'*64}, {'exp': 1},
                    {'nbf': 9999999999}, {'iat': 9999999999}, {'run_id': '12'},
                    {'run_attempt': '2'}, {'workflow_sha': 'f' * 40}, {'repository_id': '99'},
                    {'workflow_ref': 'sample/broker/.github/workflows/ci.yml@refs/heads/dev'},
                    {'ref': 'refs/heads/attacker'}, {'sub': 'repo:attacker/repo:ref:refs/heads/dev'}]
        for claims in variants:
            with self.subTest(claims=claims), auth.trusted_fixture(self.trust):
                bundle = copy.deepcopy(self.bundle)
                bundle['jwt'] = auth.sign(bundle['envelope'], claims)
                with self.assertRaises(ArmAuthorityError):
                    self.authorize(bundle)
        for header, key in [({'kid': 'unknown'}, None),
                            ({'kid': 'offline-fixture', 'x5t': 'a'*27}, None),
                            ({'kid': 'offline-fixture', 'jku': 'https://attacker.invalid'}, None),
                            ({'kid': 'offline-fixture'}, other)]:
            with self.subTest(header=header), auth.trusted_fixture(self.trust):
                bundle = copy.deepcopy(self.bundle)
                bundle['jwt'] = auth.sign(bundle['envelope'], key=key, header=header)
                with self.assertRaises(ArmAuthorityError):
                    self.authorize(bundle)
        self.assertEqual(list(Path(self.trust['consumption_directory']).iterdir()), [])

    def test_immutable_subject_substitution_and_missing_owner_cannot_consume(self):
        variants = [
            {'sub': 'repo:sample/broker:ref:refs/heads/dev'},
            {'sub': 'repo:sample@9/broker@1:ref:refs/heads/dev'},
            {'sub': 'repo:sample@30498238/broker@9:ref:refs/heads/dev'},
            {'sub': 'repo:other@30498238/broker@1:ref:refs/heads/dev'},
            {'sub': 'repo:sample@30498238/other@1:ref:refs/heads/dev'},
            {'sub': 'repo:sample@30498238/broker@1:ref:refs/heads/main'},
            {'repository_owner_id': '9'}, {'repository_owner': 'other'},
            {'repository': 'other/broker'}, {'repository': 'sample/other'},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.assert_invalid_identity(auth.sign(self.bundle['envelope'], changes))
        for claim in ['repository_owner_id', 'repository_owner']:
            with self.subTest(missing=claim):
                self.assert_invalid_identity(auth.sign(self.bundle['envelope'], missing=(claim,)))

    def assert_invalid_identity(self, token):
        bundle = dict(self.bundle, jwt=token)
        out, err = io.StringIO(), io.StringIO()
        with auth.trusted_fixture(self.trust), contextlib.redirect_stdout(out), \
             contextlib.redirect_stderr(err):
            with self.assertRaisesRegex(ArmAuthorityError, '^ARM_OIDC_VERIFICATION_FAILED$') as failure:
                self.authorize(bundle)
        self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))
        self.assertNotIn(token, str(failure.exception))
        self.assertIsNone(failure.exception.__cause__)
        self.assertEqual(list(Path(self.trust['consumption_directory']).iterdir()), [])

    def test_signed_repository_id_cannot_replace_protected_trust_identity(self):
        bundle = copy.deepcopy(self.bundle)
        bundle['envelope']['broker_repository_id'] = '9'
        bundle['jwt'] = auth.sign(bundle['envelope'])
        with auth.trusted_fixture(self.trust), self.assertRaisesRegex(
                ArmAuthorityError, '^ARM_OIDC_VERIFICATION_FAILED$'):
            self.authorize(bundle)
        self.assertEqual(list(Path(self.trust['consumption_directory']).iterdir()), [])

    def test_changed_envelope_wrong_bindings_and_missing_files_refuse(self):
        for key, value in [('journal_commit_sha', 'f' * 40), ('packet_id', 'packet:sha256:'+'f'*64),
                           ('attempt_id', 'attempt:sha256:'+'f'*64), ('request_id', 'request:sha256:'+'f'*64),
                           ('executing_broker_sha', 'f'*40), ('input_sha256', 'f'*64),
                           ('codespace_id', '999'), ('broker_metadata_sha256', 'f'*64)]:
            with self.subTest(key=key), auth.trusted_fixture(self.trust):
                bundle = copy.deepcopy(self.bundle)
                bundle['envelope'][key] = value
                with self.assertRaises(ArmAuthorityError):
                    self.authorize(bundle)
        for filename in ['broker-metadata.json', 'input-capacity.json']:
            path = self.directory / filename
            original = path.read_bytes()
            path.unlink()
            try:
                with auth.trusted_fixture(self.trust), self.assertRaises(ArmAuthorityError):
                    self.authorize()
            finally:
                path.write_bytes(original)
        with auth.trusted_fixture(self.trust), self.assertRaises(ArmAuthorityError):
            authorize_execution(None, directory=self.directory, packet_id=self.manifest['packet_id'],
                attempt_id=ATTEMPT, input_bytes=b'x', request_id=self.manifest['request_id'],
                reviewer_home=self.directory.parent/'home',
                trusted_workspace=self.arguments['trusted_workspace'])

    def test_issuer_outage_discovery_substitution_and_unknown_keys_fail(self):
        for value in [{'issuer': 'https://attacker.invalid', 'jwks_uri': 'https://attacker.invalid'},
                      {'issuer': 'https://token.actions.githubusercontent.com', 'jwks_uri': 'https://attacker.invalid'}]:
            with auth.trusted_fixture(self.trust), patch('review_broker.arm_oidc.issuer_json', return_value=value), \
                 self.assertRaises(ArmAuthorityError):
                self.authorize()
        with patch('urllib.request.build_opener') as network, self.assertRaises(ArmAuthorityError):
            issuer_json('https://attacker.invalid')
        network.assert_not_called()

    def test_corrupt_existing_entry_and_replaced_directory_refuse(self):
        root = Path(self.trust['consumption_directory'])
        entry = root / (ATTEMPT.rsplit(':', 1)[1] + '.json')
        entry.write_bytes(b'partial')
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.bundle['envelope'], self.trust)
        self.assertEqual(entry.read_bytes(), b'partial')
        moved = root.with_name('old-consumption')
        root.rename(moved)
        root.mkdir(mode=0o700)
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.bundle['envelope'], self.trust)
        self.assertEqual(list(root.iterdir()), [])

    def test_fsync_interruption_retains_reservation_and_forbids_retry(self):
        with patch('review_broker.arm_consumption.os.fsync', side_effect=OSError('fixture')):
            with self.assertRaises(ArmAuthorityError):
                consume_attempt(self.bundle['envelope'], self.trust)
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.bundle['envelope'], self.trust)
        self.assertEqual(len(list(Path(self.trust['consumption_directory']).iterdir())), 1)

    def test_missing_protected_bootstrap_is_not_self_initialized(self):
        with patch('review_broker.arm_execution.TRUST_FILE', self.directory.parent/'absent-root-trust'):
            with self.assertRaisesRegex(ArmAuthorityError, 'BOOTSTRAP'):
                load_trust()
        self.assertFalse((self.directory.parent/'absent-root-trust').exists())
