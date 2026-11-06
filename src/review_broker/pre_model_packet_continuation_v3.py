"""One bounded offline continuation from a current Worker to a cold-verified packet."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Mapping, Protocol

from .admission_evidence_v3 import validate_journal_admission_v3
from .admission_v3 import PreclaimAdmissionV3
from .github_actions_worker_authority_v3 import WorkerExecutionContextV3
from .github_issue_reference_v3 import GitHubIssueReferenceReaderV3
from .github_journal_transport_v3 import (
    GraphQLRefUpdateV3, JournalOutcomeV3, OutcomeStatusV3, VerifiedJournalSnapshotV3,
)
from .github_journal_v3 import GitHubJournalV3
from .identity import canonical_bytes
from .issue_reference_preparation_v3 import prepare_ordered_remote_observations_v3
from .journal_record_v3 import encode_journal_v2
from .packet_v2_subject import SubjectCaptureV2
from .packet_v2 import validate_subject_capture_v2
from .packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from .packet_v2_reference import build_reference_entries_v2
from .pre_model_control_v3 import transition_state
from .pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
from .pre_model_policy_selection_v3 import (
    PolicySelectionAuthorityV3, PolicySelectionContextV3, PolicySelectionReceiptV3,
    verify_policy_selection_v3,
)
from .pre_model_policy_source_v3 import (
    PolicySourceAuthorityV3, PolicySourceObservationV3, verify_policy_source_v3,
)
from .queue import AttemptState
from .pre_model_active_decision_v3 import _issue_active_decision_v3
from .pre_model_failure_boundaries_v3 import PreModelFailureCollectorV3
from .pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3
from .pre_model_failure_continuation_v3 import PreModelFailureContinuationV3, PreModelFailureResultV3
from .prepared_journal_history_v3 import require_snapshot_origin_v3

BeforeEffectV3 = Callable[[], None]
ReferenceReadersV3 = Mapping[str, GitHubIssueReferenceReaderV3]


class SubjectCaptureProviderV3(Protocol):
    """Injected offline acquisition, using existing source verification mechanisms.

    Call before_effect immediately before EVERY external read and local persistent
    effect, including internal transport calls. No implicit network fallback.
    """

    def capture(self, admission: PreclaimAdmissionV3,
                before_effect: BeforeEffectV3, *,
                failure_observer: PreModelFailureCollectorV3 | None = None) -> SubjectCaptureV2: ...


class PacketContinuationStagesV3(Protocol):
    """Explicit packet handoff; implementation belongs to packet/retention modules.

    Stages must guard their internal effect boundaries, not only method entry.
    Cold verification must use independently injected trust, never Worker memory.
    """

    def build(self, admission: PreclaimAdmissionV3, capture: SubjectCaptureV2,
              policy_bytes: bytes, source: PolicySourceObservationV3,
              selection: PolicySelectionReceiptV3, selection_context: PolicySelectionContextV3,
              readers: ReferenceReadersV3, before_effect: BeforeEffectV3) -> Path: ...

    def verify(self, candidate: Path, before_effect: BeforeEffectV3) -> dict[str, object]: ...

    def persist(self, candidate: Path, snapshot: VerifiedJournalSnapshotV3,
                before_effect: BeforeEffectV3) -> Path: ...

    def cold_verify(self, retained: Path, snapshot: VerifiedJournalSnapshotV3,
                    before_effect: BeforeEffectV3) -> dict[str, object]: ...


@dataclass(frozen=True)
class PreModelPacketContinuationResultV3:
    status: OutcomeStatusV3
    reason: str
    journal_outcome: JournalOutcomeV3 | None = None
    retained_root: Path | None = None
    packet_id: str | None = None


class PreModelPacketContinuationV3:
    """No retry, resume, dispatch, PREPARED, remote retention or inference API.

    A freshness check does not establish cross-system atomicity. Injected effects
    remain responsible for honoring the guard at their actual transport/write edge.
    """

    def __init__(self, *, journal: GitHubJournalV3,
                 current_worker_authority: CurrentBoundWorkerAuthorityV3,
                 original_admission: PreclaimAdmissionV3,
                 capture_provider: SubjectCaptureProviderV3,
                 reference_readers: Callable[[BeforeEffectV3], ReferenceReadersV3],
                 policy_source_authority: PolicySourceAuthorityV3,
                 policy_selection_authority: PolicySelectionAuthorityV3,
                 packet_stages: PacketContinuationStagesV3,
                 failure_evidence: PreModelFailureEvidenceV3 | None = None):
        if current_worker_authority.journal is not journal:
            raise ValueError("CONTINUATION_AUTHORITY_JOURNAL_MISMATCH")
        self.journal, self.authority = journal, current_worker_authority
        self.admission, self.capture_provider = original_admission, capture_provider
        self.reference_readers = reference_readers
        self.source_authority, self.selection_authority = (
            policy_source_authority, policy_selection_authority)
        self.stages = packet_stages
        self._lock, self._attempted = Lock(), False
        self._remote_handoff = None
        if failure_evidence is not None and type(failure_evidence) is not PreModelFailureEvidenceV3:
            raise ValueError("CLOSED_FAILURE_EVIDENCE_BOUNDARY_REQUIRED")
        self.failure_evidence = failure_evidence
        self._decision, self._decision_issue_gate, self._decision_admitted_outcome = None, None, None

    def claim_remote_continuation(self, context, handoff, *, remote_owner=None):
        """Consume this original process's completed handoff, never an ADMITTED read."""
        with self._lock:
            if (self._remote_handoff is None or self._remote_handoff[0] is not context
                    or self._remote_handoff[1] is not handoff or self._decision is None):
                raise ValueError("ORIGINAL_WORKER_REMOTE_CONTINUATION_REQUIRED")
            self._decision._transfer_after_handoff(self, remote_owner, context, handoff)
            self._remote_handoff = None
            return self._decision

    def run(self, context: WorkerExecutionContextV3) -> PreModelPacketContinuationResultV3 | PreModelFailureResultV3:
        with self._lock:
            if self._attempted:
                return PreModelPacketContinuationResultV3(
                    OutcomeStatusV3.UNRESOLVED, "OBSERVER_ONLY_NO_RETRY")
            self._attempted = True
        outcome = None
        decision, collector = None, None
        mutation_started = False
        try:
            self.authority.authenticate_context(context)
            current = self.journal.read(context.inputs.request_id)
            worker = self.authority.require_current(context, current, AttemptState.REQUESTED)
            admission = self.admission
            validated = validate_journal_admission_v3(
                current.record.attempt.admission, admission.origin_body_bytes)
            if (current.record.attempt.admission != admission.journal_admission()
                    or validated["admission_evidence_id"] != admission.admission_evidence_id
                    or admission.canonical_request_bytes != canonical_bytes(admission.request)
                    or admission.request_id != context.inputs.request_id):
                raise ValueError("CONTINUATION_ORIGINAL_ADMISSION_MISMATCH")
            if admission.request["atomicity"] is not False:
                raise ValueError("CONTINUATION_COHERENT_CUT_NOT_QUALIFIED")
            expected_successor = transition_state(
                current.record, AttemptState.ADMITTED, admission.admission_evidence_id,
                context.inputs.reservation_id, 1, worker)
            self.authority.require_current(context, current, AttemptState.REQUESTED)
            mutation_started = True
            outcome = self.journal.record_admission(
                current, admission.admission_evidence_id, context.inputs.reservation_id, 1, worker)
            after = outcome.snapshot
            if outcome.status is not OutcomeStatusV3.COMMITTED:
                return PreModelPacketContinuationResultV3(
                    outcome.status, "ADMITTED_CAS_NOT_ATTRIBUTED_NO_RETRY", outcome)
            if (outcome.pending is not None or after is None
                    or after.parent_sha != current.commit_sha
                    or after.journal_bytes != encode_journal_v2(expected_successor)
                    or after.writer_evidence_id is None
                    or self.journal.mutation_authority.permits(GraphQLRefUpdateV3(
                        current.repository_node_id, current.claim_ref,
                        current.commit_sha, after.commit_sha, False),
                        after.writer_evidence_id) is not True
                    or self.journal.read(admission.request_id) != after):
                return PreModelPacketContinuationResultV3(
                    OutcomeStatusV3.UNRESOLVED, "ADMITTED_CAS_NOT_ATTRIBUTED_NO_RETRY", outcome)

            require_snapshot_origin_v3(self.journal, after)
            issuer = object()
            self._decision_admitted_outcome, self._decision_issue_gate = outcome, issuer
            decision = _issue_active_decision_v3(self, context, outcome, issuer)

            def before_effect() -> None:
                decision.require_active(self)
                self.authority.require_current(context, after, AttemptState.ADMITTED)

            if self.failure_evidence is not None:
                collector = PreModelFailureCollectorV3(decision=decision, owner=self,
                    evidence=self.failure_evidence, before_effect=before_effect)
            before_effect()
            capture = (self.capture_provider.capture(admission, before_effect) if collector is None
                       else self.capture_provider.capture(admission, before_effect, failure_observer=collector))
            before_effect()
            validate_subject_capture_v2(admission, capture, before_effect=before_effect)
            before_effect()
            readers = self.reference_readers(before_effect)
            if collector is not None: readers = collector.bind_reference_readers(readers)
            before_effect()
            verification = AuthorizedPolicyVerificationV3(
                self.journal, after, self.authority.expected,
                self.source_authority, self.selection_authority, before_effect)
            remote = verification.prepare_references(admission, readers)
            build_reference_entries_v2(admission.request, len(capture.records) + 1, remote)
            before_effect()
            policy_bytes, source = self.source_authority.read_policy(
                self.authority.expected, before_effect=before_effect)
            policy = verify_policy_source_v3(
                policy_bytes, source, self.authority.expected, self.source_authority,
                before_effect=before_effect)
            policy.require_reviewer_agreement(admission.request)
            control = after.record.control
            selection_context = PolicySelectionContextV3(
                admission.request_id, admission.review_intent_id, after.record.attempt.attempt_id,
                after.claim_ref, control.generation, control.reservation_id, worker, after.commit_sha)
            before_effect()
            selection = self.selection_authority.select_policy(
                source, selection_context, self.authority.expected, before_effect=before_effect)
            verify_policy_selection_v3(
                policy_bytes, source, selection, selection_context, self.authority.expected,
                self.source_authority, self.selection_authority, before_effect=before_effect)
            before_effect()
            candidate = self.stages.build(admission, capture, policy_bytes, source, selection,
                                           selection_context, readers, before_effect)
            before_effect()
            manifest = self.stages.verify(candidate, before_effect)
            before_effect()
            retained = self.stages.persist(candidate, after, before_effect)
            before_effect()
            cold = self.stages.cold_verify(retained, after, before_effect)
            if canonical_bytes(cold) != canonical_bytes(manifest):
                raise ValueError("CONTINUATION_COLD_RECONSTRUCTION_MISMATCH")
            before_effect()
            result = PreModelPacketContinuationResultV3(
                OutcomeStatusV3.COMMITTED, "RWP03_OFFLINE_LOCAL_PACKET_COMPLETE",
                outcome, retained, str(manifest["packet_id"]))
            decision._publish_handoff(self, context, result)
            return result
        except Exception as exc:
            if collector is not None:
                failure = PreModelFailureContinuationV3(collector).run()
                if failure is not None: return failure
            return PreModelPacketContinuationResultV3(
                OutcomeStatusV3.UNRESOLVED if mutation_started else OutcomeStatusV3.REJECTED,
                f"CONTINUATION_UNCONFIRMED_NO_RETRY:{type(exc).__name__}", outcome)
        finally:
            self._decision_issue_gate = None
            if decision is not None and self._remote_handoff is None:
                decision.close(self)
