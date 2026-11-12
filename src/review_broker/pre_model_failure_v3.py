"""Validate the bounded candidate v3 permanent preparation-failure receipt."""
from __future__ import annotations

import re
from typing import Mapping, Protocol

from .identity import artifact_identity, canonical_bytes
from .pre_model_failure_time_v3 import valid_failure_observed_at_v3


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
        and valid_failure_observed_at_v3(value["observed_at"])
    )
    if not values_valid:
        raise PreModelFailureV3Error("FAILURE_RECEIPT_VALUE_INVALID")
    if failure_receipt_id != artifact_identity(canonical_bytes(value) + b"\n"):
        raise PreModelFailureV3Error("FAILURE_RECEIPT_ID_INVALID")
    return value


def validate_blocked_failure_receipt(
    receipt: Mapping[str, object], *, failure_receipt_id: str,
    request_id: str, attempt_id: str, admission_evidence_id: object,
    generation: int, reservation_id: str, worker: WorkerIdentityForFailureV3,
    accepted_reference_ids: object,
) -> dict[str, object]:
    """Distinct ADMITTED+ validator; does not broaden permanent combinations."""
    from .pre_model_failure_observation_v3 import BLOCKED_REASONS
    value = dict(receipt)
    if set(value) != _REQUIRED_FIELDS:
        raise PreModelFailureV3Error("BLOCKED_FAILURE_RECEIPT_FIELDS_INVALID")
    reason = value["reason_code"]
    if (type(reason) is not str or reason not in BLOCKED_REASONS
            or value["classification"] != BLOCKED_REASONS[reason]
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["evidence_type"] != "pre-model-preparation-failure"
            or value["request_id"] != request_id or value["attempt_id"] != attempt_id
            or not isinstance(admission_evidence_id, str)
            or _ARTIFACT.fullmatch(admission_evidence_id) is None
            or value["admission_evidence_id"] != admission_evidence_id
            or type(generation) is not int or generation != 1
            or type(value["generation"]) is not int or value["generation"] != 1
            or value["reservation_id"] != reservation_id
            or type(value["workflow_run_id"]) is not int
            or value["workflow_run_id"] != worker.run_id
            or type(value["workflow_run_attempt"]) is not int
            or value["workflow_run_attempt"] != 1 or worker.run_attempt != 1):
        raise PreModelFailureV3Error("BLOCKED_FAILURE_RECEIPT_IDENTITY_INVALID")
    reference = value["reference_id"]
    reference_reason = reason in {"SOURCE_API_UNAVAILABLE", "SOURCE_ACCESS_AMBIGUOUS"}
    if (reference_reason and (not isinstance(reference, str)
            or _REFERENCE_ID.fullmatch(reference) is None
            or not isinstance(accepted_reference_ids, list) or reference not in accepted_reference_ids)
            or not reference_reason and reference is not None
            or not isinstance(value["observation_evidence_id"], str)
            or _ARTIFACT.fullmatch(value["observation_evidence_id"]) is None
            or not valid_failure_observed_at_v3(value["observed_at"])):
        raise PreModelFailureV3Error("BLOCKED_FAILURE_RECEIPT_VALUE_INVALID")
    if failure_receipt_id != artifact_identity(canonical_bytes(value) + b"\n"):
        raise PreModelFailureV3Error("BLOCKED_FAILURE_RECEIPT_ID_INVALID")
    return value


def blocked_failure_receipt_v3(snapshot, observation) -> dict[str, object]:
    """Pure receipt projection; external provenance and current authority are separate."""
    from .pre_model_failure_observation_v3 import FailureObservationV3
    if type(observation) is not FailureObservationV3:
        raise PreModelFailureV3Error("ORIGINAL_FAILURE_OBSERVATION_REQUIRED")
    attempt, control, value = snapshot.record.attempt, snapshot.record.control, observation.value
    receipt = {"schema_version": 1, "evidence_type": "pre-model-preparation-failure",
        "request_id": attempt.request_id, "attempt_id": attempt.attempt_id,
        "admission_evidence_id": attempt.admission["admission_evidence_id"],
        "generation": control.generation, "reservation_id": control.reservation_id,
        "workflow_run_id": control.worker.run_id, "workflow_run_attempt": control.worker.run_attempt,
        "classification": observation.classification, "reason_code": observation.reason_code,
        "reference_id": value["reference_id"], "observation_evidence_id": observation.evidence_id,
        "observed_at": value["observed_at"]}
    return validate_blocked_failure_receipt(receipt,
        failure_receipt_id=artifact_identity(canonical_bytes(receipt) + b"\n"),
        request_id=attempt.request_id, attempt_id=attempt.attempt_id,
        admission_evidence_id=attempt.admission["admission_evidence_id"], generation=control.generation,
        reservation_id=control.reservation_id, worker=control.worker,
        accepted_reference_ids=attempt.admission["reference_ids"])
