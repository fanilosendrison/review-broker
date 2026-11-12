"""Pure closed experimental remote PREPARED receipt; no I/O or authority minting."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping

from .artifact_locator import _timestamp
from .identity import artifact_identity, canonical_bytes
from .github_actions_workflow_dispatch_v3 import WORKER_WORKFLOW

MAX_JSON_INTEGER = 9007199254740991
_FIELDS = {"schema_version", "evidence_type", "offline_preparation_receipt_id", "storage"}
_STORAGE = {
    "backend", "repository", "repository_id", "workflow_run_id", "workflow_run_attempt",
    "workflow_id", "workflow_path", "execution_ref", "executable_sha",
    "verified_worker_job_id", "artifact_id", "artifact_name", "artifact_digest",
    "artifact_size_in_bytes", "created_at", "expires_at",
}


def positive_json_integer_v3(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_JSON_INTEGER:
        raise ValueError("REMOTE_RECEIPT_INTEGER_INVALID")
    return value


def positive_decimal_v3(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError("REMOTE_RECEIPT_DECIMAL_INVALID")
    return value


def api_decimal_v3(value: object) -> str:
    """No floating conversion, RFC8785 rounding or leading-zero normalization."""
    if type(value) is not int or value < 1:
        raise ValueError("REMOTE_API_ID_INVALID")
    return str(value)


def prepared_artifact_name_v3(claim_ref: str, run_id: int, run_attempt: int) -> str:
    if (type(claim_ref) is not str or re.fullmatch(
            r"refs/heads/review-claims-v3/[0-9a-f]{64}", claim_ref) is None
            or type(run_attempt) is not int or run_attempt != 1):
        raise ValueError("REMOTE_ARTIFACT_NAME_BINDING_INVALID")
    return f"rb-v3-prepared-{claim_ref.rsplit('/', 1)[-1]}-{positive_json_integer_v3(run_id)}-1"


def _pattern(value: object, pattern: str) -> None:
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ValueError("REMOTE_RECEIPT_TEXT_INVALID")


@dataclass(frozen=True)
class RemotePreparedReceiptV3:
    """Store canonical bytes, not an externally mutable dictionary."""

    canonical_receipt_bytes: bytes

    def __post_init__(self) -> None:
        raw = self.canonical_receipt_bytes
        if type(raw) is not bytes:
            raise ValueError("REMOTE_RECEIPT_BYTES_REQUIRED")
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("REMOTE_RECEIPT_JSON_INVALID") from exc
        if type(value) is not dict or set(value) != _FIELDS:
            raise ValueError("REMOTE_RECEIPT_FIELDS_INVALID")
        storage = value["storage"]
        if type(storage) is not dict or set(storage) != _STORAGE:
            raise ValueError("REMOTE_RECEIPT_STORAGE_FIELDS_INVALID")
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["evidence_type"] != "remote-v3-prepared-packet-binding"
                or storage["backend"] != "github-actions-artifact"
                or storage["workflow_path"] != WORKER_WORKFLOW
                or type(storage["workflow_run_attempt"]) is not int
                or storage["workflow_run_attempt"] != 1):
            raise ValueError("REMOTE_RECEIPT_CONSTANT_INVALID")
        _pattern(value["offline_preparation_receipt_id"], r"artifact:sha256:[0-9a-f]{64}")
        for key in ("repository_id", "workflow_run_id", "workflow_id", "artifact_size_in_bytes"):
            positive_json_integer_v3(storage[key])
        for key in ("artifact_id", "verified_worker_job_id"):
            positive_decimal_v3(storage[key])
        _pattern(storage["repository"], r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
        _pattern(storage["execution_ref"], r"refs/heads/[A-Za-z0-9_./-]+")
        if (".." in storage["repository"] or ".." in storage["execution_ref"]
                or "//" in storage["execution_ref"]
                or storage["execution_ref"].endswith(("/", ".", ".lock"))):
            raise ValueError("REMOTE_RECEIPT_REF_INVALID")
        _pattern(storage["executable_sha"], r"[0-9a-f]{40}")
        _pattern(storage["artifact_digest"], r"sha256:[0-9a-f]{64}")
        _pattern(storage["artifact_name"],
                 rf"rb-v3-prepared-[0-9a-f]{{64}}-{storage['workflow_run_id']}-1")
        created = _timestamp(storage["created_at"], "REMOTE_CREATED_AT_INVALID")
        expires = _timestamp(storage["expires_at"], "REMOTE_EXPIRES_AT_INVALID")
        if created >= expires:
            raise ValueError("REMOTE_RECEIPT_TIME_ORDER_INVALID")
        if raw != canonical_bytes(value) + b"\n":
            raise ValueError("REMOTE_RECEIPT_NONCANONICAL")

    @property
    def value(self) -> dict[str, object]:
        return json.loads(self.canonical_receipt_bytes)

    @property
    def evidence_id(self) -> str:
        return artifact_identity(self.canonical_receipt_bytes)

    @classmethod
    def build(cls, offline_receipt: Mapping[str, object], storage: Mapping[str, object]):
        """Callers must supply a reconstructed offline receipt, not an asserted ID."""
        from .packet_preparation_authority_v3 import offline_packet_receipt_identity_v3
        for key in ("repository_id", "workflow_run_id", "workflow_id", "artifact_size_in_bytes", "workflow_run_attempt"):
            positive_json_integer_v3(storage.get(key))
        return cls(canonical_bytes({
            "schema_version": 1, "evidence_type": "remote-v3-prepared-packet-binding",
            "offline_preparation_receipt_id": offline_packet_receipt_identity_v3(offline_receipt),
            "storage": dict(storage),
        }) + b"\n")

    def require_links(self, offline_receipt: Mapping[str, object], expected, job_id: str,
                      claim_ref: str) -> None:
        """Pure comparison only; independent authentication belongs to the caller."""
        from .packet_preparation_authority_v3 import offline_packet_receipt_identity_v3
        value = self.value
        storage = value["storage"]
        if (value["offline_preparation_receipt_id"] != offline_packet_receipt_identity_v3(offline_receipt)
                or offline_receipt["repository"] != expected.repository
                or storage["repository"] != expected.repository
                or storage["repository_id"] != expected.repository_id
                or storage["workflow_run_id"] != offline_receipt["worker"]["run_id"]
                or storage["workflow_id"] != expected.workflow_id
                or storage["workflow_path"] != expected.workflow_path
                or storage["execution_ref"] != expected.workflow_execution_ref
                or storage["executable_sha"] != expected.executing_source_sha
                or storage["verified_worker_job_id"] != positive_decimal_v3(job_id)
                or storage["artifact_name"] != prepared_artifact_name_v3(
                    claim_ref, storage["workflow_run_id"], 1)):
            raise ValueError("REMOTE_RECEIPT_BINDING_MISMATCH")
