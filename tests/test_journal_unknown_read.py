"""R1 safety oracles: requests, real Git effects and authority are separate."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from review_broker.github_journal import GitHubRefJournal
from review_broker.queue import AttemptState, StateTransitionError
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID, record


class UnknownReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.transport = HttpGitTransport(Path(self.temp.name) / 'fixture.git')
        self.journal = GitHubRefJournal('sample/repo', runner=self.transport)
        self.ref = self.journal._claim_ref(REQUEST_ID)
        self.original = record(AttemptState.STOPPED)
        from dataclasses import replace
        self.original = replace(self.original, invocation_count=1)
        self.parent = self.transport.seed(self.original, self.ref)
        self.objects = self.transport.objects()
        self.refs = self.transport.refs()

    def save(self, name, result, permission_calls):
        destination = os.environ.get('RB102_EVIDENCE_DIRECTORY')
        if destination:
            Path(destination, name + '.json').write_text(json.dumps({
                'input': self.original.as_dict(), 'injected': name, 'result': result,
                'calls': self.transport.calls, 'objects_before': self.objects,
                'objects_after': self.transport.objects(), 'refs_before': self.refs,
                'refs_after': self.transport.refs(), 'authorization_calls': permission_calls,
            }, indent=2) + '\n')

    def assert_unknown(self, name, fault, operation=None):
        self.transport.calls.clear()
        self.transport.fault = fault
        grant = Mock()
        outcome = None
        try:
            (operation or (lambda: self.journal.claim(REQUEST_ID)))()
            grant()
        except StateTransitionError as exc:
            outcome = str(exc)
        except Exception as exc:
            outcome = 'untyped:' + type(exc).__name__
        self.save(name, outcome, grant.call_count)
        self.assertTrue(any('/git/refs/heads/' in call['endpoint'] for call in self.transport.calls),
                        'The operation must actually reach journal observation')
        self.assertIsNotNone(outcome, 'UNKNOWN must be a nonpassing result')
        self.assertFalse(outcome.startswith('untyped:'), outcome)
        self.assertEqual(self.transport.mutations, [], 'No speculative Git requests')
        self.assertEqual(self.transport.objects(), self.objects, 'No real new Git objects')
        self.assertEqual(self.transport.refs(), self.refs, 'No real ref changes')
        grant.assert_not_called()

    def test_seven_historical_r1_counterexamples(self):
        for status in (401, 403, 422, 429, 500, 503, None):
            with self.subTest(status=status):
                def fault(command, kwargs):
                    if command[3] == 'GET' and '/git/refs/heads/' in command[4]:
                        if status is None:
                            return subprocess.CompletedProcess(command, 1, '', 'synthetic network failure')
                        return http_response(command, {'message': 'injected'}, status)
                self.assert_unknown('historical-' + str(status), fault)

    def test_all_error_statuses_even_with_cli_success_are_unknown(self):
        for status in (401, 403, 408, 409, 422, 429, 500, 503, 599):
            for code in (0, 1):
                with self.subTest(status=status, code=code):
                    def fault(command, kwargs):
                        if '/git/refs/heads/' in command[4] and command[3] == 'GET':
                            return http_response(command, {}, status, code)
                    self.assert_unknown(f'status-{status}-exit-{code}', fault)

    def test_cli_exceptions_timeouts_and_malformed_success(self):
        cases = [OSError('synthetic secret'), subprocess.TimeoutExpired(['gh'], 1),
                 subprocess.SubprocessError('synthetic secret'), '', '{', 'HTTP/2.0 nope\n\n{}',
                 'HTTP/2.0 200 OK\n\n{}\nHTTP/2.0 404 Missing\n\n{}']
        for index, injected in enumerate(cases):
            with self.subTest(index=index):
                def fault(command, kwargs):
                    if command[3] == 'GET' and '/git/refs/heads/' in command[4]:
                        if isinstance(injected, Exception):
                            raise injected
                        return subprocess.CompletedProcess(command, 0, injected, '')
                self.assert_unknown('malformed-' + str(index), fault)

    def test_ref_content_failure_never_falls_back_to_claim(self):
        for status in (404, 403, 503):
            with self.subTest(status=status):
                def fault(command, kwargs):
                    if '/contents/' in command[4]:
                        return http_response(command, {}, status)
                self.assert_unknown('content-' + str(status), fault)

    def test_excessive_json_nesting_is_classified_unknown_without_mutation(self):
        import base64
        nested = '[' * 2000 + '0' + ']' * 2000
        for boundary in ('http', 'content'):
            with self.subTest(boundary=boundary):
                def fault(command, kwargs):
                    if boundary == 'http' and '/git/refs/heads/' in command[4]:
                        return subprocess.CompletedProcess(command, 0, 'HTTP/2.0 200 OK\n\n' + nested, '')
                    if boundary == 'content' and '/contents/' in command[4]:
                        return http_response(command, {'encoding': 'base64', 'type': 'file',
                            'url': 'https://api.github.com/' + command[4],
                            'path': '.review-broker/attempt.json',
                            'content': base64.b64encode(nested.encode()).decode()})
                self.transport.fault = fault
                self.assertEqual(self.journal._observe(REQUEST_ID).kind.value, 'UNKNOWN')
                self.assert_unknown('excessive-nesting-' + boundary, fault)

    def test_content_path_type_and_partial_identity_are_unknown(self):
        import base64
        from review_broker.identity import canonical_bytes
        valid = dict(encoding='base64', type='file', path='.review-broker/attempt.json',
                     url='https://api.github.com/repos/sample/repo/contents/.review-broker/attempt.json?ref=' + self.parent,
                     content=base64.b64encode(canonical_bytes(self.original.as_dict()) + b'\n').decode())
        cases = [dict(valid, path='other.json'), dict(valid, type='symlink'),
                 {k: v for k, v in valid.items() if k != 'path'},
                 {k: v for k, v in valid.items() if k != 'type'}]
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                def fault(command, kwargs):
                    if '/contents/' in command[4]:
                        return http_response(command, value)
                self.transport.fault = fault
                self.assertEqual(self.journal._observe(REQUEST_ID).kind.value, 'UNKNOWN')
                self.assert_unknown('content-identity-' + str(index), fault)

    def test_ambiguous_404_without_repository_or_credential_proof(self):
        for failed_endpoint in ('repos/sample/repo', 'graphql'):
            with self.subTest(endpoint=failed_endpoint):
                def fault(command, kwargs):
                    if '/git/refs/heads/' in command[4] or command[4] == failed_endpoint:
                        return http_response(command, {}, 404)
                self.assert_unknown('unverified-404-' + failed_endpoint.replace('/', '-'), fault)

    def test_all_real_reader_consumers_propagate_unknown_before_mutation(self):
        from tests.test_publication import intent
        from review_broker.artifact_locator import build_evidence_artifact_locator
        plan = dict(schema_version=1, evidence_type='github-actions-artifact-plan', stage='TERMINAL_CAPTURED',
                    broker_repository='sample/repo', request_id=REQUEST_ID, attempt_id=self.original.attempt_id,
                    subject_id='subject:sha256:' + 'b' * 64, packet_id='packet:sha256:' + 'c' * 64,
                    workflow_run_id='123', workflow_run_attempt='1', artifact_name='synthetic',
                    artifacts={'attempt.json': {'artifact_id': 'artifact:sha256:' + 'b' * 64, 'byte_length': 3}})
        metadata = dict(id=7, name='synthetic', expired=False, workflow_run={'id': 123},
                        digest='sha256:' + 'c' * 64, size_in_bytes=3,
                        created_at='2026-11-07T00:00:00Z', expires_at='2026-12-07T00:00:00Z')
        locator = build_evidence_artifact_locator(plan, metadata, declared_digest=metadata['digest'])
        operations = {
            'get': lambda: self.journal.get(REQUEST_ID),
            'snapshot': lambda: self.journal.get_snapshot(REQUEST_ID),
            'claim': lambda: self.journal.claim(REQUEST_ID),
            'transition': lambda: self.journal.transition(REQUEST_ID, AttemptState.ARMED, ['e']),
            'invocation': lambda: self.journal.record_invocation(REQUEST_ID),
            'capacity': lambda: self.journal.record_capacity(REQUEST_ID, {}),
            'terminal': lambda: self.journal.record_terminal_capture(REQUEST_ID, {}),
            'stopped': lambda: self.journal.record_stopped(REQUEST_ID, {}),
            'publication': lambda: self.journal.record_publication(REQUEST_ID, {}),
            'reserve-publication': lambda: self.journal.reserve_publication(REQUEST_ID, intent('a')),
            'artifact-plan': lambda: self.journal.record_evidence_locator_plan(REQUEST_ID, plan),
            'artifact-locator': lambda: self.journal.record_evidence_locator(REQUEST_ID, locator),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                def fault(command, kwargs):
                    if '/git/refs/heads/' in command[4] and command[3] == 'GET':
                        return http_response(command, {}, 503)
                self.assert_unknown('consumer-' + name, fault, operation)
