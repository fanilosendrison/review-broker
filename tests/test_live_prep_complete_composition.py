"""Full new Controller→Worker path. Doubles own external HTTP, issuer and Artifact provider only."""
from pathlib import Path
import os
import tempfile
import unittest

from review_broker.github_actions_worker_authority_v3 import WorkerInputsV3
from review_broker.live_pre_model_worker_v3 import run_live_worker_v3
from review_broker.request_v3 import request_identity_v3
from tests.live_prep_provider_support import controller_scenario,TOKEN_A,TOKEN_B
from tests.live_prep_artifact_provider_support import CompleteProviderService

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'artifacts/v3-upload-artifact'


def worker_scenario(root,service,controller,*,token=None):
    request_id=request_identity_v3(service.request)
    reservation=controller.reservation_outcome.snapshot.record.control.reservation_id
    runtime=service.runtime('worker',vars(WorkerInputsV3(request_id,reservation,1)))
    from review_broker.live_pre_model_worker_v3 import worker_observer_v3,LiveWorkerResultV3
    from review_broker.pre_model_ack_start_gate_v3 import wait_dispatch_ack_v3
    observer,dispatch=worker_observer_v3(runtime)
    gate=wait_dispatch_ack_v3(journal=observer,runtime=runtime,inputs=WorkerInputsV3(request_id,reservation,1),
        dispatch_authority=dispatch,sleeper=lambda seconds:None)
    if not gate.accepted:return LiveWorkerResultV3('REJECTED','UNCONFIRMED',gate.reason)
    private=root/'worker';private.mkdir(mode=0o700)
    return run_live_worker_v3(runtime=runtime,source_token=token or service.minted('worker'),
        app_slug='review-broker-app',installation_id=123,private_root=private,
        helper_root=HELPER,node=Path('/trusted/node24'),source_executor=service.source,
        acquire_repository=service.acquire,artifact_environment={
            'ACTIONS_RUNTIME_TOKEN':'fixture-runtime-only','ACTIONS_RESULTS_URL':'https://fixture.invalid',
            'GITHUB_TOKEN':'fixture-control','REVIEW_BROKER_SOURCE_TOKEN':TOKEN_B},
        artifact_runner=service.runner,metadata_executor=service.metadata,storage_executor=service.storage,
        sleeper=lambda seconds:None)


class CompleteCompositionTests(unittest.TestCase):
    def test_full_live_form_constructs_every_intermediate_and_cold_observer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            controller=controller_scenario(root,service)
            self.assertEqual(controller.status.value,'DISPATCH_ACKNOWLEDGED',controller)
            service.controller_running=False
            result=worker_scenario(root,service,controller)
            self.assertEqual(result.status,'COMMITTED',result)
            self.assertEqual(result.state,'PREPARED',result)
            self.assertTrue(result.cold_verified,result)
            self.assertEqual(result.reason,'STOP_BEFORE_ARMED')
            self.assertEqual(service.acquisitions,[TOKEN_A,TOKEN_B])
            self.assertEqual(service.mints,['controller','worker'])
            self.assertEqual(service.source_after_mutation,0)
            self.assertEqual(service.source_with_control,0);self.assertEqual(service.journal_with_source,0)
            self.assertEqual(len(service.uploads),1)
            self.assertTrue(service.uploads[0][1].startswith(b'PK'))
            self.assertEqual(service.started[0][0],os.getpid())
            self.assertTrue(service.metadata_calls);self.assertTrue(service.downloads)
            from review_broker.journal_record_v3 import decode_journal_v2
            commit=service.git.refs[controller.dispatch_request.claim_ref]
            tree=service.git.trees[service.git.commits[commit][0]]
            blob=next(e['sha'] for e in tree if e['path']=='.review-broker/attempt.json')
            record=decode_journal_v2(service.git.blobs[blob])
            self.assertEqual(record.attempt.state.value,'PREPARED')
            self.assertEqual(record.attempt.invocation_count,0)
            self.assertEqual(record.control.generation,1)
            self.assertEqual(record.attempt.history[-1]['state'],'PREPARED')

    def test_empty_reference_regression_uses_same_complete_chain(self):
        from review_broker.request_v3 import build_issue_envelope_v3
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            service.request['references']=[];service.body=build_issue_envelope_v3(service.request)
            controller=controller_scenario(root,service);service.controller_running=False
            result=worker_scenario(root,service,controller)
            self.assertTrue(result.cold_verified,result)
            self.assertEqual(service.acquisitions,[TOKEN_A,TOKEN_B]);self.assertEqual(len(service.uploads),1)
            self.assertEqual(list((root/'worker/remote/evidence/admitted-references').iterdir()),[])

    def test_manual_worker_without_controller_ack_never_mints_or_starts(self):
        from review_broker.live_pre_model_worker_v3 import worker_observer_v3
        from review_broker.pre_model_ack_start_gate_v3 import wait_dispatch_ack_v3
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            service.dispatch_loss=True;controller=controller_scenario(root,service)
            request_id=request_identity_v3(service.request)
            inputs=WorkerInputsV3(request_id,controller.reservation_outcome.snapshot.record.control.reservation_id,1)
            runtime=service.runtime('worker',vars(inputs));journal,dispatch=worker_observer_v3(runtime)
            before=service.git.mutation_calls
            result=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=inputs,
                dispatch_authority=dispatch,sleeper=lambda seconds:None)
            self.assertFalse(result.accepted)
            self.assertEqual(service.mints,['controller'])
            self.assertEqual(service.acquisitions,[TOKEN_A]);self.assertEqual(service.uploads,[])
            self.assertEqual(service.git.mutation_calls,before)
