"""Actual Git reservation to synthetic workload JWT to remote gate, without live services."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from review_broker.arm_authority_contract import ArmAuthorityError
from review_broker.arm_controller import arm_and_authorize
from review_broker.arm_execution import authorize_execution
from review_broker.github_journal import GitHubRefJournal
from review_broker.queue import AttemptState, StateTransitionError
from tests import arm_authority_fixture as auth
from tests import test_capacity_boundaries as fixtures
from tests.journal_git_transport import JournalGitTransport
from tests.test_input_capacity import REQUEST, ATTEMPT, BROKER


class ArmControllerTests(unittest.TestCase):
    def setUp(self):
        factory = fixtures.CapacityBoundaryTests()
        factory.setUp()
        self.addCleanup(factory.doCleanups)
        self.packet, self.manifest, memory, _, self.arguments = factory.invocation_fixture()
        self.bundle, self.trust = auth.authorization(self.packet, self.manifest, ATTEMPT)
        self.transport = JournalGitTransport(self.packet.parent/'journal.git')
        self.journal = GitHubRefJournal('sample/broker', runner=self.transport)
        self.transport.seed(memory.get(REQUEST), self.journal._claim_ref(REQUEST))
        self.environment = dict(GITHUB_REPOSITORY='sample/broker', GITHUB_REPOSITORY_ID='1',
            GITHUB_SHA=BROKER, GITHUB_ACTIONS='true', GITHUB_REF='refs/heads/dev',
            GITHUB_WORKFLOW_REF=self.trust['workflow_ref'], GITHUB_WORKFLOW_SHA=BROKER,
            GITHUB_RUN_ID='10', GITHUB_RUN_ATTEMPT='1')
        self.output = self.packet.parent/'private-authorization.json'

    def run_controller(self):
        return arm_and_authorize(journal=self.journal, packet_directory=self.packet,
            request_id=REQUEST, packet_id=self.manifest['packet_id'], codespace_name='fixture-space',
            codespace_id='2', authorization_file=self.output, environment=self.environment)

    def test_real_reservation_precedes_issuer_and_authorizes_one_remote_consumption(self):
        observed = []
        def issuer(audience, environment):
            sha, record = self.journal.get_snapshot(REQUEST)
            self.assertEqual((record.state, record.invocation_count), (AttemptState.ARMED, 1))
            self.assertEqual(record.input_capacity['packet_id'], self.manifest['packet_id'])
            observed.append(sha)
            return auth.sign(self.bundle['envelope'], {'aud': audience})
        with patch('review_broker.arm_controller.actions_token', side_effect=issuer):
            receipt = self.run_controller()
        self.assertEqual(observed, [receipt['journal_commit_sha']])
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        value = json.loads(self.output.read_bytes())
        self.assertEqual(value['envelope']['journal_commit_sha'], observed[0])
        with auth.trusted_fixture(self.trust):
            authorize_execution(self.output.read_bytes(), directory=self.packet,
                packet_id=self.manifest['packet_id'], attempt_id=ATTEMPT, request_id=REQUEST,
                input_bytes=(self.packet/'input.txt').read_bytes(),
                reviewer_home=self.packet.parent/'home', trusted_workspace=self.arguments['trusted_workspace'])
        self.assertEqual(len(list(Path(self.trust['consumption_directory']).iterdir())), 1)

    def test_losing_reservation_never_requests_oidc(self):
        with patch.object(self.journal, 'record_invocation', side_effect=StateTransitionError('CAS_LOST')), \
             patch('review_broker.arm_controller.actions_token') as issuer:
            with self.assertRaises(StateTransitionError):
                self.run_controller()
        issuer.assert_not_called()
        self.assertEqual(self.journal.get(REQUEST).invocation_count, 0)

    def test_consumed_or_other_run_cannot_mint_by_merely_reading_reservation(self):
        with patch('review_broker.arm_controller.actions_token', return_value='synthetic.token'):
            self.run_controller()
        self.output = self.output.with_name('another-run.json')
        self.environment['GITHUB_RUN_ID'] = '11'
        with patch('review_broker.arm_controller.actions_token') as issuer, self.assertRaises(ValueError):
            self.run_controller()
        issuer.assert_not_called()
        self.assertEqual(self.journal.get(REQUEST).invocation_count, 1)

    def test_oidc_failure_preserves_consumed_attempt_without_reset(self):
        with patch('review_broker.arm_controller.actions_token', side_effect=ArmAuthorityError('UNAVAILABLE')):
            with self.assertRaises(ArmAuthorityError):
                self.run_controller()
        record = self.journal.get(REQUEST)
        self.assertEqual((record.state, record.invocation_count), (AttemptState.ARMED, 1))
        self.assertEqual(self.output.read_bytes(), b'')
