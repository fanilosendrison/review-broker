"""UNKNOWN reaches real controller, reconciler and manual CLI boundaries."""
from contextlib import redirect_stderr
import io
from unittest.mock import Mock, patch
import unittest

from review_broker.cli import main
from review_broker.github_journal import GitHubRefJournal
from review_broker.github_journal_http import JournalReadUnknown
from review_broker.reconciliation import reconcile_repository
from tests import test_arm_controller as arm_fixture
from tests import test_orchestration as reconciliation_fixture
from tests.journal_http_response import http_response


class UnknownAuthorityTests(unittest.TestCase):
    def test_every_pre_mint_controller_read_unknown_blocks_oidc_and_model_authority(self):
        for read_number in range(1, 9):
            with self.subTest(read_number=read_number):
                fixture = arm_fixture.ArmControllerTests()
                fixture.setUp()
                try:
                    original = fixture.transport
                    count = 0
                    after_unknown = []
                    failed = False
                    def runner(command, **kwargs):
                        nonlocal count, failed
                        if failed:
                            after_unknown.append(command)
                        if command[3] == 'GET' and '/git/refs/heads/' in command[4]:
                            count += 1
                            if count == read_number:
                                failed = True
                                return http_response(command, {}, 503)
                        return original(command, **kwargs)
                    fixture.journal.runner = runner
                    before = fixture.transport.git('for-each-ref', '--format=%(refname) %(objectname)')
                    with patch('review_broker.arm_controller.actions_token') as mint:
                        with self.assertRaises(JournalReadUnknown):
                            fixture.run_controller()
                        mint.assert_not_called()
                    self.assertTrue(failed, 'Intended real journal observation must be reached')
                    self.assertEqual(after_unknown, [], 'No fallback reads or writes after UNKNOWN')
                    self.assertEqual(fixture.output.read_bytes(), b'')
                    if read_number <= 2:
                        self.assertEqual(fixture.transport.git('for-each-ref', '--format=%(refname) %(objectname)'), before)
                    # Read back through the genuine transport, not the injected fault.
                    fixture.journal.runner = original
                    observed = fixture.journal.get(arm_fixture.REQUEST)
                    if read_number >= 7:
                        self.assertEqual(observed.invocation_count, 1, 'Consumed ARM must survive failure')
                finally:
                    fixture.doCleanups()

    def test_reconciler_unknown_never_dispatches_or_controls_codespace(self):
        fixture = reconciliation_fixture.ReconciliationTests()
        fixture.setUp()
        journal = GitHubRefJournal('sample/repo', runner=lambda command, **kwargs: http_response(command, {}, 503))
        for issues, refs in (([fixture.issue()], []), ([], [{'ref': 'refs/heads/review-claims/' + 'a' * 64}])):
            with self.subTest(issue_path=bool(issues)):
                controller, dispatch = Mock(), Mock()
                with self.assertRaises(JournalReadUnknown):
                    reconcile_repository('sample/repo', 'synthetic', environment=fixture.environment,
                        get_json=fixture.getter(issues, refs), journal=journal,
                        controller=controller, dispatch=dispatch)
                dispatch.assert_not_called()
                self.assertEqual(controller.mock_calls, [])

    def test_manual_cli_reports_sanitized_nonpassing_unknown_without_fallback(self):
        journal = GitHubRefJournal('sample/repo', runner=lambda command, **kwargs: http_response(command, {}, 503))
        errors = io.StringIO()
        with patch('review_broker.cli.GitHubRefJournal', return_value=journal), redirect_stderr(errors):
            code = main(['--broker-repo', 'sample/repo', 'internal-transition',
                         '--request', 'request:sha256:' + 'a' * 64,
                         '--state', 'ADMITTED', '--evidence', 'synthetic'])
        self.assertEqual(code, 1)
        self.assertIn('JournalReadUnknown', errors.getvalue())
        self.assertIn('JOURNAL_REF_READ_UNKNOWN', errors.getvalue())
