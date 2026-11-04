"""Separate historical synthetic policy content from authorized expected policy."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from typing import Callable, Mapping

from .admission_v3 import PreclaimAdmissionV3
from .github_actions_identity_v3 import GitHubActionsExpectationV3
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .github_journal_v3 import GitHubJournalV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import decode_journal_v2, encode_journal_v2
from .pre_model_dispatch_ack_v3 import acknowledgment_from_record
from .pre_model_policy_selection_v3 import (
    PolicySelectionAuthorityV3, PolicySelectionContextV3, PolicySelectionReceiptV3,
    verify_policy_selection_v3,
)
from .pre_model_policy_source_v3 import PolicySourceAuthorityV3, PolicySourceObservationV3
from .packet_v2_renderer import RENDERER_ID
from .reviewer_output_contract import CANONICAL_REVIEWER_OUTPUT_INSTRUCTIONS
from .queue import AttemptState
from .request_v3 import request_identity_v3
from .review_intent_v3 import review_intent_identity_v3


class PacketV2CandidateError(ValueError):
    """Candidate packet construction or verification failed closed."""


@dataclass(frozen=True)
class TechnicalProfileSnapshotV2:
    expected_name: str
    actual_name: str
    original_bytes: bytes
    evidence_id: str
    verification: str = "SYNTHETIC_OFFLINE_VERIFIED"


@dataclass(frozen=True)
class AuthorizedPolicySnapshotV3:
    """Evidence bundle, not an authorization merely by being constructed."""

    original_bytes: bytes
    source: PolicySourceObservationV3
    selection: PolicySelectionReceiptV3


PolicySnapshotV2 = TechnicalProfileSnapshotV2 | AuthorizedPolicySnapshotV3


@dataclass(frozen=True)
class AuthorizedPolicyVerificationV3:
    """External trust dependencies; never serialized into the retained packet."""

    journal: GitHubJournalV3
    snapshot: VerifiedJournalSnapshotV3
    expected: GitHubActionsExpectationV3
    source_authority: PolicySourceAuthorityV3
    selection_authority: PolicySelectionAuthorityV3
    effect_guard: Callable[[], None] | None = None

    def before_effect(self) -> None:
        if self.effect_guard is not None:
            self.effect_guard()
        if self.journal.read(self.snapshot.record.attempt.request_id) != self.snapshot:
            raise PacketV2CandidateError("AUTHORIZED_POLICY_JOURNAL_STALE")

    def require_admission(self, admission: Mapping[str, object]) -> None:
        self.before_effect()
        if canonical_bytes(admission) != canonical_bytes(self.snapshot.record.attempt.admission):
            raise PacketV2CandidateError("AUTHORIZED_POLICY_ORIGINAL_ADMISSION_REQUIRED")

    def require_profile(self, profile: PolicySnapshotV2, admission: PreclaimAdmissionV3) -> None:
        self.require_admission(admission.journal_admission())
        if type(profile) is not AuthorizedPolicySnapshotV3:
            raise PacketV2CandidateError("AUTHORIZED_POLICY_MODE_REQUIRED")

    def require_references(self, admission: PreclaimAdmissionV3, observations: tuple) -> None:
        """Bind mutable content/provenance; observation time may legitimately advance."""
        self.require_admission(admission.journal_admission())
        original = iter(admission.issue_reference_observations)
        for item in observations:
            if getattr(item, "source_kind", None) not in {"github_issue_body", "github_issue_comment"}:
                continue
            admitted = next(original)
            fresh_basis, admitted_basis = item.provenance_basis(), admitted.provenance_basis()
            fresh_basis.pop("observed_at", None)
            admitted_basis.pop("observed_at", None)
            if (item.original_bytes != admitted.original_bytes
                    or canonical_bytes(fresh_basis) != canonical_bytes(admitted_basis)):
                raise PacketV2CandidateError("AUTHORIZED_MUTABLE_REFERENCE_CHANGED")

    def prepare_references(self, admission: PreclaimAdmissionV3, readers: Mapping | None) -> tuple:
        from .issue_reference_preparation_v3 import prepare_ordered_remote_observations_v3
        guarded = {}
        for identifier, reader in (readers or {}).items():
            clone = copy.copy(reader)
            executor = reader._executor
            def execute(request, executor=executor):
                self.before_effect()
                return executor(request)
            clone._executor = execute
            guarded[identifier] = clone
        observations = prepare_ordered_remote_observations_v3(admission.request, admission, guarded)
        self.require_references(admission, observations)
        return observations

    def selection_context(self, request: Mapping[str, object]) -> PolicySelectionContextV3:
        self.before_effect()
        snapshot = self.snapshot
        record = decode_journal_v2(snapshot.journal_bytes)
        attempt, control = record.attempt, record.control
        ack = acknowledgment_from_record(record)
        admission = attempt.admission
        if (snapshot.writer_evidence_id is None
                or encode_journal_v2(record) != snapshot.journal_bytes
                or record.as_dict() != snapshot.record.as_dict()
                or attempt.state is not AttemptState.ADMITTED
                or control.generation != 1 or control.disposition != "RESERVED"
                or control.worker is None or control.worker.run_attempt != 1
                or control.failure_receipt_id is not None
                or admission["canonical_request"] != request
                or admission["request_id"] != request_identity_v3(request)
                or admission["review_intent_id"] != review_intent_identity_v3(request)
                or snapshot.claim_ref != self.journal.claim_ref(attempt.request_id)
                or snapshot.repository != self.expected.repository
                or ack is None or ack.broker_repository_id != self.expected.repository_id
                or ack.executable_sha != self.expected.executing_source_sha
                or ack.workflow_run_id != control.worker.run_id):
            raise PacketV2CandidateError("AUTHORIZED_POLICY_ADMITTED_BINDING_REQUIRED")
        return PolicySelectionContextV3(
            attempt.request_id, admission["review_intent_id"], attempt.attempt_id,
            snapshot.claim_ref, control.generation, control.reservation_id,
            control.worker, snapshot.commit_sha)

    def verify(self, profile: AuthorizedPolicySnapshotV3,
               admission: PreclaimAdmissionV3) -> dict[str, object]:
        self.require_profile(profile, admission)
        request = admission.request
        context = self.selection_context(request)
        policy = verify_policy_selection_v3(
            profile.original_bytes, profile.source, profile.selection, context,
            self.expected, self.source_authority, self.selection_authority,
            before_effect=self.before_effect)
        policy.require_reviewer_agreement(request)
        return {"technical_policy_id": policy.technical_policy_id, "basis": policy.basis,
                "profile_evidence_id": artifact_identity(profile.original_bytes),
                "qualification": "PREMODEL_POLICY_SOURCE_VERIFIED_ONLY",
                "policy_source_evidence_id": profile.source.evidence_id,
                "selection_authorization_evidence_id": profile.selection.evidence_id}


def packet_program_v2(request: Mapping[str, object], policy: Mapping[str, object]) -> dict[str, object]:
    """The reviewer program binds the resolved policy content, never its approval."""
    return {"mission": request["mission"], "reviewer": request["reviewer"],
            "technical_policy_id": policy["technical_policy_id"], "renderer_id": RENDERER_ID,
            "output_instructions": CANONICAL_REVIEWER_OUTPUT_INSTRUCTIONS}


def require_policy_boundary_v3(profile: PolicySnapshotV2, admission: PreclaimAdmissionV3 | None,
                               verification: AuthorizedPolicyVerificationV3 | None) -> None:
    if verification is None:
        if type(profile) is AuthorizedPolicySnapshotV3:
            raise PacketV2CandidateError("PACKET_V2_POLICY_AUTHORITY_REQUIRED")
    else:
        if type(verification) is not AuthorizedPolicyVerificationV3 or admission is None:
            raise PacketV2CandidateError("AUTHORIZED_POLICY_BOUNDARY_INVALID")
        verification.require_profile(profile, admission)


def technical_policy_v2(profile: PolicySnapshotV2,
                        request: Mapping[str, object],
                        verification: AuthorizedPolicyVerificationV3 | None = None,
                        admission: PreclaimAdmissionV3 | None = None
                        ) -> dict[str, object]:
    require_policy_boundary_v3(profile, admission, verification)
    if type(profile) is AuthorizedPolicySnapshotV3:
        return verification.verify(profile, admission)
    if (not isinstance(profile, TechnicalProfileSnapshotV2)
            or profile.verification != "SYNTHETIC_OFFLINE_VERIFIED"
            or not profile.expected_name or profile.actual_name != profile.expected_name
            or not isinstance(profile.original_bytes, bytes)
            or profile.evidence_id != artifact_identity(profile.original_bytes)):
        raise PacketV2CandidateError("PACKET_V2_TECHNICAL_PROFILE_INVALID")
    basis = {"identity_schema_version": 1, "permission_profile_name": profile.actual_name,
             "permission_profile_sha256": hashlib.sha256(profile.original_bytes).hexdigest()}
    identity = "technical-policy:sha256:" + hashlib.sha256(canonical_bytes(basis)).hexdigest()
    return {"technical_policy_id": identity, "basis": basis,
            "profile_evidence_id": profile.evidence_id,
            "qualification": "SYNTHETIC_OFFLINE_ONLY"}
