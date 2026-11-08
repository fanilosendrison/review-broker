"""Explicit repository and ref-update ACK contradictions cannot grant authority."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from tests import test_arm_controller as controller_fixture
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID


def inventory(transport):
    return (transport.git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)'),
            transport.git('for-each-ref', '--format=%(refname) %(objectname)'))


class JournalAcknowledgementTests(unittest.TestCase):
    def test_each_controller_patch_ack_contradiction_blocks_mint_without_rollback(self):
        for cut in (1, 2, 3):
            for field in ('url', 'ref', 'sha', 'target-url', 'partial', 'null'):
                with self.subTest(cut=cut, field=field):
                    fixture = controller_fixture.ArmControllerTests()
                    fixture.setUp()
                    try:
                        transport = fixture.transport
                        patches = 0
                        checkpoint = None
                        calls = []
                        cut_call_count = 0
                        def runner(command, **kwargs):
                            nonlocal patches, checkpoint, cut_call_count
                            calls.append(command)
                            response = transport(command, **kwargs)
                            if command[3] == 'PATCH':
                                patches += 1
                                if patches == cut:
                                    checkpoint = inventory(transport)
                                    cut_call_count = len(calls)
                                    value = json.loads(response.stdout.replace('\r\n', '\n').split('\n\n', 1)[1])
                                    if field == 'url':
                                        value['url'] = value['url'].replace('/sample/broker/', '/wrong/repo/')
                                    elif field == 'ref':
                                        value['ref'] = 'refs/heads/other'
                                    elif field == 'sha':
                                        value['object']['sha'] = 'f' * 40
                                    elif field == 'target-url':
                                        value['object']['url'] = 'https://api.github.com/repos/wrong/repo/git/commits/' + value['object']['sha']
                                    elif field == 'partial':
                                        value = {'ref': value['ref']}
                                    else:
                                        value = None
                                    return http_response(command, value)
                            return response
                        fixture.journal.runner = runner
                        with patch('review_broker.arm_controller.actions_token') as mint:
                            with self.assertRaisesRegex(JournalReadUnknown, 'JOURNAL_UPDATE_ACK_UNKNOWN'):
                                fixture.run_controller()
                        mint.assert_not_called()
                        self.assertEqual(patches, cut)
                        self.assertEqual(inventory(transport), checkpoint)
                        self.assertEqual(len(calls), cut_call_count)
                        self.assertEqual(fixture.output.read_bytes(), b'')
                        fixture.journal.runner = transport
                        observed = fixture.journal.get(controller_fixture.REQUEST)
                        self.assertEqual(observed.invocation_count, int(cut == 3))
                    finally:
                        fixture.doCleanups()

    def test_repository_scope_metadata_positive_and_per_operand_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            transport = HttpGitTransport(Path(temp) / 'repository.git')
            journal = GitHubRefJournal('sample/repo', runner=transport)
            valid = dict(id=123, full_name='sample/repo', private=True, name='repo',
                         url='https://api.github.com/repos/sample/repo', html_url='https://github.com/sample/repo',
                         clone_url='https://github.com/sample/repo.git', git_url='git://github.com/sample/repo.git',
                         ssh_url='git@github.com:sample/repo.git', svn_url='https://github.com/sample/repo',
                         git_refs_url='https://api.github.com/repos/sample/repo/git/refs{/sha}',
                         git_commits_url='https://api.github.com/repos/sample/repo/git/commits{/sha}',
                         blobs_url='https://api.github.com/repos/sample/repo/git/blobs{/sha}',
                         trees_url='https://api.github.com/repos/sample/repo/git/trees{/sha}',
                         contents_url='https://api.github.com/repos/sample/repo/contents/{+path}',
                         owner={'login': 'sample', 'url': 'https://api.github.com/users/sample',
                                'html_url': 'https://github.com/sample'})
            def inject(value):
                return lambda command, kwargs: http_response(command, value) if command[4] == 'repos/sample/repo' else None
            transport.fault = inject(valid)
            self.assertEqual(journal._observe(REQUEST_ID).kind.value, 'ABSENT_AUTHENTICATED')
            before = inventory(transport)
            cases = [(field, str(valid[field]).replace('sample/repo', 'wrong/repo')) for field in
                     ('url', 'html_url', 'clone_url', 'git_url', 'ssh_url', 'svn_url',
                      'git_refs_url', 'git_commits_url', 'blobs_url', 'trees_url', 'contents_url')]
            cases += [('name', 'other'), ('owner', {'login': 'wrong'}),
                      ('owner', {'login': 'sample', 'url': 'https://api.github.com/users/wrong'}),
                      ('owner', {'login': 'sample', 'html_url': 'https://github.com/wrong'})]
            for field, replacement in cases:
                value = copy.deepcopy(valid)
                value[field] = replacement
                transport.fault = inject(value)
                with self.subTest(field=field, replacement=replacement):
                    self.assertEqual(journal._observe(REQUEST_ID).kind.value, 'UNKNOWN')
                    with self.assertRaises(JournalReadUnknown):
                        journal.claim(REQUEST_ID)
                    self.assertEqual(inventory(transport), before)
                    self.assertEqual(transport.mutations, [])
            transport.fault = inject(valid)
            self.assertEqual(journal.claim(REQUEST_ID).invocation_count, 0)
            self.assertEqual(len(transport.mutations), 4)
