"""Authorization and immutable GitHub pull-request resolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .identity import (
    mission_identity,
    policy_identity,
    request_identity,
    review_intent_identity,
    subject_identity,
)
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
BOUNDED_PRIVATE_V1_ADMISSION = "bounded-private-v1"


def select_operational_admission(
    request: dict[str, Any],
    environment: Mapping[str, str],
    get_json: JsonGetter,
    *,
    requester: str | None = None,
) -> str:
    """Select one explicit pre-claim operational admission path."""
    if (
        request.get("schema_version") == 2
        and environment.get("REVIEW_BROKER_V2_ENABLED") != "true"
    ):
        raise AdmissionError("V2_OPERATIONAL_ADMISSION_DISABLED")
    if environment.get("REVIEW_BROKER_SECURITY_QUALIFIED") == "true":
        if not environment.get("REVIEW_BROKER_SECURITY_EVIDENCE_ID", "").strip():
            raise AdmissionError("SECURITY_EVIDENCE_MISSING")
        return COMPREHENSIVE_ADMISSION
    if environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED") == "true":
        return _select_bounded_private(request, environment, get_json, requester)
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


def _select_bounded_private(
    request: dict[str, Any],
    environment: Mapping[str, str],
    get_json: JsonGetter,
    requester: str | None,
) -> str:
    subject = request.get("subject", {})
    executing_sha = environment.get("GITHUB_SHA", "")
    expected = {
        "requester": environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_REQUESTER"),
        "repository": environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_REPOSITORY"),
        "pull_request": environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_PULL_REQUEST"),
        "head": environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_EXPECTED_HEAD"),
    }
    if request.get("schema_version") != 2:
        raise AdmissionError("BOUNDED_PRIVATE_V2_REQUIRED")
    if requester != expected["requester"]:
        raise AdmissionError("BOUNDED_PRIVATE_REQUESTER_NOT_ADMITTED")
    if subject.get("repository") != expected["repository"]:
        raise AdmissionError("BOUNDED_PRIVATE_REPOSITORY_NOT_ADMITTED")
    if str(subject.get("pull_request")) != expected["pull_request"]:
        raise AdmissionError("BOUNDED_PRIVATE_PULL_REQUEST_NOT_ADMITTED")
    if not _sha(expected["head"]) or subject.get("expected_head_commit") != expected["head"]:
        raise AdmissionError("BOUNDED_PRIVATE_HEAD_NOT_ADMITTED")
    if (
        not _sha(executing_sha)
        or environment.get("REVIEW_BROKER_BOUNDED_PRIVATE_V1_ADMITTED_SHA") != executing_sha
    ):
        raise AdmissionError("BOUNDED_PRIVATE_SHA_NOT_ADMITTED")
    repository = subject["repository"]
    metadata = get_json(f"repos/{repository}")
    if (
        not isinstance(metadata, dict)
        or metadata.get("visibility") != "private"
        or metadata.get("private") is not True
        or metadata.get("full_name") != repository
    ):
        raise AdmissionError("PRIVATE_REPOSITORY_NOT_VERIFIED")
    installation = get_json("installation/repositories?per_page=100")
    repositories = installation.get("repositories") if isinstance(installation, dict) else None
    total_count = installation.get("total_count") if isinstance(installation, dict) else None
    if (
        total_count != 1
        or not isinstance(repositories, list)
        or len(repositories) != 1
        or repositories[0].get("full_name") != repository
    ):
        raise AdmissionError("PRIVATE_SOURCE_CREDENTIAL_SCOPE_NOT_VERIFIED")
    return BOUNDED_PRIVATE_V1_ADMISSION


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
    request_expected_head = subject.get("expected_head_commit")
    if request.get("schema_version") == 2:
        if expected_head is not None and expected_head != request_expected_head:
            raise AdmissionError("EXPECTED_HEAD_AUTHORITY_MISMATCH")
        expected_head = request_expected_head
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
    resolved = {
        "schema_version": 1,
        "request": request,
        "request_id": request_identity(request),
        "subject": resolved_subject,
        "subject_id": subject_identity(resolved_subject),
        "mission_id": mission_identity(request["mission"]),
        "policy_id": policy_identity(request["policy"]),
    }
    if request.get("schema_version") == 2:
        resolved["review_intent_id"] = review_intent_identity(request)
    return resolved


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
