"""Real local packet/evidence/ZIP/JWT fixtures with injected read-only Actions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
from unittest.mock import patch
import zipfile

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import test_evidence
from review_broker import github_oidc
from review_broker.artifact_locator import build_evidence_artifact_plan, build_evidence_artifact_locator
from review_broker.evidence import TERMINAL_CAPTURE_FILES, build_terminal_capture_receipt
from review_broker.identity import canonical_bytes
from review_broker.oidc_subject import immutable_repository_subject
from review_broker.publication import build_review_result, result_identity, render_result_comment
from review_broker.validation import validate_evidence
from rb91_full_abi_fixtures import prepared, metadata
from rb91_full_abi_model import publication_identity
from rb91_jch_contract_model import artifact, fixture_armed, fixture_transition
from rb91_result_reference_model import execution_projection, storage_audience
from rb91_storage_provenance_model import StoragePolicy, authorization_receipt


def archive(directory):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(Path(directory).rglob('*')):
            if path.is_file():bundle.writestr(path.relative_to(directory).as_posix(),path.read_bytes())
    return buffer.getvalue()


def replace_last_evidence(record, value):
    record['history'][-1]['evidence_ids'] = [value]
    record['evidence_ids'][-1] = value


class StorageCase:
    def __init__(self, root, *, recovery=True, attempt='1', same_run=False, verdict='GO', repository_id=None):
        self.root = Path(root)
        self.repository = 'sample/broker'
        source = self.root/'source'
        ready = prepared()
        if repository_id is not None:ready['admission_authority']['broker_repository_id']=repository_id
        admission = ready['admission']
        real_packet = test_evidence.build_packet
        def packet(records, **kwargs):
            kwargs.update(request_id=ready['request_id'],subject_id=admission['subject_id'],
                mission_instruction=admission['request']['mission']['instructions'],
                profile=dict(id=admission['request']['policy']['profile'],version=1))
            return real_packet(records,**kwargs)
        with patch.object(test_evidence,'build_packet',side_effect=packet):
            manifest = test_evidence.EvidenceValidationTests().fixture(source,terminal=False,
                attempt_overrides=dict(attempt_id=ready['attempt_id'],model_requested='gpt-5.6-sol',reasoning_effort_requested='xhigh'))
        broker = json.loads((source/'broker-metadata.json').read_bytes())
        broker.update(attempt_id=ready['attempt_id'],executing_broker_sha='e'*40)
        (source/'broker-metadata.json').write_bytes(canonical_bytes(broker)+b'\n')
        events = [json.loads(line) for line in (source/'codex-events.jsonl').read_text().splitlines()]
        if verdict != 'GO':
            final = json.loads((source/'codex-final.json').read_text());final['verdict'] = verdict
            final_text = json.dumps(final,separators=(',',':'))
            (source/'codex-final.json').write_text(final_text);events[1]['item']['text'] = final_text
        events.append(dict(type='turn.completed'))
        (source/'codex-events.jsonl').write_text('\n'.join(json.dumps(event) for event in events)+'\n')
        raw_input = (source/'input.txt').read_bytes();text = raw_input.decode()
        cap = ready['input_capacity']
        cap.update(packet_id=manifest['packet_id'],input_sha256=hashlib.sha256(raw_input).hexdigest(),
            unicode_scalar_characters=len(text),utf16_code_units=len(text.encode('utf-16-le'))//2,
            utf8_bytes=len(raw_input),capacity_units=len(raw_input))
        replace_last_evidence(ready,artifact(cap))
        armed = fixture_armed(ready)
        armed['arm_binding'].update(subject_id=admission['subject_id'],
            broker_repository_id=ready['admission_authority']['broker_repository_id'],workflow_ref=self.repository+'/.github/workflows/review-request.yml@refs/heads/dev')
        armed['history'][-1]['binding_sha256'] = hashlib.sha256(canonical_bytes(armed['arm_binding'])).hexdigest()
        self.armed = deepcopy(armed)
        context = dict(workflow_run_id=armed['arm_binding']['controller_run_id'],workflow_run_attempt='1')
        recovery_manifest = json.loads((source/'recovery-manifest.json').read_bytes())
        recovery_manifest.update(attempt_id=ready['attempt_id'],context=context)
        recovery_manifest['artifacts'] = {name:dict(recovered=True,artifact_id=artifact_bytes((source/name).read_bytes()),
            byte_length=(source/name).stat().st_size) for name in TERMINAL_CAPTURE_FILES}
        (source/'recovery-manifest.json').write_bytes(canonical_bytes(recovery_manifest)+b'\n')
        capture = build_terminal_capture_receipt(source,request_id=ready['request_id'],attempt_id=ready['attempt_id'],
            packet_id=manifest['packet_id'],context=context,observed_at='2026-11-09T00:00:00Z')
        (source/'terminal-capture.json').write_bytes(canonical_bytes(capture)+b'\n')
        (source/'resolved-request.json').write_bytes(canonical_bytes(admission)+b'\n')
        plan = build_evidence_artifact_plan(source,broker_repository=self.repository,artifact_name='synthetic-terminal',
            workflow_run_id=context['workflow_run_id'],workflow_run_attempt='1')
        terminal_zip = archive(source)
        validation = validate_evidence(source)
        if validation['evidence_status'] != 'VALID':raise AssertionError(validation['validation_reasons'])
        now = datetime.now(timezone.utc)
        def meta(identifier,name,data,run,sha):
            return dict(id=identifier,name=name,digest='sha256:'+hashlib.sha256(data).hexdigest(),expired=False,
                size_in_bytes=len(data),created_at=(now-timedelta(seconds=30)).isoformat(),
                expires_at=(now+timedelta(days=1)).isoformat(),workflow_run=dict(id=int(run),head_sha=sha))
        original = armed['arm_binding']
        terminal_meta = meta(11,plan['artifact_name'],terminal_zip,context['workflow_run_id'],original['workflow_sha'])
        locator = build_evidence_artifact_locator(plan,terminal_meta,declared_digest=terminal_meta['digest'])
        terminal = fixture_transition(armed,'TERMINAL_CAPTURED');replace_last_evidence(terminal,artifact(capture))
        planned = metadata(terminal,'evidence_locator_plan',plan,'EVIDENCE_LOCATOR_PLANNED')
        located = metadata(planned,'evidence_locator',locator,'EVIDENCE_LOCATOR_RECORDED')
        validated = fixture_transition(located,'VALIDATED');replace_last_evidence(validated,artifact(validation))
        mode = 'recovery' if recovery else 'original'
        separate_run = recovery and not same_run
        workflow_path = '.github/workflows/publication-recovery.yml' if separate_run else '.github/workflows/review-request.yml'
        workflow_sha = '9'*40 if separate_run else original['workflow_sha']
        run_id = '900001' if separate_run else original['controller_run_id']
        actor = dict(login='operator',id=21)
        storage = dict(mode=mode,workflow_ref=self.repository+'/'+workflow_path+'@refs/heads/dev',workflow_sha=workflow_sha,
            run_id=run_id,run_attempt=attempt,job_id=101,job_name='retain-result',actor=actor,triggering_actor=actor,
            authorization_receipt_id='artifact:sha256:'+'0'*64,authorization=None)
        result = build_review_result(admission,manifest,json.loads((source/'attempt.json').read_bytes()),validation,current_head='a'*40)
        self.raw = canonical_bytes(result)+b'\n'
        result_dir = self.root/'result-source';result_dir.mkdir();(result_dir/'review-result.json').write_bytes(self.raw)
        result_zip = archive(result_dir)
        result_meta = meta(12,'synthetic-result',result_zip,run_id,workflow_sha)
        pointer = dict(artifact_id=artifact_bytes(self.raw),byte_length=len(self.raw),media_type='application/json',contract='review-result-v1',
            execution=execution_projection(validated,'a'*40),storage=storage,
            location=dict(broker_repository=self.repository,workflow_run_id=run_id,workflow_run_attempt=attempt,
                actions_artifact_id=12,artifact_name='synthetic-result',archive_digest=result_meta['digest'],path='review-result.json'))
        workflow = dict(workflow_ref=storage['workflow_ref'],workflow_sha=workflow_sha,path=workflow_path,
                        job_name=storage['job_name'],upload_step='Upload validated result',events=['workflow_dispatch'])
        workflows = {mode:workflow}
        self.policy = StoragePolicy(self.repository,original['broker_repository_id'],'30498238','refs/heads/dev',
            workflows,frozenset({21}),deepcopy(validated),'a'*40)
        storage['authorization'] = authorization_receipt(pointer,self.policy)
        storage['authorization_receipt_id'] = artifact(storage['authorization'])
        intent = dict(schema_version=2,evidence_type='jch-result-publication-intent-v2',issue_number=7,
            request_id=ready['request_id'],attempt_id=ready['attempt_id'],result_id=result_identity(result),result_artifact=pointer,
            publisher=dict(login='broker',id=9),nonce='f'*64,reserved_at=now.isoformat())
        self.record = metadata(validated,'publication_intent',intent,'PUBLICATION_RESERVED')
        self.reseal()
        self.key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()));public.update(kid='synthetic',alg='RS256',use='sig')
        self.jwks = dict(keys=[public])
        repo = dict(id=int(self.policy.repository_id),full_name=self.repository)
        run = dict(id=int(run_id),run_attempt=int(attempt),repository=deepcopy(repo),head_sha=workflow_sha,path=workflow_path,
            head_branch='dev',event='workflow_dispatch',actor=actor,triggering_actor=actor)
        step = dict(name='Upload validated result',status='completed',conclusion='success',
            started_at=(now-timedelta(seconds=60)).isoformat(),completed_at=(now-timedelta(seconds=10)).isoformat())
        job = dict(id=101,run_id=int(run_id),run_attempt=int(attempt),head_sha=workflow_sha,name=storage['job_name'],
            status='in_progress',conclusion=None,steps=[step])
        base='repos/'+self.repository
        self.responses = {base:repo,base+'/actions/runs/'+run_id+'/attempts/'+attempt:run,
            base+'/actions/runs/'+run_id+'/attempts/'+attempt+'/jobs?per_page=100':dict(total_count=1,jobs=[job]),
            base+'/actions/artifacts/11':terminal_meta,base+'/actions/artifacts/12':result_meta,
            base+'/actions/artifacts/11/zip':terminal_zip,base+'/actions/artifacts/12/zip':result_zip}
        self.calls = []

    def reseal(self):
        intent=self.record['publication_intent'];intent['publication_id']=publication_identity(intent)
        intent['comment_body_sha256']=hashlib.sha256(render_result_comment(json.loads(self.raw),publication_id=intent['publication_id']).encode()).hexdigest()
        replace_last_evidence(self.record,artifact(intent))

    def resign_reference(self):
        pointer=self.record['publication_intent']['result_artifact']
        pointer['storage']['authorization']=authorization_receipt(pointer,self.policy)
        pointer['storage']['authorization_receipt_id']=artifact(pointer['storage']['authorization'])
        self.reseal()

    def rebind_result(self, result):
        self.raw=canonical_bytes(result)+b'\n'
        (self.root/'result-source/review-result.json').write_bytes(self.raw)
        data=archive(self.root/'result-source')
        base='repos/'+self.repository+'/actions/artifacts/12'
        self.responses[base+'/zip']=data
        self.responses[base].update(digest='sha256:'+hashlib.sha256(data).hexdigest(),size_in_bytes=len(data))
        intent=self.record['publication_intent'];pointer=intent['result_artifact']
        pointer.update(artifact_id=artifact_bytes(self.raw),byte_length=len(self.raw))
        pointer['location']['archive_digest']=self.responses[base]['digest']
        intent['result_id']=result_identity(result)
        self.resign_reference()

    def corrupt_terminal_quote_with_consistent_hashes(self):
        source=self.root/'source'
        (source/'validation.json').unlink()
        final=json.loads((source/'codex-final.json').read_text())
        final['findings'][0]['evidence'][0]['quote']='not in the retained source'
        text=json.dumps(final,separators=(',',':'))
        (source/'codex-final.json').write_text(text)
        events=[json.loads(line) for line in (source/'codex-events.jsonl').read_text().splitlines()]
        events[1]['item']['text']=text
        (source/'codex-events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
        capture=json.loads((source/'terminal-capture.json').read_bytes())
        for name in TERMINAL_CAPTURE_FILES:
            raw=(source/name).read_bytes()
            capture['artifacts'][name]=dict(sha256=hashlib.sha256(raw).hexdigest(),byte_length=len(raw))
        (source/'terminal-capture.json').write_bytes(canonical_bytes(capture)+b'\n')
        old=self.policy.execution_snapshot;plan=deepcopy(old['evidence_locator_plan'])
        for name in plan['artifacts']:
            raw=(source/name).read_bytes();plan['artifacts'][name]=dict(artifact_id=artifact_bytes(raw),byte_length=len(raw))
        data=archive(source);base='repos/'+self.repository+'/actions/artifacts/11'
        self.responses[base+'/zip']=data
        self.responses[base].update(digest='sha256:'+hashlib.sha256(data).hexdigest(),size_in_bytes=len(data))
        locator=build_evidence_artifact_locator(plan,self.responses[base],declared_digest=self.responses[base]['digest'])
        mapping={artifact(old['evidence_locator_plan']):artifact(plan),artifact(old['evidence_locator']):artifact(locator)}
        # Locate the terminal event by kind rather than relying on fixture order.
        terminal_id=next(e['evidence_ids'][0] for e in old['history'] if e.get('state')=='TERMINAL_CAPTURED')
        mapping[terminal_id]=artifact(capture)
        for record in (self.record,old):
            record['evidence_locator_plan']=deepcopy(plan);record['evidence_locator']=deepcopy(locator)
            record['evidence_ids']=[mapping.get(x,x) for x in record['evidence_ids']]
            for event in record['history']:event['evidence_ids']=[mapping.get(x,x) for x in event['evidence_ids']]
        self.policy=replace(self.policy,execution_snapshot=deepcopy(old))
        self.record['publication_intent']['result_artifact']['execution']=execution_projection(old,self.policy.arm_commit_sha)
        self.resign_reference()

    def token(self, **overrides):
        pointer=self.record['publication_intent']['result_artifact'];s=pointer['storage'];p=self.policy
        now=int(time.time())
        claims=dict(iss=github_oidc.ISSUER,aud=storage_audience(pointer),iat=now,nbf=now,exp=now+300,jti='synthetic-storage',
            repository=p.repository,repository_id=p.repository_id,repository_owner_id=p.owner_id,repository_owner=p.repository.split('/')[0],
            ref=p.ref,workflow_ref=s['workflow_ref'],workflow_sha=s['workflow_sha'],sha=s['workflow_sha'],
            run_id=s['run_id'],run_attempt=s['run_attempt'],actor=s['actor']['login'],actor_id=str(s['actor']['id']),
            sub=immutable_repository_subject(p.repository,p.repository_id,p.owner_id,p.ref))
        claims.update(overrides)
        return jwt.encode(claims,self.key,algorithm='RS256',headers=dict(kid='synthetic'))

    def issuer(self,url):
        if url == github_oidc.DISCOVERY:return dict(issuer=github_oidc.ISSUER,jwks_uri=github_oidc.JWKS)
        if url == github_oidc.JWKS:return deepcopy(self.jwks)
        raise AssertionError('unexpected issuer endpoint')

    def runner(self,command,**kwargs):
        self.calls.append(list(command))
        if command[:2] != ['gh','api'] or len(command)!=3:raise AssertionError('read-only Actions API only')
        value=self.responses.get(command[2])
        if value is None:return subprocess.CompletedProcess(command,1,'','synthetic unavailable')
        output=value if isinstance(value,bytes) else json.dumps(value)
        return subprocess.CompletedProcess(command,0,output,'')


def artifact_bytes(raw):
    return 'artifact:sha256:'+hashlib.sha256(raw).hexdigest()
