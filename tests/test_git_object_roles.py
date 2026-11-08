"""One response has one consistent Git kind per ID, including its root."""
import base64
import copy
import tempfile
from pathlib import Path
import unittest

from review_broker.github_journal_identity import git_object_sha
from review_broker.github_journal import GitHubRefJournal
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
