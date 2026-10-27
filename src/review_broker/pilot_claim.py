"""Validation and exclusive persistence of the RB-PILOT-02 durable claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from typing import Any, Callable

from .fileobservation import FileObservationError, read_regular_file_bounded
from .identity import attempt_identity, request_identity


class PilotClaimError(ValueError):
    """The fixed pilot claim is consumed, unavailable, or unwritable."""


def require_claim_available(path: Path, fixture: bytes) -> None:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise PilotClaimError("PILOT_02_CLAIM_UNAVAILABLE") from exc
    if not stat.S_ISREG(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o600:
        raise PilotClaimError("PILOT_02_CLAIM_UNAVAILABLE")
    try:
        claim_bytes = read_regular_file_bounded(path, 4_096)
        claim = json.loads(claim_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, FileObservationError) as exc:
        raise PilotClaimError("PILOT_02_CLAIM_UNAVAILABLE") from exc
    digest = hashlib.sha256(fixture).hexdigest()
    expected_request = request_identity({
        "kind": "RB-PILOT-02", "fixture_sha256": digest, "ordinal": 1,
    })
    required = {
        "pilot_id": "RB-PILOT-02", "request_id": expected_request,
        "attempt_id": attempt_identity(expected_request, 1), "status": "ARMED",
    }
    if (not isinstance(claim, dict)
            or any(claim.get(key) != value for key, value in required.items())
            or not isinstance(claim.get("packet_id"), str)
            or not claim["packet_id"]
            or not isinstance(claim.get("armed_utc"), str)
            or not claim["armed_utc"]):
        raise PilotClaimError("PILOT_02_CLAIM_UNAVAILABLE")
    raise PilotClaimError("PILOT_02_ALREADY_CONSUMED")


def write_claim(
    path: Path,
    value: dict[str, Any],
    fixture: bytes,
    write_once: Callable[[Path, dict[str, Any]], None],
) -> None:
    try:
        write_once(path, value)
    except FileExistsError:
        require_claim_available(path, fixture)
        raise AssertionError("claim availability check returned after an existing claim")
    except OSError as exc:
        raise PilotClaimError("PILOT_02_CLAIM_WRITE_FAILED") from exc
