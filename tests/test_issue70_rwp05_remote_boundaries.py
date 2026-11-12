"""Historical prototype obligations confronted with actual routable remote bytes and receipts."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import uuid
from urllib.parse import urlsplit
import zipfile

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.prepared_packet_readback_v3 import readback_prepared_packet_v3,reconstruct_prepared_packet_v3
from tests.issue70_rwp04_test_support import ArtifactService,PRINCIPAL
from tests.issue70_rwp05_remote_support import RemoteFailureScenario


class HistoricalRemoteBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.root=Path(cls.temporary.name)
        cls.s=RemoteFailureScenario(cls.root)
        cls.result=cls.s.run_remote()
        if cls.result.status.value!='COMMITTED':raise AssertionError(cls.result)
        cls.saved_artifacts=copy.deepcopy(cls.s.service.artifacts)
        cls.saved_archive=cls.s.service.archive
        cls.saved_metadata=cls.s.adapter.metadata.executor
        cls.saved_storage=cls.s.adapter.storage_executor
        cls.history=PreparedJournalHistoryV3.read(cls.s.real.worker.journal,cls.s.real.worker.admission.request_id,
            cls.s.real.worker.expected,cls.s.real.worker.dispatch_authority,PRINCIPAL)
        cls.manifest=(cls.s.handoff.retained_root/'packet/input-manifest.json').read_bytes()

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def setUp(self):
        s=self.s
        s.service.artifacts=copy.deepcopy(self.saved_artifacts);s.service.archive=self.saved_archive
        s.adapter.metadata.executor=self.saved_metadata;s.adapter.storage_executor=self.saved_storage
        # The historic observer's external storage transport serves the actual ZIP
        # even for a routable replacement ID. It has no failure collector or ticket.
        s.adapter.storage_executor=lambda request,**kwargs:ArtifactService.storage(s.service,request,**kwargs)
        self.destination=self.root/('observer-'+uuid.uuid4().hex)

    def read(self):
        s=self.s
        return readback_prepared_packet_v3(journal=s.real.worker.journal,request_id=s.real.worker.admission.request_id,
            adapter=s.adapter,source_authority=s.real.source_authority,selection_authority=s.real.selection_authority,
            destination=self.destination)

    def unchanged_commitment_and_effects(self):
        s=self.s
        self.assertEqual(s.current(),self.result.journal_outcome.snapshot)
        self.assertEqual(len(s.service.uploads),1)
        self.assertEqual(s.failure_cas_count(),0)
        self.assertEqual(s.real.worker.transport.events.count('PREPARED'),1)
        self.assertEqual(s.archive.puts,[])

    def assert_reconstructed_receipt_mismatch(self):
        before=len(self.s.service.downloads)
        back=self.read()
        self.assertEqual((back.journal_transition,back.state,back.remote_reconstruction),('COMMITTED','PREPARED','UNAVAILABLE'))
        self.assertEqual(len(self.s.service.downloads),before+1)
        self.assertEqual((self.destination/'packet/input-manifest.json').read_bytes(),self.manifest)
        storage=self.s.adapter.observe(self.history.admitted,self.history.verify)
        with self.assertRaisesRegex(ValueError,'HISTORICAL_REMOTE_COMMITMENT_MISMATCH'):
            reconstruct_prepared_packet_v3(self.destination,history=self.history,source_authority=self.s.real.source_authority,
                selection_authority=self.s.real.selection_authority,authenticated_storage=storage)
        self.unchanged_commitment_and_effects()

    def test_proto05_same_name_new_id_serves_identical_bytes_but_not_original_receipt(self):
        s=self.s;s.service.artifacts[0]['id']=992
        original=s.adapter.metadata.executor
        def resolve(request,**kwargs):
            if urlsplit(request.full_url).path.endswith('/actions/artifacts/992/zip'):
                s.service.resolutions.append(urlsplit(request.full_url).path)
                return HttpResponseV3(302,b'',{'Location':s.service.redirect})
            return original(request,**kwargs)
        s.adapter.metadata.executor=resolve
        self.assert_reconstructed_receipt_mismatch()

    def test_proto06_changed_zip_and_matching_authenticated_digest_still_changes_commitment(self):
        s=self.s;s.service.archive=self.saved_archive+b'changed ZIP bytes'
        s.service.artifacts[0].update(digest='sha256:'+hashlib.sha256(s.service.archive).hexdigest(),size_in_bytes=len(s.service.archive))
        self.assert_reconstructed_receipt_mismatch()

    def test_proto11_future_expiration_metadata_change_is_not_silently_recommitted(self):
        self.s.service.artifacts[0]['expires_at']='2026-12-06T00:00:00Z'
        self.assert_reconstructed_receipt_mismatch()

    def test_proto15_proto16_remote_source_or_missing_member_with_matching_digest_refuses(self):
        for mode in ('source','missing'):
            s=self.s;stream=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.saved_archive)) as source,zipfile.ZipFile(stream,'w') as target:
                for info in source.infolist():
                    if mode=='missing' and info.filename=='packet/input.txt':continue
                    data=source.read(info)
                    if mode=='source' and info.filename=='packet/sources/S001.bin':data=b'altered source\n'
                    target.writestr(info,data)
            s.service.archive=stream.getvalue()
            s.service.artifacts[0].update(digest='sha256:'+hashlib.sha256(s.service.archive).hexdigest(),size_in_bytes=len(s.service.archive))
            self.destination=self.root/('observer-'+uuid.uuid4().hex)
            with self.subTest(mode=mode):
                back=self.read()
                self.assertEqual((back.journal_transition,back.state,back.remote_reconstruction),('COMMITTED','PREPARED','UNAVAILABLE'))
                self.unchanged_commitment_and_effects()
