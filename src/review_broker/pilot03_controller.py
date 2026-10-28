"""Independent, fail-closed operational controller for RB-PILOT-03."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Protocol

from .identity import attempt_identity
from .pilot03_authorization import ExecutionAuthorization
from .pilot03_synthetic import PILOT_ID, pilot_fixture_03
from .pilot_controller_state import arm_controller_attempt
from .pilot_private_retention import PilotArtifactSource, retain_private_pilot_artifacts


class Pilot03ControllerError(RuntimeError):
    """A controller gate failed without authorizing a replay."""


class Pilot03Transport(Protocol):
    artifact_source: PilotArtifactSource

    def prepare(self) -> None: ...
    def preflight(self, *, source_sha: str, wheel_path: Path, wheel_sha256: str) -> None: ...
    def emit_once(self, *, wheel_sha256: str) -> int: ...
    def shutdown(self) -> None: ...
    def shutdown_observed(self) -> bool: ...


def pilot03_identities() -> tuple[str, str]:
    """Derive request and attempt identities exclusively through packet machinery."""
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        manifest = pilot_fixture_03(Path(temporary) / "fixture")
    request_id = manifest["request_id"]
    return request_id, attempt_identity(request_id, 1)


def run_pilot03_controller(
    *,
    authorization: ExecutionAuthorization,
    source_sha: str,
    wheel_path: Path,
    codespace_identity: str,
    transport: Pilot03Transport,
    _state_root: Path | None = None,
) -> dict[str, Any]:
    """Preflight, arm, emit once, retain once, and always attempt Shutdown."""
    request_id, attempt_id = pilot03_identities()
    wheel_sha256 = _wheel_identity(wheel_path)
    authorization.require_matches(
        pilot_id=PILOT_ID,
        request_id=request_id,
        attempt_id=attempt_id,
        review_broker_source_sha=source_sha,
        broker_wheel_sha256=wheel_sha256,
        codespace_identity=codespace_identity,
    )
    report = _initial_report(request_id, attempt_id)
    responsibility_started = False
    claim_armed = False
    try:
        responsibility_started = True
        transport.prepare()
        transport.preflight(
            source_sha=source_sha,
            wheel_path=Path(wheel_path),
            wheel_sha256=wheel_sha256,
        )
        arm_controller_attempt(
            pilot_id=PILOT_ID,
            request_id=request_id,
            attempt_id=attempt_id,
            source_sha=source_sha,
            _state_root=_state_root,
        )
        claim_armed = True
        report["controller_claim_armed"] = True
        report["remote_command_emissions"] = 1
        try:
            return_code = transport.emit_once(wheel_sha256=wheel_sha256)
        except Exception as exc:
            report["pilot_execution"] = "INDETERMINATE"
            report["remote_command_return"] = "UNDETERMINED"
            report["controller_error"] = _sanitary_error(exc)
        else:
            report["remote_command_return"] = "ZERO" if return_code == 0 else "NONZERO"
            report["pilot_execution"] = "COMPLETED" if return_code == 0 else "FAILED"
        _attempt_retention(
            report,
            pilot_id=PILOT_ID,
            request_id=request_id,
            attempt_id=attempt_id,
            source_sha=source_sha,
            source=transport.artifact_source,
            state_root=_state_root,
        )
        _record_operational_coherence(report)
    except Exception as exc:
        report["controller_error"] = _sanitary_error(exc)
    finally:
        if responsibility_started:
            try:
                transport.shutdown()
                report["codespace_shutdown"] = (
                    "OBSERVED" if transport.shutdown_observed() else "UNDETERMINED"
                )
            except Exception:
                report["codespace_shutdown"] = "UNDETERMINED"
        if claim_armed and report["remote_command_emissions"] != 1:
            report["controller_error"] = "REMOTE_EMISSION_ACCOUNTING_INVALID"
        _resolve_acceptance(report)
    return report


def _initial_report(request_id: str, attempt_id: str) -> dict[str, Any]:
    return {
        "pilot_id": PILOT_ID,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "pilot_functional": "UNDETERMINED",
        "validated_pilot_functional": "UNDETERMINED",
        "validated_pilot_execution": "UNDETERMINED",
        "pilot_execution": "NOT_EMITTED",
        "remote_command_return": "NOT_EMITTED",
        "receipt_set_validation": "NOT_ATTEMPTED",
        "sanitized_receipt_retention": "NOT_ATTEMPTED",
        "raw_diagnostic_retention": "NOT_ATTEMPTED",
        "codespace_shutdown": "NOT_REQUESTED",
        "pilot_acceptance": "UNDETERMINED",
        "controller_claim_armed": False,
        "remote_command_emissions": 0,
        "automatic_retries": 0,
    }


def _attempt_retention(
    report: dict[str, Any], *, pilot_id: str, request_id: str, attempt_id: str,
    source_sha: str, source: PilotArtifactSource, state_root: Path | None,
) -> None:
    try:
        retention = retain_private_pilot_artifacts(
            pilot_id=pilot_id,
            request_id=request_id,
            attempt_id=attempt_id,
            source_sha=source_sha,
            source=source,
            _state_root=state_root,
        )
    except Exception:
        report["retention_error"] = "PRIVATE_RETENTION_FAILED"
        return
    for key in (
        "receipt_set_validation", "sanitized_receipt_retention",
        "raw_diagnostic_retention", "validated_pilot_functional",
        "validated_pilot_execution",
    ):
        report[key] = retention[key]
    report["pilot_functional"] = retention["validated_pilot_functional"]
    report["retained_artifact_count"] = sum(
        entry.get("retained_local") is True
        for entry in retention.get("artifact_entries", [])
    )


def _record_operational_coherence(report: dict[str, Any]) -> None:
    contradictory = (
        report["remote_command_return"] == "ZERO"
        and report["validated_pilot_functional"] == "FAIL"
        or report["remote_command_return"] == "NONZERO"
        and report["validated_pilot_functional"] == "PASS"
    )
    report["operational_coherence"] = "FAIL" if contradictory else "PASS"


def _resolve_acceptance(report: dict[str, Any]) -> None:
    accepted = (
        report["pilot_functional"] == "PASS"
        and report["validated_pilot_execution"] == "COMPLETED"
        and report["pilot_execution"] == "COMPLETED"
        and report["receipt_set_validation"] == "RECEIPT_SET_VALID"
        and report["sanitized_receipt_retention"] == "PASS"
        and report["raw_diagnostic_retention"] == "PASS"
        and report["codespace_shutdown"] == "OBSERVED"
        and report.get("operational_coherence", "PASS") == "PASS"
        and "controller_error" not in report
        and "retention_error" not in report
    )
    report["pilot_acceptance"] = "PASS" if accepted else (
        "FAIL" if _definite_failure(report) else "UNDETERMINED"
    )


def _definite_failure(report: dict[str, Any]) -> bool:
    return (
        report["pilot_functional"] == "FAIL"
        or report["sanitized_receipt_retention"] in {"FAIL", "PARTIAL"}
        or report["raw_diagnostic_retention"] in {"PARTIAL", "SKIPPED_QUARANTINED"}
        or report.get("operational_coherence") == "FAIL"
        or "controller_error" in report
        or "retention_error" in report
    )


def _wheel_identity(path: Path) -> str:
    selected = Path(path)
    if not selected.is_file() or selected.is_symlink():
        raise Pilot03ControllerError("RB03_WHEEL_INVALID")
    digest = hashlib.sha256()
    with selected.open("rb") as stream:
        while block := stream.read(65_536):
            digest.update(block)
    return digest.hexdigest()


def _sanitary_error(exc: Exception) -> str:
    value = str(exc)
    return value if re.fullmatch(r"[A-Z0-9_:.-]{3,128}", value) else type(exc).__name__.upper()
