"""Real Controller/Worker/packet composition with independently measured failure services."""
import copy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.journal_record_v3 import decode_journal_v2
from review_broker.pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3
from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
from tests.issue70_rwp03_test_support import (
    RealContinuationScenario, ContinuationWorkerScenario, ContinuationTransport,
)
from tests.issue70_rwp02_test_support import ScopedPredecessor
from tests.issue70_rwp04_test_support import NoRemoteAuthenticatedScenario, install_historical_reads
from tests.issue70_rwp05_evidence_support import ExternalFailureAuthority, ExternalObservationArchive


class MeasuredFailureTransport(ContinuationTransport):
    def __init__(self):
        super().__init__()
        self.proposal_calls = []
        self.on_failure_commit = self.on_failure_applied = None

    def create_journal_commit(self, parent_sha, raw):
        self.proposal_calls.append((parent_sha, raw))
        record=decode_journal_v2(raw)
        if record.attempt.history[-1].get('event')=='PRE_MODEL_FAILURE' and self.on_failure_commit:
            self.on_failure_commit()
        return super().create_journal_commit(parent_sha, raw)

    def update_ref(self, update):
        failure=decode_journal_v2(self.commits[update.after_oid].journal_bytes).attempt.history[-1].get('event')=='PRE_MODEL_FAILURE'
        result=super().update_ref(update)
        if failure and result.writer_evidence_id and self.on_failure_applied:self.on_failure_applied()
        return result


class FailureWorkerScenario(ContinuationWorkerScenario):
    def __init__(self, admission):
        super().__init__(admission)
        self.transport=MeasuredFailureTransport()
        self.journal.transport=self.transport
        self.journal.predecessor_authority=ScopedPredecessor(self.transport)


class FailureScenario:
    def __init__(self, root, *, status=503, reference='requirement', no_remote=False):
        self.root=Path(root); self.worker_root=self.root/'worker'; self.external=self.root/'external'
        self.worker_root.mkdir(mode=0o700,parents=True);self.external.mkdir(mode=0o700,parents=True)
        with patch('tests.issue70_rwp03_test_support.ContinuationWorkerScenario',FailureWorkerScenario):
            if no_remote:
                with patch('tests.issue70_test_support.AuthenticatedScenario',NoRemoteAuthenticatedScenario):
                    self.real=RealContinuationScenario(self.worker_root)
            else:self.real=RealContinuationScenario(self.worker_root)
        s=self.real.worker
        install_historical_reads(s.transport)
        self.authority=ExternalFailureAuthority(self.external/'trusted-origin',s.context)
        self.archive=ExternalObservationArchive(self.external/'observation-objects')
        self.evidence=PreModelFailureEvidenceV3(self.authority,self.archive,16_000)
        self.reference_status=status;self.reference_id=reference;self.source_requests=[]
        self.target_override=None
        old_hook=s.transport.after_update_hook
        def observed(event,result):
            old_hook(event,result)
            if event=='ADMITTED' and result.writer_evidence_id:
                snapshot=s.journal.read(s.admission.request_id)
                self.authority.admit_server_snapshot(snapshot)
                self.counts_at_a=(len(s.transport.proposal_calls),len(s.transport.updates))
        s.transport.after_update_hook=observed
        for identifier,reader in self.real.inputs.issue_readers.items():
            clone=copy.copy(reader);api=reader._executor
            def execute(request,identifier=identifier,api=api):
                path=urlsplit(request.full_url).path
                selected=(identifier==self.reference_id and (
                    path.endswith('/issues/43') if identifier=='requirement' else path.endswith('/issues/comments/99')))
                if selected and self.target_override:request.full_url=self.target_override
                response=HttpResponseV3(self.reference_status,b'{}',{}) if selected and self.reference_status!=200 else api(request)
                self.source_requests.append(request)
                self.authority.service_http(request,response,role='reference',reference_id=identifier)
                return response
            clone._executor=execute
            self.real.inputs.issue_readers[identifier]=clone
        self.producer=PreModelPacketContinuationV3(journal=s.journal,current_worker_authority=self.real.authority,
            original_admission=s.admission,capture_provider=self.real,reference_readers=self.real.reference_readers,
            policy_source_authority=self.real.source_authority,policy_selection_authority=self.real.selection_authority,
            packet_stages=self.real.stages,failure_evidence=self.evidence)
        self.real.continuation=self.producer

    def run_packet(self):
        return self.producer.run(self.real.worker.context)

    def failure_cas_count(self):
        return self.real.worker.transport.events.count('PRE_MODEL_FAILURE')

    def failure_proposals(self):
        return [raw for _,raw in self.real.worker.transport.proposal_calls
                if decode_journal_v2(raw).attempt.history[-1].get('event')=='PRE_MODEL_FAILURE']

    def current(self):
        return self.real.worker.journal.read(self.real.worker.admission.request_id)
