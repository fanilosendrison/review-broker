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
    # Heterogeneous policy/JSON fields are closed and confronted below.
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
        require(observed == storage[field], 'OBSERVED_ACTOR')
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
    require(str(metadata['workflow_run']['id']) == storage['run_id'] and
            metadata['workflow_run']['head_sha'] == allowed['workflow_sha'], 'ARTIFACT_STORAGE_RUN')
    require(instant(steps[0]['started_at']) <= instant(metadata['created_at']) <= instant(steps[0]['completed_at']),
            'ARTIFACT_UPLOAD_WINDOW')
    return metadata


def verify_storage(record, policy, *, token, issuer_reader, runner, destination):
    """Authenticate BEFORE reservation; signature/bytes never authorize a model."""
    try:
        require(callable(issuer_reader) and callable(runner), 'INJECTED_TRANSPORT_REQUIRED')
        record = deepcopy(record)
        policy = replace(policy,workflows=deepcopy(policy.workflows),execution_snapshot=deepcopy(policy.execution_snapshot))
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
        store = GitHubActionsArtifactStore(policy.repository, runner=runner)
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
        require(canonical_bytes(result['validation']) == canonical_bytes(validation), 'VALIDATION_RESULT_LINK')
        require(result.get('resolved_request') == record['admission'], 'RESULT_ADMISSION_LINK')
        receipt = authorization_receipt(pointer,policy)
        require(receipt == storage['authorization'] and artifact(receipt) == storage['authorization_receipt_id'],
                'STORAGE_AUTHORIZATION_RECEIPT')
        return receipt
    except Exception:
        raise ValueError('RESULT_STORAGE_UNVERIFIED') from None
