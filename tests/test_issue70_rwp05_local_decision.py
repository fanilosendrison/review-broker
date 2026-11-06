"""Both final paths reach the same real original-ticket mutex, in both winning orders."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.pre_model_active_decision_v3 import ActivePreModelDecisionV3,PreModelDecisionStateV3
from review_broker.pre_model_failure_boundaries_v3 import PreModelFailureCollectorV3
from review_broker.pre_model_failure_continuation_v3 import PreModelFailureContinuationV3
from review_broker.pre_model_remote_retention_v3 import RemoteRetainedPacketAuthorityV3
from tests.issue70_rwp05_remote_support import RemoteFailureScenario


class LocalDecisionRaceTests(unittest.TestCase):
    def test_F06_F10_final_failure_and_prepared_choices_both_orders_after_resolved_unknown_upload(self):
        for winner in ('BLOCKED','PREPARED'):
            with tempfile.TemporaryDirectory() as temporary:
                s=RemoteFailureScenario(Path(temporary));s.service.lost_upload_response=True
                prepared_ready,blocked_ready,release_blocked,failure_done=Event(),Event(),Event(),Event()
                collectors=[];futures=[];attempted=[]
                original_bind=PreModelFailureCollectorV3.bind_artifact_adapter
                original_init=RemoteRetainedPacketAuthorityV3.__init__
                original_choose=ActivePreModelDecisionV3.choose
                def bind(c,adapter):
                    clone=original_bind(c,adapter);collectors.append((c,clone));return clone
                def choose(ticket,owner,choice,operation,identity):
                    attempted.append(choice)
                    if winner=='BLOCKED' and choice=='PREPARED':
                        prepared_ready.set();self.assertTrue(failure_done.wait(30))
                    if winner=='PREPARED' and choice=='BLOCKED':
                        blocked_ready.set();self.assertTrue(release_blocked.wait(30))
                    return original_choose(ticket,owner,choice,operation,identity)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    def constructed(authority,*args,**kwargs):
                        original_init(authority,*args,**kwargs)
                        collector,adapter=collectors[0]
                        # Actual RWP-04 metadata/bytes/inventory/packet succeeded
                        # before this constructor. A subsequent real bound metadata
                        # read now gets 503. No fake verifier output is introduced.
                        s.service.metadata_failure=503
                        worker=s.real.worker.context.runtime.run_id
                        from review_broker.remote_prepared_receipt_v3 import prepared_artifact_name_v3
                        name=prepared_artifact_name_v3(s.authority.snapshot.claim_ref,worker,1)
                        suffix='/actions/runs/'+str(worker)+'/artifacts?name='+name+'&per_page=100&page=1'
                        response=adapter.metadata.get(suffix,collector.guard)
                        self.assertEqual(response.status,503)
                        def fail():
                            if winner=='BLOCKED':self.assertTrue(prepared_ready.wait(30))
                            try:return PreModelFailureContinuationV3(collector).run()
                            finally:failure_done.set()
                        futures.append(pool.submit(fail))
                        if winner=='PREPARED':self.assertTrue(blocked_ready.wait(30))
                    try:
                        with patch.object(PreModelFailureCollectorV3,'bind_artifact_adapter',bind),\
                             patch.object(RemoteRetainedPacketAuthorityV3,'__init__',constructed),\
                             patch.object(ActivePreModelDecisionV3,'choose',choose):
                            prepared=s.run_remote()
                    finally:release_blocked.set()
                    failed=futures[0].result(timeout=30)
                with self.subTest(winner=winner):
                    self.assertCountEqual(attempted,['BLOCKED','PREPARED'])
                    self.assertEqual(len(s.service.uploads),1)
                    self.assertEqual(len(s.archive.puts),1)
                    self.assertEqual(s.failure_cas_count(),1 if winner=='BLOCKED' else 0)
                    self.assertEqual(s.real.worker.transport.events.count('PREPARED'),1 if winner=='PREPARED' else 0)
                    self.assertIs(s.producer._decision.state,PreModelDecisionStateV3('CONSUMED_FOR_'+winner))
                    self.assertEqual(failed.status.value,'COMMITTED' if winner=='BLOCKED' else 'UNRESOLVED')
                    self.assertEqual(prepared.status.value,'COMMITTED' if winner=='PREPARED' else 'UNRESOLVED')
                    if winner=='BLOCKED':
                        receipt=s.current().record.attempt.history[-1]['pre_model']['receipt']
                        self.assertEqual(receipt['reason_code'],'ARTIFACT_READ_UNAVAILABLE')
                    before=(s.failure_cas_count(),s.real.worker.transport.events.count('PREPARED'))
                    s.run_remote()
                    self.assertEqual((s.failure_cas_count(),s.real.worker.transport.events.count('PREPARED')),before)
