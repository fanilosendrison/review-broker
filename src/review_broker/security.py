"""Fail-closed qualification record for the reviewer security boundary."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityQualification:
    status: str
    reviewer: str
    subject: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class IsolationProbe:
    packet_readable: bool
    credential_readable: bool
    github_token_visible: bool
    api_key_visible: bool
    unauthorized_network_succeeded: bool


def isolation_probe_passes(probe: IsolationProbe) -> bool:
    return (
        probe.packet_readable
        and not probe.credential_readable
        and not probe.github_token_visible
        and not probe.api_key_visible
        and not probe.unauthorized_network_succeeded
    )


def require_security_qualification(qualification: SecurityQualification) -> None:
    if qualification.reviewer == qualification.subject:
        raise PermissionError("SELF_QUALIFICATION_FORBIDDEN")
    if qualification.status != "PASS":
        raise PermissionError("SECURITY_BOUNDARY_NOT_QUALIFIED")
    if not qualification.evidence_ids:
        raise PermissionError("SECURITY_QUALIFICATION_EVIDENCE_REQUIRED")
