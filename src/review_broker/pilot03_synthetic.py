"""Fixed remote entry point for the preparation-only RB-PILOT-03 identity."""
from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any, Mapping

from .fileobservation import FileObservationError, read_regular_file_bounded
from .pilot_synthetic import (
    CODEX_RUNTIME_ROOT,
    TRUSTED_WORKSPACE,
    PilotError,
    _pilot_fixture,
    _run_synthetic_pilot,
    _write_once,
)

PILOT_ID = "RB-PILOT-03"
RUN_DIRECTORY = Path("/tmp/review-broker-pilot-26-rb03")
CLAIM_PATH = Path("/tmp/review-broker-pilot-26-rb03.claim.json")


def pilot_fixture_03(run_directory: Path) -> dict[str, Any]:
    """Build the third deterministic packet without changing fixture bytes."""
    return _pilot_fixture(run_directory, pilot_id=PILOT_ID)


def require_claim_available(path: Path = CLAIM_PATH) -> None:
    """Fail closed for every pre-existing claim, including malformed claims."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise PilotError("PILOT_03_CLAIM_UNAVAILABLE") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PilotError("PILOT_03_CLAIM_UNAVAILABLE")
    try:
        value = json.loads(read_regular_file_bounded(path, 4_096))
    except (OSError, ValueError, FileObservationError) as exc:
        raise PilotError("PILOT_03_CLAIM_UNAVAILABLE") from exc
    if not isinstance(value, dict):
        raise PilotError("PILOT_03_CLAIM_UNAVAILABLE")
    raise PilotError("PILOT_03_ALREADY_CONSUMED")


def write_claim(value: dict[str, Any], path: Path = CLAIM_PATH) -> None:
    """Create the remote claim exclusively and durably before model transport."""
    try:
        _write_once(path, value)
    except FileExistsError:
        require_claim_available(path)
        raise AssertionError("existing claim unexpectedly accepted")
    except OSError as exc:
        raise PilotError("PILOT_03_CLAIM_WRITE_FAILED") from exc


def run_synthetic_pilot_03(
    *,
    broker_wheel_sha256: str,
    trusted_workspace: Path = TRUSTED_WORKSPACE,
    codex_runtime_root: Path = CODEX_RUNTIME_ROOT,
    environment: Mapping[str, str] | None = None,
    _run_directory: Path = RUN_DIRECTORY,
    _claim_path: Path = CLAIM_PATH,
) -> dict[str, Any]:
    """Run the fixed pilot once; controller authorization is checked externally."""
    return _run_synthetic_pilot(
        _run_directory,
        fixture_builder=pilot_fixture_03,
        pilot_id=PILOT_ID,
        acknowledge_unqualified_pilot=True,
        broker_wheel_sha256=broker_wheel_sha256,
        trusted_workspace=trusted_workspace,
        codex_runtime_root=codex_runtime_root,
        environment=environment,
        claim_available=lambda: require_claim_available(_claim_path),
        claim_writer=lambda value: write_claim(value, _claim_path),
    )
