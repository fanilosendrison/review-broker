"""Actual Controller-produced states with provider visibility lag and bounded read-only gates."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
from review_broker.github_actions_worker_authority_v3 import WorkerInputsV3
from review_broker.live_journal_composition_v3 import live_journal_v3,GitHubOriginalAdmissionAuthorityV3
from review_broker.pre_model_ack_start_gate_v3 import wait_dispatch_ack_v3
from review_broker.request_v3 import request_identity_v3
from tests.live_prep_provider_support import LiveProviderService,controller_scenario
from tests.live_prep_actions_support import response


class AckGateTests(unittest.TestCase):
    def prepare(self,root,*,loss=False,lost_ack=False):
        service=LiveProviderService(root);service.dispatch_loss=loss;service.git.lose_ack=lost_ack
        result=controller_scenario(root,service)
        identifier=request_identity_v3(service.request)
        inputs=WorkerInputsV3(identifier,result.reservation_outcome.snapshot.record.control.reservation_id,1)
        runtime=service.runtime('worker',vars(inputs))
        journal=live_journal_v3(runtime,GitHubOriginalAdmissionAuthorityV3(runtime.api),
            write_guard=lambda:(_ for _ in ()).throw(AssertionError('read-only gate tried mutation')))
        authority=GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api,runtime.expected)
        return service,result,inputs,runtime,journal,authority

    def gate(self,state,sleeper):
        service,result,inputs,runtime,journal,authority=state
        before=service.git.mutation_calls
        value=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=inputs,
            dispatch_authority=authority,sleeper=sleeper)
        self.assertEqual(service.git.mutation_calls,before)
        self.assertEqual(service.mints,['controller'])
        self.assertEqual(len(service.acquisitions),1)
        return value

    def test_ACK01_ACK02_ACK12_waits_for_ack_and_controller_success_without_mutating(self):
        with tempfile.TemporaryDirectory() as temporary:
            state=self.prepare(Path(temporary));service,result,inputs,runtime,journal,authority=state
            original=service.git
            reservation=result.reservation_outcome.snapshot.commit_sha
            class Lagged:
                def __call__(self,req):
                    if req.method=='GET' and req.full_url.endswith('/git/ref/'+journal.claim_ref(inputs.request_id).removeprefix('refs/')) and len(sleeps)<2:
                        return response({'ref':journal.claim_ref(inputs.request_id),'object':{'type':'commit','sha':reservation}})
                    return original(req)
            sleeps=[]
            def wait(seconds):
                self.assertEqual(seconds,2);sleeps.append(seconds)
                if len(sleeps)==3:service.controller_running=False
            service.git=Lagged()
            # Keep provider accounting independent of the response-visibility wrapper.
            before=original.mutation_calls
            value=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=inputs,
                dispatch_authority=authority,sleeper=wait)
            self.assertTrue(value.accepted,value)
            self.assertEqual(sleeps,[2,2,2]);self.assertEqual(original.mutation_calls,before)
            self.assertEqual(service.mints,['controller'])

    def test_ACK03_ACK10_manual_or_unknown_dispatch_has_no_worker_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            state=self.prepare(Path(temporary),loss=True);service=state[0]
            sleeps=[];result=self.gate(state,lambda seconds:sleeps.append(seconds))
            self.assertFalse(result.accepted);self.assertEqual(len(sleeps),29)
            self.assertEqual(len([c for c in service.calls if c[0]=='POST']),1)

    def test_ACK04_ACK07_ACK08_ACK09_wrong_run_or_execution_refuses(self):
        for fault in ('run','ref','sha','origin'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                state=self.prepare(Path(temporary));service,result,inputs,runtime,journal,authority=state
                service.controller_running=False
                if fault=='run':runtime.claim=__import__('dataclasses').replace(runtime.claim,run_id=70002)
                if fault=='ref':runtime.expected=__import__('dataclasses').replace(runtime.expected,workflow_execution_ref='refs/heads/other')
                if fault=='sha':runtime.expected=__import__('dataclasses').replace(runtime.expected,executing_source_sha='f'*40)
                if fault=='origin':service.run_overrides['controller']={'actor':{'id':17,'login':'other'}}
                self.assertFalse(self.gate(state,lambda seconds:None).accepted)

    def test_manual_owner_worker_with_no_controller_or_claim_has_no_source_mint(self):
        from review_broker.github_live_runtime_v3 import GitHubActionsRuntimeBoundaryV3,ProtectedCheckoutV3
        from tests.live_prep_actions_support import environment,SHA
        from review_broker.identity import attempt_identity
        from review_broker.journal_record_v3 import preparation_dispatch_identity
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            identifier=request_identity_v3(service.request)
            inputs=WorkerInputsV3(identifier,preparation_dispatch_identity(identifier,attempt_identity(identifier,1),1,identifier),1)
            env=environment('worker');env.update(GITHUB_ACTOR_ID='30498238',GITHUB_ACTOR='owner',GITHUB_TRIGGERING_ACTOR='owner')
            service.run_overrides['worker']={'actor':{'id':30498238,'login':'owner'},'triggering_actor':{'id':30498238,'login':'owner'}}
            runtime=GitHubActionsRuntimeBoundaryV3(environment=env,checkout=ProtectedCheckoutV3(root,SHA),
                role='worker',inputs=vars(inputs),token='fixture-control',executor=service)
            journal=live_journal_v3(runtime,GitHubOriginalAdmissionAuthorityV3(runtime.api),
                write_guard=lambda:(_ for _ in ()).throw(AssertionError('manual gate attempted mutation')))
            authority=GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api,runtime.expected)
            value=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=inputs,
                dispatch_authority=authority,sleeper=lambda seconds:None)
            self.assertFalse(value.accepted);self.assertEqual(service.claim_count(),0)
            self.assertEqual(service.mints,[]);self.assertEqual(service.acquisitions,[])
            self.assertEqual(service.git.mutation_calls,0)

    def test_ACK05_ACK06_wrong_reservation_or_generation_has_zero_reads_or_effects(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as temporary:
            service,result,inputs,runtime,journal,authority=self.prepare(Path(temporary))
            for bad in (replace(inputs,generation=2),replace(inputs,reservation_id='preparation-dispatch:sha256:'+'0'*64)):
                before=len(service.git.calls)
                value=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=bad,
                    dispatch_authority=authority,sleeper=lambda seconds:None)
                self.assertFalse(value.accepted);self.assertEqual(len(service.git.calls),before)

    def test_ACK11_applied_ack_with_lost_controller_response_cannot_start_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            state=self.prepare(Path(temporary),lost_ack=True);service=state[0]
            self.assertEqual(state[1].acknowledgment_outcome.status.value,'UNRESOLVED')
            self.assertEqual(state[1].status.value,'DISPATCH_UNRESOLVED')
            # The provider really applied ACK, but the original operation lost its
            # response. The pinned CLI maps that actual result to job non-success.
            service.controller_running=False
            service.run_overrides['controller']={'conclusion':'failure'}
            self.assertFalse(self.gate(state,lambda seconds:None).accepted)
