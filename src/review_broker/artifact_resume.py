"""Resume validation and publication from exact durable evidence artifacts."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

from .artifact_locator import (
    ArtifactLocatorError,
    GitHubActionsArtifactStore,
    validate_evidence_artifact_locator,
)
from .github_journal import GitHubRefJournal
from .identity import artifact_identity, canonical_bytes
from .orchestration import publish_validated_result
from .publication import PublicationError
from .queue import AttemptRecord, AttemptState
from .validation import validate_evidence


class ArtifactResumeError(RuntimeError):
    """Durable evidence cannot safely resume the journal attempt."""


def resume_from_durable_artifact(
    broker_repository: str,
    record: AttemptRecord,
    *,
    source_token: str | None = None,
    journal: Any | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    active_journal = journal or GitHubRefJournal(broker_repository)
    active_store = store or GitHubActionsArtifactStore(broker_repository)
    locator = record.evidence_locator
    locator_created = False
    if locator is None:
        if record.evidence_locator_plan is None:
            raise ArtifactResumeError("EVIDENCE_LOCATOR_UNAVAILABLE")
        try:
            locator = active_store.resolve_plan(record.evidence_locator_plan)
        except ArtifactLocatorError as exc:
            raise ArtifactResumeError(str(exc)) from exc
        record = active_journal.record_evidence_locator(record.request_id, locator)
        locator_created = True
    try:
        validate_evidence_artifact_locator(
            locator,
            request_id=record.request_id,
            attempt_id=record.attempt_id,
        )
    except ArtifactLocatorError as exc:
        raise ArtifactResumeError(str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="review-broker-artifact-") as temporary:
        evidence = Path(temporary) / "evidence"
        try:
            active_store.download(locator, evidence)
        except ArtifactLocatorError as exc:
            raise ArtifactResumeError(str(exc)) from exc
        _verify_downloaded_identity(evidence, locator)
        validation = validate_evidence(evidence)
        validation_id = artifact_identity((evidence / "validation.json").read_bytes())
        if record.state is AttemptState.TERMINAL_CAPTURED:
            record = active_journal.transition(
                record.request_id,
                AttemptState.VALIDATED,
                [validation_id],
            )
        elif record.state is AttemptState.VALIDATED:
            if validation_id not in record.evidence_ids:
                raise ArtifactResumeError("VALIDATION_EVIDENCE_IDENTITY_MISMATCH")
        else:
            raise ArtifactResumeError("ARTIFACT_RECOVERY_STATE_INVALID")
        try:
            result = publish_validated_result(
                broker_repository,
                evidence,
                source_token=source_token,
            )
        except PublicationError as exc:
            raise ArtifactResumeError(str(exc)) from exc
    return {
        "request_id": record.request_id,
        "attempt_id": record.attempt_id,
        "locator_created": locator_created,
        "validation_id": validation_id,
        "validation": validation,
        "result_id": artifact_identity(canonical_bytes(result)),
        "state": active_journal.get(record.request_id).state.value,
    }


def _verify_downloaded_identity(
    evidence: Path,
    locator: dict[str, Any],
) -> None:
    resolved = _read_object(evidence / "resolved-request.json")
    manifest = _read_object(evidence / "input-manifest.json")
    attempt = _read_object(evidence / "attempt.json")
    if (
        resolved.get("request_id") != locator["request_id"]
        or resolved.get("subject_id") != locator["subject_id"]
        or manifest.get("request_id") != locator["request_id"]
        or manifest.get("subject_id") != locator["subject_id"]
        or manifest.get("packet_id") != locator["packet_id"]
        or attempt.get("attempt_id") != locator["attempt_id"]
    ):
        raise ArtifactResumeError("DOWNLOADED_EVIDENCE_IDENTITY_MISMATCH")


def _read_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactResumeError("DOWNLOADED_EVIDENCE_INCOMPLETE") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
        raise ArtifactResumeError("DOWNLOADED_EVIDENCE_NONCANONICAL")
    return value
