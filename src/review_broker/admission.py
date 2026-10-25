"""Authorization and immutable GitHub pull-request resolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .identity import mission_identity, policy_identity, request_identity, subject_identity
from .request import validate_request


class AdmissionError(ValueError):
    """A request cannot cross the admission boundary."""


@dataclass(frozen=True)
class AuthorizationPolicy:
    requesters: frozenset[str]
    repositories: frozenset[str]


JsonGetter = Callable[[str], dict[str, Any]]


def authorize(actor: str, request: dict[str, Any], policy: AuthorizationPolicy) -> None:
    if actor not in policy.requesters:
        raise AdmissionError("REQUESTER_UNAUTHORIZED")
    repository = request["subject"]["repository"]
    if repository not in policy.repositories:
        raise AdmissionError("REPOSITORY_UNAUTHORIZED")


def resolve_request(
    request: dict[str, Any],
    get_json: JsonGetter,
    *,
    expected_head: str | None = None,
) -> dict[str, Any]:
    validate_request(request)
    subject = request["subject"]
    repository = subject["repository"]
    number = subject["pull_request"]
    pr = get_json(f"repos/{repository}/pulls/{number}")
    head = pr.get("head", {}).get("sha")
    base = pr.get("base", {}).get("sha")
    if not _sha(head) or not _sha(base):
        raise AdmissionError("GITHUB_PR_IDENTITY_INCOMPLETE")
    if expected_head is not None and head != expected_head:
        raise AdmissionError(f"PR_HEAD_MISMATCH:expected={expected_head}:actual={head}")
    compare = get_json(f"repos/{repository}/compare/{base}...{head}")
    merge_base = compare.get("merge_base_commit", {}).get("sha")
    if not _sha(merge_base):
        raise AdmissionError("MERGE_BASE_UNDETERMINED")
    resolved_subject = {
        "kind": "github_pr",
        "repository": repository,
        "repository_id": pr.get("base", {}).get("repo", {}).get("id"),
        "pull_request": number,
        "head_commit": head,
        "base_commit": base,
        "merge_base": merge_base,
    }
    return {
        "schema_version": 1,
        "request": request,
        "request_id": request_identity(request),
        "subject": resolved_subject,
        "subject_id": subject_identity(resolved_subject),
        "mission_id": mission_identity(request["mission"]),
        "policy_id": policy_identity(request["policy"]),
    }


def authorize_and_resolve(
    actor: str,
    request: dict[str, Any],
    policy: AuthorizationPolicy,
    get_json: JsonGetter,
    *,
    expected_head: str | None = None,
) -> dict[str, Any]:
    authorize(actor, request, policy)
    return resolve_request(request, get_json, expected_head=expected_head)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)
