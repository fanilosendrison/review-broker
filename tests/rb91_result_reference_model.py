"""Pure F1 reference relations; authentication belongs to the storage gate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from review_broker.identity import canonical_bytes
from rb91_jch_contract_model import artifact

REFERENCE_SCHEMA = json.loads((Path(__file__).resolve().parents[1] /
    'docs/architecture/qualification/rb91-result-reference-v2.schema.json').read_text())
Draft202012Validator.check_schema(REFERENCE_SCHEMA)
REGISTRY = Registry().with_resource(REFERENCE_SCHEMA['$id'], Resource.from_contents(REFERENCE_SCHEMA))


def require(condition, code):
    if not condition:
        raise ValueError(code)


def storage_statement(pointer):
    value = deepcopy(pointer)
    value['storage'].pop('authorization_receipt_id')
    value['storage'].pop('authorization')
    return value


def storage_audience(pointer):
    digest = hashlib.sha256(canonical_bytes(storage_statement(pointer))).hexdigest()
    return 'urn:review-broker:result-retention:v1:sha256:' + digest


def storage_receipt(pointer, policy_id):
    return dict(schema_version=1,evidence_type='result-storage-authorization-v1',
        issuer='https://token.actions.githubusercontent.com',authority_policy_id=policy_id,
        statement_sha256=hashlib.sha256(canonical_bytes(storage_statement(pointer))).hexdigest())


def execution_projection(record, arm_commit_sha):
    binding = record['arm_binding']
    def evidence(state):
        return next(e['evidence_ids'][0] for e in record['history'] if e.get('state') == state)
    return dict(request_id=record['request_id'],attempt_id=record['attempt_id'],
        subject_id=record['admission']['subject_id'],policy_id=record['admission']['policy_id'],
        packet_id=record['input_capacity']['packet_id'],broker_repository_id=binding['broker_repository_id'],
        controller_workflow_ref=binding['workflow_ref'],controller_workflow_sha=binding['workflow_sha'],
        controller_run_id=binding['controller_run_id'],controller_run_attempt=binding['controller_run_attempt'],
        arm_commit_sha=arm_commit_sha,arm_binding_sha256=hashlib.sha256(canonical_bytes(binding)).hexdigest(),
        terminal_capture_id=evidence('TERMINAL_CAPTURED'),terminal_locator_id=artifact(record['evidence_locator']),
        validation_id=evidence('VALIDATED'))


def validate_reference_links(record):
    pointer = record['publication_intent']['result_artifact']
    Draft202012Validator(REFERENCE_SCHEMA).validate(pointer)
    execution, storage, location = (pointer[k] for k in ('execution','storage','location'))
    receipt = storage_receipt(pointer,storage['authorization']['authority_policy_id'])
    require(storage['authorization'] == receipt and artifact(receipt) == storage['authorization_receipt_id'],
            'STORAGE_RECEIPT_CONTENT')
    # The ARM commit is authenticated separately; it cannot be inferred from a string.
    require(execution == execution_projection(record, execution['arm_commit_sha']), 'EXECUTION_PROVENANCE')
    require(record['invocation_count'] == 1, 'CONSUMPTION_REQUIRED')
    require(location['broker_repository'] == record['evidence_locator']['broker_repository'], 'RESULT_REPOSITORY')
    require((location['workflow_run_id'], location['workflow_run_attempt']) ==
            (storage['run_id'], storage['run_attempt']), 'STORAGE_RUN')
    same_run = (storage['run_id'],storage['run_attempt']) == (
        execution['controller_run_id'],execution['controller_run_attempt'])
    if storage['mode'] == 'original':
        require(same_run and storage['workflow_ref'] == execution['controller_workflow_ref'] and
                storage['workflow_sha'] == execution['controller_workflow_sha'], 'ORIGINAL_STORAGE_IDENTITY')
    else:
        require(not same_run, 'RECOVERY_IS_NOT_ORIGINAL')
    return pointer
