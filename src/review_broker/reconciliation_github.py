"""GitHub transport, pagination, dispatch, and workflow context for reconciliation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import subprocess
from typing import Any, Mapping

from .identity import canonical_bytes


class ReconciliationGitHubError(RuntimeError):
    """A complete trustworthy reconciliation observation is unavailable."""


def paginated_list(
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
            raise ReconciliationGitHubError("PAGINATED_RESPONSE_INVALID")
        values.extend(batch)
        if len(batch) < 100:
            return values
    raise ReconciliationGitHubError(incomplete_error)


def dispatch_review_workflow(
    broker_repository: str,
    default_branch: str,
    issue_number: int,
) -> None:
    github_request(
        "POST",
        f"repos/{broker_repository}/actions/workflows/review-request.yml/dispatches",
        {"ref": default_branch, "inputs": {"issue_number": str(issue_number)}},
    )


def github_json(endpoint: str, *, token: str | None = None) -> Any:
    child_environment = None
    if token is not None:
        child_environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"HOME", "PATH", "XDG_CONFIG_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        }
        child_environment["GH_TOKEN"] = token
    result = subprocess.run(
        ["gh", "api", endpoint],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        shell=False,
        env=child_environment,
    )
    if result.returncode != 0:
        raise ReconciliationGitHubError("GITHUB_API_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReconciliationGitHubError("GITHUB_RESPONSE_INVALID") from exc


def github_request(method: str, endpoint: str, payload: dict[str, Any]) -> None:
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
        raise ReconciliationGitHubError("GITHUB_API_FAILED")


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
