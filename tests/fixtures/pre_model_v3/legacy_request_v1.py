"""ReviewRequest v1 loading, validation, and GitHub issue envelope."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from .identity import canonical_bytes, request_identity

REQUEST_MARKER = "<!-- review-broker-request:v1 -->"
REQUEST_END_MARKER = "<!-- /review-broker-request:v1 -->"


class RequestContractError(ValueError):
    """The request or its GitHub envelope violates ReviewRequest v1."""


def _schema() -> dict[str, Any]:
    target = resources.files("review_broker.schemas").joinpath("review-request-v1.schema.json")
    return json.loads(target.read_text(encoding="utf-8"))


def validate_request(request: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(_schema()).iter_errors(request), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "$"
        raise RequestContractError(f"request schema violation at {location}: {first.message}")


def create_request(
    repository: str,
    pull_request: int,
    profile: str,
    mission: dict[str, Any],
) -> dict[str, Any]:
    request = {
        "schema_version": 1,
        "subject": {
            "kind": "github_pr",
            "repository": repository,
            "pull_request": pull_request,
        },
        "mission": mission,
        "policy": {"profile": profile, "version": 1},
        "reviewer": {
            "backend": "codex-cli",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
        },
    }
    validate_request(request)
    return request


def build_issue_body(request: dict[str, Any]) -> str:
    validate_request(request)
    canonical = canonical_bytes(request).decode("utf-8")
    return (
        "## Review Broker request\n\n"
        f"Request-ID: `{request_identity(request)}`\n\n"
        f"{REQUEST_MARKER}\n{canonical}\n{REQUEST_END_MARKER}\n\n"
        "The JSON between the markers is the complete canonical ReviewRequest v1. "
        "Issue text outside the markers is not part of the request.\n"
    )


def parse_issue_body(body: str) -> dict[str, Any]:
    if body.count(REQUEST_MARKER) != 1 or body.count(REQUEST_END_MARKER) != 1:
        raise RequestContractError("issue body must contain exactly one request envelope")
    start = body.index(REQUEST_MARKER) + len(REQUEST_MARKER)
    end = body.index(REQUEST_END_MARKER, start)
    raw = body[start:end].strip()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RequestContractError("request envelope is not JSON") from exc
    if not isinstance(request, dict):
        raise RequestContractError("request envelope must be an object")
    validate_request(request)
    if raw.encode("utf-8") != canonical_bytes(request):
        raise RequestContractError("request envelope is not canonical RFC 8785 JSON")
    return request
