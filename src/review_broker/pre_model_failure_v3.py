"""Validate the bounded candidate v3 permanent preparation-failure receipt."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping, Protocol

from .identity import artifact_identity, canonical_bytes


class WorkerIdentityForFailureV3(Protocol):
    run_id: int
    run_attempt: int


class PreModelFailureV3Error(ValueError):
    pass


_ARTIFACT = re.compile(r"artifact:sha256:[0-9a-f]{64}\Z")
_REQUIRED_FIELDS = {
    "schema_version", "evidence_type", "request_id", "attempt_id",
    "admission_evidence_id", "generation", "reservation_id",
    "workflow_run_id", "workflow_run_attempt", "classification",
    "reason_code", "reference_id", "observation_evidence_id", "observed_at",
}
_REASON_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_REFERENCE_ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def validate_permanent_failure_receipt(
    receipt: Mapping[str, object], *, failure_receipt_id: str,
    request_id: str, attempt_id: str, admission_evidence_id: object,
    generation: int, reservation_id: str, worker: WorkerIdentityForFailureV3,
    accepted_reference_ids: object,
) -> dict[str, object]:
    value = dict(receipt)
    if set(value) != _REQUIRED_FIELDS:
        raise PreModelFailureV3Error("FAILURE_RECEIPT_FIELDS_INVALID")
    identities_match = (
        type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["evidence_type"] == "pre-model-preparation-failure"
        and value["request_id"] == request_id
        and value["attempt_id"] == attempt_id
        and isinstance(admission_evidence_id, str)
        and _ARTIFACT.fullmatch(admission_evidence_id) is not None
        and value["admission_evidence_id"] == admission_evidence_id
        and type(value["generation"]) is int
        and value["generation"] == generation
        and value["reservation_id"] == reservation_id
        and type(value["workflow_run_id"]) is int
        and value["workflow_run_id"] == worker.run_id
        and type(value["workflow_run_attempt"]) is int
        and value["workflow_run_attempt"] == worker.run_attempt
        and value["classification"] == "PERMANENT"
        and value["reason_code"] == "SOURCE_DIGEST_MISMATCH"
    )
    if not identities_match:
        raise PreModelFailureV3Error("FAILURE_RECEIPT_IDENTITY_INVALID")
    reference = value["reference_id"]
    values_valid = (
        isinstance(value["reason_code"], str)
        and _REASON_CODE.fullmatch(value["reason_code"]) is not None
        and isinstance(reference, str)
        and _REFERENCE_ID.fullmatch(reference) is not None
        and isinstance(accepted_reference_ids, list)
        and reference in accepted_reference_ids
        and isinstance(value["observation_evidence_id"], str)
        and _ARTIFACT.fullmatch(value["observation_evidence_id"]) is not None
        and isinstance(value["observed_at"], str)
        and _TIMESTAMP.fullmatch(value["observed_at"]) is not None
    )
    if values_valid:
        try:
            observed_at = datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
            values_valid = observed_at.tzinfo == timezone.utc
        except ValueError:
            values_valid = False
    if not values_valid:
        raise PreModelFailureV3Error("FAILURE_RECEIPT_VALUE_INVALID")
    if failure_receipt_id != artifact_identity(canonical_bytes(value) + b"\n"):
        raise PreModelFailureV3Error("FAILURE_RECEIPT_ID_INVALID")
    return value
