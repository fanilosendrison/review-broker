"""One response has one consistent Git kind per ID, including its root."""
import base64
import copy
import json
import tempfile
from pathlib import Path
import unittest

from review_broker.github_journal_identity import git_object_facts, git_object_identity, git_object_sha
from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptState
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID, record


class GitObjectRoleTests(unittest.TestCase):
    def test_mixed_child_roles_refuse_in_either_order(self):
        entries = [dict(path='directory', mode='040000', type='tree', sha='b' * 40),
                   dict(path='file', mode='100644', type='blob', sha='b' * 40)]
        for ordered in (entries, list(reversed(entries))):
            with self.subTest(first=ordered[0]['type']):
                value = dict(sha='a' * 40, tree=ordered, truncated=False)
                with self.assertRaises(ValueError):
                    git_object_sha(value, 'sample/repo', 'trees')

    def test_known_root_and_nested_commit_roles_refuse(self):
        with self.assertRaises(ValueError):
            git_object_sha({'sha': 'a' * 40}, 'sample/repo', 'trees', known_roles={'a' * 40: 'commit'})
        value = dict(sha='a' * 40, tree={'sha': 'b' * 40}, parents=[{'sha': 'b' * 40}])
        with self.assertRaises(ValueError):
            git_object_sha(value, 'sample/repo', 'commits')

    def test_validated_nested_roles_are_returned_for_the_next_response(self):
        known = {'d' * 40: 'blob'}
        value = dict(sha='a' * 40, tree={'sha': 'b' * 40}, parents=[{'sha': 'c' * 40}])
        sha, roles, sizes, links = git_object_facts(value, 'sample/repo', 'commits', known_roles=known)
        self.assertEqual(sha, 'a' * 40)
        self.assertEqual(sizes, {})
        self.assertEqual(links, {'a' * 40: frozenset({'b' * 40, 'c' * 40})})
        self.assertEqual(git_object_identity(value, 'sample/repo', 'commits', known_roles=known),
                         (sha, roles, sizes))
        self.assertEqual(roles, {'a' * 40: 'commit', 'b' * 40: 'tree',
                                 'c' * 40: 'commit', 'd' * 40: 'blob'})
        self.assertEqual(known, {'d' * 40: 'blob'})
        with self.assertRaises(ValueError):
            git_object_sha({'sha': 'c' * 40}, 'sample/repo', 'blobs', known_roles=roles)

    def test_known_and_new_blob_sizes_apply_to_every_alias_and_are_retained(self):
        value = dict(sha='a' * 40, tree=[
            dict(path='first', mode='100644', type='blob', sha='b' * 40, size=10),
            dict(path='second', mode='100644', type='blob', sha='b' * 40, size=10),
        ])
        sha, roles, sizes, links = git_object_facts(value, 'sample/repo', 'trees')
        self.assertEqual(sizes, {'b' * 40: 10})
        with self.assertRaises(ValueError):
            git_object_sha({'sha': 'b' * 40, 'size': 11}, 'sample/repo', 'blobs', known_sizes=sizes)
        for rows in (value['tree'], list(reversed(value['tree']))):
            bad = copy.deepcopy(value)
            bad['tree'] = copy.deepcopy(rows)
            bad['tree'][1]['size'] = 11
            with self.assertRaises(ValueError):
                git_object_sha(bad, 'sample/repo', 'trees')
        self.assertEqual(sizes, {'b' * 40: 10})

    def test_nested_supplied_links_cannot_reintroduce_an_ancestor(self):
        tree = dict(sha='a' * 40, tree=[dict(path='child', mode='040000', type='tree',
            sha='b' * 40, tree=[dict(path='back', mode='040000', type='tree', sha='a' * 40)])])
        commit = dict(sha='a' * 40, parents=[dict(sha='b' * 40, parents=[dict(sha='a' * 40)])])
        for resource, value in (('trees', tree), ('commits', commit)):
            with self.subTest(resource=resource), self.assertRaises(ValueError):
                git_object_identity(value, 'sample/repo', resource)

    def test_sibling_and_retained_links_cannot_hide_a_cycle(self):
        first = dict(path='first', mode='040000', type='tree', sha='b' * 40,
            tree=[dict(path='to-second', mode='040000', type='tree', sha='c' * 40)])
        second = dict(path='second', mode='040000', type='tree', sha='c' * 40,
            tree=[dict(path='to-first', mode='040000', type='tree', sha='b' * 40)])
        for rows in ([first, second], [second, first]):
            with self.assertRaises(ValueError):
                git_object_identity(dict(sha='a' * 40, tree=rows), 'sample/repo', 'trees')
        root = dict(sha='a' * 40, tree=[dict(path='child', mode='040000', type='tree', sha='b' * 40)])
        _, roles, sizes, links = git_object_facts(root, 'sample/repo', 'trees')
        before = copy.deepcopy(links)
        later = dict(sha='b' * 40, tree=[dict(path='back', mode='040000', type='tree', sha='a' * 40)])
        with self.assertRaises(ValueError):
            git_object_identity(later, 'sample/repo', 'trees', known_roles=roles, known_links=links)
        self.assertEqual(links, before)
        # Reusing a checked subtree elsewhere in the DAG is not a cycle.
        later['tree'][0]['sha'] = 'c' * 40
        self.assertEqual(git_object_sha(later, 'sample/repo', 'trees', known_roles=roles,
            known_links=links), 'b' * 40)

    def test_flat_recursive_paths_bind_only_explicit_tree_ancestors(self):
        entries = [dict(path='first', mode='040000', type='tree', sha='b' * 40),
            dict(path='first/second', mode='040000', type='tree', sha='c' * 40),
            dict(path='first/second/back', mode='040000', type='tree', sha='b' * 40)]
        for rows in (entries, list(reversed(entries))):
            with self.assertRaises(ValueError):
                git_object_facts(dict(sha='a' * 40, tree=rows), 'sample/repo', 'trees')
        entries[-1] = dict(path='first/second/file', mode='100644', type='blob', sha='d' * 40)
        entries.append(dict(path='shared', mode='040000', type='tree', sha='b' * 40))
        _, _, _, links = git_object_facts(dict(sha='a' * 40, tree=entries), 'sample/repo', 'trees')
        self.assertEqual(links['b' * 40], frozenset({'c' * 40, 'd' * 40}))
        self.assertEqual(links['c' * 40], frozenset({'d' * 40}))
        # A missing prefix has no asserted identity and supplies no invented node.
        _, _, _, sparse = git_object_facts(dict(sha='a' * 40,
            tree=[dict(path='unknown/file', mode='100644', type='blob', sha='d' * 40)]),
            'sample/repo', 'trees')
        self.assertEqual(sparse, {'a' * 40: frozenset({'d' * 40})})

    def test_tree_cycle_ack_preserves_completed_objects_but_stops_before_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = HttpGitTransport(Path(directory) / 'cycle.git')
            checkpoint = None
            cut = None
            def runner(command, **kwargs):
                nonlocal checkpoint, cut
                response = transport(command, **kwargs)
                if command[3] == 'POST' and command[4].endswith('/git/trees'):
                    checkpoint = (transport.objects(), transport.refs())
                    cut = len(transport.calls)
                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                    child = transport.git('rev-parse', value['sha'] + ':.review-broker').decode().strip()
                    value['tree'] = [dict(path='.review-broker', mode='040000', type='tree', sha=child,
                        tree=[dict(path='back', mode='040000', type='tree', sha=value['sha'])])]
                    return http_response(command, value, 201)
                return response
            journal = GitHubRefJournal('sample/repo', runner=runner)
            with self.assertRaisesRegex(JournalReadUnknown, 'JOURNAL_OBJECT_RESPONSE_UNKNOWN'):
                journal.claim(REQUEST_ID)
            self.assertIsNotNone(checkpoint)
            self.assertEqual((transport.objects(), transport.refs()), checkpoint)
            self.assertEqual(len(transport.calls), cut)
            self.assertEqual(len(transport.mutations), 2)

    def test_snapshot_commit_and_supplied_blob_cannot_share_one_id(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = HttpGitTransport(Path(directory) / 'snapshot.git')
            journal = GitHubRefJournal('sample/repo', runner=transport)
            raw = canonical_bytes(record(AttemptState.PREPARED).as_dict()) + b'\n'
            blob = transport.git('hash-object', '--stdin', data=raw).decode()[:-1]
            def fault(command, kwargs):
                if '/git/refs/heads/' in command[4]:
                    return http_response(command, dict(ref=journal._claim_ref(REQUEST_ID),
                        url='https://api.github.com/' + command[4], object={'sha': blob, 'type': 'commit'}))
                if '/contents/' in command[4]:
                    return http_response(command, dict(type='file', path='.review-broker/attempt.json',
                        url='https://api.github.com/' + command[4], encoding='base64',
                        content=base64.b64encode(raw).decode(), sha=blob))
            transport.fault = fault
            before = (transport.objects(), transport.refs())
            self.assertEqual(journal._observe(REQUEST_ID).kind.value, 'UNKNOWN')
            self.assertEqual((transport.objects(), transport.refs()), before)
            self.assertEqual(transport.mutations, [])

    def test_same_kind_repetitions_are_valid_and_context_remains_immutable(self):
        known = {'c' * 40: 'blob'}
        before = copy.deepcopy(known)
        value = dict(sha='a' * 40, truncated=False, tree=[
            dict(path='one', mode='040000', type='tree', sha='b' * 40),
            dict(path='two', mode='040000', type='tree', sha='b' * 40),
            dict(path='file', mode='100644', type='blob', sha='c' * 40),
        ])
        self.assertEqual(git_object_sha(value, 'sample/repo', 'trees', known_roles=known), 'a' * 40)
        self.assertEqual(known, before)
