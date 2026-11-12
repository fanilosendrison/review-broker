"""One original Python Worker, concrete dependencies, existing RWP-02 through RWP-05."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

from .actions_artifact_child_v3 import GitHubActionsArtifactChildV3,run_artifact_child_v3
from .actions_artifact_http_v3 import GitHubActionsArtifactHttpV3
from .cold_packet_observer_v3 import collect_api_corpus_v3,run_cold_observer_v3
from .github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
from .github_prepared_artifact_v3 import GitHubPreparedArtifactV3,PreparedArtifactUploaderV3
from .github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from .github_policy_authority_v3 import GitHubProtectedPolicyAuthorityV3
from .identity import canonical_bytes
from .live_failure_provenance_v3 import LiveFailureOriginV3,OriginalFailureArchiveRouterV3
from .live_journal_composition_v3 import live_journal_v3,GitHubOriginalAdmissionAuthorityV3
from .live_source_admission_v3 import LiveSourceSessionV3
from .original_admission_envelope_v3 import OriginalAdmissionEnvelopeV3
from .packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from .pre_model_ack_start_gate_v3 import wait_dispatch_ack_v3
from .pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
from .pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3
from .pre_model_packet_continuation_v3 import PreModelPacketContinuationV3,PreModelPacketContinuationResultV3
from .pre_model_policy_evidence_retention_v3 import LocalAuthorizedPacketStagesV3
from .pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from .pre_model_worker_v3 import PreModelWorkerV3
from .prepared_artifact_transport_v3 import PreparedMetadataReaderV3
from .queue import AttemptState


@dataclass(frozen=True)
class LiveWorkerResultV3:
    status: str
    state: str
    reason: str
    packet_id: str | None = None
    remote_receipt_id: str | None = None
    cold_verified: bool = False
    disposition: str | None = None


def _observed_state(result):
    outcome=getattr(result,'journal_outcome',None)
    snapshot=None if outcome is None else outcome.snapshot
    return 'UNCONFIRMED' if snapshot is None else snapshot.record.attempt.state.value


def worker_observer_v3(runtime):
    original=GitHubOriginalAdmissionAuthorityV3(runtime.api)
    def deny():raise ValueError('OBSERVER_CANNOT_MUTATE')
    journal=live_journal_v3(runtime,original,write_guard=deny)
    dispatch=GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api,runtime.expected)
    return journal,dispatch


def run_live_worker_v3(*,runtime,source_token,app_slug,installation_id,private_root:Path,
                       helper_root:Path,node:Path,artifact_environment,source_executor,
                       acquire_repository=None,artifact_runner=run_artifact_child_v3,
                       metadata_executor=None,storage_executor=None,sleeper=None):
    context=runtime.worker_context()
    observer,dispatch=worker_observer_v3(runtime)
    options={} if sleeper is None else {'sleeper':sleeper}
    with runtime.diagnostics.phase('ACK_GATE'):
        gate=wait_dispatch_ack_v3(journal=observer,runtime=runtime,inputs=context.inputs,
            dispatch_authority=dispatch,**options)
    if not gate.accepted:return LiveWorkerResultV3('REJECTED','UNCONFIRMED',gate.reason)
    if source_token==runtime.api.token:raise ValueError('CONTROL_TOKEN_IS_NOT_SOURCE_AUTHORITY')
    anchor=[observer.read(context.inputs.request_id)]
    from .github_observed_dispatch_v3 import GitHubObservedDispatchV3
    from .pre_model_dispatch_ack_v3 import acknowledgment_from_record
    observed_dispatch=GitHubObservedDispatchV3(dispatch,acknowledgment_from_record(anchor[0].record))
    origin=LiveFailureOriginV3()
    def write_guard():
        observed=runtime.observe()
        if observed.actor_id!=gate.principal_id or observed.triggering_actor_id!=gate.principal_id:
            raise ValueError('WORKER_PRINCIPAL_CHANGED')
        if observer.read(context.inputs.request_id)!=anchor[0]:raise ValueError('WORKER_WRITE_PREDECESSOR_MOVED')
    journal=live_journal_v3(runtime,observer.admission_authority,write_guard=write_guard)
    source=LiveSourceSessionV3(source_token,app_slug=app_slug,installation_id=installation_id,
        root=private_root/'source',guard=runtime.observe,executor=runtime.diagnostics.wrap(source_executor,source=True),
        acquire_repository=acquire_repository,observer=origin)
    source.diagnostics=runtime.diagnostics
    source.require_original_scope(anchor[0].record.attempt.admission)
    source.origin_body=observer.admission_authority.origin(anchor[0].record.attempt.admission)
    binding=PreModelWorkerV3(journal=journal,actions_reader=runtime.reader,expected=runtime.expected,
        execution_boundary=runtime,execution_boundary_id=runtime.boundary_id,
        dispatch_authority=observed_dispatch,dispatch_principal_id=gate.principal_id).run(context)
    if binding.status.value!='COMMITTED':return LiveWorkerResultV3(binding.status.value,'UNCONFIRMED',binding.reason)
    anchor[0]=binding.journal_outcome.snapshot
    current=CurrentBoundWorkerAuthorityV3(journal=journal,actions_reader=runtime.reader,
        expected=runtime.expected,execution_boundary=runtime,execution_boundary_id=runtime.boundary_id,
        dispatch_authority=observed_dispatch,dispatch_principal_id=gate.principal_id,local_phases=True)
    envelope=OriginalAdmissionEnvelopeV3(canonical_bytes(anchor[0].record.attempt.admission),source.origin_body)
    budget=runtime.api.metadata.budget
    http=GitHubActionsArtifactHttpV3(before_effect=runtime.check_locals)
    metadata_call=metadata_executor or http.metadata
    def metadata(request,*,max_bytes):
        runtime.diagnostics.http(request,artifact=True)
        try:response=metadata_call(request,max_bytes=max_bytes)
        except TimeoutError:
            origin.read_timeout(request);raise
        origin.http(request,response)
        return response
    storage_call=storage_executor or http.storage
    def storage(request,*,max_bytes):
        runtime.diagnostics.count('ARTIFACT_STORAGE_READS')
        size=0;digest=hashlib.sha256()
        try:
            for chunk in storage_call(request,max_bytes=max_bytes):
                size+=len(chunk);digest.update(chunk);yield chunk
        except TimeoutError:
            origin.read_timeout(request);raise
        origin.stream_complete(request,size,digest.hexdigest())
    reader=PreparedMetadataReaderV3(token=runtime.api.token,repository=runtime.expected.repository,
        executor=metadata,budget=budget)
    adapter=GitHubPreparedArtifactV3(metadata=reader,
        worker_history=GitHubPreparedWorkerHistoryV3(reader,runtime.expected,observed_dispatch,gate.principal_id),
        storage_executor=storage,budget=budget,clock=runtime.reader._clock)
    adapter.diagnostics=runtime.diagnostics
    prepared_child=GitHubActionsArtifactChildV3(trusted_root=helper_root,node=node,private_base=private_root,
        environment=artifact_environment,max_bytes=budget.max_archive_bytes,runner=artifact_runner,
        on_started=origin.child_started)
    prepared_child.diagnostics=runtime.diagnostics
    failure_child=GitHubActionsArtifactChildV3(trusted_root=helper_root,node=node,private_base=private_root,
        environment=artifact_environment,max_bytes=16000,runner=artifact_runner)
    archive=OriginalFailureArchiveRouterV3(child=failure_child,adapter=adapter,context=context)
    failure=PreModelFailureEvidenceV3(origin,archive,16000)
    producer=None
    policy=GitHubProtectedPolicyAuthorityV3(api=runtime.api,journal=journal,expected=runtime.expected,
        dispatch_authority=dispatch,selection_guard=lambda ctx:producer.require_original_selection(ctx))
    def verification():
        return AuthorizedPolicyVerificationV3(journal,anchor[0],runtime.expected,policy,policy)
    def hydrate(snapshot,guard,*,failure_observer=None):
        current.require_current(context,snapshot,AttemptState.ADMITTED)
        anchor[0]=snapshot;archive.snapshot=snapshot
        return source.hydrate(snapshot,guard,failure_observer=failure_observer)
    def cold(root,snapshot,guard):
        guard()
        corpus=collect_api_corpus_v3(journal=journal,snapshot=snapshot,expected=runtime.expected,
            policy=policy,dispatch=dispatch,packet_root=root,local_guard=guard)
        return run_cold_observer_v3(corpus=corpus,packet_root=root,private_base=private_root,before_effect=guard)
    def references(guard):
        source.guard=guard
        return source.readers(envelope.request)[1]
    stages=LocalAuthorizedPacketStagesV3(candidate_directory=private_root/'candidate',
        retention_base=private_root/'retained',verification=verification,cold_verifier=cold,
        diagnostics=runtime.diagnostics)
    producer=PreModelPacketContinuationV3(journal=journal,current_worker_authority=current,
        original_admission=envelope,capture_provider=source,reference_readers=references,
        policy_source_authority=policy,policy_selection_authority=policy,packet_stages=stages,
        failure_evidence=failure,original_admission_loader=hydrate)
    handoff=producer.run(context)
    if type(handoff) is not PreModelPacketContinuationResultV3 or handoff.packet_id is None:
        return LiveWorkerResultV3(handoff.status.value,_observed_state(handoff),handoff.reason,
            disposition=getattr(handoff,'disposition',None))
    archive.packet_id=origin.packet_id=handoff.packet_id
    remote=PreModelRemoteRetentionV3(producer=producer,retention_base=private_root/'retained',
        verification=verification(),uploader=PreparedArtifactUploaderV3(prepared_child),adapter=adapter,
        remote_verification_root=private_root/'remote',failure_evidence=failure).run(context,handoff)
    if remote.status.value!='COMMITTED' or getattr(remote,'state',None)!='PREPARED':
        return LiveWorkerResultV3(remote.status.value,getattr(remote,'state',_observed_state(remote)),remote.reason,
            disposition=getattr(remote,'disposition',None))
    p=journal.read(context.inputs.request_id)
    try:
        with runtime.diagnostics.phase('FINAL_COLD_RECONSTRUCTION'):
            corpus=collect_api_corpus_v3(journal=journal,snapshot=p,expected=runtime.expected,
                policy=policy,dispatch=dispatch,packet_root=private_root/'remote',prepared=True)
            reconstructed=run_cold_observer_v3(corpus=corpus,packet_root=private_root/'remote',
                private_base=private_root,before_effect=lambda:None,storage=remote.remote_receipt.value['storage'])
        if reconstructed!={'packet_id':handoff.packet_id,'remote_receipt_id':remote.remote_receipt.evidence_id}:
            raise ValueError('COLD_ORIGINAL_PACKET_RECONSTRUCTION_MISMATCH')
    except Exception:
        return LiveWorkerResultV3('COMMITTED','PREPARED','COLD_RECONSTRUCTION_UNAVAILABLE',
            handoff.packet_id,remote.remote_receipt.evidence_id)
    return LiveWorkerResultV3('COMMITTED','PREPARED','STOP_BEFORE_ARMED',handoff.packet_id,
        remote.remote_receipt.evidence_id,True)
