"""Measured artifact-service facts; approval is derived from actual external service I/O."""
import hashlib
import io
import json
from urllib.parse import urlsplit
import zipfile

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_prepared_artifact_v3 import GitHubPreparedArtifactV3, PreparedArtifactUploaderV3
from review_broker.github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationResultV3
from review_broker.pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from review_broker.prepared_artifact_transport_v3 import PreparedMetadataReaderV3
from review_broker.prepared_packet_archive_v3 import extract_prepared_packet_v3
from tests.issue70_rwp04_test_support import ArtifactService, BUDGET, NOW, PRINCIPAL
from tests.issue70_rwp05_test_support import FailureScenario


class ObservedArtifactService(ArtifactService):
    def __init__(self, real, authority, remote_root):
        super().__init__(real)
        self.authority,self.remote_root=authority,remote_root
        self.metadata_failure=None
        self.metadata_failure_path=None
        self.storage_timeout=False
        self.download_body=None
        self.actual_streams=[]

    def upload_once(self, plan, archive, *, before_effect):
        count=len(self.uploads)
        try:
            result=super().upload_once(plan,archive,before_effect=before_effect)
        except Exception:
            self._record_upload(plan,'UNKNOWN',len(self.uploads)>count)
            raise
        self._record_upload(plan,result.status.value,len(self.uploads)>count)
        return result

    def _record_upload(self, plan, status, emitted):
        self.authority.upload=dict(plan=plan,boundary=self,status=status,emitted=emitted,
            artifact_id=str(self.artifacts[0]['id']) if len(self.artifacts)==1 else None,
            reconciled_unconfirmed=False)

    def metadata(self, request, *, max_bytes):
        path=urlsplit(request.full_url).path
        selected=path.endswith('/artifacts') or path.endswith('/artifacts/991/zip')
        faulted=selected and (self.metadata_failure_path is None or path.endswith(self.metadata_failure_path))
        if faulted and self.metadata_failure=='timeout':
            self.metadata_calls.append(request.full_url)
            self.authority.service_timeout(request,role='artifact',artifact_id='991' if path.endswith('/zip') else None)
            if self.authority._target_matches(self.authority.records[-1],self.authority.snapshot,None):self._unconfirmed()
            else:self.authority.reconciliation_guard_rejected=True
            raise TimeoutError('fixture precise metadata read timeout')
        if faulted and type(self.metadata_failure) is int:
            self.metadata_calls.append(request.full_url)
            response=HttpResponseV3(self.metadata_failure,b'{}',{})
        else:response=super().metadata(request,max_bytes=max_bytes)
        if selected:
            self.authority.service_http(request,response,role='artifact',artifact_id='991' if path.endswith('/zip') else None)
            if response.status in {429,502,503,504}:
                record=self.authority.records[-1]
                if self.authority._target_matches(record,self.authority.snapshot,None):self._unconfirmed()
                else:self.authority.reconciliation_guard_rejected=True
            if len(response.body)>max_bytes:self.authority.reconciliation_guard_rejected=True
            if path.endswith('/artifacts') and response.status==200:
                value=json.loads(response.body)
                if value.get('total_count')==len(value.get('artifacts',[])) and len(value['artifacts'])!=1:
                    self._unconfirmed()
        return response

    def _unconfirmed(self):
        if self.authority.upload is not None:self.authority.upload['reconciled_unconfirmed']=True

    def _logical_storage_record(self, request, fact):
        # The service independently checks the destination issued by its authenticated
        # resolver. No signed destination or credential is persisted in provenance.
        assert request.full_url==self.redirect
        assert self.resolutions and self.resolutions[-1].endswith('/artifacts/991/zip')
        assert not dict(request.header_items())
        return dict(subject=request,phase='REMOTE_READ',operation='ACTIONS_ARTIFACT_DOWNLOAD',
            fact=fact,target='/repos/'+self.s.worker.expected.repository+'/actions/artifacts/991/zip',
            reference_id=None,artifact_id='991',origin='https://api.github.com',authenticated=True,query='')

    def storage(self, request, *, max_bytes):
        self.downloads.append(request.full_url);self.storage_headers.append(dict(request.header_items()))
        raw=self.archive if self.download_body is None else self.download_body
        if self.storage_timeout:
            self.authority.records.append(self._logical_storage_record(request,{'kind':'READ_TIMEOUT'}))
            self._unconfirmed();raise TimeoutError('fixture precise storage read timeout')
        self._logical_storage_record(request,{'kind':'STREAM_STARTED'})
        expected=self.artifacts[0]
        if len(raw)>max_bytes or len(raw)>expected['size_in_bytes']:
            self.authority.reconciliation_guard_rejected=True
        for offset in range(0,len(raw),97):
            if self.storage_hook:self.storage_hook(offset)
            yield raw[offset:offset+97]
        self.actual_streams.append((len(raw),artifact_identity(raw)))
        fact=dict(kind='VERIFICATION_FAILED',check='ARCHIVE_BYTES',
            expected_id='artifact:'+expected['digest'],observed_id=artifact_identity(raw),
            expected_size=expected['size_in_bytes'],observed_size=len(raw))
        if fact['expected_id']!=fact['observed_id'] or fact['expected_size']!=fact['observed_size']:
            self.authority.verification_records.append(dict(phase='REMOTE_RECONSTRUCTION',
                operation='VERIFY_ARCHIVE_BYTES',fact=fact,reference_id=None,artifact_id='991',
                target='/repos/'+self.s.worker.expected.repository+'/actions/artifacts/991/zip',
                source_matches=lambda source:type(source) is GitHubPreparedArtifactV3 and source.storage_executor==self.storage,
                subject_matches=lambda storage:storage['artifact_id']=='991' and storage['artifact_digest']==expected['digest']))
            self._unconfirmed()
        else:self._inventory_control(raw)

    def _inventory_control(self, raw):
        expected=json.loads(self.uploads[0][0].inventory_bytes)
        # Independent test-only inventory oracle over known service ZIP data. It
        # does not replace the real bounded extractor or its inventory calculation.
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
                infos=bundle.infolist()
                if (len(infos)>BUDGET.max_members or sum(i.file_size for i in infos)>BUDGET.max_uncompressed_bytes
                        or any(i.filename.startswith('/') or '..' in i.filename.split('/')
                        or '\\' in i.filename or (i.external_attr>>16)&0o170000==0o120000 or i.flag_bits&1 for i in infos)):
                    self.authority.reconciliation_guard_rejected=True;return
                rows=[]
                for info in infos:
                    if info.is_dir():continue
                    data=bundle.read(info)
                    rows.append(dict(path=info.filename,byte_length=len(data),sha256=hashlib.sha256(data).hexdigest()))
                rows.sort(key=lambda row:row['path'])
        except (ValueError,zipfile.BadZipFile):
            self.authority.reconciliation_guard_rejected=True;return
        actual=dict(schema_version=1,files=rows)
        if actual!=expected:
            if {r['path'] for r in actual['files']}!={r['path'] for r in expected['files']}:
                self.authority.reconciliation_guard_rejected=True;return
            fact=dict(kind='VERIFICATION_FAILED',check='INVENTORY',
                expected_id=artifact_identity(canonical_bytes(expected)+b'\n'),
                observed_id=artifact_identity(canonical_bytes(actual)+b'\n'),expected_size=None,observed_size=None)
            self.authority.verification_records.append(dict(phase='REMOTE_RECONSTRUCTION',
                operation='VERIFY_ARCHIVE_INVENTORY',fact=fact,reference_id=None,artifact_id='991',
                target='/repos/'+self.s.worker.expected.repository+'/actions/artifacts/991/zip',source=extract_prepared_packet_v3,
                subject_matches=lambda subject:subject[0]==self.remote_root and subject[1]==expected and subject[2]==actual))
            self._unconfirmed()


class RemoteFailureScenario(FailureScenario):
    def __init__(self, root, *, no_remote=False):
        super().__init__(root,status=200,no_remote=no_remote)
        self.handoff=self.run_packet()
        assert type(self.handoff) is PreModelPacketContinuationResultV3 and self.handoff.packet_id is not None
        self.verification=self.real.verification()
        # Independent fixture owner verifies the actual original handoff/packet;
        # it does not approve a packet ID copied from a failure payload.
        assert self.producer._remote_handoff[1] is self.handoff
        _,_,_,manifest=load_packet_evidence_v3(self.handoff.retained_root,
            self.real.worker.admission.journal_admission(),policy_verification=self.verification)
        assert manifest['packet_id']==self.handoff.packet_id
        self.authority.packet_id=manifest['packet_id']
        self.remote_root=self.worker_root/'downloaded-remote'
        self.service=ObservedArtifactService(self.real,self.authority,self.remote_root)
        self.adapter=self.make_adapter()
        self.uploader=PreparedArtifactUploaderV3(self.service)
        self.remote=PreModelRemoteRetentionV3(producer=self.producer,retention_base=self.worker_root/'retained',
            verification=self.verification,uploader=self.uploader,adapter=self.adapter,
            remote_verification_root=self.remote_root,failure_evidence=self.evidence)

    def make_adapter(self, budget=BUDGET):
        metadata=PreparedMetadataReaderV3(token='fixture-github-credential',repository=self.real.worker.expected.repository,
                                          executor=self.service.metadata,budget=budget)
        return GitHubPreparedArtifactV3(metadata=metadata,
            worker_history=GitHubPreparedWorkerHistoryV3(metadata,self.real.worker.expected,self.real.worker.dispatch_authority,PRINCIPAL),
            storage_executor=self.service.storage,budget=budget,clock=lambda:NOW)

    def run_remote(self):return self.remote.run(self.real.worker.context,self.handoff)
