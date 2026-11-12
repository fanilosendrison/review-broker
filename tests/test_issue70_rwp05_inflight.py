"""An attributable competing refusal fences the NEXT real effect, not an already launched read."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import review_broker.github_subject_capture_v3 as capture_module
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_conflict_support import commit_foreign_permanent


class InflightFailureFenceTests(unittest.TestCase):
    def scenario(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return FailureScenario(Path(temporary.name),status=200)

    def check_fenced(self,s,result,winners):
        self.assertEqual([r.status.value for r in winners],['COMMITTED'])
        self.assertNotEqual(result.status.value,'COMMITTED')
        self.assertEqual(s.current().record.control.disposition,'REFUSED_PERMANENT')
        self.assertEqual(s.failure_cas_count(),1)  # The foreign existing writer only.
        self.assertEqual(s.archive.puts,[])
        self.assertEqual(s.real.worker.transport.events.count('PREPARED'),0)
        self.assertIsNone(s.producer._remote_handoff)

    def test_F14_acquisition_process_started_before_failure_can_finish_without_next_launch(self):
        s=self.scenario();original=capture_module._popen;winners=[];started=[];finished=[]
        class InflightProcess:
            def __init__(self,delegate):self.delegate=delegate
            def __getattr__(self,name):return getattr(self.delegate,name)
            def communicate(self,*args,**kwargs):
                winners.append(commit_foreign_permanent(s))
                result=self.delegate.communicate(*args,**kwargs);finished.append(True);return result
        def launch(*args,**kwargs):
            started.append(args[0]);return InflightProcess(original(*args,**kwargs))
        with patch.object(capture_module,'_popen',launch):result=s.run_packet()
        self.check_fenced(s,result,winners)
        self.assertEqual(len(started),1)
        self.assertEqual(finished,[True])

    def test_F14_reference_response_can_return_but_following_transport_is_fenced(self):
        s=self.scenario();reader=s.real.inputs.issue_readers['requirement'];original=reader._executor
        winners=[];issue_reads=[]
        def execute(request):
            response=original(request)
            if request.full_url.endswith('/issues/43'):
                issue_reads.append(request.full_url);winners.append(commit_foreign_permanent(s))
            return response
        reader._executor=execute
        result=s.run_packet();self.check_fenced(s,result,winners)
        self.assertEqual(len(issue_reads),1)
        self.assertFalse((s.worker_root/'candidate').exists())

    def test_F14_first_persistence_write_finishes_then_next_write_and_publication_are_fenced(self):
        s=self.scenario();original_open,original_sync=os.open,os.fsync
        descriptors={};winners=[];writes=[]
        def open_file(path,*args,**kwargs):
            fd=original_open(path,*args,**kwargs)
            descriptors[fd]=Path(os.fsdecode(path)).name
            return fd
        def sync(fd):
            original_sync(fd)
            if descriptors.get(fd)=='expected-policy.bin' and not winners:
                writes.append('expected-policy.bin');winners.append(commit_foreign_permanent(s))
        with patch('os.open',open_file),patch('os.fsync',sync):result=s.run_packet()
        self.check_fenced(s,result,winners)
        self.assertEqual(writes,['expected-policy.bin'])
        self.assertFalse((s.worker_root/'retained'/s.current().claim_ref.rsplit('/',1)[-1]).exists())
