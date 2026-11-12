"""Offline proposed-schema conformance; no mint, journal writer or runtime adapter."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from review_broker.codex_policy import CodexPolicy
from review_broker.identity import canonical_bytes
from review_broker.github_oidc import verify_github_identity
from review_broker.oidc_subject import immutable_repository_subject
from rb91_jch_contract_model import artifact, parse_strict
from rb91_full_abi_model import validate as validate_qualified_record
from jch_datetime import complete_date_time, qualify_complete_checker
from jch_patterns import JCHValidator, qualified_resources

ROOT=Path(__file__).resolve().parents[1]
PREFIX='https://github.com/fanilosendrison/review-broker/schemas/'
RESOURCES={p.name:json.loads(p.read_text()) for p in (ROOT/'schemas').glob('jch-*.schema.json')}
REGISTRY=Registry().with_resources((v['$id'],Resource.from_contents(v)) for v in RESOURCES.values())
for schema in RESOURCES.values():Draft202012Validator.check_schema(schema)
EVALUATED_RESOURCES,EVALUATED_REGISTRY=qualified_resources(RESOURCES)


def require(condition, code):
    if not condition:raise ValueError(code)


def qualified_format_checker():
    checker=FormatChecker()
    require('date-time' in checker.checkers,'DATE_TIME_ASSERTION_UNAVAILABLE')
    for valid in ('2024-02-29T00:00:00Z','1985-04-12T23:20:50.52Z',
                  '1996-12-19T16:39:57-08:00','1937-01-01T12:00:27.87+00:20',
                  '2024-02-29t00:00:00z'):
        require(checker.conforms(valid,'date-time'),'DATE_TIME_ASSERTION_BROKEN')
    for invalid in ('2026-02-30T00:00:00Z','2025-02-29T00:00:00Z','2026-13-01T00:00:00Z',
                    '2026-11-09T00:00:00','not-a-timestamp'):
        require(not checker.conforms(invalid,'date-time'),'DATE_TIME_ASSERTION_PERMISSIVE')
    original,raises=checker.checkers['date-time']

    @checker.checks('date-time',raises=raises)
    def qualified_date_time(value):
        return complete_date_time(value,original)

    require(not checker.conforms('2026-11-09T00:00:00Z\n','date-time'),
            'DATE_TIME_ASSERTION_PERMISSIVE')
    qualify_complete_checker(checker)
    return checker


def check(name,value):
    JCHValidator(EVALUATED_RESOURCES[name],registry=EVALUATED_REGISTRY,
                 format_checker=qualified_format_checker()).validate(value)
    return value


def digest(value):return hashlib.sha256(canonical_bytes(value)).hexdigest()


def arm_audience(envelope):
    check('jch-arm-envelope-v1.schema.json',envelope)
    return 'urn:review-broker:j-ch-v1:arm-authority:sha256:'+digest(envelope)


def workload_claims(envelope, deployment):
    binding=envelope['binding'];repository=deployment['broker_repository']
    return dict(repository=repository,repository_id=deployment['broker_repository_id'],
        repository_owner_id=deployment['broker_repository_owner_id'],repository_owner=repository.split('/')[0],
        ref=deployment['ref'],workflow_ref=binding['workflow_ref'],workflow_sha=binding['workflow_sha'],
        sha=binding['workflow_sha'],run_id=binding['controller_run_id'],run_attempt=binding['controller_run_attempt'],
        sub=immutable_repository_subject(repository,deployment['broker_repository_id'],deployment['broker_repository_owner_id'],deployment['ref']))


def verify_workload_claims(token,envelope,deployment,issuer_reader):
    """Cryptographic conformance only; never a journal/session ownership grant."""
    require(callable(issuer_reader),'INJECTED_ISSUER_REQUIRED')
    check('jch-deployment-policy-v1.schema.json',deployment)
    verify_github_identity(token,audience=arm_audience(envelope),expected_claims=workload_claims(envelope,deployment),
                           issuer_reader=issuer_reader,allow_thumbprints=True)


def validate_arm(envelope, *, hello, record, deployment, arm_commit_sha, metadata_bytes):
    """Semantic comparison oracle; trusted context/authentication is not constructed here."""
    for name,value in [('jch-arm-envelope-v1.schema.json',envelope),('jch-launcher-message-v1.schema.json',hello),
                       ('jch-deployment-policy-v1.schema.json',deployment),('jch-journal-v2.schema.json',record)]:check(name,value)
    validate_qualified_record(record)
    require(hello['message_type']=='HELLO','ORIGINAL_HELLO_REQUIRED')
    require(record['state']=='ARMED' and record['invocation_count']==1,'CONSUMED_ARM_REQUIRED')
    binding=record['arm_binding'];capacity=record['input_capacity']
    require(canonical_bytes(envelope['binding'])==canonical_bytes(binding),'EXACT_BINDING')
    require(envelope['arm_commit_sha']==arm_commit_sha,'ACKNOWLEDGED_ARM_COMMIT')
    require(canonical_bytes(envelope['capacity_receipt'])==canonical_bytes(capacity) and capacity['status']=='PASS','EXACT_CAPACITY')
    for field in ('broker_repository','broker_repository_owner_id','ref'):
        require(envelope[field]==deployment[field],'PROTECTED_DEPLOYMENT')
    require(binding['broker_repository_id']==deployment['broker_repository_id'],'BROKER_IDENTITY')
    require(binding['workflow_sha']==deployment['executing_broker_sha']==deployment['workflow_sha'],'EXECUTING_SOURCE')
    require(binding['workflow_ref']==deployment['workflow_ref']==envelope['broker_repository']+'/.github/workflows/review-request.yml@'+envelope['ref'],'WORKFLOW_REF')
    require(envelope['reviewer_policy']==asdict(CodexPolicy())==deployment['reviewer_policy'],'COMMAND_POLICY')
    require(binding['reviewer_policy_sha256']==digest(envelope['reviewer_policy']),'POLICY_DIGEST')
    require(len(metadata_bytes)<=100000,'METADATA_CAPACITY')
    metadata=parse_strict(metadata_bytes);check('jch-broker-metadata-v1.schema.json',metadata)
    require(envelope['broker_metadata_sha256']==hashlib.sha256(metadata_bytes).hexdigest(),'METADATA_DIGEST')
    for field in ('request_id','attempt_id'):
        require(metadata[field]==record[field],'METADATA_REQUEST')
    require(metadata['broker_repository']==envelope['broker_repository'] and
            metadata['executing_broker_sha']==binding['workflow_sha'],'METADATA_BROKER')
    require(metadata['requester']==record['admission_authority']['actor'] and
            metadata['admission_mode']==record['admission_authority']['admission_mode'] and
            metadata['subject_repository']==record['admission']['subject']['repository'],'METADATA_ADMISSION')
    for field in ('challenge','request_id','attempt_id','packet_id','input_sha256','capacity_receipt_id','codespace_name','codespace_id','launcher_program_sha256','broker_repository_id'):
        require(hello[field]==binding[field],'HELLO_BINDING')
    require(hello['executing_broker_sha']==binding['workflow_sha'],'HELLO_SOURCE')
    require(binding['capacity_receipt_id']==artifact(capacity),'CAPACITY_IDENTITY')
    for field in ('codespace_name','codespace_id','launcher_program_sha256'):
        require(binding[field]==deployment[field],'RECIPIENT_LAUNCHER')
    runtime=hello['reviewer_runtime_identity']
    require(runtime['native_executable_sha256']==binding['reviewer_executable_sha256']==deployment['reviewer_native_sha256'],'NATIVE_IDENTITY')
    require(runtime['permission_profile_sha256']==deployment['permission_profile_sha256'],'PROFILE_IDENTITY')
    return envelope


def frame_payload(message):
    check('jch-launcher-message-v1.schema.json',message)
    raw=canonical_bytes(message)
    limit=100000 if message['message_type']=='PROOF' else 16384
    require(len(raw)<=limit,'FRAME_CAPACITY_REFUSED')
    return len(raw).to_bytes(4,'big')+raw


def proof_budget(envelope):
    """Conservative complete canonical wrapper with maximal safe ASCII JWT length."""
    maximum='a.'+'b'*32764+'.c'
    require(len(maximum)==32768,'TEST_BUDGET_ORACLE')
    return frame_payload(dict(protocol_id='j-ch-v1',handshake_version=dict(major=1,minor=0),
                              message_type='PROOF',envelope=deepcopy(envelope),jwt=maximum))
