"""Request-bound policy decisions requiring independently recognized approval."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Protocol

from .github_actions_identity_v3 import GitHubActionsExpectationV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import WorkerIdentityV3
from .pre_model_policy_source_v3 import (
    PolicySourceAuthorityV3, PolicySourceObservationV3, verify_policy_source_v3,
)
from .pre_model_policy_v3 import ExpectedPolicyErrorV3, ExpectedPolicyV3, POLICY_SHA256


@dataclass(frozen=True)
class PolicySelectionContextV3:
    """Bindings obtained from authenticated ADMITTED state, not retained assertions."""

    request_id: str
    review_intent_id: str
    attempt_id: str
    claim_ref: str
    generation: int
    reservation_id: str
    worker: WorkerIdentityV3
    admitted_commit_sha: str

    def __post_init__(self) -> None:
        for value, domain in ((self.request_id, "request"),
                              (self.review_intent_id, "review-intent"),
                              (self.attempt_id, "attempt")):
            if not isinstance(value, str) or re.fullmatch(
                    rf"{domain}:sha256:[0-9a-f]{{64}}", value) is None:
                raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_CONTEXT_INVALID")
        if (type(self.generation) is not int or self.generation != 1
                or not isinstance(self.worker, WorkerIdentityV3)
                or self.worker.run_attempt != 1
                or not isinstance(self.claim_ref, str)
                or not self.claim_ref.startswith("refs/")
                or not isinstance(self.reservation_id, str) or not self.reservation_id
                or not isinstance(self.admitted_commit_sha, str)
                or re.fullmatch(r"[0-9a-f]{40}", self.admitted_commit_sha) is None):
            raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_CONTEXT_INVALID")

    @property
    def basis(self) -> dict[str, object]:
        return {**asdict(self), "worker": self.worker.as_dict()}


@dataclass(frozen=True)
class PolicySelectionReceiptV3:
    schema_version: int
    evidence_type: str
    broker_repository: str
    broker_repository_id: int
    executing_source_sha: str
    policy_source_commit_sha: str
    policy_source_path: str
    policy_source_evidence_id: str
    policy_name: str
    policy_revision: int
    policy_sha256: str
    technical_policy_id: str
    request_id: str
    review_intent_id: str
    attempt_id: str
    claim_ref: str
    generation: int
    reservation_id: str
    worker: WorkerIdentityV3
    admitted_commit_sha: str
    decision_authority_evidence_id: str

    def __post_init__(self) -> None:
        numeric = {"schema_version", "broker_repository_id", "policy_revision", "generation"}
        if (not isinstance(self.worker, WorkerIdentityV3)
                or any(type(value) is not (int if key in numeric else str)
                       for key, value in asdict(self).items() if key != "worker")):
            raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_RECEIPT_TYPES_INVALID")

    @property
    def basis(self) -> dict[str, object]:
        return {**asdict(self), "worker": self.worker.as_dict()}

    @property
    def canonical_receipt_bytes(self) -> bytes:
        return canonical_bytes(self.basis) + b"\n"

    @property
    def evidence_id(self) -> str:
        return artifact_identity(self.canonical_receipt_bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> PolicySelectionReceiptV3:
        try:
            fields = json.loads(data.decode("utf-8"))
            fields["worker"] = WorkerIdentityV3(**fields["worker"])
            receipt = cls(**fields)
            if receipt.canonical_receipt_bytes != data:
                raise ValueError("noncanonical selection receipt")
            return receipt
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_RECEIPT_INVALID") from exc


class PolicySelectionAuthorityV3(Protocol):
    """Independent approved-decision archive; never approval by digest alone."""

    def select_policy(self, source: PolicySourceObservationV3,
                      context: PolicySelectionContextV3,
                      expectation: GitHubActionsExpectationV3
                      ) -> PolicySelectionReceiptV3: ...

    def verify_selection(self, receipt: PolicySelectionReceiptV3,
                         source: PolicySourceObservationV3,
                         context: PolicySelectionContextV3,
                         expectation: GitHubActionsExpectationV3) -> None: ...


def verify_policy_selection_v3(
    original_bytes: bytes, source: PolicySourceObservationV3,
    receipt: PolicySelectionReceiptV3, context: PolicySelectionContextV3,
    expectation: GitHubActionsExpectationV3,
    source_authority: PolicySourceAuthorityV3 | None,
    selection_authority: PolicySelectionAuthorityV3 | None,
) -> ExpectedPolicyV3:
    """Reverify provenance before checking the exact independently approved decision."""
    policy = verify_policy_source_v3(original_bytes, source, expectation, source_authority)
    if selection_authority is None:
        raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_AUTHORITY_REQUIRED")
    if (type(receipt) is not PolicySelectionReceiptV3
            or type(context) is not PolicySelectionContextV3):
        raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_RECEIPT_INVALID")
    expected = {
        "schema_version": 1, "evidence_type": "v3-broker-policy-selection",
        "broker_repository": expectation.repository,
        "broker_repository_id": expectation.repository_id,
        "executing_source_sha": expectation.executing_source_sha,
        "policy_source_commit_sha": source.source_commit_sha,
        "policy_source_path": source.source_path,
        "policy_source_evidence_id": source.evidence_id,
        "policy_name": policy.document["policy_name"],
        "policy_revision": policy.document["policy_revision"],
        "policy_sha256": POLICY_SHA256,
        "technical_policy_id": policy.technical_policy_id,
        **context.basis,
        "decision_authority_evidence_id": receipt.decision_authority_evidence_id,
    }
    if (canonical_bytes(receipt.basis) != canonical_bytes(expected)
            or not isinstance(receipt.decision_authority_evidence_id, str)
            or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",
                            receipt.decision_authority_evidence_id) is None):
        raise ExpectedPolicyErrorV3("POLICY_V3_SELECTION_BINDING_MISMATCH")
    selection_authority.verify_selection(receipt, source, context, expectation)
    return policy
