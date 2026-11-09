"""Offline F1 admission model using real issuer, artifact and evidence validators.

All network calls are injected in tests. This is not a production adapter or
an operational proof. Policy and execution snapshot enter from trusted context,
never from the result reference, packet, job inputs or reviewer output.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
import json
from pathlib import Path

from review_broker.artifact_locator import GitHubActionsArtifactStore, build_evidence_artifact_locator
from review_broker.evidence import validate_terminal_capture_receipt
from review_broker.github_oidc import verify_github_identity
from review_broker.identity import canonical_bytes
from review_broker.oidc_subject import immutable_repository_subject
from review_broker.publication import build_review_result
from review_broker.validation import validate_evidence
from rb91_full_abi_model import validate, validate_result_bytes
from rb91_jch_contract_model import artifact
from rb91_result_reference_model import require, storage_audience, storage_receipt


@dataclass(frozen=True)
class StoragePolicy:
    repository: str
    repository_id: str
    owner_id: str
    ref: str
    # Heterogeneous trusted policy/provider JSON is confronted below; the
    # journal/result reference itself has the closed executable schema.
    workflows: dict
    actors: frozenset[int]
    execution_snapshot: dict
    arm_commit_sha: str


def authorization_receipt(pointer, policy):
    basis = dict(repository=policy.repository,repository_id=policy.repository_id,owner_id=policy.owner_id,
                 ref=policy.ref,workflows=policy.workflows,actors=sorted(policy.actors),
                 recovery_scope=dict(request_id=policy.execution_snapshot['request_id'],
                    attempt_id=policy.execution_snapshot['attempt_id'],arm_commit_sha=policy.arm_commit_sha,
                    terminal_locator_id=artifact(policy.execution_snapshot['evidence_locator'])))
    return storage_receipt(pointer,artifact(basis))


def instant(text):
    value = datetime.fromisoformat(text.replace('Z','+00:00'))
    require(value.tzinfo is not None, 'OBSERVATION_TIME')
    return value


class ScopedArtifactStore(GitHubActionsArtifactStore):
    """Confront source/run metadata on EVERY read, including inherited download reads."""
    def __init__(self, repository, runner, bindings, repository_id):
        super().__init__(repository,runner=runner)
        self.bindings = bindings
        self.repository_id = repository_id

    def _json(self, endpoint):
        value = super()._json(endpoint)
        for identifier, (run_id, source_sha) in self.bindings.items():
            if endpoint == f'repos/{self.repository}/actions/artifacts/{identifier}':
                require(type(value.get('id')) is int and value['id'] == identifier, 'ARTIFACT_IDENTITY')
                observed = value['workflow_run']
                require(type(observed['id']) is int and str(observed['id']) == run_id and
                        observed['head_sha'] == source_sha, 'ARTIFACT_SOURCE_CONTEXT')
                for field in ('repository_id','head_repository_id'):
                    if field in observed:
                        require(type(observed[field]) is int and str(observed[field]) == self.repository_id,
                                'ARTIFACT_REPOSITORY_CONTEXT')
        return value


def verify_faithful_projection(result, record, terminal, validation):
    """Reuse accepted result construction; do not mistake embedded validation for its projection."""
    manifest = json.loads((terminal/'input-manifest.json').read_bytes())
    attempt = json.loads((terminal/'attempt.json').read_bytes())
    rebuilt = build_review_result(record['admission'],manifest,attempt,validation,
                                 current_head=result['applicability']['checked_head_commit'])
    for field, expected in rebuilt.items():
        if field == 'reviewer':
            # Preserve additional non-authoritative metadata allowed by public v1.
            for key, value in expected.items():
                require(canonical_bytes(result[field][key]) == canonical_bytes(value), 'RESULT_REVIEWER_PROJECTION')
        else:
            require(canonical_bytes(result[field]) == canonical_bytes(expected), 'RESULT_EVIDENCE_PROJECTION')


def _verify_job(pointer, policy, store):
    storage, location = pointer['storage'], pointer['location']
    mode = storage['mode']
    allowed = policy.workflows[mode]
    require((storage['workflow_ref'],storage['workflow_sha'],storage['job_name']) ==
            (allowed['workflow_ref'],allowed['workflow_sha'],allowed['job_name']), 'STORAGE_WORKFLOW_NOT_ALLOWED')
    require(storage['actor']['id'] in policy.actors and storage['triggering_actor']['id'] in policy.actors,
            'STORAGE_ACTOR_NOT_ALLOWED')
    base = 'repos/' + policy.repository
    repo = store._json(base)
    require(repo['full_name'] == policy.repository and str(repo['id']) == policy.repository_id, 'OBSERVED_REPOSITORY')
    run = store._json(base + '/actions/runs/' + storage['run_id'] + '/attempts/' + storage['run_attempt'])
    require(str(run['id']) == storage['run_id'] and str(run['run_attempt']) == storage['run_attempt'], 'OBSERVED_STORAGE_RUN')
    require(run['repository']['id'] == repo['id'] and run['repository']['full_name'] == policy.repository,
            'RUN_REPOSITORY')
    require(run['head_sha'] == allowed['workflow_sha'] and run['path'] == allowed['path'] and
            run['head_branch'] == policy.ref.removeprefix('refs/heads/'), 'OBSERVED_WORKFLOW')
    require(run['event'] in allowed['events'], 'STORAGE_EVENT_NOT_ALLOWED')
    for field in ('actor','triggering_actor'):
        observed = {key:run[field][key] for key in ('login','id')}
        require(canonical_bytes(observed) == canonical_bytes(storage[field]), 'OBSERVED_ACTOR')
    response = store._json(base + '/actions/runs/' + storage['run_id'] + '/attempts/' + storage['run_attempt'] + '/jobs?per_page=100')
    jobs = response['jobs']
    require(type(response['total_count']) is int and response['total_count'] == len(jobs) <= 100, 'JOB_SCAN_INCOMPLETE')
    named = [j for j in jobs if j['name'] == allowed['job_name']]
    require(len(named) == 1, 'STORAGE_JOB_AMBIGUOUS')
    job = named[0]
    require(type(job['id']) is int and job['id'] == storage['job_id'] and str(job['run_id']) == storage['run_id'] and
            str(job['run_attempt']) == storage['run_attempt'] and job['head_sha'] == allowed['workflow_sha'], 'OBSERVED_JOB')
    require(job['status'] == 'in_progress' or job['status'] == 'completed' and job['conclusion'] == 'success', 'JOB_NOT_USABLE')
    steps = [s for s in job['steps'] if s['name'] == allowed['upload_step']]
    require(len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success', 'UPLOAD_STEP')
    metadata = store._json(base + '/actions/artifacts/' + str(location['actions_artifact_id']))
    require(metadata['id'] == location['actions_artifact_id'] and metadata['name'] == location['artifact_name'] and
            metadata['digest'] == location['archive_digest'] and metadata['expired'] is False, 'OBSERVED_ARTIFACT')
    require(instant(steps[0]['started_at']) <= instant(metadata['created_at']) <= instant(steps[0]['completed_at']),
            'ARTIFACT_UPLOAD_WINDOW')
    return metadata


def verify_storage(record, policy, *, token, issuer_reader, runner, destination):
    """Authenticate BEFORE reservation; signature/bytes never authorize a model."""
    try:
        require(callable(issuer_reader) and callable(runner), 'INJECTED_TRANSPORT_REQUIRED')
        record = deepcopy(record)
        policy = replace(policy,workflows=deepcopy(policy.workflows),execution_snapshot=deepcopy(policy.execution_snapshot))
        require(type(policy.actors) is frozenset and bool(policy.actors) and
                all(type(actor) is int and 0 < actor <= 9007199254740991 for actor in policy.actors), 'POLICY_ACTOR_TYPES')
        validate(record)
        pointer = record['publication_intent']['result_artifact']
        snapshot = policy.execution_snapshot
        require(snapshot['state'] == 'VALIDATED' and record['history'][:len(snapshot['history'])] == snapshot['history'],
                'VALIDATED_SNAPSHOT')
        for key in ('request_id','attempt_id','admission','arm_binding','input_capacity','evidence_locator_plan','evidence_locator'):
            require(canonical_bytes(record[key]) == canonical_bytes(snapshot[key]), 'EXECUTION_SNAPSHOT_CHANGED')
        execution, storage, location = (pointer[k] for k in ('execution','storage','location'))
        require(execution['arm_commit_sha'] == policy.arm_commit_sha, 'ARM_COMMIT_NOT_AUTHENTICATED')
        require(location['broker_repository'] == policy.repository and
                execution['broker_repository_id'] == policy.repository_id, 'STORAGE_REPOSITORY')
        expected = dict(repository=policy.repository,repository_id=policy.repository_id,repository_owner_id=policy.owner_id,
            repository_owner=policy.repository.split('/')[0],ref=policy.ref,
            workflow_ref=storage['workflow_ref'],workflow_sha=storage['workflow_sha'],sha=storage['workflow_sha'],
            run_id=storage['run_id'],run_attempt=storage['run_attempt'],actor=storage['actor']['login'],actor_id=str(storage['actor']['id']))
        expected['sub'] = immutable_repository_subject(policy.repository,policy.repository_id,policy.owner_id,policy.ref)
        verify_github_identity(token,audience=storage_audience(pointer),expected_claims=expected,
                               issuer_reader=issuer_reader,allow_thumbprints=True)
        original_artifact = snapshot['evidence_locator']['artifact_id']
        result_artifact = location['actions_artifact_id']
        require(original_artifact != result_artifact, 'ARTIFACT_ROLE_ALIAS')
        store = ScopedArtifactStore(policy.repository,runner,{
            original_artifact:(execution['controller_run_id'],execution['controller_workflow_sha']),
            result_artifact:(storage['run_id'],policy.workflows[storage['mode']]['workflow_sha'])},policy.repository_id)
        metadata = _verify_job(pointer,policy,store)
        terminal = Path(destination) / 'terminal'
        store.download(snapshot['evidence_locator'],terminal)
        capture = json.loads((terminal/'terminal-capture.json').read_bytes())
        require(validate_terminal_capture_receipt(capture,request_id=record['request_id'],attempt_id=record['attempt_id']) ==
                execution['terminal_capture_id'], 'TERMINAL_CAPTURE_ID')
        require(capture['packet_id'] == execution['packet_id'] and capture['context'] == dict(
            workflow_run_id=execution['controller_run_id'],workflow_run_attempt=execution['controller_run_attempt']), 'TERMINAL_EXECUTION_CONTEXT')
        validation = validate_evidence(terminal)
        require(validation['evidence_status'] == 'VALID' and artifact(validation) == execution['validation_id'], 'VALIDATION_EVIDENCE')
        plan = dict(schema_version=1,evidence_type='github-actions-artifact-plan',stage='TERMINAL_CAPTURED',
            broker_repository=policy.repository,request_id=record['request_id'],attempt_id=record['attempt_id'],
            subject_id=execution['subject_id'],packet_id=execution['packet_id'],workflow_run_id=storage['run_id'],
            workflow_run_attempt=storage['run_attempt'],artifact_name=location['artifact_name'],
            artifacts={location['path']:dict(artifact_id=pointer['artifact_id'],byte_length=pointer['byte_length'])})
        locator = build_evidence_artifact_locator(plan,metadata,declared_digest=location['archive_digest'])
        result_directory = Path(destination) / 'result'
        store.download(locator,result_directory)
        result = validate_result_bytes(record,(result_directory/location['path']).read_bytes())
        verify_faithful_projection(result,record,terminal,validation)
        require(canonical_bytes(result['validation']) == canonical_bytes(validation), 'VALIDATION_RESULT_LINK')
        require(canonical_bytes(result.get('resolved_request')) == canonical_bytes(record['admission']),
                'RESULT_ADMISSION_LINK')
        receipt = authorization_receipt(pointer,policy)
        require(receipt == storage['authorization'] and artifact(receipt) == storage['authorization_receipt_id'],
                'STORAGE_AUTHORIZATION_RECEIPT')
        return receipt
    except Exception:
        raise ValueError('RESULT_STORAGE_UNVERIFIED') from None
