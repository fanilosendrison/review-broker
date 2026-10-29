"""Lost-delivery discovery and evidence-bound durable reconciliation."""
from __future__ import annotations

import os
from typing import Any, Mapping

from .admission import (
    BOUNDED_PRIVATE_V1_ADMISSION, COMPREHENSIVE_ADMISSION,
    AdmissionError,
    AuthorizationPolicy, authorize, resolve_request, select_operational_admission,
)
from .artifact_resume import ArtifactResumeError, resume_from_durable_artifact
from .codespace import CodespaceController, CodespaceError
from .evidence import build_shutdown_observation
from .github_journal import GitHubRefJournal
from .identity import artifact_identity, canonical_bytes
from .queue import AttemptState
from .recovery import RecoveryAction, decide_recovery
from .reconciliation_github import (
    ReconciliationGitHubError,
    dispatch_review_workflow,
    github_json,
    paginated_list,
    utc_now,
    workflow_context,
)
from .predecessor import (
    PredecessorError,
    github_predecessor_authority,
    verify_v2_operation,
)
from .request import RequestContractError, parse_issue_body
from .source_authorization import (
    SourceAuthorizationError,
    require_private_source_environment,
)


ReconciliationError = ReconciliationGitHubError


class PrivateSourceCredentialRequired(ReconciliationError):
    """An authorized private consumer has no bounded source-read credential."""


def reconcile_repository(
    broker_repository: str,
    codespace_name: str,
    *,
    codespace_environment: Mapping[str, str] | None = None,
    environment: Mapping[str, str] = os.environ,
    get_json: Any | None = None,
    journal: Any | None = None,
    controller: Any | None = None,
    dispatch: Any | None = None,
    max_issue_pages: int = 100,
    max_ref_pages: int = 100,
    source_token: str | None = None,
) -> list[dict[str, Any]]:
    getter = get_json or github_json
    dispatcher = dispatch or dispatch_review_workflow
    default_branch = environment.get("REVIEW_BROKER_DEFAULT_BRANCH", "dev")
    authorization = AuthorizationPolicy(
        requesters=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REQUESTERS", "")),
        repositories=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REPOSITORIES", "")),
    )
    private_repositories = _csv_set(
        environment.get("REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES", "")
    )
    issues = paginated_list(
        getter,
        f"repos/{broker_repository}/issues?state=open",
        maximum_pages=max_issue_pages,
        incomplete_error="ISSUE_SCAN_INCOMPLETE",
    )
    refs = paginated_list(
        getter,
        f"repos/{broker_repository}/git/matching-refs/heads/review-claims/",
        maximum_pages=max_ref_pages,
        incomplete_error="CLAIM_REF_SCAN_INCOMPLETE",
    )
    active_journal = journal or GitHubRefJournal(
        broker_repository,
        base_branch=default_branch,
    )
    active_controller = controller or CodespaceController(
        codespace_name,
        environment=codespace_environment,
    )
    codespace_state: str | None = None
    context = workflow_context(environment, source="reconciler")
    decisions: list[dict[str, Any]] = []
    processed_requests: set[str] = set()

    for issue in sorted(issues, key=lambda value: value.get("number", 0)):
        if "pull_request" in issue:
            continue
        try:
            request = parse_issue_body(issue.get("body") or "")
            authorize(issue["user"]["login"], request, authorization)
            repository = request["subject"]["repository"]
            private_mode_requested = (
                environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED") == "true"
            )
            if private_mode_requested:
                require_private_source_environment(
                    repository, private_repositories, source_token
                )
            if get_json is not None:
                source_getter = getter
            else:
                selected_token = source_token if private_mode_requested else None

                def source_getter(endpoint: str) -> Any:
                    return github_json(endpoint, token=selected_token)

            admission_mode = select_operational_admission(
                request, environment, source_getter,
                requester=issue["user"]["login"],
            )
            private_source = repository in private_repositories and admission_mode in {
                BOUNDED_PRIVATE_V1_ADMISSION, COMPREHENSIVE_ADMISSION,
            }
            if private_source and not source_token:
                raise PrivateSourceCredentialRequired
            if get_json is None and private_source:
                def source_getter(endpoint: str) -> Any:
                    return github_json(endpoint, token=source_token)
            resolved = resolve_request(request, source_getter)
            if request.get("schema_version") == 2:
                verify_v2_operation(
                    request,
                    resolved,
                    github_predecessor_authority(
                        broker_repository, active_journal, getter
                    ),
                )
        except SourceAuthorizationError as exc:
            decisions.append({
                "issue_number": issue.get("number"),
                "action": str(exc),
                "reason": "Dedicated read-only private-source authority is unavailable.",
                "outcome": "BLOCKED",
            })
            continue
        except PrivateSourceCredentialRequired:
            decisions.append({
                "issue_number": issue.get("number"),
                "action": "PRIVATE_SOURCE_CREDENTIAL_REQUIRED",
                "reason": "Dedicated read-only private-source authority is unavailable.",
                "outcome": "BLOCKED",
            })
            continue
        except (
            AdmissionError, PredecessorError, RequestContractError, KeyError, TypeError,
        ) as exc:
            decisions.append({
                "issue_number": issue.get("number"),
                "action": "REJECTED_REQUEST",
                "reason": type(exc).__name__,
                "outcome": "BLOCKED",
            })
            continue
        request_id = resolved["request_id"]
        if request_id in processed_requests:
            decisions.append({
                "issue_number": issue["number"],
                "request_id": request_id,
                "action": "DUPLICATE_ISSUE",
                "reason": "Canonical request already discovered in this complete scan.",
                "outcome": "NO_SECOND_ATTEMPT",
            })
            continue
        processed_requests.add(request_id)
        admission = resolved if request.get("schema_version") == 2 else None
        record = active_journal.claim(request_id, admission)
        codespace_state = codespace_state or active_controller.state()
        decision = decide_recovery(record, codespace_state=codespace_state)
        if decision.action is RecoveryAction.RESUME_PRE_MODEL:
            if record.state is AttemptState.PREPARED:
                decisions.append({"issue_number": issue["number"], "request_id": request_id,
                    "state": record.state.value, "action": "AWAIT_EXPLICIT_PREPARED_RECOVERY",
                    "reason": "Explicit dispatch required.", "outcome": "BLOCKED"})
                continue
            dispatcher(broker_repository, default_branch, issue["number"])
            decisions.append({
                "issue_number": issue["number"],
                "request_id": request_id,
                "state": record.state.value,
                "action": "DISPATCH_PRE_MODEL",
                "reason": decision.reason,
                "outcome": "DISPATCHED",
            })
            continue
        entry, codespace_state = _execute_recovery_decision(
            active_journal,
            active_controller,
            record,
            decision,
            codespace_state=codespace_state,
            context=context,
            broker_repository=broker_repository,
            source_token=source_token,
        )
        entry["issue_number"] = issue["number"]
        decisions.append(entry)

    for ref in refs:
        name = ref.get("ref", "")
        digest = name.rsplit("/", 1)[-1]
        request_id = f"request:sha256:{digest}"
        if request_id in processed_requests:
            continue
        try:
            record = active_journal.get(request_id)
        except (KeyError, ValueError):
            continue
        codespace_state = codespace_state or active_controller.state()
        decision = decide_recovery(record, codespace_state=codespace_state)
        if decision.action is RecoveryAction.RESUME_PRE_MODEL:
            decisions.append({
                "request_id": request_id,
                "state": record.state.value,
                "action": "BLOCKED_REQUEST_ISSUE_UNAVAILABLE",
                "reason": "Pre-model recovery requires its authenticated request Issue.",
                "outcome": "BLOCKED",
            })
            continue
        entry, codespace_state = _execute_recovery_decision(
            active_journal,
            active_controller,
            record,
            decision,
            codespace_state=codespace_state,
            context=context,
            broker_repository=broker_repository,
            source_token=source_token,
        )
        decisions.append(entry)
    return decisions


def _execute_recovery_decision(
    journal: Any,
    controller: Any,
    record: Any,
    decision: Any,
    *,
    codespace_state: str,
    context: Mapping[str, str],
    broker_repository: str,
    source_token: str | None,
) -> tuple[dict[str, Any], str]:
    entry: dict[str, Any] = {
        "request_id": record.request_id,
        "attempt_id": record.attempt_id,
        "state": record.state.value,
        "action": decision.action.value,
        "reason": decision.reason,
        "outcome": "NO_ACTION",
    }
    if decision.action is RecoveryAction.RESUME_FROM_ARTIFACT:
        try:
            resumed = resume_from_durable_artifact(
                broker_repository,
                record,
                source_token=source_token,
                journal=journal,
            )
        except ArtifactResumeError as exc:
            entry["outcome"] = "BLOCKED_ARTIFACT_RECOVERY"
            entry["artifact_recovery_error"] = str(exc)
        else:
            entry["outcome"] = "VALIDATED_AND_REPORTED"
            entry["final_state"] = resumed["state"]
            entry["validation_id"] = resumed["validation_id"]
    elif decision.action is RecoveryAction.MARK_INDETERMINATE_AND_STOP:
        indeterminate = {
            "schema_version": 1,
            "evidence_type": "indeterminate-recovery",
            "request_id": record.request_id,
            "attempt_id": record.attempt_id,
            "journal_state": record.state.value,
            "codespace_state": codespace_state,
            "observed_at": utc_now(),
            "context": dict(context),
            "reason": decision.reason,
        }
        evidence_id = artifact_identity(canonical_bytes(indeterminate) + b"\n")
        record = journal.transition(
            record.request_id,
            AttemptState.INDETERMINATE,
            [evidence_id],
        )
        entry["indeterminate_evidence_id"] = evidence_id
        entry["indeterminate_evidence"] = indeterminate
        entry["state"] = record.state.value
        receipt, codespace_state = _reconciler_shutdown_observation(
            controller,
            record,
            codespace_state=codespace_state,
            context=context,
        )
        stopped = journal.record_stopped(record.request_id, receipt)
        entry["shutdown_evidence_id"] = artifact_identity(
            canonical_bytes(receipt) + b"\n"
        )
        entry["shutdown_observation"] = receipt
        entry["final_state"] = stopped.state.value
        entry["outcome"] = "INDETERMINATE_AND_STOPPED"
    elif decision.action in {RecoveryAction.STOP_CODESPACE, RecoveryAction.RECORD_STOPPED}:
        receipt, codespace_state = _reconciler_shutdown_observation(
            controller,
            record,
            codespace_state=codespace_state,
            context=context,
        )
        stopped = journal.record_stopped(record.request_id, receipt)
        entry["shutdown_evidence_id"] = artifact_identity(
            canonical_bytes(receipt) + b"\n"
        )
        entry["shutdown_observation"] = receipt
        entry["final_state"] = stopped.state.value
        entry["outcome"] = "STOPPED"
    elif decision.action is RecoveryAction.BLOCKED_EVIDENCE_LOCATION:
        entry["outcome"] = "BLOCKED"
    elif decision.action is RecoveryAction.INFRASTRUCTURE_INCIDENT:
        entry["outcome"] = "INFRASTRUCTURE_INCIDENT"
    return entry, codespace_state


def _reconciler_shutdown_observation(
    controller: Any,
    record: Any,
    *,
    codespace_state: str,
    context: Mapping[str, str],
) -> tuple[dict[str, Any], str]:
    try:
        if codespace_state != "Shutdown":
            controller.stop()
        observed = controller.state()
        receipt = build_shutdown_observation(
            codespace_name=controller.name,
            request_id=record.request_id,
            attempt_id=record.attempt_id,
            observed_state=observed,
            context=context,
        )
    except (CodespaceError, ValueError) as exc:
        raise ReconciliationError(
            "INFRASTRUCTURE_INCIDENT:SHUTDOWN_UNVERIFIED"
        ) from exc
    return receipt, observed


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())
