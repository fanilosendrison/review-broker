"""Pinned transport capacity, exact Unicode units, and immutable input observation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

# Any describes heterogeneous JSON receipts; exact keys, types and bindings are checked below.

from .codex_policy import CodexPolicy
from .fileobservation import FileObservationError, read_regular_file_bounded
from .identity import artifact_identity, canonical_bytes
from .packets import MAX_PACKET_BYTES, PacketError, verify_packet

MAX_CHARS = 1_048_576
LIMIT_POLICY = "codex-0.164.0-turn-input-v1"
COUNTING_RULE = "utf8-bytes-conservative-upper-bound-v1"
# This qualification boundary intentionally does not follow future runtime upgrades.
QUALIFIED_DISTRIBUTION = "@openai/codex"
QUALIFIED_VERSION = "0.164.0"


class CapacityError(ValueError):
    """Input capacity or its immutable binding cannot be established."""


def measure_input(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8", errors="strict")
        scalar_count = len(text)
        utf16_count = len(text.encode("utf-16-le", errors="strict")) // 2
    except (UnicodeError, AttributeError) as exc:
        raise CapacityError("CAPACITY_INPUT_ENCODING_INVALID") from exc
    return {
        "unicode_scalar_characters": scalar_count,
        "utf16_code_units": utf16_count,
        "utf8_bytes": len(data),
        "capacity_units": max(scalar_count, utf16_count, len(data)),
        "input_sha256": hashlib.sha256(data).hexdigest(),
    }


def read_verified_input(directory: Path, expected_packet_id: str) -> tuple[dict[str, Any], bytes]:
    """Bind the complete immutable packet to a coherent, non-aliased input snapshot."""
    if directory.is_symlink():
        raise CapacityError("CAPACITY_PACKET_ROOT_INVALID")
    try:
        manifest = verify_packet(directory)
        if manifest["packet_id"] != expected_packet_id:
            raise CapacityError("CAPACITY_PACKET_ID_MISMATCH")
        path = directory / "input.txt"
        if path.lstat().st_nlink != 1:
            raise CapacityError("CAPACITY_INPUT_ALIAS_INVALID")
        data = read_regular_file_bounded(path, MAX_PACKET_BYTES)
        if (len(data) != manifest["prompt_byte_length"]
            or hashlib.sha256(data).hexdigest() != manifest["prompt_sha256"]):
            raise CapacityError("CAPACITY_INPUT_SUBSTITUTION")
        measure_input(data)
    except (PacketError, FileObservationError, OSError, KeyError, TypeError) as exc:
        raise CapacityError("CAPACITY_PACKET_OR_INPUT_INVALID") from exc
    return manifest, data


def capacity_receipt(
    data: bytes, *, request_id: str, packet_id: str, attempt_id: str,
    executing_broker_sha: str,
) -> dict[str, Any]:
    policy = CodexPolicy()
    if (policy.distribution, policy.distribution_version) != (QUALIFIED_DISTRIBUTION, QUALIFIED_VERSION):
        raise CapacityError("CAPACITY_RUNTIME_NOT_QUALIFIED")
    counts = measure_input(data)
    value = {
        "schema_version": 1,
        "evidence_type": "rendered-input-capacity-v1",
        "request_id": request_id,
        "packet_id": packet_id,
        "attempt_id": attempt_id,
        "executing_broker_sha": executing_broker_sha,
        "runtime_distribution": QUALIFIED_DISTRIBUTION,
        "runtime_version": QUALIFIED_VERSION,
        "limit_policy": LIMIT_POLICY,
        "max_chars": MAX_CHARS,
        "counting_rule": COUNTING_RULE,
        **counts,
        "status": "PASS" if counts["capacity_units"] <= MAX_CHARS else "REJECTED",
    }
    validate_capacity_receipt(value)
    return value


def assess_packet_capacity(
    directory: Path, *, request_id: str, packet_id: str,
    attempt_id: str, executing_broker_sha: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, data = read_verified_input(directory, packet_id)
    try:
        raw = read_regular_file_bounded(directory / "broker-metadata.json", 100_000)
        metadata = json.loads(raw)
        if raw != canonical_bytes(metadata) + b"\n":
            raise ValueError
        if (manifest["request_id"] != request_id
            or metadata.get("request_id") != request_id
            or metadata.get("attempt_id") != attempt_id
            or metadata.get("executing_broker_sha") != executing_broker_sha):
            raise ValueError
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise CapacityError("CAPACITY_EXECUTION_BINDING_INVALID") from exc
    return manifest, capacity_receipt(data, request_id=request_id, packet_id=packet_id,
        attempt_id=attempt_id, executing_broker_sha=executing_broker_sha)


def validate_capacity_receipt(value: dict[str, Any]) -> str:
    """Validate exact policy and count semantics; return the canonical evidence identity."""
    fixed = {"schema_version": 1, "evidence_type": "rendered-input-capacity-v1",
             "runtime_distribution": QUALIFIED_DISTRIBUTION, "runtime_version": QUALIFIED_VERSION,
             "limit_policy": LIMIT_POLICY, "max_chars": MAX_CHARS, "counting_rule": COUNTING_RULE}
    counts = {"unicode_scalar_characters", "utf16_code_units", "utf8_bytes", "capacity_units"}
    identities = {"request_id", "packet_id", "attempt_id", "executing_broker_sha", "input_sha256"}
    if (not isinstance(value, dict) or set(value) != set(fixed) | counts | identities | {"status"}
        or any(type(value.get(k)) is not type(v) or value[k] != v for k, v in fixed.items())
        or any(type(value.get(k)) is not int or value[k] < 0 for k in counts)):
        raise CapacityError("CAPACITY_RECEIPT_POLICY_INVALID")
    for key, prefix, length in [("request_id", "request:sha256:", 64),
                               ("packet_id", "packet:sha256:", 64),
                               ("attempt_id", "attempt:sha256:", 64),
                               ("executing_broker_sha", "", 40), ("input_sha256", "", 64)]:
        if not isinstance(value.get(key), str) or not re.fullmatch(prefix + "[0-9a-f]{" + str(length) + "}", value[key]):
            raise CapacityError("CAPACITY_RECEIPT_IDENTITY_INVALID")
    scalar, utf16, octets = (value[k] for k in ["unicode_scalar_characters", "utf16_code_units", "utf8_bytes"])
    if (not scalar <= utf16 <= 2 * scalar or not utf16 <= octets <= 4 * scalar
        or value["capacity_units"] != max(scalar, utf16, octets)
        or value["status"] != ("PASS" if value["capacity_units"] <= MAX_CHARS else "REJECTED")):
        raise CapacityError("CAPACITY_RECEIPT_COUNTS_INVALID")
    return artifact_identity(canonical_bytes(value) + b"\n")
