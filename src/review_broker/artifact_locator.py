"""Exact GitHub Actions artifact location and retrieval for review evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from typing import Any, Callable, Mapping
import zipfile

from .identity import artifact_identity, canonical_bytes


ARTIFACT_NAME = re.compile(r"[A-Za-z0-9_.-]{1,255}\Z")
IDENTITY = re.compile(r"(?:request|attempt|subject|packet):sha256:[0-9a-f]{64}\Z")
DIGEST = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
Runner = Callable[..., subprocess.CompletedProcess[Any]]


class ArtifactLocatorError(RuntimeError):
    """An artifact cannot prove exact durable evidence identity."""


def build_evidence_artifact_plan(
    evidence_directory: Path,
    *,
    broker_repository: str,
    artifact_name: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
) -> dict[str, Any]:
    resolved = _read_object(evidence_directory / "resolved-request.json")
    manifest = _read_object(evidence_directory / "input-manifest.json")
    attempt = _read_object(evidence_directory / "attempt.json")
    terminal = _read_object(evidence_directory / "terminal-capture.json")
    request_id = resolved.get("request_id")
    attempt_id = attempt.get("attempt_id")
    subject_id = resolved.get("subject_id")
    packet_id = manifest.get("packet_id")
    if (
        terminal.get("request_id") != request_id
        or terminal.get("attempt_id") != attempt_id
        or terminal.get("packet_id") != packet_id
        or manifest.get("request_id") != request_id
        or manifest.get("subject_id") != subject_id
    ):
        raise ArtifactLocatorError("ARTIFACT_PLAN_IDENTITY_MISMATCH")
    plan = {
        "schema_version": 1,
        "evidence_type": "github-actions-artifact-plan",
        "stage": "TERMINAL_CAPTURED",
        "broker_repository": broker_repository,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "subject_id": subject_id,
        "packet_id": packet_id,
        "workflow_run_id": _positive_integer_text(workflow_run_id, "WORKFLOW_RUN_ID_INVALID"),
        "workflow_run_attempt": _positive_integer_text(
            workflow_run_attempt, "WORKFLOW_RUN_ATTEMPT_INVALID"
        ),
        "artifact_name": _artifact_name(artifact_name),
        "artifacts": _inventory(evidence_directory),
    }
    validate_evidence_artifact_plan(plan)
    return plan


def validate_evidence_artifact_plan(
    plan: Mapping[str, Any],
    *,
    request_id: str | None = None,
    attempt_id: str | None = None,
) -> str:
    if (
        plan.get("schema_version") != 1
        or plan.get("evidence_type") != "github-actions-artifact-plan"
        or plan.get("stage") != "TERMINAL_CAPTURED"
        or not isinstance(plan.get("broker_repository"), str)
        or "/" not in plan["broker_repository"]
    ):
        raise ArtifactLocatorError("ARTIFACT_PLAN_INVALID")
    for field in ("request_id", "attempt_id", "subject_id", "packet_id"):
        value = plan.get(field)
        if not isinstance(value, str) or not IDENTITY.fullmatch(value):
            raise ArtifactLocatorError(f"ARTIFACT_PLAN_{field.upper()}_INVALID")
    if request_id is not None and plan["request_id"] != request_id:
        raise ArtifactLocatorError("ARTIFACT_PLAN_REQUEST_MISMATCH")
    if attempt_id is not None and plan["attempt_id"] != attempt_id:
        raise ArtifactLocatorError("ARTIFACT_PLAN_ATTEMPT_MISMATCH")
    _positive_integer_text(plan.get("workflow_run_id"), "WORKFLOW_RUN_ID_INVALID")
    _positive_integer_text(plan.get("workflow_run_attempt"), "WORKFLOW_RUN_ATTEMPT_INVALID")
    _artifact_name(plan.get("artifact_name"))
    artifacts = plan.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ArtifactLocatorError("ARTIFACT_PLAN_INVENTORY_INVALID")
    for path, entry in artifacts.items():
        if not _safe_relative_path(path) or not isinstance(entry, dict):
            raise ArtifactLocatorError("ARTIFACT_PLAN_INVENTORY_INVALID")
        if (
            not isinstance(entry.get("artifact_id"), str)
            or not re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", entry["artifact_id"])
            or not isinstance(entry.get("byte_length"), int)
            or entry["byte_length"] < 0
        ):
            raise ArtifactLocatorError("ARTIFACT_PLAN_INVENTORY_INVALID")
    return artifact_identity(canonical_bytes(dict(plan)) + b"\n")

def build_evidence_artifact_locator(
    plan: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    declared_digest: str,
) -> dict[str, Any]:
    validate_evidence_artifact_plan(plan)
    artifact_id = metadata.get("id")
    digest = _normalized_digest(metadata.get("digest"))
    if digest != _normalized_digest(declared_digest):
        raise ArtifactLocatorError("ARTIFACT_DIGEST_MISMATCH")
    workflow_run = metadata.get("workflow_run")
    if (
        not isinstance(artifact_id, int)
        or artifact_id < 1
        or metadata.get("name") != plan["artifact_name"]
        or metadata.get("expired") is not False
        or not isinstance(workflow_run, dict)
        or str(workflow_run.get("id")) != plan["workflow_run_id"]
    ):
        raise ArtifactLocatorError("ARTIFACT_METADATA_MISMATCH")
    locator = {
        "schema_version": 1,
        "evidence_type": "github-actions-artifact-locator",
        "stage": plan["stage"],
        "broker_repository": plan["broker_repository"],
        "request_id": plan["request_id"],
        "attempt_id": plan["attempt_id"],
        "subject_id": plan["subject_id"],
        "packet_id": plan["packet_id"],
        "workflow_run_id": plan["workflow_run_id"],
        "workflow_run_attempt": plan["workflow_run_attempt"],
        "artifact_id": artifact_id,
        "artifact_name": plan["artifact_name"],
        "artifact_digest": digest,
        "artifact_size_in_bytes": metadata.get("size_in_bytes"),
        "created_at": metadata.get("created_at"),
        "expires_at": metadata.get("expires_at"),
        "artifacts": plan["artifacts"],
    }
    validate_evidence_artifact_locator(locator)
    return locator


def validate_evidence_artifact_locator(
    locator: Mapping[str, Any],
    *,
    request_id: str | None = None,
    attempt_id: str | None = None,
) -> str:
    plan = {
        key: locator.get(key)
        for key in (
            "schema_version", "stage", "broker_repository", "request_id",
            "attempt_id", "subject_id", "packet_id", "workflow_run_id",
            "workflow_run_attempt", "artifact_name", "artifacts",
        )
    }
    plan["evidence_type"] = "github-actions-artifact-plan"
    validate_evidence_artifact_plan(
        plan,
        request_id=request_id,
        attempt_id=attempt_id,
    )
    if (
        locator.get("evidence_type") != "github-actions-artifact-locator"
        or not isinstance(locator.get("artifact_id"), int)
        or locator["artifact_id"] < 1
        or _normalized_digest(locator.get("artifact_digest"))
        != locator.get("artifact_digest")
        or not isinstance(locator.get("artifact_size_in_bytes"), int)
        or locator["artifact_size_in_bytes"] < 1
    ):
        raise ArtifactLocatorError("ARTIFACT_LOCATOR_INVALID")
    for field in ("created_at", "expires_at"):
        _timestamp(locator.get(field), f"ARTIFACT_{field.upper()}_INVALID")
    return artifact_identity(canonical_bytes(dict(locator)) + b"\n")

class GitHubActionsArtifactStore:
    """Observe and retrieve one immutable Actions artifact through GitHub API."""

    def __init__(self, repository: str, runner: Runner = subprocess.run):
        self.repository = repository
        self.runner = runner

    def finalize(self, plan: Mapping[str, Any], artifact_id: int, digest: str) -> dict[str, Any]:
        if plan.get("broker_repository") != self.repository:
            raise ArtifactLocatorError("ARTIFACT_REPOSITORY_MISMATCH")
        metadata = self._json(f"repos/{self.repository}/actions/artifacts/{artifact_id}")
        return build_evidence_artifact_locator(plan, metadata, declared_digest=digest)

    def resolve_plan(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        validate_evidence_artifact_plan(plan)
        if plan.get("broker_repository") != self.repository:
            raise ArtifactLocatorError("ARTIFACT_REPOSITORY_MISMATCH")
        endpoint = (
            f"repos/{self.repository}/actions/runs/{plan['workflow_run_id']}"
            f"/artifacts?name={plan['artifact_name']}&per_page=100"
        )
        response = self._json(endpoint)
        artifacts = response.get("artifacts") if isinstance(response, dict) else None
        total_count = response.get("total_count") if isinstance(response, dict) else None
        if (
            not isinstance(artifacts, list)
            or not isinstance(total_count, int)
            or total_count != len(artifacts)
        ):
            raise ArtifactLocatorError("ARTIFACT_LIST_RESPONSE_INVALID")
        candidates = [
            item for item in artifacts
            if isinstance(item, dict) and item.get("name") == plan["artifact_name"]
        ]
        if len(candidates) != 1:
            raise ArtifactLocatorError("ARTIFACT_UNAVAILABLE_OR_AMBIGUOUS")
        digest = candidates[0].get("digest")
        return build_evidence_artifact_locator(plan, candidates[0], declared_digest=digest)

    def download(self, locator: Mapping[str, Any], destination: Path) -> None:
        validate_evidence_artifact_locator(locator)
        if locator.get("broker_repository") != self.repository:
            raise ArtifactLocatorError("ARTIFACT_REPOSITORY_MISMATCH")
        metadata = self._json(
            f"repos/{self.repository}/actions/artifacts/{locator['artifact_id']}"
        )
        observed = build_evidence_artifact_locator(
            {**dict(locator), "evidence_type": "github-actions-artifact-plan"},
            metadata,
            declared_digest=locator["artifact_digest"],
        )
        for field in ("artifact_id", "artifact_digest", "expires_at", "artifacts"):
            if observed[field] != locator[field]:
                raise ArtifactLocatorError("ARTIFACT_LOCATOR_METADATA_CHANGED")
        if _timestamp(locator["expires_at"], "ARTIFACT_EXPIRES_AT_INVALID") <= datetime.now(timezone.utc):
            raise ArtifactLocatorError("ARTIFACT_EXPIRED")
        archive = self._bytes(
            f"repos/{self.repository}/actions/artifacts/{locator['artifact_id']}/zip"
        )
        if (
            len(archive) != locator["artifact_size_in_bytes"]
            or "sha256:" + hashlib.sha256(archive).hexdigest()
            != locator["artifact_digest"]
        ):
            raise ArtifactLocatorError("ARTIFACT_ARCHIVE_DIGEST_MISMATCH")
        temporary = destination.with_name(destination.name + ".partial")
        if destination.exists() or temporary.exists():
            raise ArtifactLocatorError("ARTIFACT_DESTINATION_EXISTS")
        temporary.mkdir(mode=0o700, parents=True)
        try:
            archive_path = temporary / "artifact.zip"
            archive_path.write_bytes(archive)
            extracted = temporary / "content"
            extracted.mkdir(mode=0o700)
            _extract_exact(archive_path, extracted)
            _verify_inventory(extracted, locator["artifacts"])
            archive_path.unlink()
            extracted.replace(destination)
            temporary.rmdir()
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def _json(self, endpoint: str) -> dict[str, Any]:
        result = self.runner(
            ["gh", "api", endpoint],
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            shell=False,
        )
        if result.returncode != 0:
            raise ArtifactLocatorError("ARTIFACT_API_FAILED")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ArtifactLocatorError("ARTIFACT_API_RESPONSE_INVALID") from exc
        if not isinstance(value, dict):
            raise ArtifactLocatorError("ARTIFACT_API_RESPONSE_INVALID")
        return value

    def _bytes(self, endpoint: str) -> bytes:
        result = self.runner(
            ["gh", "api", endpoint],
            capture_output=True,
            check=False,
            timeout=300,
            shell=False,
        )
        if result.returncode != 0 or not isinstance(result.stdout, bytes):
            raise ArtifactLocatorError("ARTIFACT_DOWNLOAD_FAILED")
        return result.stdout


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise ArtifactLocatorError("ARTIFACT_SOURCE_SYMLINK")
            continue
        relative = path.relative_to(root).as_posix()
        if not _safe_relative_path(relative):
            raise ArtifactLocatorError("ARTIFACT_SOURCE_PATH_INVALID")
        data = path.read_bytes()
        inventory[relative] = {
            "artifact_id": artifact_identity(data),
            "byte_length": len(data),
        }
    if not inventory:
        raise ArtifactLocatorError("ARTIFACT_SOURCE_EMPTY")
    return inventory

def _verify_inventory(root: Path, expected: Mapping[str, Any]) -> None:
    actual = _inventory(root)
    if actual != expected:
        raise ArtifactLocatorError("ARTIFACT_CONTENT_IDENTITY_MISMATCH")

def _extract_exact(archive: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as bundle:
            seen: set[str] = set()
            for info in bundle.infolist():
                name = info.filename.removesuffix("/")
                if not name:
                    continue
                if name in seen or not _safe_relative_path(name):
                    raise ArtifactLocatorError("ARTIFACT_ARCHIVE_PATH_INVALID")
                seen.add(name)
                mode = info.external_attr >> 16
                if mode & 0o170000 == 0o120000:
                    raise ArtifactLocatorError("ARTIFACT_ARCHIVE_SYMLINK")
                target = destination / name
                if info.is_dir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise ArtifactLocatorError("ARTIFACT_ARCHIVE_INVALID") from exc


def _read_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactLocatorError("ARTIFACT_PLAN_INPUT_INVALID") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
        raise ArtifactLocatorError("ARTIFACT_PLAN_INPUT_INVALID")
    return value

def _safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _artifact_name(value: Any) -> str:
    if not isinstance(value, str) or not ARTIFACT_NAME.fullmatch(value):
        raise ArtifactLocatorError("ARTIFACT_NAME_INVALID")
    return value


def _positive_integer_text(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or int(value) < 1:
        raise ArtifactLocatorError(error)
    return value


def _normalized_digest(value: Any) -> str:
    if not isinstance(value, str):
        raise ArtifactLocatorError("ARTIFACT_DIGEST_INVALID")
    match = DIGEST.fullmatch(value)
    if match is None:
        raise ArtifactLocatorError("ARTIFACT_DIGEST_INVALID")
    return "sha256:" + match.group(1)


def _timestamp(value: Any, error: str) -> datetime:
    if not isinstance(value, str):
        raise ArtifactLocatorError(error)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactLocatorError(error) from exc
    if parsed.tzinfo is None:
        raise ArtifactLocatorError(error)
    return parsed
