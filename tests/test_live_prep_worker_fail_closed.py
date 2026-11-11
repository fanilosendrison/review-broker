"""Worker drift/refusal and real retained BLOCKED from original live-form HTTP evidence."""
from pathlib import Path
import json
import tempfile
import unittest

from tests.live_prep_artifact_provider_support import CompleteProviderService
from tests.live_prep_provider_support import controller_scenario,TOKEN_A
from tests.test_live_prep_complete_composition import worker_scenario
from review_broker.journal_record_v3 import decode_journal_v2


def current_record(service,controller):
    commit=service.git.refs[controller.dispatch_request.claim_ref]
    tree=service.git.trees[service.git.commits[commit][0]]
    blob=next(e['sha'] for e in tree if e['path']=='.review-broker/attempt.json')
    return decode_journal_v2(service.git.blobs[blob])


class WorkerFailClosedTests(unittest.TestCase):
    def test_LP01_10_issuer_policy_rejects_Controller_token_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            service=CompleteProviderService(Path(temporary))
            service.minted('controller')
            with self.assertRaisesRegex(ValueError,'Controller credential reuse'):
                service.minted('worker',proposed=TOKEN_A)
            self.assertEqual(service.mints,['controller']);self.assertEqual(service.acquisitions,[])

    def test_LP01_12_15_head_object_body_or_comment_drift_refuses_before_packet(self):
        for fault in ('head','object','body','comment'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary).resolve();service=CompleteProviderService(root)
                controller=controller_scenario(root,service);service.controller_running=False
                if fault=='head':service.pull.drift_head='f'*40
                if fault=='object':service.pull.pr_id+=1
                if fault=='body':service.body_reference+='changed'
                if fault=='comment':service.comment_reference+='changed'
                result=worker_scenario(root,service,controller)
                self.assertFalse(result.cold_verified,result)
                self.assertFalse((root/'worker/candidate').exists())
                self.assertEqual(service.uploads,[])
                record=current_record(service,controller)
                self.assertEqual(record.attempt.state.value,'ADMITTED')
                self.assertEqual(record.attempt.invocation_count,0)

    def test_original_reference_503_retained_before_unique_BLOCKED_CAS(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            controller=controller_scenario(root,service);service.controller_running=False
            service.reference_failure=503
            result=worker_scenario(root,service,controller)
            record=current_record(service,controller)
            self.assertEqual(record.control.disposition,'BLOCKED',result)
            self.assertEqual(record.attempt.state.value,'ADMITTED')
            self.assertEqual(record.attempt.invocation_count,0)
            self.assertEqual(len(service.uploads),1)
            name,raw=service.uploads[0]
            self.assertTrue(name.startswith('rb-v3-failure-observation-'))
            self.assertFalse(raw.startswith(b'PK'))
            observation=json.loads(raw)
            self.assertEqual(observation['fact'],{'kind':'HTTP_STATUS','status':503})
            self.assertEqual(observation['reference_id'],'body')
            self.assertTrue(service.downloads)
            failures=[h for h in record.attempt.history if h.get('event')=='PRE_MODEL_FAILURE']
            self.assertEqual(len(failures),1)

    def test_failure_retention_unavailable_never_invents_BLOCKED(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            controller=controller_scenario(root,service);service.controller_running=False
            service.reference_failure=503;service.metadata_failure=503
            result=worker_scenario(root,service,controller)
            record=current_record(service,controller)
            self.assertEqual(record.control.disposition,'RESERVED',result)
            self.assertFalse(any(h.get('event')=='PRE_MODEL_FAILURE' for h in record.attempt.history))
            self.assertEqual(record.attempt.state.value,'ADMITTED')
            self.assertEqual(len(service.uploads),1)
