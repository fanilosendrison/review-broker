"""Isolated, non-operational ReviewRequest v3 candidate wire handling."""
from __future__ import annotations

import hashlib
from importlib import resources
import json
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .identity import canonical_bytes
from .physical import PhysicalLineError, decode_physical_lines

V3_MARKER = "<!-- review-broker-request:v3 -->"
V3_END_MARKER = "<!-- /review-broker-request:v3 -->"
_OTHER_MARKERS = (
    "<!-- review-broker-request:v1 -->", "<!-- /review-broker-request:v1 -->",
    "<!-- review-broker-request:v2 -->", "<!-- /review-broker-request:v2 -->",
)
_REQUEST_ID_LINE = re.compile(
    r"^Request-ID:\s*(?:`(request:sha256:[0-9a-f]{64})`|(request:sha256:[0-9a-f]{64}))$\Z"
)
_REQUEST_ID_PREFIX = re.compile(r"^Request-ID:")
_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_MAX_SOURCE_BYTES = 2_000_000
_MAX_RENDERED_BYTES = 8_000_000
_PACKET_FIXED_RESERVE = 1_000_000
_MAX_JSON_INTEGER = 9_007_199_254_740_991
_MAX_REFERENCES = 997  # reserves two eventual citation identifiers for PR subject material


class RequestV3CandidateError(ValueError):
    """The experimental candidate request violates its closed wire contract."""


def inline_rendered_bound_v3(text: str) -> int:
    """Conservative numbered-line bytes for one validated inline source."""
    try:
        encoded = text.encode("utf-8")
        _, physical_lines, _ = decode_physical_lines(encoded)
    except (UnicodeEncodeError, PhysicalLineError) as exc:
        raise RequestV3CandidateError("V3_INLINE_UTF8_INVALID") from exc
    return sum(len(line.encode("utf-8")) + 9 for line in physical_lines)


def _schema() -> dict[str, Any]:
    target = resources.files("review_broker.schemas").joinpath(
        "review-request-v3.candidate.schema.json"
    )
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RequestV3CandidateError("V3_CANDIDATE_SCHEMA_INVALID")
    return value


def validate_request_v3(request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached closed candidate request object."""
    if not isinstance(request, dict):
        raise RequestV3CandidateError("V3_REQUEST_OBJECT_REQUIRED")
    errors = sorted(
        Draft202012Validator(_schema()).iter_errors(request),
        key=lambda error: [str(part) for part in error.path],
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "$"
        raise RequestV3CandidateError(f"V3_REQUEST_SCHEMA_INVALID:{location}")
    exact_integers = [
        request.get("schema_version"), request.get("subject", {}).get("repository_id"),
        request.get("subject", {}).get("pull_request"),
    ]
    for reference in request.get("references", []):
        source = reference.get("source", {}) if isinstance(reference, dict) else {}
        if source.get("kind") == "github_issue_body":
            exact_integers.append(source.get("issue"))
        if source.get("kind") == "github_issue_comment":
            exact_integers.append(source.get("comment_id"))
    if any(type(value) is not int or value < 1 or value > _MAX_JSON_INTEGER
           for value in exact_integers):
        raise RequestV3CandidateError("V3_JSON_INTEGER_INVALID")
    references = request["references"]
    if len(references) > _MAX_REFERENCES:
        raise RequestV3CandidateError("V3_REFERENCE_COUNT_EXCEEDED")
    identifiers = [reference["id"] for reference in references]
    if len(identifiers) != len(set(identifiers)):
        raise RequestV3CandidateError("V3_REFERENCE_ID_DUPLICATE")
    rendered_inline_bound = 0
    subject_repository = request["subject"]["repository"]
    for reference in references:
        source = reference["source"]
        kind = source["kind"]
        if kind == "inline":
            try:
                encoded = source["text"].encode("utf-8")
            except UnicodeEncodeError as exc:
                raise RequestV3CandidateError("V3_INLINE_UTF8_INVALID") from exc
            source_bytes = len(encoded)
            if source_bytes > _MAX_SOURCE_BYTES:
                raise RequestV3CandidateError("V3_INLINE_SOURCE_BYTES_EXCEEDED")
            rendered_inline_bound += inline_rendered_bound_v3(source["text"])
        else:
            if source["repository"] != subject_repository:
                raise RequestV3CandidateError("V3_REFERENCE_REPOSITORY_MISMATCH")
            if kind == "git_file" and (
                _PATH.fullmatch(source["path"]) is None
                or any(part in {".", ".."} for part in source["path"].split("/"))
            ):
                raise RequestV3CandidateError("V3_GIT_FILE_PATH_INVALID")
    try:
        request_bytes = canonical_bytes(request)
    except (UnicodeEncodeError, ValueError, TypeError) as exc:
        raise RequestV3CandidateError("V3_CANONICALIZATION_INVALID") from exc
    if (rendered_inline_bound + len(request_bytes) + _PACKET_FIXED_RESERVE
            > _MAX_RENDERED_BYTES):
        raise RequestV3CandidateError("V3_EVENTUAL_PACKET_BOUND_EXCEEDED")
    return json.loads(request_bytes)


def request_identity_v3(request: Mapping[str, Any]) -> str:
    validated = validate_request_v3(request)
    return "request:sha256:" + hashlib.sha256(canonical_bytes(validated)).hexdigest()


def build_issue_envelope_v3(request: Mapping[str, Any]) -> str:
    validated = validate_request_v3(request)
    return f"{V3_MARKER}\n{canonical_bytes(validated).decode('utf-8')}\n{V3_END_MARKER}"


def parse_issue_envelope_v3(body: str) -> dict[str, Any]:
    if not isinstance(body, str):
        raise RequestV3CandidateError("V3_ISSUE_BODY_STRING_REQUIRED")
    try:
        body_bytes = body.encode("utf-8")
        _, physical_lines, mapping = decode_physical_lines(body_bytes)
    except (UnicodeEncodeError, PhysicalLineError) as exc:
        raise RequestV3CandidateError("V3_ISSUE_BODY_UTF8_INVALID") from exc
    lines = list(physical_lines)
    if any(line in _OTHER_MARKERS for line in lines):
        raise RequestV3CandidateError("V3_MIXED_VERSION_ENVELOPE_FORBIDDEN")
    starts = [index for index, line in enumerate(lines) if line == V3_MARKER]
    ends = [index for index, line in enumerate(lines) if line == V3_END_MARKER]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0] + 1:
        raise RequestV3CandidateError("V3_EXACTLY_ONE_ENVELOPE_REQUIRED")
    start_byte = mapping[starts[0]]["line_end"]
    end_byte = mapping[ends[0]]["byte_start"]
    payload = body_bytes[start_byte:end_byte]
    if payload.endswith(b"\r\n"):
        payload = payload[:-2]
    elif payload.endswith((b"\r", b"\n")):
        payload = payload[:-1]
    try:
        raw = payload.decode("utf-8")
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RequestV3CandidateError("V3_ENVELOPE_JSON_INVALID") from exc
    validated = validate_request_v3(value)
    if raw.encode("utf-8") != canonical_bytes(validated):
        raise RequestV3CandidateError("V3_ENVELOPE_NONCANONICAL")
    outside = lines[:starts[0]] + lines[ends[0] + 1:]
    marker_tokens = (V3_MARKER, V3_END_MARKER) + _OTHER_MARKERS
    if any(any(token in line for token in marker_tokens) for line in outside):
        raise RequestV3CandidateError("V3_OUTSIDE_MARKER_TOKEN_FORBIDDEN")
    if any("Review-Intent-ID:" in line for line in outside):
        raise RequestV3CandidateError("V3_EXTERNAL_INTENT_ID_FORBIDDEN")
    if any("Request-ID:" in line and _REQUEST_ID_PREFIX.match(line) is None
           for line in outside):
        raise RequestV3CandidateError("V3_DECLARED_REQUEST_ID_INVALID")
    declared_lines = [line for line in outside if _REQUEST_ID_PREFIX.match(line)]
    if len(declared_lines) > 1:
        raise RequestV3CandidateError("V3_DECLARED_REQUEST_ID_AMBIGUOUS")
    if declared_lines and _REQUEST_ID_LINE.fullmatch(declared_lines[0]) is None:
        raise RequestV3CandidateError("V3_DECLARED_REQUEST_ID_INVALID")
    match = None if not declared_lines else _REQUEST_ID_LINE.fullmatch(declared_lines[0])
    declarations = [] if match is None else [match.group(1) or match.group(2)]
    if declarations and declarations[0] != request_identity_v3(validated):
        raise RequestV3CandidateError("V3_DECLARED_REQUEST_ID_MISMATCH")
    return validated
