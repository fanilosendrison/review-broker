"""Real remote composition, strict catalog boundaries and unknown-upload precedence."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from review_broker.pre_model_failure_continuation_v3 import PreModelFailureResultV3
from review_broker.pre_model_active_decision_v3 import PreModelDecisionStateV3
from review_broker.prepared_packet_readback_v3 import readback_prepared_packet_v3
import review_broker.pre_model_remote_retention_v3 as remote_module
from tests.issue70_rwp05_remote_support import RemoteFailureScenario
from tests.issue70_rwp05_reconstruction_support import register_reconstruction_fault


class RemoteFailureCompositionTests(unittest.TestCase):
    def scenario(self, **kwargs):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return RemoteFailureScenario(Path(temporary.name),**kwargs)

    def blocked(self, s, reason, result=None):
        result=s.run_remote() if result is None else result
        self.assertIs(type(result),PreModelFailureResultV3,result)
        self.assertEqual((result.status.value,result.disposition,result.observation_status),('COMMITTED','BLOCKED','VERIFIED'),result)
        receipt=s.current().record.attempt.history[-1]['pre_model']['receipt']
        self.assertEqual(receipt['reason_code'],reason)
        self.assertEqual(len(s.service.uploads),1)
        self.assertEqual(s.failure_cas_count(),1)
        self.assertEqual(s.real.worker.transport.events.count('PREPARED'),0)
        self.assertEqual(len(s.archive.puts),1)
        s.run_remote()
        self.assertEqual(len(s.service.uploads),1)
        self.assertEqual(s.failure_cas_count(),1)
        return result

    def test_F07_ack_metadata_503_is_transient(self):
        s=self.scenario();s.service.metadata_failure=503
        self.blocked(s,'ARTIFACT_READ_UNAVAILABLE')

    def test_F07_precise_metadata_and_storage_read_timeouts(self):
        for mode in ('metadata','storage'):
            s=self.scenario()
            if mode=='metadata':s.service.metadata_failure='timeout'
            else:s.service.storage_timeout=True
            with self.subTest(mode=mode):self.blocked(s,'ARTIFACT_READ_UNAVAILABLE')

    def test_F10_unknown_upload_resolves_only_after_complete_original_packet(self):
        for empty in (False,True):
            s=self.scenario(no_remote=empty);s.service.lost_upload_response=True
            result=s.run_remote()
            with self.subTest(empty=empty):
                self.assertEqual((result.status.value,result.state),('COMMITTED','PREPARED'),result)
                self.assertEqual(s.current().record.control.disposition,'RESERVED')
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.archive.puts,[])
                self.assertEqual(len(s.service.uploads),1)
                self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_PREPARED)
                back=readback_prepared_packet_v3(journal=s.real.worker.journal,
                    request_id=s.real.worker.admission.request_id,adapter=s.adapter,
                    source_authority=s.real.source_authority,selection_authority=s.real.selection_authority,
                    destination=s.root/'observer')
                self.assertEqual(back.remote_reconstruction,'VERIFIED')
                self.assertEqual(back.reconstruction.packet_id,s.handoff.packet_id)

    def test_F10_unknown_upload_read_failure_and_post_metadata_download_failure_priority(self):
        for mode in ('metadata-503','download-503','storage-timeout'):
            s=self.scenario();s.service.lost_upload_response=True
            if mode=='metadata-503':s.service.metadata_failure=503
            elif mode=='download-503':
                s.service.metadata_failure=503;s.service.metadata_failure_path='/artifacts/991/zip'
            else:s.service.storage_timeout=True
            with self.subTest(mode=mode):self.blocked(s,'ARTIFACT_UPLOAD_UNCONFIRMED')

    def test_F08_four_concrete_completed_verification_controls(self):
        for check in ('ARCHIVE_BYTES','INVENTORY','MANIFEST','PACKET_ID'):
            s=self.scenario()
            if check=='ARCHIVE_BYTES':
                def change(stage,guard):
                    if stage=='after':s.service.download_body=s.service.archive[:-1]
                s.service.upload_hook=change
                result=None
            elif check=='INVENTORY':
                def change(stage,guard):
                    if stage!='after':return
                    stream=io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(s.service.archive)) as source,zipfile.ZipFile(stream,'w') as target:
                        for info in source.infolist():
                            data=source.read(info)
                            if info.filename=='packet/input.txt':data=data+b' altered'
                            target.writestr(info,data)
                    body=stream.getvalue();s.service.download_body=body
                    s.service.artifacts[0].update(digest='sha256:'+hashlib.sha256(body).hexdigest(),size_in_bytes=len(body))
                s.service.upload_hook=change;result=None
            else:
                original=remote_module.extract_prepared_packet_v3
                def extract(raw,destination,budget,before_effect,**kwargs):
                    result=original(raw,destination,budget,before_effect,**kwargs)
                    register_reconstruction_fault(s,destination,check=check)
                    return result
                with patch.object(remote_module,'extract_prepared_packet_v3',extract):result=s.run_remote()
            with self.subTest(check=check):
                self.blocked(s,'REMOTE_RECONSTRUCTION_UNCONFIRMED',result)
                observation=s.authority.observations[-1]
                self.assertEqual(observation.value['fact']['check'],check)
                self.assertEqual(observation.value['artifact_id'],'991')
                self.assertEqual(observation.value['packet_id'],s.handoff.packet_id)

    def test_F10_unknown_upload_divergence_remains_upload_unknown(self):
        s=self.scenario();s.service.lost_upload_response=True
        def corrupt(stage,guard):
            if stage=='after':s.service.download_body=s.service.archive[:-1]
        s.service.upload_hook=corrupt
        self.blocked(s,'ARTIFACT_UPLOAD_UNCONFIRMED')

    def test_F10_unknown_upload_complete_absent_or_ambiguous_listing_can_block_unknown(self):
        for mode in ('absent','ambiguous'):
            s=self.scenario();s.service.lost_upload_response=True
            def change(stage,guard):
                if stage!='after':return
                if mode=='absent':s.service.artifacts=[]
                else:
                    other=copy.deepcopy(s.service.artifacts[0]);other['id']+=1;s.service.artifacts.append(other)
            s.service.upload_hook=change
            with self.subTest(mode=mode):self.blocked(s,'ARTIFACT_UPLOAD_UNCONFIRMED')

    def test_F02_F23_guards_are_not_catalog_observations_even_after_unknown_upload(self):
        from dataclasses import replace
        from tests.issue70_rwp04_test_support import BUDGET
        for mode in ('budget','redirect','schema'):
            s=self.scenario();s.service.lost_upload_response=True
            if mode=='budget':
                s.remote.adapter=s.make_adapter(replace(BUDGET,max_members=1))
                result=s.run_remote()
            elif mode=='redirect':
                s.service.redirect='http://fixture.blob.core.windows.net/not-admitted'
                result=s.run_remote()
            else:
                original=remote_module.extract_prepared_packet_v3
                def invalid_schema(raw,destination,budget,before_effect,**kwargs):
                    value=original(raw,destination,budget,before_effect,**kwargs)
                    s.authority.reconciliation_guard_rejected=True
                    (destination/'packet/input-manifest.json').write_bytes(b'{}\n')
                    return value
                with patch.object(remote_module,'extract_prepared_packet_v3',invalid_schema):result=s.run_remote()
            with self.subTest(mode=mode):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.archive.puts,[])
                self.assertLessEqual(len(s.service.uploads),1)
                self.assertEqual(s.real.worker.transport.events.count('PREPARED'),0)

    def test_F10_ack_absent_expired_ambiguous_or_upload_refused_do_not_create_catalog_failure(self):
        for mode in ('absent','expired','ambiguous','refused'):
            s=self.scenario()
            if mode=='refused':s.service.refuse_upload=True
            else:
                def change(stage,guard):
                    if stage!='after':return
                    if mode=='absent':s.service.artifacts=[]
                    elif mode=='expired':s.service.artifacts[0]['expired']=True
                    else:
                        other=copy.deepcopy(s.service.artifacts[0]);other['id']+=1;s.service.artifacts.append(other)
                s.service.upload_hook=change
            result=s.run_remote()
            with self.subTest(mode=mode):
                self.assertNotEqual(result.status.value,'COMMITTED')
                self.assertEqual(s.failure_proposals(),[])
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(s.archive.puts,[])
                self.assertEqual(len(s.service.uploads),1)
