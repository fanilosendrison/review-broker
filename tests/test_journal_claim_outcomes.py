"""Atomic creation and ambiguous acknowledgement controls over real local Git."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.github_journal_read import JournalReadKind
from review_broker.queue import AttemptState, StateTransitionError
from tests.journal_http_transport import HttpGitTransport, http_response
from tests.test_github_journal import REQUEST_ID, record


class ClaimOutcomesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.transport = HttpGitTransport(Path(self.temp.name) / 'objects.git')
        self.first = GitHubRefJournal('sample/repo', runner=self.transport)
        self.second = GitHubRefJournal('sample/repo', runner=self.transport)
        self.ref = self.first._claim_ref(REQUEST_ID)

    def test_authenticated_absence_and_successful_creation_then_idempotence(self):
        self.assertEqual(self.first._observe(REQUEST_ID).kind, JournalReadKind.ABSENT_AUTHENTICATED)
        self.assertEqual(self.transport.mutations, [])
        created = self.first.claim(REQUEST_ID)
        self.assertEqual(created.state, AttemptState.REQUESTED)
        self.assertEqual(created.invocation_count, 0)
        self.assertEqual(len(self.transport.mutations), 4)
        objects = self.transport.objects()
        refs = self.transport.refs()
        self.assertEqual(self.second.claim(REQUEST_ID), created)
        self.assertEqual(self.transport.objects(), objects)
        self.assertEqual(self.transport.refs(), refs)
        self.assertEqual(len(self.transport.mutations), 4)
        self.assertEqual(self.first._observe(REQUEST_ID).kind, JournalReadKind.PRESENT_VERIFIED)

    def test_two_absent_contenders_read_one_atomic_winner(self):
        observations = []
        original = self.transport.__call__
        first_response = True
        def runner(command, **kwargs):
            nonlocal first_response
            response = original(command, **kwargs)
            if command[3] == 'POST' and command[4].endswith('/git/commits') and first_response:
                first_response = False
                observations.append(self.second._observe(REQUEST_ID).kind)
                observations.append(self.second.claim(REQUEST_ID))
            return response
        self.first.runner = runner
        winner = self.first.claim(REQUEST_ID)
        self.assertEqual(observations[0], JournalReadKind.ABSENT_AUTHENTICATED)
        self.assertEqual(winner, observations[1])
        self.assertEqual(len(set(self.transport.proposals)), 2)
        self.assertEqual(len([c for c in self.transport.mutations if c['endpoint'].endswith('/git/refs')]), 2)
        self.assertEqual(len(self.transport.git('for-each-ref', '--format=%(refname)', 'refs/heads/review-claims/').splitlines()), 1)
        self.first.transition(REQUEST_ID, AttemptState.ADMITTED, ['admission'])
        self.first.transition(REQUEST_ID, AttemptState.PREPARED, ['packet'])
        self.first.transition(REQUEST_ID, AttemptState.ARMED, ['packet'])
        self.assertEqual(self.first.record_invocation(REQUEST_ID).invocation_count, 1)
        with self.assertRaisesRegex(StateTransitionError, 'INVOCATION_NOT_PERMITTED'):
            self.second.record_invocation(REQUEST_ID)

    def test_sent_post_with_lost_result_never_authorizes_or_retries(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                # Separate identities/repositories keep each fault independent.
                with tempfile.TemporaryDirectory() as temp:
                    t = HttpGitTransport(Path(temp) / 'post.git')
                    journal = GitHubRefJournal('sample/repo', runner=t)
                    def lost(command, kwargs):
                        if not accepted and command[3] == 'POST' and command[4].endswith('/git/refs'):
                            return subprocess.CompletedProcess(command, 1, '', 'lost')
                    if accepted:
                        t.after_create = lambda command, kwargs: subprocess.CompletedProcess(command, 1, '', 'lost')
                    else:
                        t.fault = lost
                    grant = Mock()
                    with self.assertRaises(JournalReadUnknown):
                        journal.claim(REQUEST_ID)
                        grant()
                    grant.assert_not_called()
                    self.assertEqual(len([c for c in t.mutations if c['endpoint'].endswith('/git/refs')]), 1)
                    refs = t.git('for-each-ref', '--format=%(refname)', 'refs/heads/review-claims/').splitlines()
                    self.assertEqual(len(refs), int(accepted))
                    self.assertEqual(len(t.proposals), 1)

    def test_post_acknowledged_but_readback_unknown_cannot_grant(self):
        def after_create(command, kwargs):
            def unreadable(command, kwargs):
                if command[3] == 'GET' and '/git/refs/heads/' in command[4]:
                    return http_response(command, {}, 503)
            self.transport.fault = unreadable
            payload = json.loads(kwargs['input'])
            return http_response(command, {'ref': payload['ref'], 'object': {'type': 'commit', 'sha': payload['sha']}}, 201)
        self.transport.after_create = after_create
        with self.assertRaises(JournalReadUnknown):
            self.first.claim(REQUEST_ID)
        self.assertEqual(len(self.transport.proposals), 1)
        self.assertEqual(len(self.transport.mutations), 4)
        self.assertEqual(self.transport.git('rev-parse', self.ref).decode().strip(), self.transport.proposals[0])
        raw = self.transport.git('show', self.transport.proposals[0] + ':.review-broker/attempt.json')
        self.assertEqual(json.loads(raw)['invocation_count'], 0)

    def test_contradictory_creation_acknowledgement_is_not_permission(self):
        self.transport.after_create = lambda command, kwargs: http_response(command, {'ref': self.ref, 'object': {'type': 'commit', 'sha': 'f' * 40}}, 201)
        with self.assertRaisesRegex(JournalReadUnknown, 'ATOMIC_CLAIM_OUTCOME_UNKNOWN'):
            self.first.claim(REQUEST_ID)
        self.assertEqual(len(self.transport.mutations), 4)

    def test_readback_of_different_consumed_winner_is_not_a_fresh_attempt(self):
        from dataclasses import replace
        consumed = replace(record(AttemptState.STOPPED), invocation_count=1)
        self.transport.before_create = lambda: self.transport.seed(consumed, self.ref)
        observed = self.first.claim(REQUEST_ID)
        self.assertEqual(observed.state, AttemptState.STOPPED)
        self.assertEqual(observed.invocation_count, 1)
        before = len(self.transport.mutations)
        with self.assertRaises(StateTransitionError):
            self.first.record_invocation(REQUEST_ID)
        with self.assertRaises(StateTransitionError):
            self.first.transition(REQUEST_ID, AttemptState.ARMED, ['replay'])
        self.assertEqual(len(self.transport.mutations), before)

    def test_422_with_own_commit_is_ambiguous_not_a_competing_winner(self):
        self.transport.after_create = lambda command, kwargs: http_response(command, {}, 422)
        with self.assertRaisesRegex(JournalReadUnknown, 'ATOMIC_CLAIM_OUTCOME_UNKNOWN'):
            self.first.claim(REQUEST_ID)
        self.assertEqual(len(self.transport.proposals), 1)

    def test_repository_identity_credential_and_contents_capability_are_independent(self):
        cases = [
            ('metadata-name', 'repos/sample/repo', {'id': 123, 'full_name': 'wrong/repo'}),
            ('metadata-id', 'repos/sample/repo', {'id': True, 'full_name': 'sample/repo'}),
            ('graphql-errors', 'graphql', {'data': {}, 'errors': []}),
            ('missing-viewer', 'graphql', {'data': {'repository': {}}}),
            ('partial-json', 'graphql', []),
        ]
        for label, endpoint, value in cases:
            with self.subTest(label=label):
                def fault(command, kwargs):
                    if command[4] == endpoint:
                        return http_response(command, value)
                self.transport.fault = fault
                before = self.transport.objects()
                self.assertEqual(self.first._observe(REQUEST_ID).kind, JournalReadKind.UNKNOWN)
                with self.assertRaises(JournalReadUnknown):
                    self.first.claim(REQUEST_ID)
                self.assertEqual(self.transport.objects(), before)
                self.assertEqual(self.transport.mutations, [])

    def test_creation_response_allows_non_authoritative_github_url_metadata(self):
        def ack(command, kwargs):
            payload = json.loads(kwargs['input'])
            return http_response(command, {'ref': payload['ref'], 'url': 'https://api.github.com/synthetic',
                'object': {'sha': payload['sha'], 'type': 'commit', 'url': 'https://api.github.com/synthetic'}}, 201)
        self.transport.after_create = ack
        self.assertEqual(self.first.claim(REQUEST_ID).state, AttemptState.REQUESTED)

    def test_parent_commit_response_is_validated_before_any_git_object_write(self):
        for value in ({}, {'tree': {'sha': 'short'}}, [], None):
            with self.subTest(value=value):
                def fault(command, kwargs):
                    if command[3] == 'GET' and '/git/commits/' in command[4]:
                        return http_response(command, value)
                self.transport.fault = fault
                before = self.transport.objects()
                with self.assertRaises(JournalReadUnknown):
                    self.first.claim(REQUEST_ID)
                self.assertEqual(self.transport.objects(), before)
                self.assertEqual(self.transport.mutations, [])

    def test_partial_object_ack_stops_before_the_next_mutation(self):
        for resource in ('blobs', 'trees', 'commits'):
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as temp:
                t = HttpGitTransport(Path(temp) / 'partial.git')
                journal = GitHubRefJournal('sample/repo', runner=t)
                def fault(command, kwargs):
                    if command[3] == 'POST' and command[4].endswith('/git/' + resource):
                        return http_response(command, {'sha': 'partial'}, 201)
                t.fault = fault
                with self.assertRaisesRegex(JournalReadUnknown, 'JOURNAL_OBJECT_RESPONSE_UNKNOWN'):
                    journal.claim(REQUEST_ID)
                self.assertTrue(t.mutations[-1]['endpoint'].endswith('/git/' + resource))
                self.assertFalse(any(c['endpoint'].endswith('/git/refs') for c in t.mutations))

    def test_new_claim_base_ref_failure_precedes_object_creation(self):
        def fault(command, kwargs):
            if '/git/ref/heads/' in command[4]:
                return http_response(command, {}, 403)
        self.transport.fault = fault
        with self.assertRaises(JournalReadUnknown):
            self.first.claim(REQUEST_ID)
        self.assertEqual(self.transport.mutations, [])
