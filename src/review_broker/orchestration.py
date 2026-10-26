"""Trusted preparation and publication use cases for GitHub workflows."""
from __future__ import annotations

from importlib import resources
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

from .admission import AuthorizationPolicy, authorize_and_resolve
from .identity import artifact_identity, canonical_bytes
from .packets import GitSourceReader, SourceSpec, build_packet
from .github_journal import GitHubRefJournal
from .publication import GitHubPublisher, build_review_result
from .queue import AttemptState
from .recovery import (
    PreparationRecoveryAction,
    decide_preparation_recovery,
    verify_rebuilt_packet,
)
from .request import parse_issue_body


class OrchestrationError(RuntimeError):
    pass


def prepare_issue(
    broker_repository: str,
    issue_number: int,
    output_directory: Path,
    *,
    environment: Mapping[str, str] = os.environ,
) -> dict[str, Any]:
    issue = _gh_json(f"repos/{broker_repository}/issues/{issue_number}")
    request = parse_issue_body(issue.get("body") or "")
    authorization = AuthorizationPolicy(
        requesters=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REQUESTERS", "")),
        repositories=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REPOSITORIES", "")),
    )
    resolved = authorize_and_resolve(
        issue["user"]["login"],
        request,
        authorization,
        _gh_json,
        expected_head=environment.get("REVIEW_BROKER_EXPECTED_HEAD") or None,
    )
    journal = GitHubRefJournal(
        broker_repository,
        base_branch=environment.get("REVIEW_BROKER_DEFAULT_BRANCH", "dev"),
    )
    attempt = journal.claim(resolved["request_id"])
    admission_evidence = artifact_identity(canonical_bytes(resolved))
    preparation_action = decide_preparation_recovery(attempt, admission_evidence)
    if preparation_action is PreparationRecoveryAction.DUPLICATE_TERMINAL_OR_MODEL_CAPABLE:
        return {"duplicate": True, "attempt": attempt.as_dict(), "resolved_request": resolved}
    if preparation_action is PreparationRecoveryAction.ADMIT_AND_BUILD:
        attempt = journal.transition(
            resolved["request_id"], AttemptState.ADMITTED, [admission_evidence]
        )
    profile = _load_profile(request["policy"]["profile"], request["policy"]["version"])
    changed = _pull_request_files(
        request["subject"]["repository"],
        request["subject"]["pull_request"],
        expected_head=resolved["subject"]["head_commit"],
    )
    if not changed:
        raise OrchestrationError("PULL_REQUEST_HAS_NO_FILES")
    with tempfile.TemporaryDirectory(prefix="review-broker-source-") as temporary:
        source_repository = Path(temporary) / "source.git"
        clone = subprocess.run(
            [
                "gh", "repo", "clone", request["subject"]["repository"],
                str(source_repository), "--", "--filter=blob:none", "--no-checkout",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
            shell=False,
        )
        if clone.returncode != 0:
            raise OrchestrationError("SOURCE_ACQUISITION_FAILED")
        commits = {resolved["subject"]["head_commit"], resolved["subject"]["base_commit"]}
        for commit in commits:
            fetch = subprocess.run(
                ["git", "-C", str(source_repository), "fetch", "origin", commit, "--depth=1"],
                text=True,
                capture_output=True,
                check=False,
                timeout=180,
                shell=False,
            )
            if fetch.returncode != 0:
                raise OrchestrationError("SOURCE_COMMIT_FETCH_FAILED")
        reader = GitSourceReader(source_repository)
        records = []
        for changed_file in changed:
            status = changed_file.get("status")
            path = changed_file.get("filename")
            if not isinstance(path, str):
                raise OrchestrationError("PULL_REQUEST_FILE_INVALID")
            commit = (
                resolved["subject"]["base_commit"]
                if status == "removed"
                else resolved["subject"]["head_commit"]
            )
            records.append(reader.read(SourceSpec(request["subject"]["repository"], commit, path)))
        instruction = _review_instruction(request, profile)
        manifest = build_packet(
            records,
            request_id=resolved["request_id"],
            subject_id=resolved["subject_id"],
            mission_instruction=instruction,
            profile=profile,
            output_directory=output_directory,
        )
    resolved["source_manifest_id"] = manifest["source_manifest_id"]
    metadata = {
        "schema_version": 1,
        "broker_repository": broker_repository,
        "issue_number": issue_number,
        "attempt_id": attempt.attempt_id,
        "request_id": resolved["request_id"],
    }
    (output_directory / "resolved-request.json").write_bytes(canonical_bytes(resolved) + b"\n")
    (output_directory / "broker-metadata.json").write_bytes(canonical_bytes(metadata) + b"\n")
    prepared_evidence = artifact_identity(canonical_bytes(manifest))
    if preparation_action is PreparationRecoveryAction.REBUILD_PREPARED:
        verify_rebuilt_packet(attempt, prepared_evidence)
    else:
        attempt = journal.transition(
            resolved["request_id"], AttemptState.PREPARED, [prepared_evidence]
        )
    return {
        "duplicate": False,
        "attempt": attempt.as_dict(),
        "resolved_request": resolved,
        "packet": manifest,
    }


def publish_validated_result(
    broker_repository: str,
    packet_directory: Path,
) -> dict[str, Any]:
    resolved = _read_object(packet_directory / "resolved-request.json")
    metadata = _read_object(packet_directory / "broker-metadata.json")
    manifest = _read_object(packet_directory / "input-manifest.json")
    attempt = _read_object(packet_directory / "attempt.json")
    validation = _read_object(packet_directory / "validation.json")
    subject = resolved["subject"]
    pr = _gh_json(f"repos/{subject['repository']}/pulls/{subject['pull_request']}")
    current_head = pr.get("head", {}).get("sha")
    result = build_review_result(
        resolved, manifest, attempt, validation, current_head=current_head
    )
    GitHubPublisher(broker_repository).publish(metadata["issue_number"], result)
    journal = GitHubRefJournal(broker_repository)
    result_evidence = artifact_identity(canonical_bytes(result))
    journal.transition(resolved["request_id"], AttemptState.REPORTED, [result_evidence])
    return result


def _review_instruction(request: dict[str, Any], profile: dict[str, Any]) -> str:
    mission = request["mission"]
    profile_rules = "\n".join(f"- {rule}" for rule in profile["mandatory_behavior"])
    criteria = "\n".join(f"- {criterion}" for criterion in mission["criteria"])
    return (
        f"OBJECTIVE: {mission['objective']}\n"
        f"REQUESTER INSTRUCTIONS: {mission['instructions']}\n"
        f"MANDATORY PROFILE BEHAVIOR:\n{profile_rules}\n"
        f"EXAMINATION CRITERIA:\n{criteria}\n"
        "The custom mission may strengthen but never disable mandatory profile behavior."
    )


def _load_profile(profile_id: str, version: int) -> dict[str, Any]:
    target = resources.files("review_broker.profiles").joinpath(f"{profile_id}-v{version}.json")
    try:
        profile = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise OrchestrationError("PROFILE_UNAVAILABLE") from exc
    if profile.get("id") != profile_id or profile.get("version") != version:
        raise OrchestrationError("PROFILE_IDENTITY_MISMATCH")
    if profile.get("custom_mission_may_disable") is not False:
        raise OrchestrationError("PROFILE_WEAKENING_FORBIDDEN")
    return profile


def _pull_request_files(
    repository: str,
    pull_request: int,
    *,
    expected_head: str,
    get_json: Any | None = None,
) -> list[dict[str, Any]]:
    getter = get_json or _gh_json
    files: list[dict[str, Any]] = []
    complete = False
    for page in range(1, 31):
        batch = getter(
            f"repos/{repository}/pulls/{pull_request}/files?per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise OrchestrationError("PULL_REQUEST_FILE_RESPONSE_INVALID")
        files.extend(batch)
        if len(batch) < 100:
            complete = True
            break
    if not complete:
        raise OrchestrationError("PULL_REQUEST_FILE_SCOPE_EXCEEDS_QUALIFIED_LIMIT")
    current = getter(f"repos/{repository}/pulls/{pull_request}")
    current_head = current.get("head", {}).get("sha") if isinstance(current, dict) else None
    if current_head != expected_head:
        raise OrchestrationError("PULL_REQUEST_HEAD_CHANGED_DURING_PREPARATION")
    return files


def _gh_json(endpoint: str) -> Any:
    result = subprocess.run(
        ["gh", "api", endpoint],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        shell=False,
    )
    if result.returncode != 0:
        raise OrchestrationError("GITHUB_API_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OrchestrationError("GITHUB_RESPONSE_INVALID") from exc


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OrchestrationError("OBJECT_FILE_INVALID")
    return value
