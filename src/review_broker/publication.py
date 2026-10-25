"""Bounded ReviewResult construction and trusted GitHub publication."""
from __future__ import annotations

from importlib import resources
import json
import subprocess
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .identity import canonical_bytes

RESULT_MARKER = "<!-- review-broker-result:v1 -->"
RESULT_END_MARKER = "<!-- /review-broker-result:v1 -->"


class PublicationError(RuntimeError):
    pass


def result_is_current(result: dict[str, Any], current_head: str | None) -> bool:
    try:
        reviewed = result["resolved_request"]["subject"]["head_commit"]
    except (KeyError, TypeError):
        return False
    return current_head is not None and reviewed == current_head


def build_review_result(
    resolved_request: dict[str, Any],
    packet_manifest: dict[str, Any],
    attempt: dict[str, Any],
    validation: dict[str, Any],
    *,
    current_head: str | None,
) -> dict[str, Any]:
    reviewed_head = resolved_request["subject"]["head_commit"]
    if current_head is None:
        applicability = "UNDETERMINED"
    elif current_head == reviewed_head:
        applicability = "CURRENT"
    else:
        applicability = "SUPERSEDED"
    result = {
        "schema_version": 1,
        "request_id": resolved_request["request_id"],
        "subject_id": resolved_request["subject_id"],
        "policy_id": resolved_request["policy_id"],
        "packet_id": packet_manifest["packet_id"],
        "attempt_id": attempt["attempt_id"],
        "execution_status": validation["execution_status"],
        "evidence_status": validation["evidence_status"],
        "review_verdict": validation["review_verdict"],
        "resolved_request": resolved_request,
        "reviewer": {
            "backend": "codex-cli",
            "model_requested": attempt["model_requested"],
            "reasoning_effort_requested": attempt["reasoning_effort_requested"],
            "effective_model_identity_verified": False,
            "effective_reasoning_effort_verified": False,
        },
        "sources_examined": validation.get("sources_examined", []),
        "findings": validation.get("findings", []),
        "remaining_uncertainties": validation.get("remaining_uncertainties", []),
        "validation": validation,
        "applicability": {"status": applicability, "checked_head_commit": current_head},
    }
    errors = list(Draft202012Validator(_result_schema()).iter_errors(result))
    if errors:
        raise PublicationError("REVIEW_RESULT_SCHEMA_INVALID")
    return result


def render_result_comment(result: dict[str, Any]) -> str:
    errors = list(Draft202012Validator(_result_schema()).iter_errors(result))
    if errors:
        raise PublicationError("REVIEW_RESULT_SCHEMA_INVALID")
    return (
        "## Review Broker bounded result\n\n"
        f"{RESULT_MARKER}\n{canonical_bytes(result).decode('utf-8')}\n{RESULT_END_MARKER}\n\n"
        "This result is evidence for the consumer's admission policy. It does not authorize merge, "
        "publication, architectural adoption, or scientific acceptance.\n"
    )


def extract_result_comment(body: str) -> dict[str, Any] | None:
    if body.count(RESULT_MARKER) != 1 or body.count(RESULT_END_MARKER) != 1:
        return None
    start = body.index(RESULT_MARKER) + len(RESULT_MARKER)
    end = body.index(RESULT_END_MARKER, start)
    try:
        value = json.loads(body[start:end].strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubPublisher:
    def __init__(self, repository: str, runner: Runner = subprocess.run):
        self.repository = repository
        self.runner = runner

    def publish(self, issue_number: int, result: dict[str, Any]) -> None:
        payload = canonical_bytes({"body": render_result_comment(result)}).decode("utf-8")
        process = self.runner(
            [
                "gh", "api", "--method", "POST",
                f"repos/{self.repository}/issues/{issue_number}/comments",
                "--input", "-",
            ],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
            shell=False,
        )
        if process.returncode != 0:
            raise PublicationError("RESULT_PUBLICATION_FAILED")


def _result_schema() -> dict[str, Any]:
    target = resources.files("review_broker.schemas").joinpath("review-result-v1.schema.json")
    return json.loads(target.read_text(encoding="utf-8"))
