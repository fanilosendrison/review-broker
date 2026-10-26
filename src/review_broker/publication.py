"""Bounded ReviewResult construction and trusted GitHub publication."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib import resources
import json
import re
import subprocess
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator

from .identity import canonical_bytes

RESULT_MARKER = "<!-- review-broker-result:v1 -->"
RESULT_END_MARKER = "<!-- /review-broker-result:v1 -->"
PUBLICATION_MARKER = "<!-- review-broker-publication:v1 "
PUBLICATION_ID = re.compile(r"publication:sha256:[0-9a-f]{64}\Z")


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


def result_identity(result: Mapping[str, Any]) -> str:
    return "result:sha256:" + hashlib.sha256(canonical_bytes(dict(result))).hexdigest()


def render_result_comment(
    result: dict[str, Any],
    *,
    publication_id: str | None = None,
) -> str:
    errors = list(Draft202012Validator(_result_schema()).iter_errors(result))
    if errors:
        raise PublicationError("REVIEW_RESULT_SCHEMA_INVALID")
    publication_line = ""
    if publication_id is not None:
        if not PUBLICATION_ID.fullmatch(publication_id):
            raise PublicationError("PUBLICATION_ID_INVALID")
        publication_line = f"{PUBLICATION_MARKER}{publication_id} -->\n"
    return (
        "## Review Broker bounded result\n\n"
        f"{publication_line}{RESULT_MARKER}\n"
        f"{canonical_bytes(result).decode('utf-8')}\n{RESULT_END_MARKER}\n\n"
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


def build_publication_intent(
    result: Mapping[str, Any],
    *,
    issue_number: int,
    publisher: Mapping[str, Any],
    nonce: str,
    reserved_at: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", nonce):
        raise PublicationError("PUBLICATION_NONCE_INVALID")
    login = publisher.get("login")
    actor_id = publisher.get("id")
    if not isinstance(login, str) or not login or not isinstance(actor_id, int):
        raise PublicationError("PUBLICATION_ACTOR_INVALID")
    basis = {
        "schema_version": 1,
        "issue_number": issue_number,
        "request_id": result.get("request_id"),
        "attempt_id": result.get("attempt_id"),
        "result_id": result_identity(result),
        "publisher": {"login": login, "id": actor_id},
        "nonce": nonce,
        "reserved_at": reserved_at,
    }
    publication_id = "publication:sha256:" + hashlib.sha256(
        canonical_bytes(basis)
    ).hexdigest()
    body = render_result_comment(dict(result), publication_id=publication_id)
    intent = {
        **basis,
        "evidence_type": "github-result-publication-intent",
        "result": dict(result),
        "publication_id": publication_id,
        "comment_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
    validate_publication_intent(intent, result=result)
    return intent


def validate_publication_intent(
    intent: Mapping[str, Any],
    *,
    result: Mapping[str, Any] | None = None,
) -> str:
    required = {
        "schema_version", "evidence_type", "issue_number", "request_id",
        "attempt_id", "result_id", "result", "publisher", "nonce",
        "reserved_at", "publication_id", "comment_body_sha256",
    }
    if set(intent) != required or intent.get("schema_version") != 1:
        raise PublicationError("PUBLICATION_INTENT_INVALID")
    if intent.get("evidence_type") != "github-result-publication-intent":
        raise PublicationError("PUBLICATION_INTENT_INVALID")
    publisher = intent.get("publisher")
    if (
        not isinstance(intent.get("issue_number"), int)
        or intent["issue_number"] < 1
        or not isinstance(publisher, dict)
        or not isinstance(publisher.get("login"), str)
        or not isinstance(publisher.get("id"), int)
        or not re.fullmatch(r"[0-9a-f]{64}", str(intent.get("nonce")))
        or not PUBLICATION_ID.fullmatch(str(intent.get("publication_id")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(intent.get("comment_body_sha256")))
    ):
        raise PublicationError("PUBLICATION_INTENT_INVALID")
    basis = {
        key: intent[key]
        for key in (
            "schema_version", "issue_number", "request_id", "attempt_id",
            "result_id", "publisher", "nonce", "reserved_at",
        )
    }
    expected_id = "publication:sha256:" + hashlib.sha256(
        canonical_bytes(basis)
    ).hexdigest()
    if expected_id != intent["publication_id"]:
        raise PublicationError("PUBLICATION_INTENT_IDENTITY_MISMATCH")
    stored_result = intent.get("result")
    if not isinstance(stored_result, dict) or result_identity(stored_result) != intent["result_id"]:
        raise PublicationError("PUBLICATION_RESULT_IDENTITY_MISMATCH")
    if result is not None:
        if (
            dict(result) != stored_result
            or result.get("request_id") != intent["request_id"]
            or result.get("attempt_id") != intent["attempt_id"]
        ):
            raise PublicationError("PUBLICATION_RESULT_IDENTITY_MISMATCH")
        body = render_result_comment(dict(result), publication_id=expected_id)
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != intent["comment_body_sha256"]:
            raise PublicationError("PUBLICATION_BODY_IDENTITY_MISMATCH")
    _timestamp(intent.get("reserved_at"), "PUBLICATION_RESERVED_AT_INVALID")
    return "artifact:sha256:" + hashlib.sha256(
        canonical_bytes(dict(intent)) + b"\n"
    ).hexdigest()


def validate_publication_receipt(
    receipt: Mapping[str, Any],
    *,
    intent: Mapping[str, Any],
) -> str:
    validate_publication_intent(intent)
    if (
        receipt.get("schema_version") != 1
        or receipt.get("evidence_type") != "github-result-publication-observation"
        or receipt.get("publication_id") != intent["publication_id"]
        or receipt.get("result_id") != intent["result_id"]
        or receipt.get("issue_number") != intent["issue_number"]
        or receipt.get("publisher") != intent["publisher"]
        or not isinstance(receipt.get("comment_id"), int)
        or not isinstance(receipt.get("comment_node_id"), str)
        or not isinstance(receipt.get("comment_url"), str)
    ):
        raise PublicationError("PUBLICATION_RECEIPT_INVALID")
    for field in ("comment_created_at", "observed_at"):
        _timestamp(receipt.get(field), "PUBLICATION_RECEIPT_INVALID")
    return "artifact:sha256:" + hashlib.sha256(
        canonical_bytes(dict(receipt)) + b"\n"
    ).hexdigest()


Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubPublisher:
    def __init__(self, repository: str, runner: Runner = subprocess.run):
        self.repository = repository
        self.runner = runner

    def identity(self) -> dict[str, Any]:
        value = self._json("GET", "user")
        if not isinstance(value.get("login"), str) or not isinstance(value.get("id"), int):
            raise PublicationError("PUBLICATION_ACTOR_INVALID")
        return {"login": value["login"], "id": value["id"]}

    def observe(
        self,
        intent: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        validate_publication_intent(intent, result=result)
        body = render_result_comment(
            dict(result), publication_id=intent["publication_id"]
        )
        matches: list[dict[str, Any]] = []
        for page in range(1, 101):
            values = self._json(
                "GET",
                f"repos/{self.repository}/issues/{intent['issue_number']}"
                f"/comments?per_page=100&page={page}",
            )
            if not isinstance(values, list):
                raise PublicationError("PUBLICATION_COMMENT_LIST_INVALID")
            for comment in values:
                if not isinstance(comment, dict) or comment.get("body") != body:
                    continue
                actor = comment.get("user")
                if not isinstance(actor, dict) or {
                    "login": actor.get("login"), "id": actor.get("id")
                } != intent["publisher"]:
                    continue
                matches.append(comment)
            if len(values) < 100:
                break
        else:
            raise PublicationError("PUBLICATION_COMMENT_SCAN_INCOMPLETE")
        if len(matches) > 1:
            raise PublicationError("DUPLICATE_PUBLICATION_INCIDENT")
        if not matches:
            return None
        comment = matches[0]
        receipt = {
            "schema_version": 1,
            "evidence_type": "github-result-publication-observation",
            "publication_id": intent["publication_id"],
            "result_id": intent["result_id"],
            "issue_number": intent["issue_number"],
            "publisher": intent["publisher"],
            "comment_id": comment.get("id"),
            "comment_node_id": comment.get("node_id"),
            "comment_url": comment.get("html_url"),
            "comment_created_at": comment.get("created_at"),
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        validate_publication_receipt(receipt, intent=intent)
        return receipt

    def publish_reserved(
        self,
        intent: Mapping[str, Any],
        result: Mapping[str, Any],
        *,
        reservation_created: bool,
    ) -> dict[str, Any]:
        observed = self.observe(intent, result)
        if observed is not None:
            return observed
        if not reservation_created:
            raise PublicationError("PUBLICATION_OUTCOME_INDETERMINATE")
        payload = {
            "body": render_result_comment(
                dict(result), publication_id=intent["publication_id"]
            )
        }
        self._json(
            "POST",
            f"repos/{self.repository}/issues/{intent['issue_number']}/comments",
            payload,
            check=False,
        )
        observed = self.observe(intent, result)
        if observed is None:
            raise PublicationError("PUBLICATION_OUTCOME_INDETERMINATE")
        return observed

    def _json(
        self,
        method: str,
        endpoint: str,
        payload: Mapping[str, Any] | None = None,
        *,
        check: bool = True,
    ) -> Any:
        command = ["gh", "api", "--method", method, endpoint]
        kwargs: dict[str, Any] = {
            "text": True,
            "capture_output": True,
            "check": False,
            "timeout": 60,
            "shell": False,
        }
        if payload is not None:
            command.extend(["--input", "-"])
            kwargs["input"] = canonical_bytes(dict(payload)).decode("utf-8")
        process = self.runner(command, **kwargs)
        if check and process.returncode != 0:
            raise PublicationError("PUBLICATION_API_FAILED")
        if process.returncode != 0:
            return None
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise PublicationError("PUBLICATION_API_RESPONSE_INVALID") from exc


def _timestamp(value: Any, error: str) -> datetime:
    if not isinstance(value, str):
        raise PublicationError(error)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicationError(error) from exc
    if parsed.tzinfo is None:
        raise PublicationError(error)
    return parsed


def _result_schema() -> dict[str, Any]:
    target = resources.files("review_broker.schemas").joinpath("review-result-v1.schema.json")
    return json.loads(target.read_text(encoding="utf-8"))
