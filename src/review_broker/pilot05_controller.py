"""RB-PILOT-05 identity and shared operational-controller binding."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .pilot03_authorization import ExecutionAuthorization
from .pilot03_controller import (
    Pilot03Transport,
    run_synthetic_pilot_controller,
    synthetic_pilot_identities,
)
from .pilot05_synthetic import PILOT_ID, pilot_fixture_05


def pilot05_identities() -> tuple[str, str]:
    """Return the deterministic isolated RB-PILOT-05 request and attempt."""
    return synthetic_pilot_identities(pilot_fixture_05)


def run_pilot05_controller(
    *,
    authorization: ExecutionAuthorization,
    source_sha: str,
    wheel_path: Path,
    codespace_identity: str,
    transport: Pilot03Transport,
    _state_root: Path | None = None,
) -> dict[str, Any]:
    """Bind RB-PILOT-05 to the shared fail-closed controller."""
    return run_synthetic_pilot_controller(
        authorization=authorization,
        source_sha=source_sha,
        wheel_path=wheel_path,
        codespace_identity=codespace_identity,
        transport=transport,
        pilot_id=PILOT_ID,
        identities=pilot05_identities,
        _state_root=_state_root,
    )
