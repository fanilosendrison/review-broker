"""Pinned broker-policy provenance, verified by an injected independent authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Protocol

from .github_actions_identity_v3 import GitHubActionsExpectationV3
from .identity import artifact_identity, canonical_bytes
from .pre_model_policy_v3 import (
    ExpectedPolicyErrorV3, ExpectedPolicyV3, POLICY_BLOB_OID, POLICY_BYTE_LENGTH,
    POLICY_SHA256, POLICY_SOURCE_PATH, parse_expected_policy_v3,
)


@dataclass(frozen=True)
class PolicySourceObservationV3:
    schema_version: int
    evidence_type: str
    broker_repository: str
    broker_repository_id: int
    executing_source_sha: str
    source_commit_sha: str
    source_path: str
    git_blob_oid: str
    original_sha256: str
    original_byte_length: int
    source_authority_evidence_id: str

    def __post_init__(self) -> None:
        values = asdict(self)
        numeric = {"schema_version", "broker_repository_id", "original_byte_length"}
        if any(type(value) is not (int if key in numeric else str)
               for key, value in values.items()):
            raise ExpectedPolicyErrorV3("POLICY_V3_SOURCE_RECEIPT_TYPES_INVALID")

    @property
    def basis(self) -> dict[str, object]:
        return asdict(self)

    @property
    def canonical_receipt_bytes(self) -> bytes:
        return canonical_bytes(self.basis) + b"\n"

    @property
    def evidence_id(self) -> str:
        return artifact_identity(self.canonical_receipt_bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> PolicySourceObservationV3:
        try:
            observation = cls(**json.loads(data.decode("utf-8")))
            if observation.canonical_receipt_bytes != data:
                raise ValueError("noncanonical source observation")
            return observation
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ExpectedPolicyErrorV3("POLICY_V3_SOURCE_RECEIPT_INVALID") from exc


class PolicySourceAuthorityV3(Protocol):
    """Trusted dependency, not recovered from packet bytes or requester input.

    Implementations must independently recognize the exact source object and
    original content. A local digest check alone does not implement this contract.
    Verification raises on unrecognized provenance; it never creates approval.
    """

    def read_policy(self, expectation: GitHubActionsExpectationV3
                    ) -> tuple[bytes, PolicySourceObservationV3]: ...

    def verify_source(self, observation: PolicySourceObservationV3,
                      original_bytes: bytes,
                      expectation: GitHubActionsExpectationV3) -> None: ...


def verify_policy_source_v3(
    original_bytes: bytes, observation: PolicySourceObservationV3,
    expectation: GitHubActionsExpectationV3,
    authority: PolicySourceAuthorityV3 | None,
) -> ExpectedPolicyV3:
    """Check content and bindings, then require independent provenance evidence."""
    policy = parse_expected_policy_v3(original_bytes)
    if authority is None:
        raise ExpectedPolicyErrorV3("POLICY_V3_SOURCE_AUTHORITY_REQUIRED")
    if (type(observation) is not PolicySourceObservationV3
            or type(observation.schema_version) is not int
            or observation.schema_version != 1
            or observation.evidence_type != "v3-broker-policy-source-observation"
            or observation.broker_repository != expectation.repository
            or type(observation.broker_repository_id) is not int
            or observation.broker_repository_id < 1
            or observation.broker_repository_id != expectation.repository_id
            or observation.executing_source_sha != expectation.executing_source_sha
            or re.fullmatch(r"[0-9a-f]{40}", observation.source_commit_sha) is None
            or observation.source_commit_sha != expectation.executing_source_sha
            or observation.source_path != POLICY_SOURCE_PATH
            or observation.git_blob_oid != POLICY_BLOB_OID
            or observation.original_sha256 != POLICY_SHA256
            or type(observation.original_byte_length) is not int
            or observation.original_byte_length != POLICY_BYTE_LENGTH
            or not isinstance(observation.source_authority_evidence_id, str)
            or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",
                            observation.source_authority_evidence_id) is None):
        raise ExpectedPolicyErrorV3("POLICY_V3_SOURCE_BINDING_MISMATCH")
    authority.verify_source(observation, original_bytes, expectation)
    return policy
