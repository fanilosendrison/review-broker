"""Transport syntax and independently falsified scope/credential predicates."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown, journal_request
from review_broker.github_journal_read import JournalReadKind
from tests.journal_http_transport import HttpGitTransport
from tests.journal_http_response import http_response
from tests.test_github_journal import REQUEST_ID, record
from review_broker.queue import AttemptState


class HttpClassificationTests(unittest.TestCase):
    def test_unverifiable_or_contradictory_transport_never_proves_absence(self):
        outputs = ['', '{}', 'HTTP/2.0 404 Missing', 'HTTP/2.0 404 Missing\n\n{',
                   'HTTP/2.0 404 Missing\n\n{"a":1,"a":2}',
                   'HTTP/2.0 404 Missing\nMalformed-Header\n\n{}',
                   'HTTP/2.0 302 Redirect\n\n{}',
                   'HTTP/2.0 200 OK\n\n{}\nHTTP/2.0 404 Missing\n\n{}',
                   'HTTP/2.0 200 OK\n\nNaN']
        for text in outputs:
            for code in (0, 1):
                with self.subTest(text=text, code=code):
                    runner = lambda command, **kwargs: subprocess.CompletedProcess(command, code, text, 'sensitive synthetic diagnostic')
                    with self.assertRaises(JournalReadUnknown) as caught:
                        journal_request(runner, 'GET', 'repos/sample/repo')
                    self.assertNotIn('sensitive', str(caught.exception))

    def test_good_http_status_is_not_replaced_by_cli_return_code(self):
        for status, code in ((200, 1), (404, 0), (404, 2), (500, 0)):
            with self.subTest(status=status, code=code):
                with self.assertRaises(JournalReadUnknown):
                    journal_request(lambda command, **kwargs: http_response(command, {}, status, code),
                                    'GET', 'repos/sample/repo')
        for status in (200, 404):
            value = journal_request(lambda command, **kwargs: http_response(command, {}, status),
                                    'GET', 'repos/sample/repo')
            self.assertEqual(value.status, status)

    def test_request_is_host_pinned_bounded_and_non_verbose(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return http_response(command, {})
        journal_request(runner, 'GET', 'repos/sample/repo')
        command, kwargs = calls[0]
        self.assertIn('--include', command)
        self.assertEqual(command[command.index('--hostname') + 1], 'github.com')
        self.assertNotIn('--verbose', command)
        self.assertNotIn('--paginate', command)
        self.assertEqual(kwargs['timeout'], 30)
        self.assertFalse(kwargs['shell'])

    def test_each_absence_identity_or_capability_operand_has_a_negative_oracle(self):
        with tempfile.TemporaryDirectory() as temp:
            t = HttpGitTransport(Path(temp) / 'scope.git')
            journal = GitHubRefJournal('sample/repo', runner=t)
            base = t.git('rev-parse', 'refs/heads/dev').decode().strip()
            identity = {'data': {'viewer': {'login': 'fixture', 'id': 'fixture-user'},
                'repository': {'nameWithOwner': 'sample/repo', 'databaseId': 123, 'viewerPermission': 'WRITE',
                    'defaultBranchRef': {'name': 'dev', 'target': {'oid': base}}}}}
            paths = [(['data', 'viewer', 'login'], ''), (['data', 'viewer', 'id'], None),
                     (['data', 'repository', 'nameWithOwner'], 'wrong/repo'),
                     (['data', 'repository', 'databaseId'], 999),
                     (['data', 'repository', 'viewerPermission'], None),
                     (['data', 'repository', 'defaultBranchRef', 'name'], 'other'),
                     (['data', 'repository', 'defaultBranchRef', 'target', 'oid'], 'f' * 40)]
            self.assertEqual(journal._observe(REQUEST_ID).kind, JournalReadKind.ABSENT_AUTHENTICATED)
            for path, replacement in paths:
                modified = copy.deepcopy(identity)
                node = modified
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = replacement
                def fault(command, kwargs):
                    if command[4] == 'graphql':
                        return http_response(command, modified)
                t.fault = fault
                with self.subTest(path=path):
                    self.assertEqual(journal._observe(REQUEST_ID).kind, JournalReadKind.UNKNOWN)
                    with self.assertRaises(JournalReadUnknown):
                        journal.claim(REQUEST_ID)
                    self.assertEqual(t.mutations, [])
            t.fault = None
            self.assertEqual(journal._observe(REQUEST_ID).kind, JournalReadKind.ABSENT_AUTHENTICATED)

    def test_wrong_ref_repository_target_type_and_sha_are_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            t = HttpGitTransport(Path(temp) / 'ref.git')
            journal = GitHubRefJournal('sample/repo', runner=t)
            ref = journal._claim_ref(REQUEST_ID)
            sha = t.seed(record(AttemptState.REQUESTED), ref)
            original = {'ref': ref, 'url': 'https://api.github.com/repos/sample/repo/git/' + ref,
                        'object': {'sha': sha, 'type': 'commit'}}
            variants = [dict(original, ref=ref + '-other'), dict(original, url='https://api.github.com/repos/wrong/repo/git/' + ref),
                        dict(original, object={'sha': sha, 'type': 'tag'}),
                        *[dict(original, object={'sha': value, 'type': 'commit'}) for value in ('short', 'g' * 40, 1, None)]]
            before = t.objects()
            for value in variants:
                def fault(command, kwargs):
                    if command[3] == 'GET' and '/git/refs/heads/' in command[4]:
                        return http_response(command, value)
                t.fault = fault
                with self.subTest(value=value):
                    self.assertEqual(journal._observe(REQUEST_ID).kind, JournalReadKind.UNKNOWN)
                    with self.assertRaises(JournalReadUnknown):
                        journal.claim(REQUEST_ID)
                    self.assertEqual(t.objects(), before)
                    self.assertEqual(t.mutations, [])
