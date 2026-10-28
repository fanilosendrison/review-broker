"""Authorization and immutable GitHub pull-request resolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .identity import mission_identity, policy_identity, request_identity, subject_identity
from .request import validate_request


class AdmissionError(ValueError):
    """A request cannot cross the admission boundary."""


@dataclass(frozen=True)
class AuthorizationPolicy:
    requesters: frozenset[str]
    repositories: frozenset[str]


JsonGetter = Callable[[str], dict[str, Any]]
COMPREHENSIVE_ADMISSION = "comprehensive-security"
BOUNDED_V1_ADMISSION = "low-sensitivity-v1"


def select_operational_admission(
    request: dict[str, Any],
    environment: Mapping[str, str],
    get_json: JsonGetter,
) -> str:
    """Select one explicit pre-claim operational admission path."""
    if environment.get("REVIEW_BROKER_SECURITY_QUALIFIED") == "true":
        if not environment.get("REVIEW_BROKER_SECURITY_EVIDENCE_ID", "").strip():
            raise AdmissionError("SECURITY_EVIDENCE_MISSING")
        return COMPREHENSIVE_ADMISSION
    if environment.get("REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED") != "true":
        raise AdmissionError("OPERATIONAL_ADMISSION_DISABLED")
    executing_sha = environment.get("GITHUB_SHA", "")
    if (
        not _sha(executing_sha)
        or environment.get("REVIEW_BROKER_LOW_SENSITIVITY_V1_ADMITTED_SHA")
        != executing_sha
    ):
        raise AdmissionError("LOW_SENSITIVITY_SHA_NOT_ADMITTED")
    repositories = _csv_set(
        environment.get("REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES", "")
    )
    repository = request["subject"]["repository"]
    if not repositories or repository not in repositories:
        raise AdmissionError("LOW_SENSITIVITY_REPOSITORY_NOT_ADMITTED")
    metadata = get_json(f"repos/{repository}")
    if (
        not isinstance(metadata, dict)
        or metadata.get("visibility") != "public"
        or metadata.get("private") is not False
        or metadata.get("full_name") != repository
    ):
        raise AdmissionError("PUBLIC_REPOSITORY_NOT_VERIFIED")
    return BOUNDED_V1_ADMISSION


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


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)
