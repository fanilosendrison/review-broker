"""Original live HTTP/child facts, distinct from observation retention and payload hashes."""
from datetime import datetime,timezone
import json
from urllib.parse import urlsplit

from .pre_model_failure_observation_v3 import FailureObservationV3
from .pre_model_failure_evidence_v3 import FailureEvidenceUnavailableV3,FailureEvidenceRejectedV3
from .github_actions_failure_archive_v3 import GitHubActionsFailureObservationArchiveV3


class LiveFailureOriginV3:
    """Owned transport execution records only. No archive put can populate provenance.

    The active corpus is intentionally not a historical origin service. After
    restart, unavailable original cause evidence stays unavailable; an Artifact
    alone never creates recognition or BLOCKED permission.
    """
    def __init__(self):
        self.http_records={};self.known={};self.prepared_started=False;self.packet_id=None
        self.timeouts={};self.resolutions={};self.streams={};self.artifacts={};self.transfers={}

    def http(self,request,response):
        self.http_records[id(request)]=(request,response.status)
        if response.status==302:
            path=urlsplit(request.full_url).path
            if '/actions/artifacts/' in path:
                identifier=path.split('/')[-2]
                for k,v in response.headers.items():
                    if k.lower()=='location':self.resolutions[v]=identifier
        if response.status==200 and urlsplit(request.full_url).path.endswith('/artifacts'):
            try:
                for row in json.loads(response.body)['artifacts']:self.artifacts[str(row['id'])]=row
            except (KeyError,TypeError,ValueError):pass

    def read_timeout(self,request):self.timeouts[id(request)]=request

    def stream_complete(self,request,size,digest):
        identifier=self.resolutions.get(request.full_url)
        if identifier is not None:self.streams[identifier]=(size,'artifact:sha256:'+digest)

    def transfer_started(self,repository,operation,arguments,process):
        clone=(operation=='GIT_CLONE' and tuple(arguments[:4])==('gh','repo','clone',f'https://github.com/{repository}.git')
            and '--no-checkout' in arguments)
        fetch=(operation=='GIT_FETCH' and len(arguments)>4 and arguments[0]=='git'
            and arguments[1]=='-C' and tuple(arguments[3:5])==('fetch','origin'))
        if clone or fetch:self.transfers[id(process)]=(repository,operation,arguments,process,False)

    def transfer_terminated(self,process):
        value=self.transfers.get(id(process))
        if value is not None and value[3] is process and process.poll() is not None:
            self.transfers[id(process)]=(*value[:4],True)

    def child_started(self,pid):
        if type(pid) is not int or pid<1:raise ValueError('ARTIFACT_CHILD_START_NOT_OBSERVED')
        self.prepared_started=True

    def observe(self,event,binding,*,before_effect):
        before_effect();v=event.fact;recognized=False
        if v.get('kind')=='HTTP_STATUS' and event.phase in {'REFERENCE_READ','REMOTE_READ'}:
            record=self.http_records.get(id(event.subject))
            if record and record[0] is event.subject and record[1]==v['status']:
                uri=urlsplit(event.subject.full_url)
                if uri.scheme=='https' and uri.netloc=='api.github.com':
                    if event.phase=='REFERENCE_READ':
                        refs=binding.snapshot.record.attempt.admission['canonical_request']['references']
                        reference=next((r for r in refs if r['id']==event.reference_id),None)
                        if reference:
                            source=reference['source']
                            tail=(f"/issues/{source['issue']}" if source['kind']=='github_issue_body'
                                  else f"/issues/comments/{source['comment_id']}")
                            recognized=uri.path=='/repos/'+binding.snapshot.repository+tail
                    else:
                        run=binding.snapshot.record.control.worker.run_id
                        recognized=(uri.path==f'/repos/{binding.snapshot.repository}/actions/runs/{run}/artifacts'
                            or uri.path.startswith(f'/repos/{binding.snapshot.repository}/actions/artifacts/'))
        elif v.get('kind')=='READ_TIMEOUT' and event.phase=='REMOTE_READ':
            request=event.subject[0] if isinstance(event.subject,tuple) else event.subject
            if self.timeouts.get(id(request)) is request:
                uri=urlsplit(request.full_url)
                recognized=(uri.netloc=='api.github.com' and '/actions/' in uri.path
                    or self.resolutions.get(request.full_url)==event.artifact_id)
        elif v.get('kind')=='TRANSFER_TIMEOUT' and event.phase=='SOURCE_ACQUISITION':
            repository,operation,arguments,process=event.subject[0],event.operation,event.subject[1],event.source
            record=self.transfers.get(id(process))
            recognized=(record is not None and record[:4]==(repository,operation,arguments,process)
                and record[4] is True and repository==binding.snapshot.repository)
        elif v.get('kind')=='VERIFICATION_FAILED' and v.get('check')=='ARCHIVE_BYTES':
            row=self.artifacts.get(event.artifact_id);stream=self.streams.get(event.artifact_id)
            recognized=(row is not None and stream is not None
                and v['expected_id']=='artifact:'+row.get('digest','')
                and v['expected_size']==row.get('size_in_bytes')
                and v['observed_size']==stream[0] and v['observed_id']==stream[1])
        elif v.get('kind')=='UPLOAD_OUTCOME_UNKNOWN' and event.phase=='REMOTE_UPLOAD':
            recognized=self.prepared_started and binding.original_packet_id==self.packet_id
        if not recognized:return None
        a=binding.snapshot;c=a.record.control
        value=dict(schema_version=1,evidence_type='pre-model-preparation-failure-observation',
            repository=a.repository,repository_node_id=a.repository_node_id,claim_ref=a.claim_ref,
            admitted_commit_sha=a.commit_sha,request_id=a.record.attempt.request_id,
            attempt_id=a.record.attempt.attempt_id,admission_evidence_id=a.record.attempt.admission['admission_evidence_id'],
            generation=1,reservation_id=c.reservation_id,workflow_run_id=c.worker.run_id,workflow_run_attempt=1,
            phase=event.phase,operation=event.operation,reference_id=event.reference_id,
            packet_id=binding.original_packet_id,artifact_name=None,artifact_id=event.artifact_id,
            fact=v,observed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        if event.phase.startswith('REMOTE_'):
            from .remote_prepared_receipt_v3 import prepared_artifact_name_v3
            value['artifact_name']=prepared_artifact_name_v3(a.claim_ref,c.worker.run_id,1)
        observation=FailureObservationV3.from_value(value)
        binding.require(observation)
        self.known[observation.evidence_id]=(observation.canonical_bytes,binding.snapshot)
        return observation

    def verify(self,observation,binding,*,before_effect):
        before_effect();binding.require(observation)
        if self.known.get(observation.evidence_id)!=(observation.canonical_bytes,binding.snapshot):
            raise FailureEvidenceRejectedV3('ORIGINAL_LIVE_FAILURE_NOT_RECOGNIZED')

    def historical_binding(self,*args,**kwargs):
        raise FailureEvidenceUnavailableV3('ORIGINAL_LIVE_EXECUTION_CORPUS_UNAVAILABLE_AFTER_RESTART')


class OriginalFailureArchiveRouterV3:
    """Select the real Artifact backend from the genuine original A, never payload authority."""
    def __init__(self,*,child,adapter,context):
        self.child,self.adapter,self.context=child,adapter,context
        self.snapshot=None;self.packet_id=None;self.archive=None

    def _get(self):
        if self.snapshot is None:raise ValueError('NO_ORIGINAL_ADMITTED_FAILURE_ARCHIVE')
        if self.archive is None:
            self.archive=GitHubActionsFailureObservationArchiveV3(child=self.child,adapter=self.adapter,
                snapshot=self.snapshot,active_context=self.context,original_packet_id=self.packet_id)
        return self.archive

    def put_once(self,evidence_id,raw,*,before_effect):
        before_effect();return self._get().put_once(evidence_id,raw,before_effect=before_effect)

    def read(self,evidence_id,*,max_bytes,before_effect):
        before_effect();return self._get().read(evidence_id,max_bytes=max_bytes,before_effect=before_effect)
