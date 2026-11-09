"""Synthetic candidate data, never production authority or live credentials."""
from copy import deepcopy
import hashlib

from review_broker.identity import (
    canonical_bytes, request_identity, attempt_identity, subject_identity,
    mission_identity, policy_identity, review_intent_identity,
)
from review_broker.publication import result_identity, render_result_comment
from rb91_jch_contract_model import (
    fixture_prepared, fixture_capacity, fixture_armed, fixture_transition, artifact,
)
from rb91_full_abi_model import publication_identity
from rb91_result_reference_model import execution_projection, storage_receipt


TIME = '2026-11-09T00:00:00Z'


def prepared(version=2):
    request = dict(schema_version=version,
        subject=dict(kind='github_pr', repository='sample/source', pull_request=7),
        mission=dict(id='design', objective='Review design', instructions='Inspect data only', criteria=['Correctness']),
        policy=dict(profile='architecture', version=1),
        reviewer=dict(backend='codex-cli', model='gpt-5.6-sol', reasoning_effort='xhigh'))
    if version == 2:
        request['subject']['expected_head_commit'] = 'a' * 40
        request['review_operation'] = dict(kind='initial')
    subject = dict(kind='github_pr', repository='sample/source', repository_id=123,
                   pull_request=7, head_commit='a'*40, base_commit='b'*40, merge_base='c'*40)
    admission = dict(schema_version=1, request=request, request_id=request_identity(request),
        subject=subject, subject_id=subject_identity(subject),
        mission_id=mission_identity(request['mission']), policy_id=policy_identity(request['policy']))
    if version == 2:
        admission['review_intent_id'] = review_intent_identity(request)
    value = fixture_prepared()
    value['request_id'] = admission['request_id']
    value['attempt_id'] = attempt_identity(value['request_id'], 1)
    value['admission'] = admission
    value['admission_authority'] = dict(actor='authorized-operator', admission_mode='low-sensitivity-v1',
        authorization_evidence_id='artifact:sha256:'+'9'*64,
        broker_repository_id='1433701208', executing_broker_sha='e'*40)
    return fixture_capacity(value)


def armed():
    value = fixture_armed(prepared())
    value['arm_binding']['subject_id'] = value['admission']['subject_id']
    value['history'][-1]['binding_sha256'] = hashlib.sha256(canonical_bytes(value['arm_binding'])).hexdigest()
    return value


def metadata(parent, field, value, event):
    child = deepcopy(parent)
    child[field] = value
    entry = dict(event=event, evidence_ids=[artifact(value)])
    child['history'].append(entry)
    child['evidence_ids'].extend(entry['evidence_ids'])
    return child


def publication_chain():
    terminal = fixture_transition(armed(), 'TERMINAL_CAPTURED')
    admission = terminal['admission']
    result = dict(schema_version=1, request_id=terminal['request_id'],
        subject_id=admission['subject_id'], policy_id=admission['policy_id'],
        packet_id=terminal['input_capacity']['packet_id'], attempt_id=terminal['attempt_id'],
        execution_status='COMPLETED', evidence_status='VALID', review_verdict='GO',
        reviewer=dict(backend='codex-cli', model_requested='gpt-5.6-sol', reasoning_effort_requested='xhigh',
                      effective_model_identity_verified=False, effective_reasoning_effort_verified=False),
        sources_examined=[], findings=[], remaining_uncertainties=[],
        validation=dict(semantic_correctness_validated=False),
        applicability=dict(status='CURRENT', checked_head_commit='a'*40))
    raw = canonical_bytes(result) + b'\n'
    entry = dict(artifact_id='artifact:sha256:'+hashlib.sha256(raw).hexdigest(), byte_length=len(raw))
    plan = dict(schema_version=1, evidence_type='github-actions-artifact-plan', stage='TERMINAL_CAPTURED',
        broker_repository='sample/broker', request_id=terminal['request_id'], attempt_id=terminal['attempt_id'],
        subject_id=admission['subject_id'], packet_id=result['packet_id'], workflow_run_id='42372558711',
        workflow_run_attempt='1', artifact_name='synthetic-terminal',
        artifacts={'terminal-capture.json': dict(artifact_id='artifact:sha256:'+'8'*64, byte_length=200)})
    planned = metadata(terminal, 'evidence_locator_plan', plan, 'EVIDENCE_LOCATOR_PLANNED')
    locator = dict(plan, evidence_type='github-actions-artifact-locator', artifact_id=11,
        artifact_digest='sha256:'+'d'*64, artifact_size_in_bytes=1000,
        created_at=TIME, expires_at='2026-12-09T00:00:00Z')
    located = metadata(planned, 'evidence_locator', locator, 'EVIDENCE_LOCATOR_RECORDED')
    validated = fixture_transition(located, 'VALIDATED')
    validated['history'][-1]['evidence_ids'] = [artifact(result['validation'])]
    validated['evidence_ids'][-1] = artifact(result['validation'])
    execution = execution_projection(validated, 'a'*40)
    binding = validated['arm_binding']
    storage = dict(mode='original',workflow_ref=binding['workflow_ref'],workflow_sha=binding['workflow_sha'],
        run_id=binding['controller_run_id'],run_attempt=binding['controller_run_attempt'],
        job_id=10,job_name='retain-result',actor=dict(login='operator',id=21),
        triggering_actor=dict(login='operator',id=21),authorization_receipt_id='artifact:sha256:'+'6'*64,authorization=None)
    intent = dict(schema_version=2, evidence_type='jch-result-publication-intent-v2',
        issue_number=7, request_id=terminal['request_id'], attempt_id=terminal['attempt_id'],
        result_id=result_identity(result), result_artifact=dict(entry,media_type='application/json',contract='review-result-v1',
            execution=execution,storage=storage,location=dict(broker_repository='sample/broker',workflow_run_id='42372558711',
                workflow_run_attempt='1',actions_artifact_id=12,artifact_name='synthetic-result',
                archive_digest='sha256:'+'7'*64,path='review-result.json')),
        publisher=dict(login='broker', id=9), nonce='f'*64, reserved_at=TIME)
    storage['authorization'] = storage_receipt(intent['result_artifact'],'artifact:sha256:'+'6'*64)
    storage['authorization_receipt_id'] = artifact(storage['authorization'])
    intent['publication_id'] = publication_identity(intent)
    intent['comment_body_sha256'] = hashlib.sha256(render_result_comment(result,
        publication_id=intent['publication_id']).encode()).hexdigest()
    reserved = metadata(validated, 'publication_intent', intent, 'PUBLICATION_RESERVED')
    receipt = dict(schema_version=1,evidence_type='github-result-publication-observation',
        publication_id=intent['publication_id'], result_id=intent['result_id'], issue_number=7,
        publisher=intent['publisher'], comment_id=8, comment_node_id='synthetic-node',
        comment_url='https://github.com/sample/broker/issues/7#issuecomment-8',
        comment_created_at=TIME, observed_at=TIME)
    reported = fixture_transition(reserved,'REPORTED')
    reported['publication_receipt'] = receipt
    reported['evidence_ids'][-1] = artifact(receipt)
    reported['history'][-1]['evidence_ids'] = [artifact(receipt)]
    return [terminal, planned, located, validated, reserved, reported], raw
