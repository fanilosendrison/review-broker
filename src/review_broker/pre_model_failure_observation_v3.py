"""Closed experimental original failure observations and pure six-reason classification."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping

from jsonschema import Draft202012Validator

from .identity import artifact_identity, canonical_bytes
from .pre_model_failure_time_v3 import valid_failure_observed_at_v3
from .remote_prepared_receipt_v3 import MAX_JSON_INTEGER, prepared_artifact_name_v3

OPERATIONS = {
    "SOURCE_ACQUISITION": ("GIT_CLONE", "GIT_FETCH"),
    "REFERENCE_READ": ("GITHUB_ISSUE_GET", "GITHUB_ISSUE_COMMENT_GET"),
    "REMOTE_UPLOAD": ("ACTIONS_ARTIFACT_UPLOAD",),
    "REMOTE_READ": ("ACTIONS_ARTIFACT_METADATA_GET", "ACTIONS_ARTIFACT_DOWNLOAD"),
    "REMOTE_RECONSTRUCTION": ("VERIFY_ARCHIVE_BYTES", "VERIFY_ARCHIVE_INVENTORY",
                              "VERIFY_REMOTE_MANIFEST", "VERIFY_REMOTE_PACKET"),
}
BLOCKED_REASONS = {
    "SOURCE_API_UNAVAILABLE": "TRANSIENT", "SOURCE_ACCESS_AMBIGUOUS": "UNKNOWN",
    "SOURCE_TRANSFER_INTERRUPTED": "TRANSIENT", "ARTIFACT_UPLOAD_UNCONFIRMED": "UNKNOWN",
    "ARTIFACT_READ_UNAVAILABLE": "TRANSIENT", "REMOTE_RECONSTRUCTION_UNCONFIRMED": "UNKNOWN",
}
TRANSIENT_HTTP = frozenset({429, 502, 503, 504})
AMBIGUOUS_HTTP = frozenset({403, 404})
CHECK_OPERATIONS = dict(zip(("ARCHIVE_BYTES", "INVENTORY", "MANIFEST", "PACKET_ID"),
                            OPERATIONS["REMOTE_RECONSTRUCTION"]))


def _closed(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _identity(domain):
    return {"type": "string", "pattern": rf"^{domain}:sha256:[0-9a-f]{{64}}$"}


def _nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


_FACT = {"oneOf": [
    _closed({"kind": {"const": "HTTP_STATUS"}, "status": {"type": "integer", "enum": sorted(TRANSIENT_HTTP | AMBIGUOUS_HTTP)}}),
    _closed({"kind": {"const": "TRANSFER_TIMEOUT"}, "process_terminated": {"const": True, "type": "boolean"}}),
    _closed({"kind": {"const": "UPLOAD_OUTCOME_UNKNOWN"}, "emitted": {"const": True, "type": "boolean"},
             "reconciliation": {"const": "UNCONFIRMED"}}),
    _closed({"kind": {"const": "READ_TIMEOUT"}}),
    _closed({"kind": {"const": "VERIFICATION_FAILED"}, "check": {"enum": list(CHECK_OPERATIONS)},
             "expected_id": _identity("(?:artifact|packet)"), "observed_id": _identity("(?:artifact|packet)"),
             "expected_size": _nullable({"type": "integer", "minimum": 0, "maximum": MAX_JSON_INTEGER}),
             "observed_size": _nullable({"type": "integer", "minimum": 0, "maximum": MAX_JSON_INTEGER})}),
]}
OBSERVATION_SCHEMA = _closed({
    "schema_version": {"const": 1, "type": "integer"},
    "evidence_type": {"const": "pre-model-preparation-failure-observation"},
    "repository": {"type": "string", "pattern": r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"},
    "repository_node_id": {"type": "string", "pattern": r"^[A-Za-z0-9_+/=-]+$"},
    "claim_ref": {"type": "string", "pattern": r"^refs/heads/review-claims-v3/[0-9a-f]{64}$"},
    "admitted_commit_sha": {"type": "string", "pattern": r"^[0-9a-f]{40}$"},
    "request_id": _identity("request"), "attempt_id": _identity("attempt"),
    "admission_evidence_id": _identity("artifact"),
    "generation": {"const": 1, "type": "integer"}, "reservation_id": _identity("preparation-dispatch"),
    "workflow_run_id": {"type": "integer", "minimum": 1, "maximum": MAX_JSON_INTEGER},
    "workflow_run_attempt": {"const": 1, "type": "integer"},
    "phase": {"enum": list(OPERATIONS)}, "operation": {"enum": [op for ops in OPERATIONS.values() for op in ops]},
    "reference_id": _nullable({"type": "string", "pattern": r"^[a-z][a-z0-9-]{0,63}$"}),
    "packet_id": _nullable(_identity("packet")),
    "artifact_name": _nullable({"type": "string", "pattern": r"^rb-v3-prepared-[0-9a-f]{64}-[1-9][0-9]*-1$"}),
    "artifact_id": _nullable({"type": "string", "pattern": r"^[1-9][0-9]*$"}),
    "fact": _FACT, "observed_at": {"type": "string"},
})
_VALIDATOR = Draft202012Validator(OBSERVATION_SCHEMA)


def valid_failure_observation_identity_v3(value):
    pattern = OBSERVATION_SCHEMA["properties"]["admission_evidence_id"]["pattern"]
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _strict_scalars(value):
    """JSON Schema's integral-float acceptance cannot erase original numeric types."""
    if isinstance(value, float):
        raise ValueError("FAILURE_OBSERVATION_FLOAT_FORBIDDEN")
    if isinstance(value, str) and any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("FAILURE_OBSERVATION_TEXT_INVALID")
    if isinstance(value, dict):
        for child in value.values(): _strict_scalars(child)
    elif isinstance(value, list):
        for child in value: _strict_scalars(child)


def classify_failure_fact_v3(phase: str, operation: str, fact: Mapping[str, object]) -> tuple[str, str]:
    """No exception text, caller reason or generic UNKNOWN participates."""
    if operation not in OPERATIONS.get(phase, ()):
        raise ValueError("FAILURE_OBSERVATION_OPERATION_INVALID")
    # Validate the union even when this pure function is called without an observation.
    _strict_scalars(fact)
    if not Draft202012Validator(_FACT).is_valid(fact):
        raise ValueError("FAILURE_OBSERVATION_FACT_INVALID")
    kind, reason = fact["kind"], None
    if phase == "REFERENCE_READ" and kind == "HTTP_STATUS":
        reason = "SOURCE_ACCESS_AMBIGUOUS" if fact["status"] in AMBIGUOUS_HTTP else "SOURCE_API_UNAVAILABLE"
    elif phase == "SOURCE_ACQUISITION" and kind == "TRANSFER_TIMEOUT":
        reason = "SOURCE_TRANSFER_INTERRUPTED"
    elif phase == "REMOTE_UPLOAD" and kind == "UPLOAD_OUTCOME_UNKNOWN":
        reason = "ARTIFACT_UPLOAD_UNCONFIRMED"
    elif phase == "REMOTE_READ" and (kind == "READ_TIMEOUT" or kind == "HTTP_STATUS" and fact["status"] in TRANSIENT_HTTP):
        reason = "ARTIFACT_READ_UNAVAILABLE"
    elif phase == "REMOTE_RECONSTRUCTION" and kind == "VERIFICATION_FAILED":
        check = fact["check"]
        domain = "packet" if check == "PACKET_ID" else "artifact"
        if (operation != CHECK_OPERATIONS[check]
                or any(re.fullmatch(rf"{domain}:sha256:[0-9a-f]{{64}}", fact[key]) is None
                       for key in ("expected_id", "observed_id"))):
            raise ValueError("FAILURE_OBSERVATION_CHECK_INVALID")
        sizes = (fact["expected_size"], fact["observed_size"])
        if check == "ARCHIVE_BYTES":
            if any(type(size) is not int or not 0 <= size <= MAX_JSON_INTEGER for size in sizes):
                raise ValueError("FAILURE_OBSERVATION_SIZE_INVALID")
        elif sizes != (None, None):
            raise ValueError("FAILURE_OBSERVATION_SIZE_FORBIDDEN")
        if fact["expected_id"] == fact["observed_id"] and sizes[0] == sizes[1]:
            raise ValueError("FAILURE_OBSERVATION_DIVERGENCE_REQUIRED")
        reason = "REMOTE_RECONSTRUCTION_UNCONFIRMED"
    if reason is None:
        raise ValueError("FAILURE_OBSERVATION_OUTSIDE_CATALOG")
    return BLOCKED_REASONS[reason], reason


def _validate(value):
    _strict_scalars(value)
    if not _VALIDATOR.is_valid(value):
        raise ValueError("FAILURE_OBSERVATION_SCHEMA_INVALID")
    for key in ("schema_version", "generation", "workflow_run_id", "workflow_run_attempt"):
        if type(value[key]) is not int:
            raise ValueError("FAILURE_OBSERVATION_INTEGER_REQUIRED")
    if not valid_failure_observed_at_v3(value["observed_at"]):
        raise ValueError("FAILURE_OBSERVATION_TIMESTAMP_INVALID")
    remote, reference = value["phase"].startswith("REMOTE_"), value["phase"] == "REFERENCE_READ"
    if ((value["reference_id"] is not None) != reference
            or (value["packet_id"] is not None) != remote
            or (value["artifact_name"] is not None) != remote
            or not remote and value["artifact_id"] is not None
            or value["phase"] == "REMOTE_RECONSTRUCTION" and value["artifact_id"] is None):
        raise ValueError("FAILURE_OBSERVATION_NULL_BINDINGS_INVALID")
    if ".." in value["repository"]:
        raise ValueError("FAILURE_OBSERVATION_REPOSITORY_INVALID")
    classify_failure_fact_v3(value["phase"], value["operation"], value["fact"])


@dataclass(frozen=True)
class FailureObservationV3:
    """Canonical evidence value only; construction and identity grant no authority."""
    canonical_bytes: bytes

    def __post_init__(self):
        if type(self.canonical_bytes) is not bytes:
            raise ValueError("FAILURE_OBSERVATION_BYTES_REQUIRED")
        value = json.loads(self.canonical_bytes)
        _validate(value)
        if self.canonical_bytes != canonical_bytes(value) + b"\n":
            raise ValueError("FAILURE_OBSERVATION_NONCANONICAL")

    @classmethod
    def from_value(cls, value: Mapping[str, object]):
        _validate(value)  # Before canonicalization could turn 1.0 into integer 1.
        return cls(canonical_bytes(value) + b"\n")

    @property
    def value(self):
        return json.loads(self.canonical_bytes)

    @property
    def evidence_id(self):
        return artifact_identity(self.canonical_bytes)

    @property
    def classification(self):
        v = self.value
        return classify_failure_fact_v3(v["phase"], v["operation"], v["fact"])[0]

    @property
    def reason_code(self):
        v = self.value
        return classify_failure_fact_v3(v["phase"], v["operation"], v["fact"])[1]

    def require_links(self, snapshot, *, original_packet_id=None, budget=None):
        from .pre_model_failure_domain_v3 import require_failure_predecessor_v3
        require_failure_predecessor_v3(snapshot.record)
        v, a, c = self.value, snapshot.record.attempt, snapshot.record.control
        expected = {"repository": snapshot.repository, "repository_node_id": snapshot.repository_node_id,
            "claim_ref": snapshot.claim_ref, "admitted_commit_sha": snapshot.commit_sha,
            "request_id": a.request_id, "attempt_id": a.attempt_id,
            "admission_evidence_id": a.admission["admission_evidence_id"], "generation": c.generation,
            "reservation_id": c.reservation_id,
            "workflow_run_id": None if c.worker is None else c.worker.run_id,
            "workflow_run_attempt": None if c.worker is None else c.worker.run_attempt}
        if any(v[key] != expected[key] for key in expected):
            raise ValueError("FAILURE_OBSERVATION_JOURNAL_BINDING_INVALID")
        if v["phase"] == "REFERENCE_READ" and v["reference_id"] not in a.admission["reference_ids"]:
            raise ValueError("FAILURE_OBSERVATION_REFERENCE_UNADMITTED")
        if v["phase"].startswith("REMOTE_") and (
                v["packet_id"] != original_packet_id or v["artifact_name"] != prepared_artifact_name_v3(
                    snapshot.claim_ref, c.worker.run_id, 1)):
            raise ValueError("FAILURE_OBSERVATION_REMOTE_BINDING_INVALID")
        if v["fact"].get("check") == "PACKET_ID" and v["fact"]["expected_id"] != original_packet_id:
            raise ValueError("FAILURE_OBSERVATION_ORIGINAL_PACKET_EXPECTATION_INVALID")
        if v["fact"].get("check") == "ARCHIVE_BYTES":
            from .prepared_artifact_transport_v3 import PreparedArtifactBudgetV3
            if type(budget) is not PreparedArtifactBudgetV3 or any(
                    v["fact"][key] > budget.max_archive_bytes for key in ("expected_size", "observed_size")):
                raise ValueError("FAILURE_OBSERVATION_ARCHIVE_BUDGET_INVALID")
