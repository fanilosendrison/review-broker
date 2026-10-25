"""Canonical serialization and domain-separated identities."""
from __future__ import annotations

import hashlib
from typing import Any

import rfc8785


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785 JSON Canonicalization Scheme bytes."""
    return rfc8785.dumps(value)


def _identity(domain: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    return f"{domain}:sha256:{digest}"


def request_identity(request: dict[str, Any]) -> str:
    return _identity("request", request)


def mission_identity(mission: dict[str, Any]) -> str:
    return _identity("mission", mission)


def policy_identity(policy: dict[str, Any]) -> str:
    return _identity("policy", policy)


def subject_identity(resolved_subject: dict[str, Any]) -> str:
    return _identity("subject", resolved_subject)


def attempt_identity(request_id: str, ordinal: int) -> str:
    if ordinal < 1:
        raise ValueError("attempt ordinal must be positive")
    return _identity("attempt", {"request_id": request_id, "ordinal": ordinal})


def packet_identity(packet_basis: dict[str, Any]) -> str:
    return _identity("packet", packet_basis)


def artifact_identity(data: bytes) -> str:
    return f"artifact:sha256:{hashlib.sha256(data).hexdigest()}"
