"""Conformance examples for the proposed workload ABI; no executable authority."""
from copy import deepcopy
from dataclasses import asdict
import hashlib

from review_broker.codex_policy import CodexPolicy
from review_broker.identity import canonical_bytes
from rb91_full_abi_fixtures import armed
from jch_normative_schemas import digest


def workload():
    record=armed();binding=record['arm_binding'];policy=asdict(CodexPolicy())
    repository='sample/broker'
    binding.update(workflow_ref=repository+'/.github/workflows/review-request.yml@refs/heads/dev',
                   reviewer_policy_sha256=digest(policy))
    record['history'][-1]['binding_sha256']=digest(binding)
    role=dict(workflow_ref=repository+'/.github/workflows/publication-recovery.yml@refs/heads/dev',
        workflow_sha='9'*40,path='.github/workflows/publication-recovery.yml',job_name='retain-result',
        upload_step='Upload validated result',events=['workflow_dispatch'])
    deployment=dict(schema_version=1,protocol_id='j-ch-v1',broker_repository=repository,
        broker_repository_id=binding['broker_repository_id'],broker_repository_owner_id='30498238',
        ref='refs/heads/dev',executing_broker_sha=binding['workflow_sha'],workflow_ref=binding['workflow_ref'],
        workflow_sha=binding['workflow_sha'],launcher_program_sha256=binding['launcher_program_sha256'],
        reviewer_native_sha256=binding['reviewer_executable_sha256'],permission_profile_sha256='7'*64,
        reviewer_policy=policy,codespace_name=binding['codespace_name'],codespace_id=binding['codespace_id'],
        storage_workflows=dict(recovery=role),storage_actor_ids=[21])
    metadata=dict(schema_version=1,broker_repository=repository,issue_number=7,
        request_id=record['request_id'],attempt_id=record['attempt_id'],admission_mode='low-sensitivity-v1',
        executing_broker_sha=binding['workflow_sha'],requester=record['admission_authority']['actor'],
        subject_repository=record['admission']['subject']['repository'],admission_checks=dict(
          requester_authorized=True,repository_authorized=True,executing_sha_admitted=True,
          low_sensitivity_repository_admitted=True,public_repository_verified=True))
    raw=canonical_bytes(metadata)+b'\n'
    envelope=dict(schema_version=1,protocol_id='j-ch-v1',authorization_id='a'*64,
        broker_repository=repository,broker_repository_owner_id=deployment['broker_repository_owner_id'],
        ref='refs/heads/dev',arm_commit_sha='b'*40,binding=deepcopy(binding),
        broker_metadata_sha256=hashlib.sha256(raw).hexdigest(),capacity_receipt=deepcopy(record['input_capacity']),
        reviewer_policy=deepcopy(policy))
    hello=dict(protocol_id='j-ch-v1',handshake_version=dict(major=1,minor=0),message_type='HELLO',
        executing_broker_sha=binding['workflow_sha'],reviewer_runtime_identity=dict(
          distribution='@openai/codex',distribution_version='0.164.0',native_executable_sha256=binding['reviewer_executable_sha256'],
          permission_profile_sha256=deployment['permission_profile_sha256']))
    for key in ('challenge','request_id','attempt_id','packet_id','broker_repository_id','codespace_name','codespace_id',
                'launcher_program_sha256','input_sha256','capacity_receipt_id'):hello[key]=binding[key]
    return envelope,hello,record,deployment,raw


def quiescence(record, *, count=1, method='codespace-shutdown'):
    binding=record['arm_binding']
    return dict(schema_version=1,evidence_type='jch-quiescence-v1',protocol_id='j-ch-v1',
        request_id=record['request_id'],attempt_id=record['attempt_id'],invocation_count=count,
        arm_commit_sha='b'*40 if count else None,arm_binding_sha256=digest(binding) if count else None,
        codespace_name=binding['codespace_name'],codespace_id=binding['codespace_id'],method=method,
        observed_state='Shutdown' if method=='codespace-shutdown' else 'QUIESCENT',observed_at='2026-11-09T00:00:00Z',
        lifecycle_context=dict(workflow_ref='sample/broker/.github/workflows/review-reconciler.yml@refs/heads/dev',
            workflow_sha='e'*40,run_id='123',run_attempt='1',actor=dict(login='operator',id=21)),
        custody_evidence_id='artifact:sha256:'+'1'*64,observation_evidence_id='artifact:sha256:'+'2'*64)
