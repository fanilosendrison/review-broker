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
    def preflight(self, *, source_sha: str, wheel_sha256: str) -> None: ...
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
    """Arm durably before one emission, retain privately, and always shut down."""
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
    report: dict[str, Any] = {
        "pilot_id": PILOT_ID,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "pilot_functional": "UNDETERMINED",
        "pilot_execution": "NOT_EMITTED",
        "sanitized_receipt_retention": "NOT_ATTEMPTED",
        "raw_diagnostic_retention": "NOT_ATTEMPTED",
        "codespace_shutdown": "NOT_REQUESTED",
        "remote_command_emissions": 0,
        "automatic_retries": 0,
    }
    responsibility_started = False
    try:
        responsibility_started = True
        transport.prepare()
        transport.preflight(source_sha=source_sha, wheel_sha256=wheel_sha256)
        arm_controller_attempt(
            pilot_id=PILOT_ID,
            request_id=request_id,
            attempt_id=attempt_id,
            source_sha=source_sha,
            _state_root=_state_root,
        )
        report["controller_claim_armed"] = True
        report["remote_command_emissions"] = 1
        return_code = transport.emit_once(wheel_sha256=wheel_sha256)
        report["pilot_execution"] = "COMPLETED" if return_code == 0 else "FAILED"
        report["pilot_functional"] = "PASS" if return_code == 0 else "FAIL"
        try:
            retention = retain_private_pilot_artifacts(
                pilot_id=PILOT_ID,
                request_id=request_id,
                attempt_id=attempt_id,
                source_sha=source_sha,
                source=transport.artifact_source,
                _state_root=_state_root,
            )
        except Exception:
            report["retention_error"] = "PRIVATE_RETENTION_FAILED"
        else:
            report["sanitized_receipt_retention"] = retention["sanitized_receipt_retention"]
            report["raw_diagnostic_retention"] = retention["raw_diagnostic_retention"]
            summary = retention.get("artifact_entries", [])
            report["retained_artifact_count"] = sum(
                entry.get("retained_local") is True for entry in summary
            )
        return report
    except Exception as exc:
        report["controller_error"] = _sanitary_error(exc)
        return report
    finally:
        if responsibility_started:
            try:
                transport.shutdown()
                report["codespace_shutdown"] = (
                    "OBSERVED" if transport.shutdown_observed() else "UNDETERMINED"
                )
            except Exception:
                report["codespace_shutdown"] = "UNDETERMINED"


def _wheel_identity(path: Path) -> str:
    selected = Path(path)
    if not selected.is_file() or selected.is_symlink():
        raise Pilot03ControllerError("RB03_WHEEL_INVALID")
    digest = hashlib.sha256()
    with selected.open("rb") as stream:
        while block := stream.read(65_536):
            digest.update(block)
    value = digest.hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AssertionError("invalid SHA-256 implementation")
    return value


def _sanitary_error(exc: Exception) -> str:
    value = str(exc)
    return value if re.fullmatch(r"[A-Z0-9_:.-]{3,128}", value) else type(exc).__name__.upper()
