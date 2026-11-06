"""External simulated service trust and immutable archive, separate from Worker inputs."""
from dataclasses import asdict
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.pre_model_failure_evidence_v3 import (
    FailureObservationBindingV3, FailureRetentionResultV3, FailureRetentionStatusV3,
    FailureEvidenceRejectedV3, FailureEvidenceUnavailableV3,
)
from review_broker.pre_model_failure_observation_v3 import FailureObservationV3, valid_failure_observation_identity_v3
from review_broker.remote_prepared_receipt_v3 import prepared_artifact_name_v3
from tests.issue70_rwp04_test_support import BUDGET

STAMP = '2026-11-06T07:00:00Z'


def private_write(path, raw):
    path = Path(path); path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())


class ExternalObservationArchive:
    """A put never inserts anything into the independent recognition corpus."""
    def __init__(self, root, *, create=True):
        self.root = Path(root)
        if create:self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.puts, self.reads = [], []
        self.lose_ack = self.drop_put = self.unavailable = False
        self.corrupt = False
        self.on_put = self.on_read = None

    def put_once(self, evidence_id, raw, *, before_effect):
        if not valid_failure_observation_identity_v3(evidence_id):raise FailureEvidenceRejectedV3('invalid object address')
        before_effect(); self.puts.append((evidence_id, raw))
        if self.on_put: self.on_put()
        if not self.drop_put:
            before_effect()
            try: private_write(self.root/evidence_id.rsplit(':',1)[-1], raw)
            except FileExistsError: return FailureRetentionResultV3(FailureRetentionStatusV3.REFUSED)
        if self.lose_ack: raise OSError('fixture lost retention response')
        return FailureRetentionResultV3(FailureRetentionStatusV3.ACK)

    def read(self, evidence_id, *, max_bytes, before_effect):
        if not valid_failure_observation_identity_v3(evidence_id):raise FailureEvidenceRejectedV3('invalid object address')
        before_effect(); self.reads.append(evidence_id)
        if self.on_read: self.on_read()
        if self.unavailable: raise FailureEvidenceUnavailableV3('fixture archive unavailable')
        path = self.root/evidence_id.rsplit(':',1)[-1]
        before_effect()
        if not path.exists(): return None
        before_effect()
        with path.open('rb') as source:
            before_effect(); raw = source.read(max_bytes+1)
        return raw+b'corrupt' if self.corrupt else raw


class ExternalFailureAuthority:
    """Recognize independently measured service executions, never archive payloads.

    Service adapters append Request/process identities and facts after an actual
    external-boundary execution. observe derives the approved value from those
    service-owned records and the independently observed ADMITTED server state.
    Only safe target/operation facts enter the immutable trust corpus. Cold
    verify reads that corpus; it does not create fresh observations or approval.
    """
    def __init__(self, root, context=None, *, create=True):
        self.root = Path(root)
        if create:self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.context = None if context is None else asdict(context)
        self.snapshot = None
        self.records = []
        self.observations = []
        self.recognized = True
        self.packet_id = None
        self.verification_records = []
        self.upload = None
        self.reconciliation_guard_rejected = False

    def admit_server_snapshot(self, snapshot):
        assert snapshot.record.attempt.state.value == 'ADMITTED'
        self.snapshot = snapshot

    def _service_request(self, request, fact, *, role, reference_id=None, artifact_id=None):
        # Called by the external API adapter, NOT by the observation callback.
        from tests.issue69_test_support import TOKEN
        expected_token = TOKEN if role=='reference' else 'fixture-github-credential'
        authenticated = request.headers.get('Authorization')=='Bearer '+expected_token
        self.records.append(dict(subject=request, role=role, authenticated=authenticated,
            origin=urlsplit(request.full_url).scheme+'://'+urlsplit(request.full_url).netloc, reference_id=reference_id,
            artifact_id=artifact_id, target=urlsplit(request.full_url).path,
            query=urlsplit(request.full_url).query, fact=fact,
            phase='REFERENCE_READ' if role=='reference' else 'REMOTE_READ',
            operation=('GITHUB_ISSUE_COMMENT_GET' if '/issues/comments/' in request.full_url else 'GITHUB_ISSUE_GET')
                      if role=='reference' else ('ACTIONS_ARTIFACT_DOWNLOAD' if request.full_url.split('?')[0].endswith('/zip') else 'ACTIONS_ARTIFACT_METADATA_GET')))

    def service_http(self, request, response, **scope):
        self._service_request(request,{'kind':'HTTP_STATUS','status':response.status},**scope)

    def service_timeout(self, request, **scope):
        self._service_request(request,{'kind':'READ_TIMEOUT'},**scope)

    def _scope(self, snapshot):
        return dict(repository=snapshot.repository, repository_node_id=snapshot.repository_node_id,
            claim_ref=snapshot.claim_ref, admitted_commit_sha=snapshot.commit_sha,
            journal_bytes_id=artifact_identity(snapshot.journal_bytes))

    def _reference_target(self, snapshot, reference_id, operation):
        request=snapshot.record.attempt.admission['canonical_request']
        reference=next((r for r in request['references'] if r['id']==reference_id),None)
        if reference is None:return None
        source=reference['source'];prefix='/repos/'+source['repository']
        if source['kind']=='github_issue_body' and operation=='GITHUB_ISSUE_GET':
            return prefix+'/issues/'+str(source['issue'])
        if source['kind']=='github_issue_comment':
            if operation=='GITHUB_ISSUE_COMMENT_GET':return prefix+'/issues/comments/'+str(source['comment_id'])
            admitted=next(x for x in snapshot.record.attempt.admission['issue_reference_admissions']
                          if x['source_kind']=='github_issue_comment' and x['selector_id']==source['comment_id'])
            return prefix+'/issues/'+str(admitted['issue_number'])
        return None

    def _target_matches(self, record, snapshot, reference_id):
        if record['phase']=='REFERENCE_READ':
            return (record.get('origin')=='https://api.github.com' and record.get('authenticated') is True
                    and not record.get('query','')
                    and record['target']==self._reference_target(snapshot,reference_id,record['operation']))
        if record['phase']=='SOURCE_ACQUISITION':
            return record['target']==snapshot.record.attempt.admission['canonical_request']['subject']['repository']
        expected='/repos/'+snapshot.repository+'/actions/'
        if (not record['target'].startswith(expected) or record.get('origin')!='https://api.github.com'
                or record.get('authenticated') is not True):return False
        worker=snapshot.record.control.worker
        if record['operation']=='ACTIONS_ARTIFACT_METADATA_GET':
            query=parse_qs(record.get('query',''))
            return (record['target']==expected+'runs/'+str(worker.run_id)+'/artifacts'
                    and query.get('name')==[prepared_artifact_name_v3(snapshot.claim_ref,worker.run_id,1)]
                    and query.get('per_page')==['100'] and len(query.get('page',[]))==1
                    and set(query)=={'name','per_page','page'}
                    and query['page'][0].isascii() and query['page'][0].isdecimal() and int(query['page'][0])>0)
        return (record['artifact_id'] is not None and record['target']==expected+'artifacts/'+record['artifact_id']+'/zip'
                and not record.get('query',''))

    def _actual_record(self, event):
        subject=event.subject[0] if isinstance(event.subject,tuple) and event.phase=='REMOTE_READ' else event.subject
        for record in reversed(self.records):
            if record['subject'] is subject and record['phase']==event.phase and record['operation']==event.operation:
                return record
        return None

    def _composed_upload(self, event):
        if (self.upload is None or self.upload['status']!='UNKNOWN' or not self.upload['emitted']
                or self.reconciliation_guard_rejected or not self.upload.get('reconciled_unconfirmed')):
            return None
        pending=event.subject[0]
        if pending.subject is not self.upload['plan'] or pending.source.boundary is not self.upload['boundary']:
            return None
        return dict(phase='REMOTE_UPLOAD',operation='ACTIONS_ARTIFACT_UPLOAD',reference_id=None,
            artifact_id=event.artifact_id,target=self.upload['plan'].artifact_name,
            fact={'kind':'UPLOAD_OUTCOME_UNKNOWN','emitted':True,'reconciliation':'UNCONFIRMED'})

    def observe(self, event, binding, *, before_effect):
        before_effect()
        if not self.recognized or self.snapshot is None or self._scope(binding.snapshot)!=self._scope(self.snapshot):return None
        if binding.context is None or asdict(binding.context)!=self.context:return None
        if event.phase=='REMOTE_UPLOAD':record=self._composed_upload(event)
        elif event.phase=='REMOTE_RECONSTRUCTION':
            record=next((r for r in self.verification_records
                         if (r.get('source') is event.source or r.get('source_matches',lambda value:False)(event.source))
                         and r['subject_matches'](event.subject) and r['fact']==event.fact),None)
        elif event.phase=='SOURCE_ACQUISITION':
            record=next((r for r in self.records if r.get('process') is event.source
                         and r['phase']=='SOURCE_ACQUISITION' and r['operation']==event.operation
                         and tuple(r['arguments'])==event.subject[1] and r['target']==event.subject[0]
                         and r['timed_out'] and r['process'].poll() is not None),None)
        else:record=self._actual_record(event)
        if record is None:return None
        if event.phase not in {'REMOTE_UPLOAD','REMOTE_RECONSTRUCTION'} and not self._target_matches(record,self.snapshot,event.reference_id):return None
        if record['fact']!=event.fact or record.get('reference_id')!=event.reference_id:return None
        if event.phase.startswith('REMOTE_'):
            if self.packet_id is None or binding.original_packet_id!=self.packet_id:return None
            if self.upload is None or not self.upload['emitted']:return None
            plan=self.upload['plan']
            if (plan.artifact_name!=prepared_artifact_name_v3(self.snapshot.claim_ref,self.snapshot.record.control.worker.run_id,1)
                    or asdict(plan.worker_context)!=self.context):return None
            if event.artifact_id is not None and event.artifact_id!=self.upload.get('artifact_id'):return None
        a,c=self.snapshot.record.attempt,self.snapshot.record.control
        value=dict(schema_version=1,evidence_type='pre-model-preparation-failure-observation',
            repository=self.snapshot.repository,repository_node_id=self.snapshot.repository_node_id,
            claim_ref=self.snapshot.claim_ref,admitted_commit_sha=self.snapshot.commit_sha,
            request_id=a.request_id,attempt_id=a.attempt_id,admission_evidence_id=a.admission['admission_evidence_id'],
            generation=1,reservation_id=c.reservation_id,workflow_run_id=c.worker.run_id,workflow_run_attempt=1,
            phase=record['phase'],operation=record['operation'],reference_id=record.get('reference_id'),
            packet_id=self.packet_id if event.phase.startswith('REMOTE_') else None,
            artifact_name=prepared_artifact_name_v3(self.snapshot.claim_ref,c.worker.run_id,1) if event.phase.startswith('REMOTE_') else None,
            artifact_id=event.artifact_id,fact=record['fact'],observed_at=STAMP)
        try: observation=FailureObservationV3.from_value(value)
        except ValueError:return None
        proof=dict(scope=self._scope(self.snapshot),context=self.context,observation=value,
            actual_target=record['target'],actual_query=record.get('query',''),
            actual_origin=record.get('origin'),authenticated=record.get('authenticated'),original_packet_id=self.packet_id,
            budget=asdict(BUDGET) if event.phase.startswith('REMOTE_') else None)
        path=self.root/observation.evidence_id.rsplit(':',1)[-1]
        before_effect()
        if not path.exists():
            before_effect(); private_write(path,canonical_bytes(proof)+b'\n')
        self.observations.append(observation)
        return observation

    def _read_proof(self, evidence_id, before_effect):
        if not self.recognized:raise FailureEvidenceRejectedV3('fixture origin recognition withdrawn')
        path=self.root/evidence_id.rsplit(':',1)[-1]
        before_effect()
        if not self.root.exists():raise FailureEvidenceUnavailableV3('fixture external origin archive unavailable')
        before_effect()
        if not path.exists():raise FailureEvidenceRejectedV3('no independently measured execution')
        before_effect();return json.loads(path.read_bytes())

    def verify(self, observation, binding, *, before_effect):
        proof=self._read_proof(observation.evidence_id,before_effect)
        if (proof['scope']!=self._scope(binding.snapshot)
                or proof['observation']!=observation.value
                or binding.original_packet_id!=proof['original_packet_id'] and observation.value['phase'].startswith('REMOTE_')
                or binding.context is not None and asdict(binding.context)!=proof['context']):
            raise FailureEvidenceRejectedV3('fixture independent origin/bindings mismatch')
        value=observation.value
        record=dict(phase=value['phase'],operation=value['operation'],target=proof['actual_target'],query=proof.get('actual_query',''),
                    origin=proof.get('actual_origin'),authenticated=proof.get('authenticated'),artifact_id=value['artifact_id'])
        if value['phase'] in {'REFERENCE_READ','SOURCE_ACQUISITION','REMOTE_READ'} and not self._target_matches(record,binding.snapshot,value['reference_id']):
            raise FailureEvidenceRejectedV3('fixture actual executed target differs')

    def historical_binding(self, snapshot, evidence_id, *, before_effect):
        from review_broker.prepared_artifact_transport_v3 import PreparedArtifactBudgetV3
        proof=self._read_proof(evidence_id,before_effect)
        if proof['scope']!=self._scope(snapshot):raise FailureEvidenceRejectedV3('fixture historical A differs')
        return FailureObservationBindingV3(snapshot,original_packet_id=proof['original_packet_id'],
            budget=None if proof['budget'] is None else PreparedArtifactBudgetV3(**proof['budget']))
