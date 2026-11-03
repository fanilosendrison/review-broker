"""Deterministic same-parent CAS exclusion against real Git identity/ref rules."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from review_broker.github_journal import GitHubRefJournal
from review_broker.queue import AttemptState, StateTransitionError
from tests.journal_git_transport import JournalGitTransport
from tests.test_github_journal import REQUEST_ID, record


class JournalCasTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.transport = JournalGitTransport(Path(temporary.name) / 'objects.git')
        nonces = iter(f'{n:064x}' for n in range(1, 100))
        self.nonce = patch('secrets.token_hex', side_effect=lambda size: next(nonces))
        self.nonce.start()
        self.addCleanup(self.nonce.stop)
        self.first = GitHubRefJournal('sample/repo', runner=self.transport)
        self.second = GitHubRefJournal('sample/repo', runner=self.transport)
        self.ref = self.first._claim_ref(REQUEST_ID)

    def seed(self, state):
        self.original = record(state)
        self.parent = self.transport.seed(self.original, self.ref)

    def test_competing_identical_arm_proposals_have_only_one_execution_owner(self):
        self.seed(AttemptState.PREPARED)
        invocation = Mock(wraps=self.first.record_invocation)
        evidence = ['packet:sha256:' + 'b' * 64]
        winners = []
        def competitor():
            winners.append(self.second.transition(REQUEST_ID, AttemptState.ARMED, evidence))
        self.transport.before_patch = competitor
        with self.assertRaisesRegex(StateTransitionError, 'STATE_COMPARE_AND_SWAP_FAILED'):
            self.first.transition(REQUEST_ID, AttemptState.ARMED, evidence)
            invocation(REQUEST_ID)
        invocation.assert_not_called()
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(set(self.transport.proposals)), 2)
        self.assertEqual(self.transport.noops, 0)
        self.assertEqual(self.second.record_invocation(REQUEST_ID).invocation_count, 1)
        with self.assertRaisesRegex(StateTransitionError, 'INVOCATION_NOT_PERMITTED'):
            self.first.record_invocation(REQUEST_ID)

    def test_competing_identical_count_one_updates_cannot_reserve_twice(self):
        self.seed(AttemptState.ARMED)
        winners = []
        self.transport.before_patch = lambda: winners.append(self.second.record_invocation(REQUEST_ID))
        with self.assertRaisesRegex(StateTransitionError, 'STATE_COMPARE_AND_SWAP_FAILED'):
            self.first.record_invocation(REQUEST_ID)
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(set(self.transport.proposals)), 2)
        self.assertEqual(self.first.get(REQUEST_ID).invocation_count, 1)
        self.assertEqual(self.transport.noops, 0)

    def test_transport_accepts_exact_sha_noop_but_not_stale_sibling(self):
        self.seed(AttemptState.ARMED)
        self.first.record_invocation(REQUEST_ID)
        sha, _ = self.first._read(REQUEST_ID)
        response = self.first._api('PATCH', f'repos/sample/repo/git/{self.ref}',
                                   {'sha': sha, 'force': False})
        self.assertEqual(response.returncode, 0)
        self.assertEqual(self.transport.noops, 1)
        with self.assertRaisesRegex(StateTransitionError, 'INVOCATION_NOT_PERMITTED'):
            self.second.record_invocation(REQUEST_ID)

    def test_success_response_without_observed_update_does_not_reserve(self):
        self.seed(AttemptState.ARMED)
        self.transport.ignore_update = True
        with self.assertRaisesRegex(StateTransitionError, 'STATE_COMPARE_AND_SWAP_NOT_OBSERVED'):
            self.first.record_invocation(REQUEST_ID)
        self.assertEqual(self.first.get(REQUEST_ID).invocation_count, 0)

    def test_valid_update_is_verified_even_when_response_body_is_empty(self):
        self.seed(AttemptState.ARMED)
        self.transport.malformed_update = True
        self.assertEqual(self.first.record_invocation(REQUEST_ID).invocation_count, 1)

    def test_sequential_transitions_preserve_logical_record_and_old_bytes(self):
        self.seed(AttemptState.REQUESTED)
        historical = self.transport.git('show', self.parent + ':.review-broker/attempt.json')
        self.assertNotIn('input_capacity', json.loads(historical))
        self.first.transition(REQUEST_ID, AttemptState.ADMITTED, ['admission'])
        self.first.transition(REQUEST_ID, AttemptState.PREPARED, ['packet'])
        self.first.transition(REQUEST_ID, AttemptState.ARMED, ['packet'])
        updated = self.first.record_invocation(REQUEST_ID)
        self.assertEqual(updated.invocation_count, 1)
        self.assertEqual(len(set(self.transport.proposals)), 4)
        self.assertNotIn('transaction_nonce', updated.as_dict())
        self.assertEqual(self.transport.git('show', self.parent + ':.review-broker/attempt.json'), historical)
        self.assertEqual(type(updated).from_dict(json.loads(historical)), self.original)

    def test_each_identical_proposal_uses_a_fresh_commit_nonce(self):
        self.seed(AttemptState.ARMED)
        updated = replace(self.original, invocation_count=1)
        first = self.first._state_commit(self.parent, updated)
        second = self.second._state_commit(self.parent, updated)
        self.assertNotEqual(first, second)
        self.assertEqual(self.transport.git('show', first + ':.review-broker/attempt.json'),
                         self.transport.git('show', second + ':.review-broker/attempt.json'))
        self.assertNotEqual(self.transport.git('show', '-s', '--format=%B', first),
                            self.transport.git('show', '-s', '--format=%B', second))
