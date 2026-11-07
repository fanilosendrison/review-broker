"""Concrete dispatch requires the actual complete source phase and original Controller CAS."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from review_broker.github_actions_controller_authority_v3 import GitHubActionsControllerAuthorityV3,GATES
from review_broker.github_actions_initial_dispatch_v3 import GitHubActionsInitialDispatchTransportV3
from review_broker.github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
from review_broker.github_live_runtime_v3 import REPOSITORY,WORKER_PATH
from review_broker.identity import canonical_bytes
from review_broker.pre_model_dispatch_ack_v3 import acknowledgment_from_record
from review_broker.request_v3 import request_identity_v3
from tests.live_prep_actions_support import PRINCIPAL
from tests.live_prep_provider_support import LiveProviderService,controller_scenario


class DispatchAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve();self.service=LiveProviderService(self.root)
        self.identifier=request_identity_v3(self.service.request)
        self.runtime=self.service.runtime('controller',{'request_issue_number':51,'request_id':self.identifier})
        self.authority=GitHubActionsControllerAuthorityV3(self.runtime,issue=51,request_id=self.identifier,
            gates=self.service.gates(self.identifier))

    def run_controller(self):
        result=controller_scenario(self.root,self.service)
        self.service.controller_running=False
        if result.status.value!='DISPATCH_ACKNOWLEDGED':
            self.service.run_overrides['controller']={'conclusion':'failure'}
        return result

    def acknowledgment(self,result):
        receipt=acknowledgment_from_record(result.acknowledgment_outcome.snapshot.record)
        runtime=self.service.runtime('worker',{'request_id':self.identifier,
            'reservation_id':receipt.reservation_id,'generation':1})
        return receipt,GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api,runtime.expected)

    def test_D01_D02_D10_D11_D12_exact_dispatch_and_cold_observation(self):
        result=self.run_controller();self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
        receipt,ack=self.acknowledgment(result)
        calls=[c for c in self.service.calls if c[0]=='POST']
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads(calls[0][2]),{'ref':'qualification-branch','inputs':{
            'request_id':self.identifier,'reservation_id':receipt.reservation_id,'generation':1},'return_run_details':True})
        self.assertEqual(ack.principal_id(receipt),PRINCIPAL)
        self.assertNotEqual(PRINCIPAL,30498238)
        self.assertFalse(ack.authenticates(receipt,dispatch_principal_id=30498238))
        cold=GitHubActionsDispatchAcknowledgmentAuthorityV3(ack.api,ack.expected)
        self.assertEqual(cold.principal_id(receipt),PRINCIPAL)
        # Valid fields, token and even the real old reservation do not recreate this
        # Controller operation's consumed dispatch opportunity.
        bare=GitHubActionsInitialDispatchTransportV3(self.authority)
        before=len(calls)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_CONTROLLER_DISPATCH_OPPORTUNITY_REQUIRED'):
            bare.dispatch(result.dispatch_request)
        self.assertEqual(len([c for c in self.service.calls if c[0]=='POST']),before)
        admission=result.claim_outcome.snapshot.record.attempt.admission
        with self.assertRaises((ValueError,RuntimeError)):
            self.authority.require_current()
        self.service.controller_running=True
        self.assertIsNone(self.authority.authorize(broker_repository=REPOSITORY,
            broker_repository_node_id=self.service.node_id,target=self.authority.target,
            journal_admission_bytes=canonical_bytes(admission),origin_body_bytes=self.service.body.encode()))

    def test_D02_D03_D04_D05_bad_or_lost_response_never_retries(self):
        for fault in ('204','malformed','url','loss'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary).resolve();s=LiveProviderService(root)
                s.dispatch_status=204 if fault=='204' else 200;s.dispatch_loss=fault=='loss'
                s.dispatch_result={} if fault=='malformed' else ({'workflow_run_id':70001,
                    'run_url':'https://wrong.invalid','html_url':f'https://github.com/{REPOSITORY}/actions/runs/70001'} if fault=='url' else None)
                result=controller_scenario(root,s)
                self.assertEqual(result.status.value,'DISPATCH_UNRESOLVED',result)
                self.assertEqual(len([c for c in s.calls if c[0]=='POST']),1)
                self.assertIsNone(result.acknowledgment_outcome)

    def test_D06_D07_D08_D09_D13_run_forgery_cannot_reuse_receipt_hash(self):
        receipt,ack=self.acknowledgment(self.run_controller())
        changes=({'repository':{'id':123,'full_name':REPOSITORY}},{'workflow_id':12},
            {'path':'.github/workflows/other.yml'},{'name':'other'},{'head_sha':'f'*40},
            {'head_branch':'other'},{'run_attempt':2},{'event':'push'})
        for change in changes:
            self.service.run_overrides['worker']=change
            with self.assertRaises((ValueError,RuntimeError)):ack.principal_id(receipt)
        self.service.run_overrides.clear()
        self.assertEqual(ack.principal_id(receipt),PRINCIPAL)
        with self.assertRaises(ValueError):
            ack.principal_id(replace(receipt,dispatch_response_evidence_id='artifact:sha256:'+'9'*64))

    def test_C01_C05_owner_gate_bindings_refuse_before_mutation(self):
        for key in GATES:
            gates=self.service.gates(self.identifier);gates[key]=''
            with self.assertRaises(ValueError):GitHubActionsControllerAuthorityV3(self.runtime,
                issue=51,request_id=self.identifier,gates=gates)
        for key in GATES[:3]:
            gates=self.service.gates(self.identifier);gates[key]='99'
            with self.assertRaises(ValueError):GitHubActionsControllerAuthorityV3(self.runtime,
                issue=51,request_id=self.identifier,gates=gates)
        self.service.body+='changed'
        with self.assertRaises(ValueError):self.authority.require_current()
        self.assertEqual(self.service.git.mutation_calls,0)

    def test_C06_C07_actor_or_job_mismatch_refuses(self):
        for override in ({'actor':{'id':123,'login':'owner'}},{'triggering_actor':{'id':123,'login':'owner'}},
                         {'path':WORKER_PATH},{'head_sha':'f'*40}):
            self.service.run_overrides['controller']=override
            with self.assertRaises((ValueError,RuntimeError)):self.authority.require_current()
        self.service.run_overrides.clear();self.service.job_overrides['controller']={'name':'other'}
        with self.assertRaises((ValueError,RuntimeError)):self.authority.require_current()
        self.assertEqual(self.service.git.mutation_calls,0)
