"""Authenticated, read-only GitHub Issue-origin observations for experimental v3."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Callable, Mapping
from urllib.parse import quote
from urllib.request import Request

from .github_http_live_v3 import HttpExecutorV3, HttpResponseV3, urllib_executor
from .identity import artifact_identity, canonical_bytes

_API = "https://api.github.com"
_VERSION = "2022-11-28"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubIssueOriginV3Error(RuntimeError):
    """The Issue origin could not be authenticated exactly."""


@dataclass(frozen=True)
class GitHubIssueOriginObservationV3:
    repository: str
    repository_id: int
    issue_number: int
    issue_id: int
    requester_id: int
    requester_login: str
    body: str | None
    body_sha256: str | None
    observed_at: str
    api_source: str
    evidence_id: str


ClockV3 = Callable[[], datetime]


def _positive(value: object, marker: str) -> int:
    if type(value) is not int or value < 1:
        raise GitHubIssueOriginV3Error(marker)
    return value


def _json(response: HttpResponseV3) -> Mapping[str, object]:
    try:
        value = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubIssueOriginV3Error("GITHUB_ISSUE_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise GitHubIssueOriginV3Error("GITHUB_ISSUE_JSON_INVALID")
    return value


class GitHubIssueOriginReaderV3:
    """Read one Issue and bind it to a freshly authenticated repository identity."""

    def __init__(self, token: str, repository: str, repository_id: int, *,
                 executor: HttpExecutorV3 | None = None,
                 clock: ClockV3 | None = None):
        if not token or token.strip() != token or any(c in token for c in "\r\n"):
            raise ValueError("GITHUB_TOKEN_INVALID")
        if _REPOSITORY.fullmatch(repository) is None or ".." in repository:
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        _positive(repository_id, "GITHUB_REPOSITORY_ID_INVALID")
        self._token = token
        self.repository = repository
        self.repository_id = repository_id
        self._executor = executor or urllib_executor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owner, self._name = repository.split("/", 1)

    def _get(self, suffix: str) -> HttpResponseV3:
        root = f"/repos/{quote(self._owner, safe='')}/{quote(self._name, safe='')}"
        if suffix not in {""} and re.fullmatch(r"/issues/[1-9][0-9]*", suffix) is None:
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_ENDPOINT_INVALID")
        request = Request(
            _API + root + suffix,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": _VERSION,
            },
            method="GET",
        )
        try:
            response = self._executor(request)
        except Exception:
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_UNAVAILABLE") from None
        if not isinstance(response, HttpResponseV3):
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_RESPONSE_INVALID")
        return response

    def _verify_repository_identity(self) -> None:
        response = self._get("")
        if response.status != 200:
            raise GitHubIssueOriginV3Error("GITHUB_REPOSITORY_IDENTITY_UNAVAILABLE")
        repository = _json(response)
        if (repository.get("full_name") != self.repository
                or _positive(repository.get("id"), "GITHUB_REPOSITORY_ID_INVALID")
                != self.repository_id):
            raise GitHubIssueOriginV3Error("GITHUB_REPOSITORY_IDENTITY_MISMATCH")

    def observe(self, issue_number: int) -> GitHubIssueOriginObservationV3:
        issue_number = _positive(issue_number, "GITHUB_ISSUE_NUMBER_INVALID")
        self._verify_repository_identity()
        issue_response = self._get(f"/issues/{issue_number}")
        if issue_response.status != 200:
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_UNAVAILABLE")
        issue = _json(issue_response)
        if "pull_request" in issue:
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_PULL_REQUEST_FORBIDDEN")
        if _positive(issue.get("number"), "GITHUB_ISSUE_NUMBER_INVALID") != issue_number:
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_NUMBER_MISMATCH")
        issue_id = _positive(issue.get("id"), "GITHUB_ISSUE_ID_INVALID")
        user = issue.get("user")
        if not isinstance(user, dict):
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_REQUESTER_INVALID")
        requester_id = _positive(user.get("id"), "GITHUB_ISSUE_REQUESTER_ID_INVALID")
        requester_login = user.get("login")
        if (not isinstance(requester_login, str) or not requester_login
                or requester_login.strip() != requester_login):
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_REQUESTER_LOGIN_INVALID")
        body = issue.get("body")
        if body is not None and not isinstance(body, str):
            raise GitHubIssueOriginV3Error("GITHUB_ISSUE_BODY_INVALID")
        body_sha256 = None if body is None else hashlib.sha256(body.encode("utf-8")).hexdigest()
        self._verify_repository_identity()
        observed = self._clock()
        if observed.tzinfo is None:
            raise GitHubIssueOriginV3Error("GITHUB_OBSERVATION_TIME_INVALID")
        observed_at = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        api_source = f"{_API}/repos/{self.repository}/issues/{issue_number}"
        basis = {
            "schema_version": 1,
            "evidence_type": "github-issue-origin-observation",
            "repository": self.repository,
            "repository_id": self.repository_id,
            "issue_number": issue_number,
            "issue_id": issue_id,
            "requester_id": requester_id,
            "requester_login": requester_login,
            "body": body,
            "body_sha256": body_sha256,
            "observed_at": observed_at,
            "api_source": api_source,
        }
        return GitHubIssueOriginObservationV3(
            self.repository, self.repository_id, issue_number, issue_id,
            requester_id, requester_login, body, body_sha256, observed_at,
            api_source, artifact_identity(canonical_bytes(basis) + b"\n"),
        )
