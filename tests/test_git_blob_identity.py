"""Qualify the official Git primitive, neutral context and fail-closed errors."""
import base64
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from review_broker.git_blob_identity import blob_identity, GitBlobIdentityError
from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.queue import AttemptState
from tests.journal_git_transport import JournalGitTransport
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID, record


class GitBlobIdentityTests(unittest.TestCase):
    def test_exact_bytes_and_caller_git_state_cannot_change_sha1_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            oracle = JournalGitTransport(root / 'oracle.git')
            samples = [b'', b'hello\n', b'a\r\nb\n', 'non-ASCII: é\n'.encode(), bytes(range(256))]
            expected = {raw: oracle.git('hash-object', '--stdin', data=raw).decode()[:-1] for raw in samples}
            before = oracle.git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)')
            self.assertEqual(expected[b'hello\n'], 'ce013625030ba8dba906f756967f9e9ca394464a')
            ambient = root / 'ambient.git'
            env = dict(oracle.env, GIT_DEFAULT_HASH='sha256')
            subprocess.run(['git', 'init', '--bare', '--quiet', str(ambient)], env=env, check=True,
                           capture_output=True)
            original = subprocess.run
            observed = []
            def capture(command, **kwargs):
                observed.append((command, kwargs))
                return original(command, **kwargs)
            with patch.dict(os.environ, {'GIT_DIR': str(ambient), 'GIT_WORK_TREE': str(root),
                                        'GIT_DEFAULT_HASH': 'sha256', 'GH_TOKEN': 'inert-fixture',
                                        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.autocrlf',
                                        'GIT_CONFIG_VALUE_0': 'true'}), \
                 patch('review_broker.git_blob_identity.subprocess.run', side_effect=capture):
                for raw in samples:
                    self.assertEqual(blob_identity(raw), expected[raw])
            self.assertEqual(len(observed), len(samples) * 2)
            for command, kwargs in observed:
                self.assertNotIn('GH_TOKEN', kwargs['env'])
                self.assertNotIn('GIT_DIR', kwargs['env'])
                self.assertNotIn('GIT_CONFIG_COUNT', kwargs['env'])
                self.assertEqual(kwargs['env']['GIT_DEFAULT_HASH'], 'sha1')
                self.assertFalse(kwargs['shell'])
                self.assertEqual(kwargs['timeout'], 30)
                self.assertNotIn('-w', command)
                if 'hash-object' in command:
                    self.assertIn('--no-filters', command)
                    self.assertIn(kwargs['input'], samples)
            self.assertEqual(oracle.git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)'), before)

    def test_primitive_errors_and_malformed_outputs_are_non_secret_unknowns(self):
        success = subprocess.CompletedProcess([], 0, b'', b'')
        failures = [OSError('sensitive fixture'), subprocess.TimeoutExpired('git', 30),
                    subprocess.CompletedProcess([], 1, b'', b'sensitive fixture'),
                    subprocess.CompletedProcess([], 0, b'a' * 64 + b'\n', b''),
                    subprocess.CompletedProcess([], 0, b'a' * 40, b''),
                    subprocess.CompletedProcess([], 0, b'a' * 40 + b'\n\n', b'')]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with patch('review_broker.git_blob_identity.subprocess.run', side_effect=[success, failure]):
                    with self.assertRaisesRegex(GitBlobIdentityError, '^GIT_BLOB_IDENTITY_UNKNOWN$'):
                        blob_identity(b'held bytes')
        with patch('review_broker.git_blob_identity.subprocess.run', return_value=failures[2]):
            with self.assertRaises(GitBlobIdentityError):
                blob_identity(b'held bytes')

    def test_hash_unavailability_cannot_become_claim_or_snapshot_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            transport = HttpGitTransport(Path(temp) / 'unavailable.git')
            journal = GitHubRefJournal('sample/repo', runner=transport)
            before = (transport.objects(), transport.refs())
            with patch('review_broker.github_journal_objects.blob_identity', side_effect=GitBlobIdentityError('fixed')):
                with self.assertRaises(JournalReadUnknown):
                    journal.claim(REQUEST_ID)
            self.assertEqual((transport.objects(), transport.refs()), before)
            self.assertEqual(transport.mutations, [])
            current = transport.seed(record(AttemptState.REQUESTED), journal._claim_ref(REQUEST_ID))
            raw = transport.git('show', current + ':.review-broker/attempt.json')
            blob = transport.git('rev-parse', current + ':.review-broker/attempt.json').decode().strip()
            def fault(command, kwargs):
                if '/contents/' in command[4]:
                    return http_response(command, {'url': 'https://api.github.com/' + command[4],
                        'type': 'file', 'path': '.review-broker/attempt.json', 'encoding': 'base64',
                        'content': base64.b64encode(raw).decode(), 'sha': blob})
            transport.fault = fault
            before = (transport.objects(), transport.refs())
            with patch('review_broker.github_journal_identity.blob_identity', side_effect=GitBlobIdentityError('fixed')):
                with self.assertRaises(JournalReadUnknown):
                    journal.claim(REQUEST_ID)
            self.assertEqual((transport.objects(), transport.refs()), before)
            self.assertEqual(transport.mutations, [])
