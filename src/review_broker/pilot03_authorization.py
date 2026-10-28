"""Typed, attempt-bound representation of future RB-PILOT-03 execution consent."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .fileobservation import read_regular_file_bounded

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"request:sha256:[0-9a-f]{64}\Z")
_ATTEMPT = re.compile(r"attempt:sha256:[0-9a-f]{64}\Z")
_CODESPACE = re.compile(r"[A-Za-z0-9-]+\Z")


class ExecutionAuthorizationError(ValueError):
    """Execution consent is absent, malformed, or bound to another attempt."""


@dataclass(frozen=True)
class ExecutionAuthorization:
    pilot_id: str
    request_id: str
    attempt_id: str
    review_broker_source_sha: str
    broker_wheel_sha256: str
    codespace_identity: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExecutionAuthorization":
        required = {
            "schema_version", "pilot_id", "request_id", "attempt_id",
            "review_broker_source_sha", "broker_wheel_sha256", "codespace_identity",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_INVALID")
        if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_INVALID")
        authorization = cls(**{key: value[key] for key in required - {"schema_version"}})
        if (
            authorization.pilot_id not in {"RB-PILOT-03", "RB-PILOT-04"}
            or not _REQUEST.fullmatch(authorization.request_id)
            or not _ATTEMPT.fullmatch(authorization.attempt_id)
            or not _SHA40.fullmatch(authorization.review_broker_source_sha)
            or not _SHA256.fullmatch(authorization.broker_wheel_sha256)
            or not _CODESPACE.fullmatch(authorization.codespace_identity)
        ):
            raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_INVALID")
        return authorization

    def require_matches(self, **expected: str) -> None:
        if any(getattr(self, key) != value for key, value in expected.items()):
            raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_MISMATCH")


def load_execution_authorization(path: Path | None) -> ExecutionAuthorization:
    """Load a local fixture/record; its governance provenance remains external."""
    if path is None:
        raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_DENIED")
    try:
        raw = read_regular_file_bounded(path, 16_384)
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ExecutionAuthorizationError("RB03_EXECUTION_AUTHORIZATION_INVALID") from exc
    return ExecutionAuthorization.from_mapping(value)
