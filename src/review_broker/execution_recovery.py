"""Evidence-bound workflow recovery operations outside model execution."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .artifact_locator import (
    GitHubActionsArtifactStore,
    build_evidence_artifact_plan,
    validate_evidence_artifact_plan,
)
from .codespace import CodespaceController, CodespaceError
from .evidence import (
    TERMINAL_CAPTURE_FILES,
    build_shutdown_observation,
    build_terminal_capture_receipt,
)
from .github_journal import GitHubRefJournal
from .identity import artifact_identity, canonical_bytes
from .queue import AttemptState


class ExecutionRecoveryError(RuntimeError):
    """A recovery operation cannot establish its required evidence."""


def plan_durable_evidence_artifact(
    broker_repository: str,
    evidence_directory: Path,
    output_path: Path,
    *,
    artifact_name: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
) -> dict[str, Any]:
    if output_path.exists():
        plan = _read_object(output_path)
        validate_evidence_artifact_plan(plan)
    else:
        plan = build_evidence_artifact_plan(
            evidence_directory,
            broker_repository=broker_repository,
            artifact_name=artifact_name,
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
        )
        _write_object_exclusive(output_path, plan)
    GitHubRefJournal(broker_repository).record_evidence_locator_plan(
        plan["request_id"], plan
    )
    return plan


def finalize_durable_evidence_artifact(
    broker_repository: str,
    plan_path: Path,
    output_path: Path,
    *,
    artifact_id: int,
    artifact_digest: str,
) -> dict[str, Any]:
    plan = _read_object(plan_path)
    locator = GitHubActionsArtifactStore(broker_repository).finalize(
        plan,
        artifact_id,
        artifact_digest,
    )
    GitHubRefJournal(broker_repository).record_evidence_locator(
        locator["request_id"], locator
    )
    _write_object_exclusive(output_path, locator)
    return locator


def recover_runtime_evidence(
    controller: CodespaceController,
    remote_directory: str,
    output_directory: Path,
    *,
    request_id: str,
    attempt_id: str,
    context: Mapping[str, str],
) -> dict[str, Any]:
    output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any]] = {}
    for name in TERMINAL_CAPTURE_FILES:
        destination = output_directory / name
        try:
            controller.recover(f"{remote_directory}/{name}", destination)
        except CodespaceError as exc:
            artifacts[name] = {
                "recovered": False,
                "artifact_id": None,
                "error": str(exc),
            }
            continue
        data = destination.read_bytes()
        artifacts[name] = {
            "recovered": True,
            "artifact_id": artifact_identity(data),
            "byte_length": len(data),
        }
    manifest = {
        "schema_version": 1,
        "evidence_type": "runtime-evidence-recovery",
        "codespace_name": controller.name,
        "remote_directory": remote_directory,
        "request_id": request_id,
        "attempt_id": attempt_id,
        "observed_at": _utc_now(),
        "context": dict(context),
        "artifacts": artifacts,
        "complete": all(entry["recovered"] for entry in artifacts.values()),
    }
    _write_object_exclusive(output_directory / "recovery-manifest.json", manifest)
    return manifest


def capture_terminal_transition(
    broker_repository: str,
    packet_directory: Path,
    *,
    request_id: str,
    attempt_id: str,
    packet_id: str,
    context: Mapping[str, str],
) -> dict[str, Any]:
    receipt_path = packet_directory / "terminal-capture.json"
    if receipt_path.exists():
        receipt = _read_object(receipt_path)
        if receipt.get("packet_id") != packet_id:
            raise ExecutionRecoveryError("TERMINAL_PACKET_ID_MISMATCH")
    else:
        receipt = build_terminal_capture_receipt(
            packet_directory,
            request_id=request_id,
            attempt_id=attempt_id,
            packet_id=packet_id,
            context=context,
        )
        _write_object_exclusive(receipt_path, receipt)
    GitHubRefJournal(broker_repository).record_terminal_capture(request_id, receipt)
    return receipt


def mark_ambiguous_execution_indeterminate(
    broker_repository: str,
    recovery_manifest_path: Path,
    *,
    request_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    manifest = _read_object(recovery_manifest_path)
    if (
        manifest.get("evidence_type") != "runtime-evidence-recovery"
        or manifest.get("request_id") != request_id
        or manifest.get("attempt_id") != attempt_id
    ):
        raise ExecutionRecoveryError("RECOVERY_MANIFEST_IDENTITY_MISMATCH")
    journal = GitHubRefJournal(broker_repository)
    current = journal.get(request_id)
    if current.attempt_id != attempt_id:
        raise ExecutionRecoveryError("RECOVERY_ATTEMPT_ID_MISMATCH")
    if current.state is AttemptState.TERMINAL_CAPTURED:
        return {"state": current.state.value, "transitioned": False}
    if current.state is not AttemptState.ARMED:
        raise ExecutionRecoveryError("INDETERMINATE_SOURCE_STATE_INVALID")
    evidence_id = artifact_identity(canonical_bytes(manifest) + b"\n")
    updated = journal.transition(
        request_id,
        AttemptState.INDETERMINATE,
        [evidence_id],
    )
    return {"state": updated.state.value, "transitioned": True}


def stop_and_observe_shutdown(
    controller: CodespaceController,
    output_directory: Path,
    *,
    request_id: str,
    attempt_id: str,
    context: Mapping[str, str],
) -> dict[str, Any]:
    output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    observed_before = "UNOBSERVED"
    try:
        observed_before = controller.state()
        if observed_before != "Shutdown":
            controller.stop()
        observed_after = controller.state()
        receipt = build_shutdown_observation(
            codespace_name=controller.name,
            request_id=request_id,
            attempt_id=attempt_id,
            observed_state=observed_after,
            context=context,
        )
    except (CodespaceError, ValueError) as exc:
        incident = {
            "schema_version": 1,
            "evidence_type": "codespace-shutdown-incident",
            "codespace_name": controller.name,
            "request_id": request_id,
            "attempt_id": attempt_id,
            "observed_before": observed_before,
            "observed_at": _utc_now(),
            "context": dict(context),
            "error": str(exc),
        }
        _write_object_exclusive(output_directory / "shutdown-incident.json", incident)
        raise ExecutionRecoveryError(
            "INFRASTRUCTURE_INCIDENT:SHUTDOWN_UNVERIFIED"
        ) from exc
    _write_object_exclusive(output_directory / "shutdown-observation.json", receipt)
    return receipt


def record_stopped_transition(
    broker_repository: str,
    observation_path: Path,
    *,
    request_id: str,
    attempt_id: str,
    codespace_name: str,
) -> dict[str, Any]:
    receipt = _read_object(observation_path)
    if receipt.get("codespace_name") != codespace_name:
        raise ExecutionRecoveryError("SHUTDOWN_CODESPACE_IDENTITY_MISMATCH")
    journal = GitHubRefJournal(broker_repository)
    current = journal.get(request_id)
    if current.attempt_id != attempt_id:
        raise ExecutionRecoveryError("SHUTDOWN_ATTEMPT_ID_MISMATCH")
    updated = journal.record_stopped(request_id, receipt)
    return updated.as_dict()


def workflow_context(
    environment: Mapping[str, str],
    *,
    source: str,
) -> dict[str, str]:
    return {
        "source": source,
        "workflow_run_id": environment.get("GITHUB_RUN_ID", "UNAVAILABLE"),
        "workflow_run_attempt": environment.get("GITHUB_RUN_ATTEMPT", "UNAVAILABLE"),
        "workflow": environment.get("GITHUB_WORKFLOW", "UNAVAILABLE"),
        "job": environment.get("GITHUB_JOB", "UNAVAILABLE"),
        "ref": environment.get("GITHUB_REF", "UNAVAILABLE"),
        "sha": environment.get("GITHUB_SHA", "UNAVAILABLE"),
    }


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExecutionRecoveryError("OBJECT_FILE_INVALID")
    return value


def _write_object_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical_bytes(dict(value)) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
