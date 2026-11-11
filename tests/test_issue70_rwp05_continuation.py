"""Original recognized reference failures through real ADMITTED and BLOCKED CAS."""
import copy
from pathlib import Path
import tempfile
import unittest

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import decode_journal_v2, encode_journal_v2
from review_broker.pre_model_active_decision_v3 import ActivePreModelDecisionV3, PreModelDecisionStateV3
from review_broker.pre_model_failure_continuation_v3 import PreModelFailureResultV3
from review_broker.pre_model_failure_evidence_v3 import FailureObservationBindingV3, FailureEvidenceRejectedV3
from review_broker.pre_model_failure_observation_v3 import FailureObservationV3
from tests.issue70_rwp05_test_support import FailureScenario


class OriginalFailureContinuationTests(unittest.TestCase):
    def scenario(self, **kwargs):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return FailureScenario(Path(temporary.name),**kwargs)

    def blocked(self, scenario, classification, reason):
        result=scenario.run_packet()
        self.assertIs(type(result),PreModelFailureResultV3,result)
        self.assertEqual((result.status.value,result.state,result.disposition,result.observation_status),
                         ('COMMITTED','ADMITTED','BLOCKED','VERIFIED'),result)
        self.assertEqual(scenario.failure_cas_count(),1)
        self.assertEqual(len(scenario.failure_proposals()),1)
        self.assertEqual(len(scenario.archive.puts),1)
        a=scenario.authority.snapshot;b=scenario.current()
        self.assertEqual(b.parent_sha,a.commit_sha)
        self.assertEqual(b.record.attempt.history[:-1],a.record.attempt.history)
        self.assertEqual(b.record.control.worker,a.record.control.worker)
        self.assertEqual(b.record.attempt.invocation_count,0)
        receipt=b.record.attempt.history[-1]['pre_model']['receipt']
        self.assertEqual((receipt['classification'],receipt['reason_code']),(classification,reason))
        self.assertEqual(receipt['observed_at'],'2026-11-06T07:00:00Z')
        self.assertEqual(result.failure_receipt_id,artifact_identity(canonical_bytes(receipt)+b'\n'))
        self.assertEqual(encode_journal_v2(decode_journal_v2(b.journal_bytes)),b.journal_bytes)
        self.assertFalse((scenario.worker_root/'candidate').exists())
        self.assertFalse((scenario.worker_root/'retained').exists())
        self.assertIs(scenario.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
        with self.assertRaises(ValueError):scenario.producer.claim_remote_continuation(scenario.real.worker.context,result)
        self.assertEqual(scenario.producer.run(scenario.real.worker.context).reason,'OBSERVER_ONLY_NO_RETRY')
        self.assertEqual(scenario.failure_cas_count(),1)
        return result

    def test_F07_recognized_reference_503_transient(self):
        self.blocked(self.scenario(),'TRANSIENT','SOURCE_API_UNAVAILABLE')

    def test_F08_recognized_comment_404_is_unknown_not_absence(self):
        self.blocked(self.scenario(status=404,reference='decision'),'UNKNOWN','SOURCE_ACCESS_AMBIGUOUS')

    def test_F04_lost_retention_ack_exact_readback_no_second_put(self):
        s=self.scenario();s.archive.lose_ack=True
        self.blocked(s,'TRANSIENT','SOURCE_API_UNAVAILABLE')
        self.assertEqual(len(s.archive.puts),1)

    def test_F04_no_retained_original_no_failure_git_proposal(self):
        for mode in ('drop_put','corrupt','unavailable'):
            s=self.scenario();setattr(s.archive,mode,True)
            result=s.run_packet()
            with self.subTest(mode=mode):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.current().record.control.disposition,'RESERVED')
                self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CLOSED)

    def test_F02_F03_status_or_wrong_actual_target_without_recognition_is_not_authority(self):
        for mode in ('unrecognized','wrong-target','outside-catalog'):
            s=self.scenario()
            if mode=='unrecognized':s.authority.recognized=False
            elif mode=='wrong-target':s.target_override='https://api.github.com/repos/other/repository/issues/43'
            else:s.reference_status=500
            result=s.run_packet()
            with self.subTest(mode=mode):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.archive.puts,[])
                self.assertTrue(s.source_requests)

    def test_F05_unattributed_applied_admission_emits_no_ticket(self):
        s=self.scenario();s.real.worker.transport.lose_update_acknowledgment=True
        result=s.run_packet()
        self.assertEqual(result.status.value,'UNRESOLVED')
        self.assertIsNone(s.producer._decision)
        self.assertEqual(s.real.capture_calls,0)
        self.assertEqual(s.archive.puts,[])
        self.assertEqual(s.failure_cas_count(),0)

    def test_F06_direct_copy_subclass_and_forged_ticket_refuse(self):
        with self.assertRaises(ValueError):ActivePreModelDecisionV3()
        with self.assertRaises(TypeError):
            class ForgedSubclass(ActivePreModelDecisionV3):pass
        fake=object.__new__(ActivePreModelDecisionV3)
        with self.assertRaises(ValueError):fake.require_active(object())
        s=self.scenario();self.blocked(s,'TRANSIENT','SOURCE_API_UNAVAILABLE')
        with self.assertRaises(ValueError):copy.copy(s.producer._decision)
        with self.assertRaises(ValueError):copy.deepcopy(s.producer._decision)
        with self.assertRaises(ValueError):s.producer._decision.choose(s.producer,'PREPARED',object(),'fake')
        self.assertEqual(s.failure_cas_count(),1)

    def test_F06_two_original_handlers_share_one_retention_and_journal_entry(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch
        from review_broker.pre_model_failure_continuation_v3 import PreModelFailureContinuationV3
        s=self.scenario();entered,release=Event(),Event();results=[]
        def hold_first_put():
            if len(s.archive.puts)==1:
                entered.set()
                if not release.wait(20):raise RuntimeError('test barrier expired')
        s.archive.on_put=hold_first_put
        original=PreModelFailureContinuationV3.run
        def compete(first):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(original,first)
                try:
                    self.assertTrue(entered.wait(20))
                    second=original(PreModelFailureContinuationV3(first.collector))
                finally:release.set()
                primary=future.result(timeout=30)
            results.extend([primary,second])
            return primary if primary is not None and primary.status.value=='COMMITTED' else second
        with patch.object(PreModelFailureContinuationV3,'run',compete):result=s.run_packet()
        self.assertEqual(result.status.value,'COMMITTED',result)
        self.assertEqual(sum(r is not None and r.status.value=='COMMITTED' for r in results),1)
        self.assertEqual(len(s.archive.puts),1)
        self.assertEqual(s.failure_cas_count(),1)
        self.assertEqual(len(s.failure_proposals()),1)

    def test_F20_committed_failure_survives_immediate_original_proof_loss(self):
        s=self.scenario();s.real.worker.transport.on_failure_applied=lambda:setattr(s.archive,'unavailable',True)
        result=s.run_packet()
        self.assertEqual((result.status.value,result.disposition,result.observation_status),
                         ('COMMITTED','BLOCKED','UNAVAILABLE'),result)
        self.assertEqual(s.current().record.control.disposition,'BLOCKED')
        self.assertEqual(s.failure_cas_count(),1)

    def test_F20_historical_commitment_separate_from_original_cause_availability(self):
        from review_broker.pre_model_failure_readback_v3 import read_pre_model_failure_v3
        s=self.scenario();result=self.blocked(s,'TRANSIENT','SOURCE_API_UNAVAILABLE')
        original=s.current()
        def read():
            return read_pre_model_failure_v3(journal=s.real.worker.journal,
                request_id=s.real.worker.admission.request_id,evidence=s.evidence)
        back=read()
        self.assertEqual((back.status.value,back.failure_observation,back.receipt_id),
                         ('COMMITTED','VERIFIED',result.failure_receipt_id))
        self.assertEqual(back.observed_at,'2026-11-06T07:00:00Z')
        for mode,expected in [('unavailable','UNAVAILABLE'),('corrupt','REJECTED'),('origin','REJECTED')]:
            if mode=='origin':s.authority.recognized=False
            else:setattr(s.archive,mode,True)
            with self.subTest(mode=mode):
                back=read()
                self.assertEqual((back.status.value,back.state,back.disposition,back.failure_observation),
                                 ('COMMITTED','ADMITTED','BLOCKED',expected))
                self.assertEqual(s.current(),original)
                self.assertEqual(s.failure_cas_count(),1)
                self.assertEqual(len(s.archive.puts),1)
            s.archive.unavailable=s.archive.corrupt=False;s.authority.recognized=True

    def test_F02_put_of_well_typed_hash_does_not_create_origin(self):
        s=self.scenario();self.blocked(s,'TRANSIENT','SOURCE_API_UNAVAILABLE')
        original=s.authority.observations[-1]
        forged=FailureObservationV3.from_value({**original.value,'observed_at':'2026-11-06T07:00:01Z'})
        s.archive.put_once(forged.evidence_id,forged.canonical_bytes,before_effect=lambda:None)
        with self.assertRaises(FailureEvidenceRejectedV3):
            s.evidence.read_original(forged.evidence_id,FailureObservationBindingV3(s.authority.snapshot),lambda:None)
        self.assertEqual(s.failure_cas_count(),1)
