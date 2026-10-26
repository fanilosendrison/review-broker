"""Lost-delivery discovery and evidence-bound durable reconciliation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import subprocess
from typing import Any, Mapping

from .admission import AdmissionError, AuthorizationPolicy, authorize_and_resolve
from .codespace import CodespaceController, CodespaceError
from .evidence import build_shutdown_observation
from .github_journal import GitHubRefJournal
from .identity import artifact_identity, canonical_bytes
from .queue import AttemptState
from .recovery import RecoveryAction, decide_recovery
from .request import RequestContractError, parse_issue_body


class ReconciliationError(RuntimeError):
    """Reconciliation cannot safely complete the advertised operation."""


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
) -> list[dict[str, Any]]:
    getter = get_json or _gh_json
    dispatcher = dispatch or _dispatch_review_workflow
    default_branch = environment.get("REVIEW_BROKER_DEFAULT_BRANCH", "dev")
    authorization = AuthorizationPolicy(
        requesters=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REQUESTERS", "")),
        repositories=_csv_set(environment.get("REVIEW_BROKER_AUTHORIZED_REPOSITORIES", "")),
    )
    issues = _paginated_list(
        getter,
        f"repos/{broker_repository}/issues?state=open",
        maximum_pages=max_issue_pages,
        incomplete_error="ISSUE_SCAN_INCOMPLETE",
    )
    refs = _paginated_list(
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
    codespace_state = active_controller.state()
    context = workflow_context(environment, source="reconciler")
    decisions: list[dict[str, Any]] = []
    processed_requests: set[str] = set()

    for issue in sorted(issues, key=lambda value: value.get("number", 0)):
        if "pull_request" in issue:
            continue
        try:
            request = parse_issue_body(issue.get("body") or "")
            resolved = authorize_and_resolve(
                issue["user"]["login"],
                request,
                authorization,
                getter,
            )
        except (AdmissionError, RequestContractError, KeyError, TypeError) as exc:
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
        record = active_journal.claim(request_id)
        decision = decide_recovery(record, codespace_state=codespace_state)
        if decision.action is RecoveryAction.RESUME_PRE_MODEL:
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
) -> tuple[dict[str, Any], str]:
    entry: dict[str, Any] = {
        "request_id": record.request_id,
        "attempt_id": record.attempt_id,
        "state": record.state.value,
        "action": decision.action.value,
        "reason": decision.reason,
        "outcome": "NO_ACTION",
    }
    if decision.action is RecoveryAction.MARK_INDETERMINATE_AND_STOP:
        indeterminate = {
            "schema_version": 1,
            "evidence_type": "indeterminate-recovery",
            "request_id": record.request_id,
            "attempt_id": record.attempt_id,
            "journal_state": record.state.value,
            "codespace_state": codespace_state,
            "observed_at": _utc_now(),
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


def _paginated_list(
    get_json: Any,
    endpoint: str,
    *,
    maximum_pages: int,
    incomplete_error: str,
) -> list[dict[str, Any]]:
    if maximum_pages < 1:
        raise ValueError("maximum_pages must be positive")
    values: list[dict[str, Any]] = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, maximum_pages + 1):
        batch = get_json(f"{endpoint}{separator}per_page=100&page={page}")
        if not isinstance(batch, list) or any(not isinstance(item, dict) for item in batch):
            raise ReconciliationError("PAGINATED_RESPONSE_INVALID")
        values.extend(batch)
        if len(batch) < 100:
            return values
    raise ReconciliationError(incomplete_error)


def _dispatch_review_workflow(
    broker_repository: str,
    default_branch: str,
    issue_number: int,
) -> None:
    _gh_request(
        "POST",
        f"repos/{broker_repository}/actions/workflows/review-request.yml/dispatches",
        {"ref": default_branch, "inputs": {"issue_number": str(issue_number)}},
    )




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
        raise ReconciliationError("GITHUB_API_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReconciliationError("GITHUB_RESPONSE_INVALID") from exc


def _gh_request(method: str, endpoint: str, payload: dict[str, Any]) -> None:
    result = subprocess.run(
        ["gh", "api", "--method", method, endpoint, "--input", "-"],
        input=canonical_bytes(payload).decode("utf-8"),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        shell=False,
    )
    if result.returncode != 0:
        raise ReconciliationError("GITHUB_API_FAILED")


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


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
