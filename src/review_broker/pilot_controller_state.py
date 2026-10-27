"""Durable controller-side reservation of synthetic pilot request identities."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from .identity import canonical_bytes

_IDENTITY = re.compile(r"(?:request|attempt):sha256:[0-9a-f]{64}\Z")
_PILOT_ID = re.compile(r"RB-PILOT-[A-Z0-9-]+\Z")
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ControllerClaimError(ValueError):
    """A controller reservation is invalid, unavailable, or already consumed."""


def controller_pilot_root(home: Path | None = None) -> Path:
    """Return the persistent controller root; callers cannot select it via CLI."""
    selected = Path.home() if home is None else Path(home)
    if not selected.is_absolute():
        raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED")
    return selected / ".local" / "state" / "review-broker" / "pilots"


def request_reservation_digest(request_id: str) -> str:
    _require_identity(request_id, "request")
    return hashlib.sha256(canonical_bytes(request_id)).hexdigest()


def arm_controller_attempt(
    *,
    pilot_id: str,
    request_id: str,
    attempt_id: str,
    source_sha: str,
    _state_root: Path | None = None,
    _created_utc: str | None = None,
) -> dict[str, Any]:
    """Persist ARMED before model-capable emission; never remove or replace it."""
    _validate_values(pilot_id, request_id, attempt_id, source_sha)
    root = controller_pilot_root() if _state_root is None else Path(_state_root)
    if _state_root is None:
        _ensure_managed_chain(Path.home(), root)
    else:
        _ensure_private_root(root)
    reservation = root / request_reservation_digest(request_id)
    try:
        reservation.mkdir(mode=0o700)
        _fsync_directory(root)
    except FileExistsError:
        _validate_private_directory(reservation)
        _raise_existing_claim(reservation / "controller-claim.json", request_id)
    except OSError as exc:
        raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc
    claim_path = reservation / "controller-claim.json"
    value = {
        "schema_version": 1,
        "record_type": "synthetic-controller-claim",
        "pilot_id": pilot_id,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "source_sha": source_sha,
        "state": "ARMED",
        "created_utc": _created_utc or datetime.now(timezone.utc).isoformat(),
    }
    try:
        _write_exclusive(claim_path, canonical_bytes(value) + b"\n")
    except FileExistsError:
        _raise_existing_claim(claim_path, request_id)
    except OSError as exc:
        raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc
    return value


def read_controller_claim(
    request_id: str, *, _state_root: Path | None = None,
) -> dict[str, Any]:
    root = controller_pilot_root() if _state_root is None else Path(_state_root)
    if _state_root is None:
        _validate_managed_chain(Path.home(), root)
    else:
        _validate_private_directory(root)
    reservation = root / request_reservation_digest(request_id)
    _validate_private_directory(reservation)
    claim_path = reservation / "controller-claim.json"
    try:
        metadata = claim_path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ControllerClaimError("CONTROLLER_CLAIM_UNAVAILABLE")
        raw = claim_path.read_bytes()
        value = json.loads(raw)
    except ControllerClaimError:
        raise
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ControllerClaimError("CONTROLLER_CLAIM_UNAVAILABLE") from exc
    if raw != canonical_bytes(value) + b"\n" or not _valid_claim(value, request_id):
        raise ControllerClaimError("CONTROLLER_CLAIM_UNAVAILABLE")
    return value


def _raise_existing_claim(path: Path, request_id: str) -> None:
    try:
        value = read_controller_claim(request_id, _state_root=path.parent.parent)
    except ControllerClaimError as exc:
        raise ControllerClaimError("CONTROLLER_CLAIM_UNAVAILABLE") from exc
    if value["request_id"] == request_id:
        raise ControllerClaimError("CONTROLLER_ATTEMPT_ALREADY_ARMED")
    raise ControllerClaimError("CONTROLLER_CLAIM_UNAVAILABLE")


def _validate_values(pilot_id: str, request_id: str, attempt_id: str, source_sha: str) -> None:
    if (
        not isinstance(pilot_id, str) or not _PILOT_ID.fullmatch(pilot_id)
        or not isinstance(request_id, str) or not _IDENTITY.fullmatch(request_id)
        or not request_id.startswith("request:")
        or not isinstance(attempt_id, str) or not _IDENTITY.fullmatch(attempt_id)
        or not attempt_id.startswith("attempt:")
        or not isinstance(source_sha, str) or not _SOURCE_SHA.fullmatch(source_sha)
    ):
        raise ControllerClaimError("CONTROLLER_ATTEMPT_IDENTITY_INVALID")


def _require_identity(value: str, kind: str) -> None:
    if not isinstance(value, str) or not value.startswith(kind + ":") or not _IDENTITY.fullmatch(value):
        raise ControllerClaimError("CONTROLLER_ATTEMPT_IDENTITY_INVALID")


def _valid_claim(value: Any, request_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "record_type", "pilot_id", "request_id", "attempt_id",
        "source_sha", "state", "created_utc",
    }:
        return False
    try:
        _validate_values(value["pilot_id"], value["request_id"], value["attempt_id"], value["source_sha"])
        datetime.fromisoformat(value["created_utc"].replace("Z", "+00:00"))
    except (ControllerClaimError, AttributeError, TypeError, ValueError):
        return False
    return (
        value["schema_version"] == 1
        and value["record_type"] == "synthetic-controller-claim"
        and value["request_id"] == request_id
        and value["state"] == "ARMED"
    )


def _ensure_managed_chain(home: Path, root: Path) -> None:
    try:
        relative = root.relative_to(home)
    except ValueError as exc:
        raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
    current = home
    for part in relative.parts:
        parent = current
        current = current / part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
        try:
            _fsync_directory(parent)
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED")
    _validate_private_directory(root)


def _validate_managed_chain(home: Path, root: Path) -> None:
    try:
        relative = root.relative_to(home)
    except ValueError as exc:
        raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
    current = home
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED")
    _validate_private_directory(root)


def _ensure_private_root(root: Path) -> None:
    missing: list[Path] = []
    current = root
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            _validate_private_directory(directory)
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc
        try:
            _fsync_directory(directory.parent)
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc
    _validate_private_directory(root)
    if not missing:
        try:
            _fsync_directory(root.parent)
        except OSError as exc:
            raise ControllerClaimError("CONTROLLER_CLAIM_WRITE_FAILED") from exc


def _validate_private_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED") from exc
    if (
        not path.is_absolute() or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != os.getuid()
    ):
        raise ControllerClaimError("CONTROLLER_STATE_ROOT_UNTRUSTED")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)
