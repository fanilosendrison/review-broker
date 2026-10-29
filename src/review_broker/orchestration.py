"""Trusted preparation and publication use cases for GitHub workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import resources
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from typing import Any, Mapping

from .admission import (
    BOUNDED_V1_ADMISSION,
    AuthorizationPolicy,
    authorize,
    resolve_request,
    select_operational_admission,
)
from .identity import artifact_identity, canonical_bytes
from .packets import GitSourceReader, SourceSpec, build_packet
from .github_journal import GitHubRefJournal
from .predecessor import github_predecessor_authority, verify_v2_operation
from .publication import (
    GitHubPublisher,
    build_publication_intent,
    build_review_result,
    validate_publication_intent,
)
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
    source_token: str | None = None,
) -> dict[str, Any]:
    issue = _gh_json(f"repos/{broker_repository}/issues/{issue_number}")
    request = parse_issue_body(issue.get("body") or "")
    authorization = AuthorizationPolicy(
        requesters=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REQUESTERS", "")),
        repositories=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REPOSITORIES", "")),
    )
    authorize(issue["user"]["login"], request, authorization)
    admission_mode = select_operational_admission(
        request, environment, lambda endpoint: _gh_json(endpoint)
    )
    source_repository_name = request["subject"]["repository"]
    private_repositories = _csv_set(
        environment.get("REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES", "")
    )
    source_environment = (
        None
        if admission_mode == BOUNDED_V1_ADMISSION
        else _source_environment_for_repository(
            source_repository_name,
            private_repositories,
            source_token,
        )
    )

    def source_getter(endpoint: str) -> Any:
        return _gh_json(endpoint, environment=source_environment)
    resolved = resolve_request(
        request,
        source_getter,
        expected_head=environment.get("REVIEW_BROKER_EXPECTED_HEAD") or None,
    )
    journal = GitHubRefJournal(
        broker_repository,
        base_branch=environment.get("REVIEW_BROKER_DEFAULT_BRANCH", "dev"),
    )
    if request.get("schema_version") == 2:
        authority = github_predecessor_authority(
            broker_repository, journal, lambda endpoint: _gh_json(endpoint)
        )
        verify_v2_operation(request, resolved, authority)
    admission = resolved if request.get("schema_version") == 2 else None
    attempt = journal.claim(resolved["request_id"], admission)
    admission_evidence = artifact_identity(canonical_bytes(resolved))
    preparation_action = decide_preparation_recovery(attempt, admission_evidence)
    if preparation_action is PreparationRecoveryAction.DUPLICATE_TERMINAL_OR_MODEL_CAPABLE:
        return {
            "duplicate": True, "attempt": attempt.as_dict(),
            "resolved_request": resolved, "admission_mode": admission_mode,
        }
    if preparation_action is PreparationRecoveryAction.ADMIT_AND_BUILD:
        attempt = journal.transition(
            resolved["request_id"], AttemptState.ADMITTED, [admission_evidence]
        )
    profile = _load_profile(request["policy"]["profile"], request["policy"]["version"])
    changed = _pull_request_files(
        request["subject"]["repository"],
        request["subject"]["pull_request"],
        expected_head=resolved["subject"]["head_commit"],
        get_json=source_getter,
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
            env=source_environment,
        )
        if clone.returncode != 0:
            raise OrchestrationError("SOURCE_ACQUISITION_FAILED")
        commits = {resolved["subject"][key] for key in ("head_commit", "base_commit", "merge_base")}
        for commit in commits:
            fetch = subprocess.run(
                ["git", "-C", str(source_repository), "fetch", "origin", commit, "--depth=1"],
                text=True,
                capture_output=True,
                check=False,
                timeout=180,
                shell=False,
                env=source_environment,
            )
            if fetch.returncode != 0:
                raise OrchestrationError("SOURCE_COMMIT_FETCH_FAILED")
        reader = GitSourceReader(source_repository, environment=source_environment)
        merge_base = resolved["subject"]["merge_base"]
        head = resolved["subject"]["head_commit"]
        paths = [item.get("filename") for item in changed]
        if (any(not isinstance(path, str) for path in paths) or
            len(set(paths)) != len(paths) or reader.changed_paths(merge_base, head) != set(paths)):
            raise OrchestrationError("PULL_REQUEST_CHANGE_SCOPE_MISMATCH")
        records = []
        changes = []
        for changed_file in changed:
            status = changed_file.get("status")
            path = changed_file["filename"]
            previous = changed_file.get("previous_filename") if status in {"renamed", "copied"} else None
            if (status not in {"added", "removed", "modified", "renamed", "copied", "changed"}
                or (status in {"renamed", "copied"} and not isinstance(previous, str))):
                raise OrchestrationError("PULL_REQUEST_CHANGE_STATUS_UNSUPPORTED")
            before_id = after_id = None
            if status != "added":
                before_id = f"S{len(records) + 1:03d}"
                records.append(reader.read(SourceSpec(request["subject"]["repository"],
                                                      merge_base, previous or path)))
            if status != "removed":
                after_id = f"S{len(records) + 1:03d}"
                records.append(reader.read(SourceSpec(request["subject"]["repository"], head, path)))
            changes.append({"status": status, "path": path, "previous_path": previous,
                            "before_source_id": before_id, "after_source_id": after_id})
        instruction = _review_instruction(request, profile)
        manifest = build_packet(
            records,
            request_id=resolved["request_id"],
            subject_id=resolved["subject_id"],
            mission_instruction=instruction,
            profile=profile,
            output_directory=output_directory,
            changes=changes,
            change_diff=reader.diff(merge_base, head),
            merge_base=merge_base,
            head=head,
        )
    resolved["source_manifest_id"] = manifest["source_manifest_id"]
    metadata = {
        "schema_version": 1,
        "broker_repository": broker_repository,
        "issue_number": issue_number,
        "attempt_id": attempt.attempt_id,
        "request_id": resolved["request_id"],
        "admission_mode": admission_mode,
        "executing_broker_sha": environment.get("GITHUB_SHA", ""),
        "requester": issue["user"]["login"],
        "subject_repository": source_repository_name,
        "admission_checks": {
            "requester_authorized": True,
            "repository_authorized": True,
            "low_sensitivity_repository_admitted": admission_mode == BOUNDED_V1_ADMISSION,
            "public_repository_verified": admission_mode == BOUNDED_V1_ADMISSION,
            "executing_sha_admitted": admission_mode == BOUNDED_V1_ADMISSION,
        },
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
        "admission_mode": admission_mode,
    }


def publish_validated_result(
    broker_repository: str,
    packet_directory: Path,
    *,
    source_token: str | None = None,
) -> dict[str, Any]:
    resolved = _read_object(packet_directory / "resolved-request.json")
    metadata = _read_object(packet_directory / "broker-metadata.json")
    manifest = _read_object(packet_directory / "input-manifest.json")
    attempt = _read_object(packet_directory / "attempt.json")
    validation = _read_object(packet_directory / "validation.json")
    subject = resolved["subject"]
    private_repositories = _csv_set(
        os.environ.get("REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES", "")
    )
    source_environment = _source_environment_for_repository(
        subject["repository"],
        private_repositories,
        source_token,
    )
    pr = _gh_json(
        f"repos/{subject['repository']}/pulls/{subject['pull_request']}",
        environment=source_environment,
    )
    current_head = pr.get("head", {}).get("sha")
    result = build_review_result(
        resolved, manifest, attempt, validation, current_head=current_head
    )
    publisher = GitHubPublisher(broker_repository)
    journal = GitHubRefJournal(broker_repository)
    current = journal.get(resolved["request_id"])
    reservation_created = False
    if current.publication_intent is None:
        candidate_intent = build_publication_intent(
            result,
            issue_number=metadata["issue_number"],
            publisher=publisher.identity(),
            nonce=secrets.token_hex(32),
            reserved_at=datetime.now(timezone.utc).isoformat(),
        )
        current, reservation_created = journal.reserve_publication(
            resolved["request_id"], candidate_intent
        )
    intent = current.publication_intent
    if intent is None:
        raise OrchestrationError("PUBLICATION_INTENT_NOT_RECORDED")
    publication_result = intent.get("result")
    if not isinstance(publication_result, dict):
        raise OrchestrationError("PUBLICATION_RESULT_NOT_RECORDED")
    validate_publication_intent(intent, result=publication_result)
    receipt = publisher.publish_reserved(
        intent,
        publication_result,
        reservation_created=reservation_created,
    )
    journal.record_publication(resolved["request_id"], receipt)
    return publication_result


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


def _gh_json(
    endpoint: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> Any:
    result = subprocess.run(
        ["gh", "api", endpoint],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        shell=False,
        env=environment,
    )
    if result.returncode != 0:
        raise OrchestrationError("GITHUB_API_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OrchestrationError("GITHUB_RESPONSE_INVALID") from exc


def _source_environment_for_repository(
    repository: str,
    private_repositories: frozenset[str],
    source_token: str | None,
) -> dict[str, str] | None:
    if repository not in private_repositories:
        return None
    if not source_token:
        raise OrchestrationError("PRIVATE_SOURCE_CREDENTIAL_REQUIRED")
    return _source_environment(source_token)


def _source_environment(source_token: str | None) -> dict[str, str] | None:
    if source_token is None:
        return None
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "PATH", "XDG_CONFIG_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    }
    environment["GH_TOKEN"] = source_token
    return environment


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OrchestrationError("OBJECT_FILE_INVALID")
    return value
