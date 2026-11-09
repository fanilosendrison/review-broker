"""Real local Git ACK boundaries retain child bindings across one proposal."""
import base64
import json
from pathlib import Path
import tempfile
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.queue import AttemptState
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID


def leaf(path, sha):
    return dict(path=path, sha=sha, type='blob', mode='100644')


def directory(path, sha, **rest):
    return dict(path=path, sha=sha, type='tree', mode='040000', **rest)


class JournalTreeBindingRetentionTests(unittest.TestCase):
    def scenario(self, first_boundary, conflict):
        with tempfile.TemporaryDirectory() as tmp:
            t = HttpGitTransport(Path(tmp) / 'native.git')
            b = t.blob(base64.b64encode(b'original\n').decode())
            c = t.blob(base64.b64encode(b'different\n').decode())
            shared = t.git('mktree', data=f'100644 blob {b}\talpha\n'.encode()).decode().strip()
            base_tree = t.git('mktree', data=(f'040000 tree {shared}\tfirst\n'
                f'040000 tree {shared}\tshared\n').encode()).decode().strip()
            parent = t.commit(base_tree, [], 'native shared subtrees')
            t.git('update-ref', 'refs/heads/dev', parent)
            self.assertEqual(t.git('rev-parse', parent + ':first/alpha').decode().strip(), b)
            self.assertEqual(t.git('rev-parse', parent + ':shared/alpha').decode().strip(), b)
            checkpoint = cut = None
            def description(tree, blob, nested):
                rows = [directory('first', shared), directory('shared', shared)]
                if nested:
                    rows[1]['tree'] = [leaf('alpha', blob)]
                else:
                    rows.append(leaf('first/alpha', blob))
                # Preserve the native root's actual journal-containing subtree.
                result = t.git('rev-parse', tree + ':.review-broker', check=False)
                if not result.returncode:
                    rows.append(directory('.review-broker', result.stdout.decode().strip()))
                return dict(sha=tree, tree=rows, truncated=False)
            def runner(command, **kwargs):
                nonlocal checkpoint, cut
                response = t(command, **kwargs)
                method, endpoint = command[3:5]
                if method == 'GET' and '/git/commits/' in endpoint and first_boundary == 'parent':
                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                    value['tree'] = description(base_tree, b, False)
                    return http_response(command, value)
                if method == 'POST' and endpoint.endswith('/git/trees'):
                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                    if first_boundary == 'parent':
                        checkpoint, cut = (t.objects(), t.refs()), len(t.calls)
                        value = description(value['sha'], c if conflict else b, True)
                    else:
                        value = description(value['sha'], b, False)
                    return http_response(command, value, 201)
                if method == 'POST' and endpoint.endswith('/git/commits') and first_boundary == 'tree':
                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                    payload = json.loads(kwargs['input'])
                    checkpoint, cut = (t.objects(), t.refs()), len(t.calls)
                    value['tree'] = description(payload['tree'], c if conflict else b, True)
                    return http_response(command, value, 201)
                return response
            journal = GitHubRefJournal('sample/repo', runner=runner)
            if conflict:
                with self.assertRaisesRegex(JournalReadUnknown, 'JOURNAL_OBJECT_RESPONSE_UNKNOWN'):
                    journal.claim(REQUEST_ID)
                self.assertIsNotNone(checkpoint)
                self.assertEqual((t.objects(), t.refs()), checkpoint)
                self.assertEqual(t.calls[cut:], [])
                self.assertEqual(len(t.mutations), 2 if first_boundary == 'parent' else 3)
            else:
                self.assertEqual(journal.claim(REQUEST_ID).state, AttemptState.REQUESTED)
                self.assertEqual(len(t.mutations), 4)

    def test_parent_facts_refuse_contradictory_child_in_tree_ack(self):
        self.scenario('parent', True)

    def test_tree_facts_refuse_contradictory_child_in_commit_ack(self):
        self.scenario('tree', True)

    def test_compatible_flat_nested_facts_survive_successive_acks(self):
        for boundary in ('parent', 'tree'):
            with self.subTest(boundary=boundary):
                self.scenario(boundary, False)
