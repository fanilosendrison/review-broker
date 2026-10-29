"""Trusted predecessor evidence and ReviewRequest v2 operation invariants."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .identity import request_identity, review_intent_identity
from .publication import PublicationError
from .queue import AttemptRecord
from .verifiedresult import ResultUnavailable, read_verified_result


class PredecessorError(ValueError):
    """Authoritative history cannot support the requested v2 operation."""


@dataclass(frozen=True)
class PredecessorEvidence:
    request_id: str
    request: dict[str, Any]
    intent_id: str
    head_commit: str
    attempt_id: str
    source: str
    evidence_status: str | None = None


class PredecessorAuthority:
    """Resolve immutable admission records or receipt-authenticated results."""

    def __init__(
        self,
        journal: Any,
        request_ids: Callable[[], Iterable[str]],
        result_reader: Callable[[str], dict[str, Any]],
    ) -> None:
        self._journal = journal
        self._request_ids = request_ids
        self._result_reader = result_reader

    def get(self, request_id: str) -> PredecessorEvidence:
        try:
            record = self._journal.get(request_id)
        except KeyError as exc:
            raise PredecessorError("PREDECESSOR_CLAIM_NOT_FOUND") from exc
        if record.request_id != request_id:
            raise PredecessorError("PREDECESSOR_CLAIM_IDENTITY_MISMATCH")
        if record.admission is not None:
            return _from_admission(record)
        try:
            result = self._result_reader(request_id)
        except (PublicationError, ResultUnavailable, KeyError) as exc:
            raise PredecessorError("PREDECESSOR_EVIDENCE_UNAVAILABLE") from exc
        return _from_result(record, result)

    def history(self) -> tuple[PredecessorEvidence, ...]:
        evidence = []
        seen: set[str] = set()
        try:
            request_ids = tuple(self._request_ids())
        except Exception as exc:
            raise PredecessorError("PREDECESSOR_HISTORY_SCAN_INCOMPLETE") from exc
        for request_id in request_ids:
            if request_id in seen:
                continue
            seen.add(request_id)
            evidence.append(self.get(request_id))
        return tuple(evidence)


def github_predecessor_authority(
    broker_repository: str,
    journal: Any,
    get_json: Callable[[str], Any],
) -> PredecessorAuthority:
    def request_ids() -> Iterable[str]:
        for page in range(1, 101):
            values = get_json(
                f"repos/{broker_repository}/git/matching-refs/heads/review-claims/"
                f"?per_page=100&page={page}"
            )
            if not isinstance(values, list):
                raise PredecessorError("PREDECESSOR_HISTORY_RESPONSE_INVALID")
            for value in values:
                ref = value.get("ref") if isinstance(value, dict) else None
                digest = str(ref).rsplit("/", 1)[-1]
                if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    raise PredecessorError("PREDECESSOR_HISTORY_REF_INVALID")
                yield f"request:sha256:{digest}"
            if len(values) < 100:
                return
        raise PredecessorError("PREDECESSOR_HISTORY_SCAN_INCOMPLETE")

    return PredecessorAuthority(
        journal,
        request_ids,
        lambda request_id: read_verified_result(broker_repository, request_id, journal=journal),
    )


def verify_v2_operation(
    request: dict[str, Any],
    resolved: dict[str, Any],
    authority: PredecessorAuthority,
) -> None:
    if request.get("schema_version") != 2:
        return
    operation = request["review_operation"]
    kind = operation["kind"]
    current_id = resolved["request_id"]
    current_intent = resolved["review_intent_id"]
    current_head = resolved["subject"]["head_commit"]
    if kind == "initial":
        if any(
            item.request_id != current_id and item.intent_id == current_intent
            for item in authority.history()
        ):
            raise PredecessorError("INITIAL_REVIEW_INTENT_ALREADY_EXISTS")
        return
    previous_id = operation["previous_request_id"]
    if previous_id == current_id:
        raise PredecessorError("PREDECESSOR_EQUALS_CURRENT_REQUEST")
    previous = authority.get(previous_id)
    if previous.intent_id != current_intent:
        raise PredecessorError("PREDECESSOR_INTENT_MISMATCH")
    if kind == "changed_head":
        if previous.head_commit == current_head:
            raise PredecessorError("CHANGED_HEAD_REQUIRES_DIFFERENT_HEAD")
        return
    if previous.head_commit != current_head:
        raise PredecessorError("REPEAT_SAME_HEAD_REQUIRES_IDENTICAL_HEAD")
    nonce = operation["authorization_nonce"]
    for item in authority.history():
        prior_operation = item.request.get("review_operation", {})
        if (
            item.request_id != current_id
            and prior_operation.get("kind") == "repeat_same_head"
            and prior_operation.get("authorization_nonce") == nonce
        ):
            raise PredecessorError("REPEAT_AUTHORIZATION_NONCE_REUSED")


def _from_admission(record: AttemptRecord) -> PredecessorEvidence:
    resolved = record.admission
    if not isinstance(resolved, dict):
        raise PredecessorError("PREDECESSOR_ADMISSION_INVALID")
    return _evidence(record, resolved, "journal-admission")


def _from_result(record: AttemptRecord, result: dict[str, Any]) -> PredecessorEvidence:
    resolved = result.get("resolved_request")
    if (
        result.get("request_id") != record.request_id
        or result.get("attempt_id") != record.attempt_id
        or not isinstance(resolved, dict)
    ):
        raise PredecessorError("PREDECESSOR_RESULT_IDENTITY_MISMATCH")
    evidence = _evidence(record, resolved, "verified-publication")
    return PredecessorEvidence(
        **{**evidence.__dict__, "evidence_status": result.get("evidence_status")}
    )


def _evidence(
    record: AttemptRecord,
    resolved: dict[str, Any],
    source: str,
) -> PredecessorEvidence:
    request = resolved.get("request")
    subject = resolved.get("subject")
    if (
        not isinstance(request, dict)
        or not isinstance(subject, dict)
        or resolved.get("request_id") != record.request_id
        or request_identity(request) != record.request_id
        or not isinstance(subject.get("head_commit"), str)
    ):
        raise PredecessorError("PREDECESSOR_RESOLVED_REQUEST_INVALID")
    return PredecessorEvidence(
        request_id=record.request_id,
        request=request,
        intent_id=review_intent_identity(request),
        head_commit=subject["head_commit"],
        attempt_id=record.attempt_id,
        source=source,
    )
