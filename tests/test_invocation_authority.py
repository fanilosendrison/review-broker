"""Offline operational-entry regression: packet data is not durable execution authority."""
from contextlib import redirect_stderr
import copy
import io
import os
import shutil
import subprocess
import unittest
from unittest.mock import patch

from review_broker.cli import main
from review_broker.codex import invoke_once, InvocationError
from review_broker.identity import canonical_bytes
from review_broker.reviewer_profile import install_reviewer_profile
from tests import arm_authority_fixture as auth
from tests import test_capacity_boundaries as fixtures
from tests.test_input_capacity import ATTEMPT


class InvocationAuthorityTests(unittest.TestCase):
    def test_direct_cli_without_metadata_or_arm_authority_cannot_transport(self):
        factory = fixtures.CapacityBoundaryTests()
        factory.setUp()
        self.addCleanup(factory.doCleanups)
        directory, manifest, journal, schema, arguments = factory.invocation_fixture()
        for name in ['broker-metadata.json', 'input-capacity.json']:
            path = directory / name
            if path.exists():
                path.unlink()
        calls = []
        def fake_runner(command, **kwargs):
            calls.append(command)
            (directory / 'codex-final.json').write_bytes(b'{}')
            return subprocess.CompletedProcess(command, 0)
        def actual_adapter(*args, **kwargs):
            return invoke_once(*args, **kwargs, runner=fake_runner,
                               runtime_verifier=arguments['runtime_verifier'],
                               environment=arguments['environment'])
        errors = io.StringIO()
        with patch('review_broker.cli.invoke_once', side_effect=actual_adapter), redirect_stderr(errors):
            code = main(['internal-invoke', '--packet-dir', str(directory), '--schema', str(schema),
                         '--attempt', ATTEMPT, '--packet-id', manifest['packet_id'],
                         '--broker-wheel-sha256', arguments['broker_wheel_sha256'],
                         '--trusted-workspace', str(arguments['trusted_workspace']),
                         '--codex-runtime-root', str(arguments['codex_runtime_root'])])
        self.assertEqual(len(calls), 0, f'MODEL_RUNNER_CALLS={len(calls)}; fake transport only')
        self.assertNotEqual(code, 0)
        self.assertFalse((directory / 'attempt.json').exists())
        self.assertEqual(journal.get(manifest['request_id']).invocation_count, 0)

    def test_each_invalid_operational_authority_has_zero_model_runner_calls(self):
        for scenario in ['metadata', 'capacity', 'wrong-attempt', 'wrong-request', 'wrong-packet',
                         'wrong-broker', 'changed-input', 'missing-authorization', 'forged-jwt', 'stale-jwt',
                         'caller-armed-true', 'policy-substitution', 'runtime-name-missing',
                         'native-absent', 'native-false', 'trust-id', 'capacity-mismatch']:
            with self.subTest(scenario=scenario):
                factory = fixtures.CapacityBoundaryTests()
                factory.setUp()
                self.addCleanup(factory.doCleanups)
                directory, manifest, _, schema, arguments = factory.invocation_fixture()
                bundle, trust = auth.authorization(directory, manifest, ATTEMPT)
                if scenario in ['metadata', 'capacity']:
                    (directory / ('broker-metadata.json' if scenario == 'metadata' else 'input-capacity.json')).unlink()
                elif scenario.startswith('wrong-'):
                    field = {'wrong-attempt': 'attempt_id', 'wrong-request': 'request_id',
                             'wrong-packet': 'packet_id', 'wrong-broker': 'executing_broker_sha'}[scenario]
                    value = copy.deepcopy(bundle['envelope']['capacity_receipt'])
                    prefix, separator, digest = value[field].rpartition(':')
                    value[field] = prefix + separator + ('f' * len(digest))
                    from review_broker.input_capacity import validate_capacity_receipt
                    validate_capacity_receipt(value)
                    (directory/'input-capacity.json').write_bytes(canonical_bytes(value)+b'\n')
                elif scenario == 'changed-input':
                    (directory/'input.txt').write_bytes(b'substitution')
                elif scenario == 'caller-armed-true':
                    arguments['armed'] = True
                elif scenario == 'policy-substitution':
                    from dataclasses import replace
                    from review_broker.codex_policy import CodexPolicy
                    arguments['policy'] = replace(CodexPolicy(), model='unauthorized-model')
                elif scenario == 'forged-jwt':
                    bundle['jwt'] = 'not.a.signature'
                elif scenario == 'stale-jwt':
                    bundle['jwt'] = auth.sign(bundle['envelope'], {'exp': 1})
                if scenario == 'trust-id':trust['codespace_id'] = '999'
                if scenario == 'capacity-mismatch':
                    receipt = copy.deepcopy(bundle['envelope']['capacity_receipt'])
                    receipt['input_sha256'] = 'f' * 64
                    (directory/'input-capacity.json').write_bytes(canonical_bytes(receipt)+b'\n')
                calls = []
                def runner(*args, **kwargs):
                    calls.append(args)
                    raise AssertionError('model transport forbidden')
                with auth.trusted_fixture(trust), self.assertRaises((InvocationError, ValueError)):
                    if scenario == 'runtime-name-missing':os.environ.pop('CODESPACE_NAME',None)
                    if scenario == 'native-absent':os.environ.pop('CODESPACES',None)
                    if scenario == 'native-false':os.environ['CODESPACES'] = 'false'
                    invoke_once(directory, schema, ATTEMPT, runner=runner,
                        authorization_bundle=None if scenario in {'missing-authorization', 'caller-armed-true'} else canonical_bytes(bundle)+b'\n',
                        **arguments)
                self.assertEqual(calls, [], 'MODEL_RUNNER_CALLS=0 required')
                self.assertFalse((directory/'attempt.json').exists())

    def test_authorized_single_call_then_different_packet_directory_cannot_replay(self):
        factory = fixtures.CapacityBoundaryTests()
        factory.setUp()
        self.addCleanup(factory.doCleanups)
        directory, manifest, _, schema, arguments = factory.invocation_fixture()
        bundle, trust = auth.authorization(directory, manifest, ATTEMPT)
        duplicate = directory.with_name('second-packet')
        shutil.copytree(directory, duplicate)
        install_reviewer_profile(directory.parent/'home', arguments['trusted_workspace'], duplicate)
        arguments['environment'].update(CODESPACE_NAME='fixture-space', CODESPACES='true',
            ACTIONS_ID_TOKEN_REQUEST_TOKEN='forbidden-oidc-token', GH_TOKEN='forbidden-control-token',
            GITHUB_TOKEN='forbidden-publication-token')
        calls = []
        def runner(command, **kwargs):
            self.assertNotIn(bundle['jwt'].encode(), kwargs['input'])
            self.assertEqual(os.environ['CODESPACE_NAME'], 'fixture-space')
            self.assertNotIn('CODESPACE_NAME', kwargs['env'])
            self.assertEqual(kwargs['env']['CODESPACES'], 'true')
            for name in ['ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN']:
                self.assertNotIn(name, kwargs['env'])
            self.assertNotIn(bundle['jwt'], ' '.join(command))
            calls.append(command)
            (directory/'codex-final.json').write_bytes(b'{}')
            return subprocess.CompletedProcess(command, 0)
        raw = canonical_bytes(bundle)+b'\n'
        with auth.trusted_fixture(trust):
            invoke_once(directory, schema, ATTEMPT, runner=runner, authorization_bundle=raw, **arguments)
            self.assertFalse((duplicate/'attempt.json').exists())
            with self.assertRaises(InvocationError):
                invoke_once(duplicate, schema, ATTEMPT, runner=runner, authorization_bundle=raw, **arguments)
        self.assertEqual(len(calls), 1)
