"""Exact expected-policy content; neither source nor selection authorization."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import resources
import json
from typing import Mapping

from jsonschema import Draft202012Validator

from .identity import canonical_bytes

POLICY_SOURCE_PATH = "src/review_broker/profiles/pre-model-v3-expected-policy.json"
POLICY_SHA256 = "6f9c0d9ed04cc708fd633bb7ed12e168338d1c91e92456f7a7188205deb63e63"
POLICY_BLOB_OID = "5bdd27d4d8fd66b591f07a6d165a73aca15a50de"
POLICY_BYTE_LENGTH = 589


class ExpectedPolicyErrorV3(ValueError):
    """Expected-policy content or its independently supplied binding is invalid."""


@dataclass(frozen=True)
class ExpectedPolicyV3:
    """Immutable original bytes; derived mappings are fresh defensive copies."""

    original_bytes: bytes

    def __post_init__(self) -> None:
        _validate_bytes(self.original_bytes)

    @property
    def document(self) -> dict[str, object]:
        return json.loads(self.original_bytes)

    @property
    def basis(self) -> dict[str, object]:
        return {
            "identity_schema_version": 1,
            "permission_profile_name": self.document["policy_name"],
            "permission_profile_sha256": POLICY_SHA256,
        }

    @property
    def technical_policy_id(self) -> str:
        digest = hashlib.sha256(canonical_bytes(self.basis)).hexdigest()
        return f"technical-policy:sha256:{digest}"

    def require_reviewer_agreement(self, request: Mapping[str, object]) -> None:
        if request.get("reviewer") != self.document["reviewer"]:
            raise ExpectedPolicyErrorV3("POLICY_V3_REVIEWER_MISMATCH")


def _validate_bytes(data: bytes) -> None:
    if (type(data) is not bytes or len(data) != POLICY_BYTE_LENGTH
            or hashlib.sha256(data).hexdigest() != POLICY_SHA256):
        raise ExpectedPolicyErrorV3("POLICY_V3_ORIGINAL_BYTES_MISMATCH")
    try:
        document = json.loads(data.decode("utf-8"))
        schema_path = resources.files("review_broker.schemas").joinpath(
            "pre-model-v3-expected-policy.candidate.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(document)
        if canonical_bytes(document) + b"\n" != data:
            raise ExpectedPolicyErrorV3("POLICY_V3_NONCANONICAL")
    except (UnicodeError, ValueError) as exc:
        raise ExpectedPolicyErrorV3("POLICY_V3_INVALID_DOCUMENT") from exc
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if hashlib.sha1(blob).hexdigest() != POLICY_BLOB_OID:
        raise ExpectedPolicyErrorV3("POLICY_V3_BLOB_MISMATCH")


def parse_expected_policy_v3(data: bytes) -> ExpectedPolicyV3:
    """Parse exact canonical bytes without granting authority over their use."""
    return ExpectedPolicyV3(data)
