"""Coherently rehashed failure fields and actual executed-target provenance attacks."""
import copy
from pathlib import Path
import tempfile
import unittest

from review_broker.identity import attempt_identity
from review_broker.journal_record_v3 import preparation_dispatch_identity
from review_broker.pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3,FailureObservationBindingV3,FailureEvidenceRejectedV3
from review_broker.pre_model_failure_observation_v3 import FailureObservationV3
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario


class ForgedObservationProxy:
    def __init__(self,original,transform):self.original,self.transform=original,transform
    def observe(self,event,binding,*,before_effect):
        value=self.original.observe(event,binding,before_effect=before_effect)
        return None if value is None else FailureObservationV3.from_value(self.transform(copy.deepcopy(value.value)))
    def verify(self,*args,**kwargs):return self.original.verify(*args,**kwargs)
    def historical_binding(self,*args,**kwargs):return self.original.historical_binding(*args,**kwargs)


class FailureAuthorityTests(unittest.TestCase):
    def scenario(self,remote=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return (RemoteFailureScenario if remote else FailureScenario)(Path(temporary.name))

    def test_F03_rehashed_journal_worker_reference_and_phase_bindings_refuse_before_git(self):
        variants=[('repository','other/repository'),('repository_node_id','R_other'),
            ('admitted_commit_sha','f'*40),('attempt_id','attempt:sha256:'+'1'*64),
            ('admission_evidence_id','artifact:sha256:'+'2'*64),('reservation_id','preparation-dispatch:sha256:'+'3'*64),
            ('workflow_run_id',70002),('reference_id','contract'),('reference_id','unadmitted'),
            ('observed_at','2026-11-06T07:00:01Z'),('coherent-request',None),('coherent-phase',None)]
        for key,bad in variants:
            s=self.scenario()
            def transform(value):
                if key=='coherent-request':
                    request='request:sha256:'+'4'*64;attempt=attempt_identity(request,1)
                    value.update(request_id=request,attempt_id=attempt,
                        claim_ref='refs/heads/review-claims-v3/'+'4'*64,
                        reservation_id=preparation_dispatch_identity(request,attempt,1,request))
                elif key=='coherent-phase':
                    value.update(phase='SOURCE_ACQUISITION',operation='GIT_FETCH',reference_id=None,
                                 fact={'kind':'TRANSFER_TIMEOUT','process_terminated':True})
                else:value[key]=bad
                return value
            s.producer.failure_evidence=PreModelFailureEvidenceV3(ForgedObservationProxy(s.authority,transform),s.archive,16_000)
            result=s.run_packet()
            with self.subTest(key=key,bad=bad):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.archive.puts,[])

    def test_F03_remote_original_packet_artifact_plan_and_id_falsifications(self):
        for key,bad in [('packet_id','packet:sha256:'+'1'*64),('artifact_name','rb-v3-prepared-'+'1'*64+'-70001-1'),
                        ('artifact_id','992')]:
            s=self.scenario(remote=True);s.service.metadata_failure=503;s.service.metadata_failure_path='/artifacts/991/zip'
            proxy=ForgedObservationProxy(s.authority,lambda value:{**value,key:bad})
            s.remote.failure_evidence=PreModelFailureEvidenceV3(proxy,s.archive,16_000)
            result=s.run_remote()
            with self.subTest(key=key):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.archive.puts,[])
                self.assertEqual(len(s.service.uploads),1)
                self.assertEqual(s.real.worker.transport.events.count('PREPARED'),0)

    def test_F02_F03_actual_origin_query_and_authenticated_principal_are_checked(self):
        for mode in ('origin','query','credential'):
            s=self.scenario()
            if mode=='origin':s.target_override='https://other.invalid/repos/fanilosendrison/review-broker/issues/43'
            elif mode=='query':s.target_override='https://api.github.com/repos/fanilosendrison/review-broker/issues/43?unapproved=true'
            else:
                reader=s.real.inputs.issue_readers['requirement'];original=reader._executor
                def execute(request):
                    if request.full_url.endswith('/issues/43'):request.remove_header('Authorization')
                    return original(request)
                reader._executor=execute
            result=s.run_packet()
            with self.subTest(mode=mode):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.archive.puts,[])

    def test_F03_F06_final_receipt_rehash_cannot_change_recognized_cause_or_reuse_choice(self):
        from unittest.mock import patch
        from review_broker.github_journal_v3 import GitHubJournalV3
        from review_broker.identity import artifact_identity,canonical_bytes
        from review_broker.pre_model_active_decision_v3 import PreModelDecisionStateV3
        original=GitHubJournalV3.block_pre_model
        for variant in ('time','reason'):
            s=self.scenario();authorities=[]
            def mutate(journal,current,identity,receipt,reservation,generation,worker,authority):
                changed=dict(receipt)
                if variant=='time':changed['observed_at']='2026-11-06T07:00:01Z'
                else:changed.update(classification='UNKNOWN',reason_code='SOURCE_ACCESS_AMBIGUOUS')
                authorities.append(authority)
                return original(journal,current,artifact_identity(canonical_bytes(changed)+b'\n'),changed,
                                reservation,generation,worker,authority)
            with patch.object(GitHubJournalV3,'block_pre_model',mutate):result=s.run_packet()
            with self.subTest(variant=variant):
                self.assertEqual(result.status.value,'UNRESOLVED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(len(s.archive.puts),1)
                self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
                with self.assertRaises(ValueError):authorities[0].claim_entry()
                self.assertEqual(s.failure_proposals(),[])

    def test_RWP04_original_packet_substitution_remains_refused_with_failure_support(self):
        from tests.issue70_rwp05_reconstruction_support import mutate_coherently
        s=self.scenario(remote=True)
        mutate_coherently(s.handoff.retained_root,s.verification)
        result=s.run_remote()
        self.assertEqual(result.status.value,'REJECTED')
        self.assertEqual(s.service.uploads,[])
        self.assertEqual(s.failure_proposals(),[])
        self.assertEqual(s.archive.puts,[])

    def test_F03_invalid_observation_address_is_refused_before_external_read(self):
        s=self.scenario();s.run_packet()
        before=len(s.archive.reads)
        for bad in ('artifact:sha256:../../outside','../outside','artifact:sha256:'+'F'*64,True):
            with self.subTest(bad=bad),self.assertRaises(FailureEvidenceRejectedV3):
                s.evidence.read_original(bad,FailureObservationBindingV3(s.authority.snapshot),lambda:None)
        self.assertEqual(len(s.archive.reads),before)
        self.assertEqual(s.failure_cas_count(),1)
