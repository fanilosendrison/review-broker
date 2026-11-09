"""Offline candidate journal ABI checks; never imported by product code.

This model reuses the historical core oracle and accepted nested validators.
It is not a journal writer, OIDC verifier, or operational evidence attestation.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from review_broker.artifact_locator import (
    validate_evidence_artifact_plan, validate_evidence_artifact_locator,
)
from review_broker.identity import (
    canonical_bytes, request_identity, subject_identity, mission_identity,
    policy_identity, review_intent_identity,
)
from review_broker.publication import result_identity, render_result_comment
from rb91_jch_contract_model import (
    artifact, validate as validate_core, validate_transition as transition_core,
    parse_strict,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'docs/architecture/qualification/rb91-journal-v2-candidate.schema.json').read_text())
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
METADATA = ('evidence_locator_plan', 'evidence_locator', 'publication_intent', 'publication_receipt')
EVENTS = dict(evidence_locator_plan='EVIDENCE_LOCATOR_PLANNED',
              evidence_locator='EVIDENCE_LOCATOR_RECORDED',
              publication_intent='PUBLICATION_RESERVED')


def require(condition, code):
    if not condition:
        raise ValueError(code)


def core_view(record):
    value = deepcopy(record)
    value.pop('admission')
    value.pop('admission_authority')
    for field in METADATA:
        value[field] = None
    return value


def publication_identity(intent):
    basis = {k: v for k, v in intent.items()
             if k not in {'publication_id', 'comment_body_sha256', 'evidence_type'}}
    return 'publication:sha256:' + hashlib.sha256(canonical_bytes(basis)).hexdigest()


def validate(record):
    # Strict raw parsing is a separate entry gate, tested through parse_strict.
    require(type(record.get('schema_version')) is int, 'VERSION_TYPE')
    VALIDATOR.validate(record)
    validate_core(core_view(record))
    admission = record['admission']
    request = admission['request']
    require(admission['request_id'] == record['request_id'] == request_identity(request), 'REQUEST_ID')
    require(admission['subject_id'] == subject_identity(admission['subject']), 'SUBJECT_ID')
    require(admission['mission_id'] == mission_identity(request['mission']), 'MISSION_ID')
    require(admission['policy_id'] == policy_identity(request['policy']), 'POLICY_ID')
    for field in ('kind', 'repository', 'pull_request'):
        require(request['subject'][field] == admission['subject'][field], 'SUBJECT_LINK')
    if request['schema_version'] == 2:
        require(admission.get('review_intent_id') == review_intent_identity(request), 'INTENT_ID')
        require(request['subject']['expected_head_commit'] == admission['subject']['head_commit'], 'HEAD')
    else:
        require('review_intent_id' not in admission, 'LEGACY_INTENT_EXTENSION')
    cap = record.get('input_capacity')
    binding = record['arm_binding']
    auth = record['admission_authority']
    if cap is not None:
        require(cap['executing_broker_sha'] == auth['executing_broker_sha'], 'EXECUTABLE')
        if cap['status'] == 'REJECTED':
            require(record['state'] == 'PREPARED' and record['invocation_count'] == 0, 'REJECTED_STAYS_PREPARED')
    if binding is not None:
        require(binding['subject_id'] == admission['subject_id'], 'BOUND_SUBJECT')
        require(binding['broker_repository_id'] == auth['broker_repository_id'], 'BROKER_ID')
    stages = [e.get('state') for e in record['history'] if 'state' in e]
    for field in METADATA:
        value = record[field]
        if value is None:
            continue
        event = EVENTS.get(field)
        if event:
            require(any(e.get('event') == event and artifact(value) in e['evidence_ids']
                        for e in record['history']), 'METADATA_EVENT')
        require('TERMINAL_CAPTURED' in stages, 'METADATA_BEFORE_TERMINAL')
        if field.startswith('publication'):
            require('VALIDATED' in stages, 'PUBLICATION_BEFORE_VALIDATION')
        else:
            for key in ('request_id', 'attempt_id'):
                require(value[key] == record[key], 'ARTIFACT_RECORD_LINK')
            require(value['subject_id'] == admission['subject_id'], 'ARTIFACT_SUBJECT')
            require(cap is not None and value['packet_id'] == cap['packet_id'], 'ARTIFACT_PACKET')
            if binding:
                require(value['workflow_run_id'] == binding['controller_run_id'] and
                        value['workflow_run_attempt'] == binding['controller_run_attempt'], 'ARTIFACT_RUN')
    plan, locator = record['evidence_locator_plan'], record['evidence_locator']
    if plan:
        validate_evidence_artifact_plan(plan, request_id=record['request_id'], attempt_id=record['attempt_id'])
    if locator:
        validate_evidence_artifact_locator(locator, request_id=record['request_id'], attempt_id=record['attempt_id'])
        require(plan is not None, 'LOCATOR_WITHOUT_PLAN')
        for key in plan:
            if key != 'evidence_type':
                require(plan[key] == locator[key], 'LOCATOR_PLAN_LINK')
        require(datetime.fromisoformat(locator['expires_at'].replace('Z', '+00:00')) >
                datetime.fromisoformat(locator['created_at'].replace('Z', '+00:00')), 'EXPIRY')
    intent, receipt = record['publication_intent'], record['publication_receipt']
    if intent:
        require(locator is not None, 'PUBLICATION_WITHOUT_LOCATOR')
        for key in ('request_id', 'attempt_id'):
            require(intent[key] == record[key], 'PUBLICATION_RECORD_LINK')
        require(intent['publication_id'] == publication_identity(intent), 'PUBLICATION_ID')
        location = intent['result_artifact']['location']
        require(location['broker_repository'] == locator['broker_repository'], 'RESULT_REPOSITORY')
        if binding:
            require(location['workflow_run_id'] == binding['controller_run_id'] and
                    location['workflow_run_attempt'] == binding['controller_run_attempt'], 'RESULT_RUN')
    if receipt:
        require(intent is not None, 'RECEIPT_WITHOUT_INTENT')
        for key in ('publication_id', 'result_id', 'issue_number', 'publisher'):
            require(receipt[key] == intent[key], 'RECEIPT_LINK')
        require(any(e.get('state') == 'REPORTED' and artifact(receipt) in e['evidence_ids']
                    for e in record['history']), 'RECEIPT_EVENT')
    return record


def validate_result_bytes(record, raw):
    """Resolve a typed content reference; this never treats existence as publication."""
    intent = record['publication_intent']
    require(intent is not None, 'NO_INTENT')
    pointer = intent['result_artifact']
    require(len(raw) == pointer['byte_length'] and
            'artifact:sha256:' + hashlib.sha256(raw).hexdigest() == pointer['artifact_id'], 'RESULT_BYTES')
    result = parse_strict(raw)
    result_schema = json.loads((ROOT / 'schemas/review-result-v1.schema.json').read_text())
    Draft202012Validator(result_schema).validate(result)
    require(result_identity(result) == intent['result_id'], 'RESULT_ID')
    for key in ('request_id', 'attempt_id'):
        require(result[key] == record[key], 'RESULT_RECORD')
    require(result['subject_id'] == record['admission']['subject_id'], 'RESULT_SUBJECT')
    require(result['policy_id'] == record['admission']['policy_id'], 'RESULT_POLICY')
    require(result['packet_id'] == record['input_capacity']['packet_id'], 'RESULT_PACKET')
    rendered = render_result_comment(result, publication_id=intent['publication_id'])
    require(hashlib.sha256(rendered.encode()).hexdigest() == intent['comment_body_sha256'], 'RESULT_BODY')
    return result


def validate_transition(parent, child, *, parent_sha, operation):
    """Pure structural/relational gate, NOT external evidence authentication."""
    validate(parent)
    validate(child)
    for key in ('admission', 'admission_authority'):
        require(canonical_bytes(parent[key]) == canonical_bytes(child[key]), 'ADMISSION_IMMUTABLE')
    transition_core(core_view(parent), core_view(child), parent_sha=parent_sha, operation=operation)
    changed = [k for k in METADATA if parent[k] != child[k]]
    for field in changed:
        require(parent[field] is None and child[field] is not None, 'METADATA_IMMUTABLE')
    if operation == 'metadata':
        require(len(changed) == 1 and changed[0] in EVENTS, 'ONE_METADATA_FIELD')
        require(child['history'][-1].get('event') == EVENTS[changed[0]], 'METADATA_OWNER')
    elif child['state'] == 'REPORTED':
        require(changed == ['publication_receipt'], 'REPORTED_RECEIPT')
    else:
        require(not changed, 'UNRELATED_METADATA')
    return True
