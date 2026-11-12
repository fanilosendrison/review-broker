"""Source-transfer catalog evidence comes from the real run/terminate boundary."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import review_broker.github_subject_capture_v3 as capture_module
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_transfer_support import TransferService


class TransferFailureTests(unittest.TestCase):
    def scenario(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return FailureScenario(Path(temporary.name),status=200)

    def test_F07_clone_and_fetch_timeouts_require_real_termination(self):
        for operation in ('GIT_CLONE','GIT_FETCH'):
            s=self.scenario();service=TransferService(s,operation=operation);self.addCleanup(service.close)
            original=capture_module.capture_authenticated_subject_v3
            def capture(*args,**kwargs):
                if operation=='GIT_CLONE':kwargs['acquire_repository']=None
                return original(*args,**kwargs)
            with patch.object(capture_module,'_popen',service),patch.object(capture_module,'capture_authenticated_subject_v3',capture):
                result=s.run_packet()
            with self.subTest(operation=operation):
                self.assertEqual((result.status.value,result.disposition),('COMMITTED','BLOCKED'),result)
                receipt=s.current().record.attempt.history[-1]['pre_model']['receipt']
                self.assertEqual(receipt['reason_code'],'SOURCE_TRANSFER_INTERRUPTED')
                self.assertEqual(receipt['classification'],'TRANSIENT')
                self.assertEqual(len(service.processes),1)
                self.assertTrue(service.processes[0].record['timed_out'])
                self.assertIsNotNone(service.processes[0].poll())
                self.assertEqual(s.failure_cas_count(),1)

    def test_F02_generic_nonzero_git_exit_is_not_transfer_evidence(self):
        s=self.scenario();service=TransferService(s,timeout=False);self.addCleanup(service.close)
        with patch.object(capture_module,'_popen',service):result=s.run_packet()
        self.assertNotEqual(result.status.value,'COMMITTED')
        self.assertEqual(s.failure_proposals(),[])
        self.assertEqual(s.archive.puts,[])
        self.assertFalse(service.processes[0].record['timed_out'])

    def test_F02_timeout_without_confirmed_termination_cannot_block(self):
        s=self.scenario();service=TransferService(s);self.addCleanup(service.close)
        with patch.object(capture_module,'_popen',service),patch.object(capture_module,'_terminate',lambda process:None):
            result=s.run_packet()
        self.assertNotEqual(result.status.value,'COMMITTED')
        self.assertIsNone(service.processes[0].poll())
        self.assertEqual(s.failure_proposals(),[])
        self.assertEqual(s.archive.puts,[])
