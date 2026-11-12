"""Read an attributable published result from its durable journal receipt."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from .github_journal import GitHubRefJournal
from .publication import (
    GitHubPublisher,
    PublicationError,
    attributable_result_comment,
    render_result_comment,
    validate_publication_intent,
    validate_publication_receipt,
)
from .queue import AttemptState


class ResultUnavailable(RuntimeError):
    """The request has no verified published result."""


def read_verified_result(
    repository: str,
    request_id: str,
    *,
    journal: GitHubRefJournal | None = None,
    publisher: GitHubPublisher | None = None,
) -> dict[str, Any]:
    active_journal = journal if journal is not None else GitHubRefJournal(repository)
    active_publisher = publisher if publisher is not None else GitHubPublisher(repository)
    try:
        record = active_journal.get(request_id)
    except KeyError as exc:
        raise ResultUnavailable("RESULT_UNAVAILABLE") from exc
    if record.request_id != request_id:
        raise PublicationError("PUBLICATION_REQUEST_MISMATCH")
    if record.state is AttemptState.INDETERMINATE or (
        record.state is AttemptState.STOPPED and record.publication_receipt is None
        and any(item.get("state") == AttemptState.INDETERMINATE.value
                for item in record.history)
    ):
        raise ResultUnavailable("RESULT_EXECUTION_INDETERMINATE")
    intent = record.publication_intent
    receipt = record.publication_receipt
    if intent is not None and receipt is None:
        raise ResultUnavailable("RESULT_PUBLICATION_INDETERMINATE")
    if record.state not in {AttemptState.REPORTED, AttemptState.STOPPED}:
        raise ResultUnavailable("RESULT_UNAVAILABLE")
    if intent is None or receipt is None:
        raise PublicationError("PUBLICATION_RECEIPT_MISSING")
    validate_publication_intent(intent)
    validate_publication_receipt(receipt, intent=intent)
    result = intent["result"]
    if (intent["request_id"] != request_id or
        intent["attempt_id"] != record.attempt_id or
        result.get("request_id") != request_id or
        result.get("attempt_id") != record.attempt_id):
        raise PublicationError("PUBLICATION_JOURNAL_IDENTITY_MISMATCH")

    expected_body = render_result_comment(result, publication_id=intent["publication_id"])
    issue_number = intent["issue_number"]
    matching_comments = [
        comment for comment in active_publisher.comments(issue_number)
        if attributable_result_comment(comment, expected_body, intent["publisher"])
    ]
    if len(matching_comments) != 1:
        raise PublicationError("PUBLICATION_COMMENT_MISSING_OR_AMBIGUOUS")
    listed = matching_comments[0]
    comment = active_publisher.comment(receipt["comment_id"])
    expected_issue_path = f"/repos/{repository}/issues/{issue_number}"
    for observed in (listed, comment):
        fields = {
            "id": "comment_id", "node_id": "comment_node_id",
            "html_url": "comment_url", "created_at": "comment_created_at",
        }
        if (not attributable_result_comment(observed, expected_body, intent["publisher"]) or
            any(observed.get(key) != receipt[field] for key, field in fields.items()) or
            urlsplit(str(observed.get("issue_url", ""))).path != expected_issue_path):
            raise PublicationError("PUBLICATION_COMMENT_IDENTITY_MISMATCH")
    return result
