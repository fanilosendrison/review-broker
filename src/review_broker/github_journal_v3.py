"""Injected GitHub transport for the bounded experimental v3 journal core."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Mapping

from .github_journal_transport_v3 import (
    AdmissionAuthorityV3, CreateRefStatusV3, FailureAuthorityV3, GitHubTransportV3,
    GraphQLRefUpdateV3, JournalOutcomeV3, MutationAuthorityV3, OutcomeStatusV3,
    PacketAuthorityV3, PendingWriteV3, PredecessorAuthorityV3, ReadStatusV3,
    RejectionAuthorityV3, TransportSnapshotV3, VerifiedJournalSnapshotV3,
    WorkerAuthorityV3,
)
from .identity import canonical_bytes, request_identity
from .journal_record_v3 import (
    JournalRecordV3, JournalRecordV3Error, WorkerIdentityV3, decode_journal_v2,
    encode_journal_v2, initial_record,
)
from .pre_model_control_v3 import (
    RecordMutationV3, refuse_permanently, register_worker, reserve_initial,
    transition_state,
)
from .queue import AttemptState
from .pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3, DispatchAcknowledgmentAuthorityV3


class GitHubJournalV3Error(RuntimeError):
    """The v3 journal operation was invalid or could not be resolved."""


class GitHubJournalV3:
    """Version-scoped journal using REST create-ref and GraphQL expected-old CAS."""

    CLAIM_PREFIX = "refs/heads/review-claims-v3/"

    def __init__(self, repository: str, repository_node_id: str, base_sha: str,
                 transport: GitHubTransportV3,
                 admission_authority: AdmissionAuthorityV3,
                 mutation_authority: MutationAuthorityV3,
                 rejection_authority: RejectionAuthorityV3,
                 predecessor_authority: PredecessorAuthorityV3, *, operation_guard=None, operation_ready=None):
        if not repository or not repository_node_id or len(base_sha) != 40:
            raise ValueError("V3_JOURNAL_IDENTITY_INVALID")
        self.repository = repository
        self.repository_node_id = repository_node_id
        self.base_sha = base_sha
        self.transport = transport
        self.admission_authority = admission_authority
        self.mutation_authority = mutation_authority
        self.rejection_authority = rejection_authority
        self.predecessor_authority = predecessor_authority
        self.operation_guard = operation_guard
        self.operation_ready = operation_ready

    @staticmethod
    def _is_sha(value: str) -> bool:
        return len(value) == 40 and all(character in "0123456789abcdef" for character in value)

    @classmethod
    def claim_ref(cls, request_id: str) -> str:
        prefix = "request:sha256:"
        if not request_id.startswith(prefix) or len(request_id) != len(prefix) + 64:
            raise GitHubJournalV3Error("REQUEST_ID_INVALID")
        digest = request_id[len(prefix):]
        if any(character not in "0123456789abcdef" for character in digest):
            raise GitHubJournalV3Error("REQUEST_ID_INVALID")
        return cls.CLAIM_PREFIX + digest

    def _verified(self, claim_ref: str, transport: TransportSnapshotV3) -> VerifiedJournalSnapshotV3:
        from .github_journal_snapshot_v3 import verify_journal_snapshot
        return verify_journal_snapshot(self, claim_ref, transport)

    def read(self, request_id: str) -> VerifiedJournalSnapshotV3:
        claim_ref = self.claim_ref(request_id)
        result = self.transport.read_claim(claim_ref)
        if result.status is not ReadStatusV3.FOUND or result.snapshot is None:
            raise GitHubJournalV3Error(f"JOURNAL_READ_{result.status.value}")
        return self._verified(claim_ref, result.snapshot)

    def read_at(self, request_id: str, commit_sha: str) -> VerifiedJournalSnapshotV3:
        from .prepared_journal_history_v3 import read_authenticated_journal_at_v3
        return read_authenticated_journal_at_v3(self, request_id, commit_sha)

    @staticmethod
    def _matches_claim(snapshot: VerifiedJournalSnapshotV3, request_id: str,
                       admission: Mapping[str, object]) -> bool:
        return (snapshot.record.attempt.request_id == request_id
                and canonical_bytes(snapshot.record.attempt.admission)
                == canonical_bytes(dict(admission)))

    def claim(self, request: Mapping[str, object],
              admission: Mapping[str, object]) -> JournalOutcomeV3:
        request_value = deepcopy(dict(request))
        request_id = request_identity(request_value)
        admission_evidence = self.admission_authority.evidence_id(
            repository=self.repository, request=request_value, admission=admission
        )
        if not (isinstance(admission_evidence, str)
                and admission_evidence.startswith("artifact:sha256:")
                and len(admission_evidence) == 80):
            raise GitHubJournalV3Error("ADMISSION_AUTHORITY_UNTRUSTED")
        if request_value.get("schema_version") != 3:
            raise GitHubJournalV3Error("REQUEST_V3_REQUIRED")
        if admission.get("request_id") != request_id:
            raise GitHubJournalV3Error("ADMISSION_REQUEST_ID_MISMATCH")
        record = initial_record(request_id, admission)
        claim_ref = self.claim_ref(request_id)
        encoded = encode_journal_v2(record)
        operation=None if self.operation_guard is None else self.operation_guard(None,claim_ref,encoded)
        intended_sha = self.transport.create_journal_commit(self.base_sha,encoded)
        if self.operation_ready is not None:self.operation_ready(intended_sha,operation)
        pending = PendingWriteV3(
            self.repository, claim_ref, None, intended_sha, request_id,
            deepcopy(dict(admission)), "CREATE_REF",
            creation_evidence_id=admission_evidence,
        )
        result = self.transport.create_ref(claim_ref, intended_sha)
        pending = replace(
            pending,
            writer_evidence_id=result.writer_evidence_id,
            creation_may_reuse_existing=(result.status is not CreateRefStatusV3.CREATED),
        )
        return self._reconcile_create(pending, result.status)

    def _reconcile_create(self, pending: PendingWriteV3,
                          create_status: CreateRefStatusV3) -> JournalOutcomeV3:
        read = self.transport.read_claim(pending.claim_ref)
        if read.status is ReadStatusV3.FOUND and read.snapshot is not None:
            snapshot = self._verified(pending.claim_ref, read.snapshot)
            if self._matches_claim(snapshot, pending.request_id, pending.admission):
                if (create_status is CreateRefStatusV3.CREATED
                        and snapshot.commit_sha != pending.intended_sha):
                    return JournalOutcomeV3(
                        OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
                        reason="CREATED_REF_EXACT_TARGET_UNRESOLVED",
                    )
                evidence = (pending.writer_evidence_id
                            if snapshot.commit_sha == pending.intended_sha
                            else snapshot.writer_evidence_id)
                transport_snapshot = TransportSnapshotV3(
                    snapshot.commit_sha, snapshot.parent_sha, snapshot.journal_bytes
                )
                if (evidence is None
                        or not self.predecessor_authority.permits_evidence(
                            repository=self.repository, claim_ref=pending.claim_ref,
                            snapshot=transport_snapshot, evidence_id=evidence,
                        )):
                    return JournalOutcomeV3(
                        OutcomeStatusV3.UNRESOLVED, snapshot=snapshot, pending=pending,
                        reason="CREATED_REF_WRITER_UNATTRIBUTED",
                    )
                attributed = replace(snapshot, writer_evidence_id=evidence)
                return JournalOutcomeV3(OutcomeStatusV3.COMMITTED, snapshot=attributed)
            return JournalOutcomeV3(
                OutcomeStatusV3.REJECTED, snapshot=snapshot, reason="CLAIM_IDENTITY_CONFLICT"
            )
        if create_status is CreateRefStatusV3.ALREADY_EXISTS and read.status is ReadStatusV3.MISSING:
            return JournalOutcomeV3(
                OutcomeStatusV3.UNRESOLVED, pending=pending,
                reason="EXISTING_CLAIM_READBACK_NOT_VISIBLE",
            )
        return JournalOutcomeV3(
            OutcomeStatusV3.UNRESOLVED, pending=pending,
            reason="CLAIM_CREATION_ACKNOWLEDGMENT_UNRESOLVED",
        )

    from .github_journal_reconciliation_v3 import reconcile_pending_write_v3 as reconcile

    def _transition(self, current: VerifiedJournalSnapshotV3,
                    mutation: RecordMutationV3, before_effect=None) -> JournalOutcomeV3:
        if current.repository != self.repository or current.repository_node_id != self.repository_node_id:
            raise GitHubJournalV3Error("SNAPSHOT_REPOSITORY_MISMATCH")
        reread = decode_journal_v2(current.journal_bytes)
        if current.claim_ref != self.claim_ref(reread.attempt.request_id):
            raise GitHubJournalV3Error("SNAPSHOT_CLAIM_REF_MISMATCH")
        if not self._is_sha(current.commit_sha) or not self._is_sha(current.parent_sha):
            raise GitHubJournalV3Error("SNAPSHOT_COMMIT_IDENTITY_INVALID")
        if current.writer_evidence_id is None:
            raise GitHubJournalV3Error("PREDECESSOR_WRITER_EVIDENCE_UNAVAILABLE")
        transport_snapshot = TransportSnapshotV3(
            current.commit_sha, current.parent_sha, current.journal_bytes
        )
        if not self.predecessor_authority.permits_evidence(
            repository=self.repository, claim_ref=current.claim_ref,
            snapshot=transport_snapshot, evidence_id=current.writer_evidence_id,
        ):
            raise GitHubJournalV3Error("PREDECESSOR_WRITER_EVIDENCE_UNTRUSTED")
        if encode_journal_v2(current.record) != current.journal_bytes:
            raise GitHubJournalV3Error("SNAPSHOT_RECORD_MISMATCH")
        try:
            successor = mutation(reread)
            encoded = encode_journal_v2(successor)
        except JournalRecordV3Error as exc:
            raise GitHubJournalV3Error(str(exc)) from exc
        operation=None if self.operation_guard is None else self.operation_guard(current,current.claim_ref,encoded)
        if before_effect is not None: before_effect()
        successor_sha = self.transport.create_journal_commit(current.commit_sha, encoded)
        if self.operation_ready is not None:self.operation_ready(successor_sha,operation)
        pending = PendingWriteV3(
            self.repository, current.claim_ref, current.commit_sha, successor_sha,
            current.record.attempt.request_id,
            deepcopy(current.record.attempt.admission or {}), "UPDATE_REFS",
        )
        update = GraphQLRefUpdateV3(
            repository_id=self.repository_node_id,
            name=current.claim_ref,
            before_oid=current.commit_sha,
            after_oid=successor_sha,
            force=False,
        )
        try:
            if before_effect is not None: before_effect()
            result = self.transport.update_ref(update)
            evidence = result.writer_evidence_id
            if not (result.http_status == 200 and not result.errors
                    and isinstance(evidence, str)
                    and evidence.startswith("artifact:sha256:") and len(evidence) == 80
                    and all(character in "0123456789abcdef" for character in evidence[16:])
                    and self.mutation_authority.permits(update, evidence)):
                evidence = None
            # Retain each independently recognized result before any further
            # authority/readback call can fail. Unknown evidence stays absent.
            pending = replace(pending, writer_evidence_id=evidence, application_errors=result.errors)
            rejection_evidence = result.rejection_evidence_id
            definite_rejection = (
                result.http_status == 200 and bool(result.errors)
                and result.expected_old_rejected
                and isinstance(rejection_evidence, str)
                and self.rejection_authority.permits(update, rejection_evidence)
            )
            pending = replace(pending, expected_old_rejected=definite_rejection,
                              rejection_evidence_id=rejection_evidence if definite_rejection else None)
            return self.reconcile(pending)
        except Exception:
            # The intended successor is already known; never discard its pending
            # record or turn an observation failure into another write permit.
            return JournalOutcomeV3(OutcomeStatusV3.UNRESOLVED, pending=pending,
                                    reason="TRANSITION_RESULT_UNRESOLVED")

    def reserve_initial(self, current: VerifiedJournalSnapshotV3) -> JournalOutcomeV3:
        return self._transition(current, reserve_initial)

    def acknowledge_dispatch(self, current: VerifiedJournalSnapshotV3,
                             receipt: DispatchAcknowledgmentV3,
                             authority: DispatchAcknowledgmentAuthorityV3) -> JournalOutcomeV3:
        from .pre_model_control_v3 import acknowledge_dispatch
        if (receipt.reservation_commit_sha != current.commit_sha
                or receipt.broker_repository != self.repository
                or authority.permits_ack(current, receipt) is not True):
            raise GitHubJournalV3Error("DISPATCH_ACK_AUTHORITY_UNTRUSTED")
        return self._transition(current, lambda record: acknowledge_dispatch(record, receipt))

    def register_worker(self, current: VerifiedJournalSnapshotV3, reservation_id: str,
                        generation: int, worker: WorkerIdentityV3,
                        authority: WorkerAuthorityV3) -> JournalOutcomeV3:
        from .pre_model_dispatch_ack_v3 import check_worker_ack_authority
        try:
            check_worker_ack_authority(current, authority)
        except ValueError as exc:
            raise GitHubJournalV3Error(str(exc)) from exc
        attempt = current.record.attempt
        authority_evidence_id = authority.evidence_id(
            repository=self.repository, request_id=attempt.request_id,
            attempt_id=attempt.attempt_id, reservation_id=reservation_id,
            generation=generation, worker=worker,
        )
        if authority_evidence_id is None:
            raise GitHubJournalV3Error("WORKER_AUTHORITY_UNTRUSTED")
        return self._transition(
            current,
            lambda record: register_worker(
                record, reservation_id, generation, worker, authority_evidence_id
            ),
        )

    def record_admission(self, current: VerifiedJournalSnapshotV3, evidence_id: str,
                         reservation_id: str, generation: int,
                         worker: WorkerIdentityV3) -> JournalOutcomeV3:
        return self._transition(current, lambda record: transition_state(
            record, AttemptState.ADMITTED, evidence_id, reservation_id, generation, worker
        ))

    def prepare(self, current: VerifiedJournalSnapshotV3, packet_evidence_id: str,
                reservation_id: str, generation: int,
                worker: WorkerIdentityV3,
                authority: PacketAuthorityV3, *, before_effect=None) -> JournalOutcomeV3:
        if not authority.permits(
            snapshot=current, packet_evidence_id=packet_evidence_id,
            reservation_id=reservation_id, generation=generation, worker=worker,
        ):
            raise GitHubJournalV3Error("PACKET_AUTHORITY_UNTRUSTED")
        return self._transition(current, lambda record: transition_state(
            record, AttemptState.PREPARED, packet_evidence_id,
            reservation_id, generation, worker
        ), before_effect)

    def refuse_permanently(self, current: VerifiedJournalSnapshotV3,
                           failure_receipt_id: str, receipt: Mapping[str, object],
                           reservation_id: str, generation: int,
                           worker: WorkerIdentityV3,
                           authority: FailureAuthorityV3) -> JournalOutcomeV3:
        if not authority.permits(receipt):
            raise GitHubJournalV3Error("FAILURE_AUTHORITY_UNTRUSTED")
        return self._transition(current, lambda record: refuse_permanently(
            record, failure_receipt_id, receipt, reservation_id, generation, worker
        ))

    from .github_journal_failure_v3 import block_pre_model

    def unsupported(self, operation: str) -> None:
        raise GitHubJournalV3Error(f"V3_OPERATION_UNSUPPORTED:{operation}")
