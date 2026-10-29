"""Versioned ReviewRequest loading, validation, and GitHub Issue envelopes."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from .identity import canonical_bytes, request_identity, review_intent_identity

REQUEST_MARKERS = {
    1: ("<!-- review-broker-request:v1 -->", "<!-- /review-broker-request:v1 -->"),
    2: ("<!-- review-broker-request:v2 -->", "<!-- /review-broker-request:v2 -->"),
}
REQUEST_MARKER, REQUEST_END_MARKER = REQUEST_MARKERS[1]


class RequestContractError(ValueError):
    """A request or GitHub envelope violates its versioned contract."""


def _schema(version: int) -> dict[str, Any]:
    if version not in REQUEST_MARKERS:
        raise RequestContractError("unsupported request schema version")
    target = resources.files("review_broker.schemas").joinpath(
        f"review-request-v{version}.schema.json"
    )
    return json.loads(target.read_text(encoding="utf-8"))


def validate_request(request: dict[str, Any]) -> None:
    version = request.get("schema_version")
    if type(version) is not int or version not in REQUEST_MARKERS:
        raise RequestContractError("unsupported request schema version")
    errors = sorted(
        Draft202012Validator(_schema(version)).iter_errors(request),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "$"
        raise RequestContractError(
            f"request schema violation at {location}: {first.message}"
        )


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
    version = request["schema_version"]
    marker, end_marker = REQUEST_MARKERS[version]
    canonical = canonical_bytes(request).decode("utf-8")
    intent_line = (
        f"Review-Intent-ID: `{review_intent_identity(request)}`\n\n"
        if version == 2 else ""
    )
    return (
        "## Review Broker request\n\n"
        f"Request-ID: `{request_identity(request)}`\n\n"
        f"{intent_line}{marker}\n{canonical}\n{end_marker}\n\n"
        f"The JSON between the markers is the complete canonical ReviewRequest v{version}. "
        "Issue text outside the markers is not part of the request.\n"
    )


def parse_issue_body(body: str) -> dict[str, Any]:
    present = [
        version for version, markers in REQUEST_MARKERS.items()
        if markers[0] in body or markers[1] in body
    ]
    if len(present) != 1:
        raise RequestContractError("issue body must contain exactly one versioned request envelope")
    version = present[0]
    marker, end_marker = REQUEST_MARKERS[version]
    if body.count(marker) != 1 or body.count(end_marker) != 1:
        raise RequestContractError("issue body must contain exactly one request envelope")
    start = body.index(marker) + len(marker)
    end = body.index(end_marker, start)
    raw = body[start:end].strip()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RequestContractError("request envelope is not JSON") from exc
    if not isinstance(request, dict):
        raise RequestContractError("request envelope must be an object")
    if request.get("schema_version") != version:
        raise RequestContractError("request marker and schema version disagree")
    validate_request(request)
    if raw.encode("utf-8") != canonical_bytes(request):
        raise RequestContractError("request envelope is not canonical RFC 8785 JSON")
    return request
