"""Adversarial scheduling against original live-form authority, not replacement decisions."""
import copy
from dataclasses import replace
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_actions_identity_v3 import GitHubActionsIdentityV3Error
from review_broker.github_issue_reference_v3 import GitHubIssueReferenceV3Error
from review_broker.pre_model_policy_evidence_retention_v3 import LocalAuthorizedPacketStagesV3
from review_broker.worker_local_phase_v3 import WorkerLocalPhaseV3
from tests.live_prep_artifact_provider_support import CompleteProviderService
from tests.live_prep_provider_support import controller_scenario
from tests.test_live_prep_complete_composition import worker_scenario


class WorkerLocalPhaseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        root = Path(cls.directory.name).resolve()
        service = CompleteProviderService(root)
        controller = controller_scenario(root, service)
        service.controller_running = False
        cls.probes = {}
        original = LocalAuthorizedPacketStagesV3.verify
        tester = unittest.TestCase()

        def verify(stages, candidate, before_effect):
            phase = before_effect
            tester.assertIs(type(phase), WorkerLocalPhaseV3)
            authority = phase._authority
            snapshot = phase._snapshot
            cls.original_phase = phase
            counts = authority.reader.diagnostics.counts
            before = dict(counts)
            for _ in range(10):
                stages._inputs[3].before_effect()
            middle = dict(counts)
            for _ in range(100):
                stages._inputs[3].before_effect()
            tester.assertEqual(before, middle)
            tester.assertEqual(middle, dict(counts))
            cls.probes['scaling'] = True

            old = service.git.refs[snapshot.claim_ref]
            service.git.refs[snapshot.claim_ref] = snapshot.parent_sha
            try:
                before_source = len(service.source_calls)
                with tester.assertRaisesRegex(ValueError, 'CURRENT_WORKER_STALE_JOURNAL'):
                    phase()
                admission, _, _, verification, readers = stages._inputs
                with tester.assertRaisesRegex(GitHubIssueReferenceV3Error, 'ISSUE_REFERENCE_AUTHORITY_UNAVAILABLE'):
                    verification.prepare_references(admission, readers)
                tester.assertEqual(len(service.source_calls), before_source)
            finally:
                service.git.refs[snapshot.claim_ref] = old
            cls.probes['S1'] = True

            service.run_overrides['worker'] = {'status': 'completed', 'conclusion': 'cancelled'}
            try:
                with tester.assertRaisesRegex(GitHubActionsIdentityV3Error, 'GITHUB_ACTIONS_UNAVAILABLE'):
                    phase()
            finally:
                service.run_overrides.clear()
            cls.probes['S4'] = True

            service.job_overrides['worker'] = {'id': 999}
            try:
                with tester.assertRaisesRegex(ValueError, 'CURRENT_WORKER_RUN_JOB_UNTRUSTED'):
                    phase()
            finally:
                service.job_overrides.clear()
            cls.probes['S5'] = True

            principal = authority.principal
            authority.principal += 1
            try:
                with tester.assertRaisesRegex(ValueError, 'ORIGINAL_WORKER_PHASE_REQUIRED'):
                    phase()
            finally:
                authority.principal = principal
            cls.probes['S6'] = True

            expected = authority.expected
            authority.expected = replace(expected, executing_source_sha='0' * 40)
            try:
                with tester.assertRaisesRegex(ValueError, 'ORIGINAL_WORKER_PHASE_REQUIRED'):
                    phase()
            finally:
                authority.expected = expected
            cls.probes['S7'] = True

            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with tester.assertRaisesRegex(ValueError, 'WORKER_PHASE_(COPY|SERIALIZATION)_FORBIDDEN'):
                    operation(phase)
            forged = object.__new__(WorkerLocalPhaseV3)
            forged.__dict__.update(phase.__dict__)
            with tester.assertRaisesRegex(ValueError, 'ORIGINAL_WORKER_PHASE_REQUIRED'):
                forged()
            cls.probes['S9'] = True

            before_mutations = service.git.mutation_calls
            with tester.assertRaises(AttributeError):
                authority.journal.prepare(snapshot, 'artifact:sha256:' + '1' * 64,
                    snapshot.record.control.reservation_id, 1, snapshot.record.control.worker, phase)
            tester.assertEqual(before_mutations, service.git.mutation_calls)
            cls.probes['S11'] = True
            return original(stages, candidate, before_effect)

        with patch.object(LocalAuthorizedPacketStagesV3, 'verify', verify):
            result = worker_scenario(root, service, controller)
        tester.assertTrue(result.cold_verified, result)
        tester.assertEqual(len(service.uploads), 1)
        cls.result = result

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_local_work_10N_has_no_proportional_provider_authentication(self):
        self.assertTrue(self.probes['scaling'])

    def test_S1_stale_journal_refuses_external_source_guard(self):
        self.assertTrue(self.probes['S1'])

    def test_S4_cancelled_worker_refuses_new_effect(self):
        self.assertTrue(self.probes['S4'])

    def test_S5_wrong_job_refuses(self):
        self.assertTrue(self.probes['S5'])

    def test_S6_principal_mismatch_refuses(self):
        self.assertTrue(self.probes['S6'])

    def test_S7_executable_mismatch_refuses(self):
        self.assertTrue(self.probes['S7'])

    def test_S8_transferred_phase_is_not_active_for_next_phase(self):
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_WORKER_PHASE_REQUIRED'):
            self.original_phase()

    def test_S9_copy_serialization_and_raw_clone_refuse(self):
        self.assertTrue(self.probes['S9'])

    def test_S10_restarted_object_cannot_issue_active_scope(self):
        with self.assertRaisesRegex(ValueError, 'WORKER_PHASE_ISSUER_REQUIRED'):
            WorkerLocalPhaseV3()

    def test_S11_cached_binding_is_not_mutation_authority(self):
        self.assertTrue(self.probes['S11'])
