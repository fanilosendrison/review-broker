"""Independent finite provider-count gates over the complete production-form composition."""
from pathlib import Path
import tempfile
import unittest

from tests.worker_observation_measurement_support import measure_complete


class WorkerReadAmplificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.report, cls.service, _, cls.result = measure_complete(Path(cls.directory.name).resolve())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_R1_local_retention_does_not_reauthenticate_per_file_operation(self):
        count = self.report['phases'].get('LOCAL_RETENTION', {}).get('full_current_auth', 0)
        self.assertLessEqual(count, 10, self.report)

    def test_R2_local_packet_verification_has_bounded_Actions_reads(self):
        counts = self.report['phases'].get('PACKET_VERIFY', {})
        self.assertLessEqual(counts.get('actions_runs', 0), 10, counts)
        self.assertLessEqual(counts.get('actions_jobs', 0), 10, counts)

    def test_R3_historical_local_verification_does_not_reconstruct_ACK_per_operation(self):
        counts = self.report['phases'].get('HISTORICAL_CORPUS', {})
        self.assertLessEqual(counts.get('ack_reconstruction', 0), 10, counts)

    def test_future_live_diagnostics_cover_each_required_phase(self):
        from review_broker.pre_model_observation_diagnostics_v3 import PHASES
        report = self.service.diagnostic_reports[-1]
        self.assertEqual(set(report['phase_seconds']), PHASES)
        self.assertGreater(report['counts']['TOTAL_GITHUB_READS'], 0)
        self.assertGreater(report['counts']['ACK_RECONSTRUCTION_COUNT'], 0)

    def test_R4_historical_provider_reads_fit_explicit_budget(self):
        counts = self.report['phases'].get('HISTORICAL_CORPUS', {})
        reads = sum(counts.get(k, 0) for k in ('actions_workflows', 'actions_runs',
            'actions_jobs', 'journal_ref', 'journal_immutable', 'repository_or_issue',
            'controller_reconstruction'))
        self.assertLessEqual(reads, 1000, counts)
        self.assertTrue(self.result.cold_verified)
        self.assertEqual(len(self.service.uploads), 1)
