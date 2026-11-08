"""Response-identity faults cannot rewrite consumed state or advance mutation."""
import base64
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.queue import AttemptState
from tests import test_arm_controller as controller_fixture
from tests import test_journal_unknown_read as unknown_fixture
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID


class ResponseBindingTests(unittest.TestCase):
    def test_stale_contents_response_cannot_rearm_consumed_controller_attempt(self):
        fixture = controller_fixture.ArmControllerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        journal, transport = fixture.journal, fixture.transport
        request = controller_fixture.REQUEST
        prepared_sha, prepared = journal.get_snapshot(request)
        consumed = replace(prepared, state=AttemptState.STOPPED, invocation_count=1)
        consumed_sha = transport.seed(consumed, journal._claim_ref(request))
        before_refs = transport.git('for-each-ref', '--format=%(refname) %(objectname)')
        before_objects = transport.git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)')
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if '/contents/' in command[4] and command[4].endswith('?ref=' + consumed_sha):
                stale = list(command)
                stale[4] = command[4].split('?ref=')[0] + '?ref=' + prepared_sha
                return transport(stale, **kwargs)
            return transport(command, **kwargs)
        journal.runner = runner
        self.assertEqual(journal._observe(request).kind.value, 'UNKNOWN')
        with patch('review_broker.arm_controller.actions_token') as mint:
            with self.assertRaises(JournalReadUnknown):
                fixture.run_controller()
        mint.assert_not_called()
        self.assertEqual(fixture.output.read_bytes(), b'')
        self.assertTrue(all(command[3] == 'GET' for command in calls))
        self.assertEqual(transport.git('for-each-ref', '--format=%(refname) %(objectname)'), before_refs)
        self.assertEqual(transport.git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)'), before_objects)
        journal.runner = transport
        self.assertEqual(journal.get(request).state, AttemptState.STOPPED)
        self.assertEqual(journal.get(request).invocation_count, 1)

    def test_parent_and_parent_tree_wrong_scope_precede_all_object_mutation(self):
        for boundary in ('parent', 'parent-tree'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp:
                t = HttpGitTransport(Path(temp) / 'parent.git')
                journal = GitHubRefJournal('sample/repo', runner=t)
                parent = t.git('rev-parse', 'refs/heads/dev').decode().strip()
                before_objects, before_refs = t.objects(), t.refs()
                def fault(command, kwargs):
                    if command[3] == 'GET' and '/git/commits/' in command[4]:
                        value = {'sha': parent, 'url': 'https://api.github.com/repos/sample/repo/git/commits/' + parent,
                                 'tree': {'sha': t.base_tree, 'url': 'https://api.github.com/repos/sample/repo/git/trees/' + t.base_tree}}
                        selected = value if boundary == 'parent' else value['tree']
                        selected['url'] = selected['url'].replace('/sample/repo/', '/wrong/repo/')
                        return http_response(command, value)
                t.fault = fault
                with self.assertRaises(JournalReadUnknown):
                    journal.claim(REQUEST_ID)
                self.assertEqual(t.mutations, [])
                self.assertEqual(t.objects(), before_objects)
                self.assertEqual(t.refs(), before_refs)

    def test_wrong_scope_object_ack_preserves_completed_effect_but_never_advances(self):
        cases = [(resource, 'url') for resource in ('blobs', 'trees', 'commits')]
        cases += [('commits', field) for field in ('html_url', 'tree', 'parents', 'tree-url', 'parent-url')]
        for resource, field in cases:
            with self.subTest(resource=resource, field=field), tempfile.TemporaryDirectory() as temp:
                t = HttpGitTransport(Path(temp) / 'ack.git')
                checkpoint = None
                cut_call_count = 0
                def runner(command, **kwargs):
                    nonlocal checkpoint, cut_call_count
                    response = t(command, **kwargs)
                    if command[3] == 'POST' and command[4].endswith('/git/' + resource):
                        checkpoint = (t.objects(), t.refs())
                        cut_call_count = len(t.calls)
                        value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                        payload = json.loads(kwargs['input'])
                        if field == 'url':
                            value['url'] = 'https://api.github.com/repos/wrong/repo/git/' + resource + '/' + value['sha']
                        elif field == 'html_url':
                            value['html_url'] = 'https://github.com/wrong/repo/commit/' + value['sha']
                        elif field in ('tree', 'tree-url'):
                            tree = 'f' * 40 if field == 'tree' else payload['tree']
                            repo = 'sample/repo' if field == 'tree' else 'wrong/repo'
                            value['tree'] = {'sha': tree, 'url': f'https://api.github.com/repos/{repo}/git/trees/{tree}'}
                        else:
                            parent = 'f' * 40 if field == 'parents' else payload['parents'][0]
                            repo = 'sample/repo' if field == 'parents' else 'wrong/repo'
                            value['parents'] = [{'sha': parent, 'url': f'https://api.github.com/repos/{repo}/git/commits/{parent}'}]
                        return http_response(command, value, 201)
                    return response
                journal = GitHubRefJournal('sample/repo', runner=runner)
                with self.assertRaisesRegex(JournalReadUnknown, 'JOURNAL_OBJECT_RESPONSE_UNKNOWN'):
                    journal.claim(REQUEST_ID)
                self.assertIsNotNone(checkpoint)
                self.assertEqual((t.objects(), t.refs()), checkpoint)
                self.assertEqual(len(t.calls), cut_call_count)
                self.assertEqual(len(t.mutations), ('blobs', 'trees', 'commits').index(resource) + 1)
                self.assertFalse(any(c['endpoint'].endswith('/git/refs') for c in t.mutations))

    def test_complete_consistent_commit_ack_metadata_remains_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            t = HttpGitTransport(Path(temp) / 'complete-ack.git')
            def runner(command, **kwargs):
                response = t(command, **kwargs)
                if command[3] == 'POST' and command[4].endswith('/git/commits'):
                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                    payload = json.loads(kwargs['input'])
                    value['url'] = 'https://api.github.com/repos/sample/repo/git/commits/' + value['sha']
                    value['html_url'] = 'https://github.com/sample/repo/commit/' + value['sha']
                    value['tree'] = {'sha': payload['tree'], 'url': 'https://api.github.com/repos/sample/repo/git/trees/' + payload['tree']}
                    value['parents'] = [{'sha': p, 'url': 'https://api.github.com/repos/sample/repo/git/commits/' + p} for p in payload['parents']]
                    return http_response(command, value, 201)
                return response
            journal = GitHubRefJournal('sample/repo', runner=runner)
            self.assertEqual(journal.claim(REQUEST_ID).state, AttemptState.REQUESTED)
            self.assertEqual(len(t.mutations), 4)

    def test_complete_content_metadata_and_each_contradictory_identity_operand(self):
        fixture = unknown_fixture.UnknownReadTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        t = fixture.transport
        path = '.review-broker/attempt.json'
        raw = t.git('show', fixture.parent + ':' + path)
        blob = t.git('rev-parse', fixture.parent + ':' + path).decode().strip()
        url = 'https://api.github.com/repos/sample/repo/contents/' + path + '?ref=' + fixture.parent
        html = 'https://github.com/sample/repo/blob/' + fixture.parent + '/' + path
        git = 'https://api.github.com/repos/sample/repo/git/blobs/' + blob
        valid = dict(type='file', path=path, name='attempt.json', sha=blob, size=len(raw),
                     encoding='base64', content=base64.b64encode(raw).decode(), url=url,
                     html_url=html, git_url=git, _links={'self': url, 'html': html, 'git': git},
                     download_url='https://raw.githubusercontent.com/sample/repo/' + fixture.parent + '/' + path + '?token=fixture')
        def inject(value):
            def fault(command, kwargs):
                if '/contents/' in command[4]:
                    return http_response(command, value)
            return fault
        t.fault = inject(valid)
        self.assertEqual(fixture.journal.get(REQUEST_ID).invocation_count, 1)
        cases = [('url', url.replace(fixture.parent, 'f' * 40)), ('url', None),
                 ('html_url', html.replace(fixture.parent, 'f' * 40)),
                 ('git_url', git.replace('/sample/repo/', '/wrong/repo/')),
                 ('download_url', valid['download_url'].replace(fixture.parent, 'f' * 40)),
                 ('size', len(raw) + 1), ('size', True), ('name', 'other.json'), ('sha', 'short'),
                 ('_links', {'self': url.replace(fixture.parent, 'f' * 40)}),
                 ('_links', {'html': html.replace('/sample/repo/', '/wrong/repo/')}),
                 ('_links', {'git': git.replace('/sample/repo/', '/wrong/repo/')})]
        for index, (field, replacement) in enumerate(cases):
            value = copy.deepcopy(valid)
            value[field] = replacement
            with self.subTest(field=field, index=index):
                t.fault = inject(value)
                self.assertEqual(fixture.journal._observe(REQUEST_ID).kind.value, 'UNKNOWN')
                fixture.assert_unknown('content-commit-scope-' + str(index), inject(value))
        value = copy.deepcopy(valid)
        del value['url']
        fixture.assert_unknown('content-commit-scope-missing-url', inject(value))
        t.fault = inject(valid)
        self.assertEqual(fixture.journal.get(REQUEST_ID).invocation_count, 1)
