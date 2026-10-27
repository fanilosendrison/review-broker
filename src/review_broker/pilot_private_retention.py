"""Private controller retention of bounded synthetic-pilot artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable, Mapping, Protocol
import uuid

from .evidence import EvidenceCaptureError, scan_for_credentials
from .fileobservation import FileObservationError, observed_regular_file
from .identity import canonical_bytes
from .pilot_controller_state import (
    controller_pilot_root,
    read_controller_claim,
    request_reservation_digest,
)
from .pilot_receipt_validation import validate_pilot_receipt_set

RECEIPTS = ("pilot-claim.json", "pilot-armed.json", "pilot-summary.json", "pilot-failure.json")
DIAGNOSTIC_LIMITS = {
    "codex-events.jsonl": 64 * 1024 * 1024,
    "codex-stderr.txt": 16 * 1024 * 1024,
    "codex-final.json": 1024 * 1024,
    "codex-exit-code.txt": 64,
}
_ALLOWED_NAMES = frozenset((*RECEIPTS, *DIAGNOSTIC_LIMITS))
_STATUSES = frozenset({
    "PASS", "ABSENT", "REFUSED_CONTAMINATED", "REFUSED_SCREEN_UNDETERMINED",
    "REFUSED_OVERSIZED", "HASH_MISMATCH", "TRANSFER_FAILED",
    "LOCAL_VALIDATION_FAILED", "UNDETERMINED",
})


class PilotRetentionError(RuntimeError):
    """Private retention could not establish a truthful durable result."""


@dataclass(frozen=True)
class RemoteArtifact:
    present: bool
    regular: bool = False
    symlink: bool = False
    link_count: int = 0
    byte_length: int = 0
    sha256: str | None = None
    credential_screen: str = "UNDETERMINED"


class PilotArtifactSource(Protocol):
    def observe(self, relative_name: str) -> RemoteArtifact: ...
    def copy_literal(self, relative_name: str, destination: Path) -> None: ...


class CodespaceLiteralCopier:
    """Copy only fixed pilot artifacts through gh cp without remote expansion."""

    def __init__(
        self, codespace: str, paths: Mapping[str, str], *,
        runner: Callable[..., Any],
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9-]+", codespace) or set(paths) - _ALLOWED_NAMES:
            raise ValueError("PRIVATE_RETENTION_SOURCE_INVALID")
        if any(not re.fullmatch(r"/[A-Za-z0-9_./-]+", value) for value in paths.values()):
            raise ValueError("PRIVATE_RETENTION_SOURCE_INVALID")
        self.codespace = codespace
        self.paths = dict(paths)
        self.runner = runner

    def copy_literal(self, relative_name: str, destination: Path) -> None:
        if relative_name not in self.paths:
            raise PilotRetentionError("PRIVATE_RETENTION_PATH_NOT_ALLOWED")
        result = self.runner(
            ["gh", "codespace", "cp", "-c", self.codespace,
             f"remote:{self.paths[relative_name]}", str(destination)],
            capture_output=True, check=False, timeout=120, shell=False,
        )
        if result.returncode != 0:
            raise PilotRetentionError("PRIVATE_RETENTION_TRANSFER_FAILED")


def retain_private_pilot_artifacts(
    *,
    pilot_id: str,
    request_id: str,
    attempt_id: str,
    source_sha: str,
    source: PilotArtifactSource,
    _state_root: Path | None = None,
    _retained_at: str | None = None,
) -> dict[str, Any]:
    """Retain verified receipts and eligible diagnostics under the armed request."""
    state_root = controller_pilot_root() if _state_root is None else Path(_state_root)
    claim = read_controller_claim(request_id, _state_root=state_root)
    if any(claim[key] != value for key, value in {
        "pilot_id": pilot_id, "request_id": request_id,
        "attempt_id": attempt_id, "source_sha": source_sha,
    }.items()):
        raise PilotRetentionError("PRIVATE_RETENTION_IDENTITY_MISMATCH")
    attempt_directory = state_root / request_reservation_digest(request_id)
    _private_directory(attempt_directory)
    receipts = attempt_directory / "receipts"
    diagnostics = attempt_directory / "diagnostics"
    _make_private_directory(receipts)
    _make_private_directory(diagnostics)
    staging = attempt_directory / (".retention-" + uuid.uuid4().hex)
    staging.mkdir(mode=0o700)
    entries: list[dict[str, Any]] = []
    try:
        for name in RECEIPTS:
            entries.append(_retain_one(source, name, receipts, staging, None, True))
        receipt_validation = validate_pilot_receipt_set(receipts, claim)
        summary = receipt_validation.summary or {}
        receipt_status = _receipt_aggregate(
            entries, receipt_validation.valid, summary.get("pilot_functional"),
        )
        diagnostic_gate = (
            receipt_status == "PASS"
            and summary.get("credential_screen") == "PASS_NO_MATCH"
        )
        for name, limit in DIAGNOSTIC_LIMITS.items():
            entries.append(_retain_one(
                source, name, diagnostics, staging, limit, diagnostic_gate,
            ))
    finally:
        _remove_empty_staging(staging)
    diagnostic_status = (
        _aggregate(entries, set(DIAGNOSTIC_LIMITS), "UNDETERMINED")
        if diagnostic_gate else "SKIPPED_QUARANTINED"
    )
    manifest = {
        "schema_version": 1,
        "record_type": "synthetic-pilot-private-retention",
        "pilot_id": pilot_id,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "source_sha": source_sha,
        "controller_retention_utc": _retained_at or datetime.now(timezone.utc).isoformat(),
        "sanitized_receipt_retention": receipt_status,
        "raw_diagnostic_retention": diagnostic_status,
        "credential_screening": summary.get("credential_screen", "UNDETERMINED"),
        "receipt_set_validation": receipt_validation.status,
        "artifact_entries": entries,
    }
    _write_manifest(attempt_directory / "retention-manifest.json", manifest)
    return manifest


def retention_then_shutdown(
    retain: Callable[[], dict[str, Any]], shutdown: Callable[[], None],
) -> dict[str, Any]:
    """Always cross the shutdown boundary after controller responsibility begins."""
    try:
        return retain()
    finally:
        shutdown()


def _retain_one(
    source: PilotArtifactSource,
    name: str,
    destination_directory: Path,
    staging: Path,
    limit: int | None,
    eligible: bool,
) -> dict[str, Any]:
    observed = source.observe(name)
    entry = {
        "relative_name": name, "present_remote": observed.present,
        "eligible_for_transfer": False, "transfer_attempted": False,
        "retained_local": False, "byte_length": observed.byte_length,
        "sha256": observed.sha256, "retention_status": "UNDETERMINED",
    }
    if not observed.present:
        return _status(entry, "ABSENT")
    if not _valid_remote(observed):
        return _status(entry, "LOCAL_VALIDATION_FAILED")
    if limit is not None and observed.byte_length > limit:
        return _status(entry, "REFUSED_OVERSIZED")
    if not eligible or (limit is not None and observed.credential_screen != "PASS_NO_MATCH"):
        status = (
            "REFUSED_CONTAMINATED" if observed.credential_screen == "CONTAMINATED"
            else "REFUSED_SCREEN_UNDETERMINED"
        )
        return _status(entry, status)
    entry["eligible_for_transfer"] = True
    temporary = staging / name
    entry["transfer_attempted"] = True
    try:
        source.copy_literal(name, temporary)
    except Exception:
        return _status(entry, "TRANSFER_FAILED")
    try:
        length, digest = _local_identity(temporary, limit)
        if length != observed.byte_length or digest != observed.sha256:
            return _status(entry, "HASH_MISMATCH")
        if name in scan_for_credentials(staging):
            return _status(entry, "REFUSED_CONTAMINATED")
        destination = destination_directory / name
        _publish_idempotent(temporary, destination, digest)
    except (OSError, FileObservationError, EvidenceCaptureError, PilotRetentionError):
        return _status(entry, "LOCAL_VALIDATION_FAILED")
    entry["retained_local"] = True
    return _status(entry, "PASS")


def _valid_remote(value: RemoteArtifact) -> bool:
    return (
        value.regular and not value.symlink and value.link_count == 1
        and type(value.byte_length) is int and value.byte_length >= 0
        and isinstance(value.sha256, str) and re.fullmatch(r"[0-9a-f]{64}", value.sha256)
    )


def _local_identity(path: Path, limit: int | None) -> tuple[int, str]:
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode) or path.is_symlink()
        or metadata.st_nlink != 1 or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.getuid()
    ):
        raise PilotRetentionError("PRIVATE_RETENTION_LOCAL_FILE_UNTRUSTED")
    digest = hashlib.sha256()
    length = 0
    with observed_regular_file(path) as stream:
        while chunk := stream.read(65_536):
            length += len(chunk)
            if limit is not None and length > limit:
                raise PilotRetentionError("PRIVATE_RETENTION_LIMIT_EXCEEDED")
            digest.update(chunk)
    return length, digest.hexdigest()


def _publish_idempotent(staged: Path, destination: Path, digest: str) -> None:
    if destination.exists() or destination.is_symlink():
        _, existing = _local_identity(destination, None)
        if existing != digest:
            raise PilotRetentionError("PRIVATE_RETENTION_DESTINATION_CONFLICT")
        staged.unlink()
        return
    os.link(staged, destination)
    os.chmod(destination, 0o600)
    staged.unlink()
    descriptor = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(destination.parent)


def _write_manifest(path: Path, value: Mapping[str, Any]) -> None:
    data = canonical_bytes(dict(value)) + b"\n"
    if path.exists():
        if path.read_bytes() != data:
            raise PilotRetentionError("PRIVATE_RETENTION_MANIFEST_CONFLICT")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _receipt_aggregate(
    entries: list[dict[str, Any]], receipt_set_valid: bool, outcome: Any,
) -> str:
    statuses = {
        entry["relative_name"]: entry["retention_status"]
        for entry in entries if entry["relative_name"] in RECEIPTS
    }
    required_pass = all(
        statuses.get(name) == "PASS"
        for name in ("pilot-claim.json", "pilot-armed.json", "pilot-summary.json")
    )
    failure_status = statuses.get("pilot-failure.json")
    failure_coherent = (
        outcome == "FAIL" and failure_status == "PASS"
        or outcome == "PASS" and failure_status == "ABSENT"
    )
    if receipt_set_valid and required_pass and failure_coherent:
        return "PASS"
    if any(status == "PASS" for status in statuses.values()):
        return "PARTIAL"
    return "FAIL"


def _aggregate(entries: list[dict[str, Any]], names: set[str], empty: str) -> str:
    selected = [entry["retention_status"] for entry in entries if entry["relative_name"] in names]
    passed = sum(status == "PASS" for status in selected)
    if passed == len(selected):
        return "PASS"
    if passed:
        return "PARTIAL"
    return empty


def _status(entry: dict[str, Any], value: str) -> dict[str, Any]:
    if value not in _STATUSES:
        raise AssertionError("unsupported retention status")
    entry["retention_status"] = value
    return entry


def _make_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, exist_ok=True)
    _private_directory(path)


def _private_directory(path: Path) -> None:
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PilotRetentionError("PRIVATE_RETENTION_ROOT_UNTRUSTED")


def _remove_empty_staging(path: Path) -> None:
    try:
        for child in path.iterdir():
            child.unlink(missing_ok=True)
        path.rmdir()
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
