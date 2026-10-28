"""Git-ref-backed durable attempt journal."""
from __future__ import annotations

import base64
from dataclasses import replace
import json
import subprocess
from typing import Any, Callable, Mapping

from .artifact_locator import (
    validate_evidence_artifact_locator,
    validate_evidence_artifact_plan,
)
from .identity import attempt_identity, canonical_bytes
from .publication import validate_publication_intent, validate_publication_receipt
from .queue import (
    AttemptRecord,
    AttemptState,
    StateTransitionError,
    record_publication_transition,
    record_shutdown_transition,
    record_terminal_capture_transition,
    transition_record,
)

Runner = Callable[..., subprocess.CompletedProcess[str]]
_BASE64_ALPHABET = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
_BASE64_WHITESPACE = frozenset(b" \t\r\n")


def _decode_github_contents_base64(encoded: str) -> bytes:
    """Strictly decode standard Base64 with GitHub's ASCII line formatting."""
    if not isinstance(encoded, str):
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID")
    try:
        formatted = encoded.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID") from exc
    compact = bytes(value for value in formatted if value not in _BASE64_WHITESPACE)
    if any(value not in _BASE64_ALPHABET for value in compact):
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID")
    raw = base64.b64decode(compact, validate=True)
    if base64.b64encode(raw) != compact:
        raise ValueError("GITHUB_CONTENT_BASE64_NONCANONICAL")
    return raw


class GitHubRefJournal:
    """Git-ref-backed journal using create-ref and fast-forward as atomic operations."""

    STATE_PATH = ".review-broker/attempt.json"

    def __init__(self, repository: str, base_branch: str = "dev", runner: Runner = subprocess.run):
        self.repository = repository
        self.base_branch = base_branch
        self.runner = runner

    def claim(self, request_id: str) -> AttemptRecord:
        existing = self._read(request_id)
        if existing is not None:
            return existing[1]
        record = AttemptRecord(
            request_id=request_id,
            attempt_id=attempt_identity(request_id, 1),
            state=AttemptState.REQUESTED,
            history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
        )
        base_sha = self._ref_sha(f"heads/{self.base_branch}")
        commit_sha = self._state_commit(base_sha, record)
        result = self._api(
            "POST",
            f"repos/{self.repository}/git/refs",
            {"ref": self._claim_ref(request_id), "sha": commit_sha},
            check=False,
        )
        if result.returncode == 0:
            return record
        winner = self._read(request_id)
        if winner is None:
            raise StateTransitionError("ATOMIC_CLAIM_FAILED")
        return winner[1]

    def get(self, request_id: str) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        return found[1]

    def transition(
        self,
        request_id: str,
        target: AttemptState,
        evidence_ids: list[str] | tuple[str, ...],
    ) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        updated = transition_record(current, target, evidence_ids)
        self._compare_and_swap(request_id, current_sha, updated)
        return updated

    def record_terminal_capture(
        self,
        request_id: str,
        receipt: Mapping[str, Any],
    ) -> AttemptRecord:
        return self._record_verified_transition(
            request_id,
            lambda current: record_terminal_capture_transition(current, receipt),
        )

    def record_stopped(
        self,
        request_id: str,
        receipt: Mapping[str, Any],
    ) -> AttemptRecord:
        return self._record_verified_transition(
            request_id,
            lambda current: record_shutdown_transition(current, receipt),
        )

    def _record_verified_transition(
        self,
        request_id: str,
        transition: Callable[[AttemptRecord], AttemptRecord],
    ) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        updated = transition(current)
        self._compare_and_swap(request_id, current_sha, updated)
        return updated

    def record_evidence_locator_plan(
        self,
        request_id: str,
        plan: Mapping[str, Any],
    ) -> AttemptRecord:
        evidence_id = validate_evidence_artifact_plan(
            plan,
            request_id=request_id,
        )
        if plan.get("broker_repository") != self.repository:
            raise StateTransitionError("ARTIFACT_PLAN_REPOSITORY_MISMATCH")
        return self._record_bound_metadata(
            request_id,
            field="evidence_locator_plan",
            value=dict(plan),
            evidence_id=evidence_id,
            event="EVIDENCE_LOCATOR_PLANNED",
            allowed_states={AttemptState.TERMINAL_CAPTURED},
        )

    def record_evidence_locator(
        self,
        request_id: str,
        locator: Mapping[str, Any],
    ) -> AttemptRecord:
        evidence_id = validate_evidence_artifact_locator(
            locator,
            request_id=request_id,
        )
        if locator.get("broker_repository") != self.repository:
            raise StateTransitionError("ARTIFACT_LOCATOR_REPOSITORY_MISMATCH")
        return self._record_bound_metadata(
            request_id,
            field="evidence_locator",
            value=dict(locator),
            evidence_id=evidence_id,
            event="EVIDENCE_LOCATOR_RECORDED",
            allowed_states={AttemptState.TERMINAL_CAPTURED, AttemptState.VALIDATED},
        )

    def _record_bound_metadata(
        self,
        request_id: str,
        *,
        field: str,
        value: dict[str, Any],
        evidence_id: str,
        event: str,
        allowed_states: set[AttemptState],
    ) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        if current.attempt_id != value.get("attempt_id"):
            raise StateTransitionError("BOUND_METADATA_ATTEMPT_MISMATCH")
        existing = getattr(current, field)
        if existing is not None:
            if existing != value:
                raise StateTransitionError("BOUND_METADATA_CONFLICT")
            return current
        if current.state not in allowed_states:
            raise StateTransitionError("BOUND_METADATA_STATE_INVALID")
        history_entry = {"event": event, "evidence_ids": [evidence_id]}
        updated = replace(
            current,
            **{field: value},
            evidence_ids=current.evidence_ids + (evidence_id,),
            history=current.history + (history_entry,),
        )
        self._compare_and_swap(request_id, current_sha, updated)
        return updated

    def reserve_publication(
        self,
        request_id: str,
        intent: Mapping[str, Any],
    ) -> tuple[AttemptRecord, bool]:
        evidence_id = validate_publication_intent(intent)
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        if current.attempt_id != intent.get("attempt_id"):
            raise StateTransitionError("PUBLICATION_ATTEMPT_MISMATCH")
        if current.publication_intent is not None:
            return current, False
        if current.state is not AttemptState.VALIDATED:
            raise StateTransitionError("PUBLICATION_STATE_INVALID")
        updated = replace(
            current,
            publication_intent=dict(intent),
            evidence_ids=current.evidence_ids + (evidence_id,),
            history=current.history + ({
                "event": "PUBLICATION_RESERVED",
                "evidence_ids": [evidence_id],
            },),
        )
        try:
            self._compare_and_swap(request_id, current_sha, updated)
        except StateTransitionError:
            winner = self.get(request_id)
            if winner.publication_intent is not None:
                return winner, False
            raise
        return updated, True

    def record_publication(
        self,
        request_id: str,
        receipt: Mapping[str, Any],
    ) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        if current.publication_intent is None:
            raise StateTransitionError("PUBLICATION_INTENT_REQUIRED")
        evidence_id = validate_publication_receipt(
            receipt,
            intent=current.publication_intent,
        )
        if current.state is AttemptState.REPORTED:
            if current.publication_receipt != receipt:
                raise StateTransitionError("PUBLICATION_RECEIPT_CONFLICT")
            return current
        updated = record_publication_transition(current, receipt, evidence_id)
        self._compare_and_swap(request_id, current_sha, updated)
        return updated

    def record_invocation(self, request_id: str) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        current_sha, current = found
        if current.state is not AttemptState.ARMED or current.invocation_count != 0:
            raise StateTransitionError("INVOCATION_NOT_PERMITTED")
        updated = replace(current, invocation_count=1)
        self._compare_and_swap(request_id, current_sha, updated)
        return updated

    def _compare_and_swap(
        self,
        request_id: str,
        current_sha: str,
        updated: AttemptRecord,
    ) -> None:
        commit_sha = self._state_commit(current_sha, updated)
        result = self._api(
            "PATCH",
            f"repos/{self.repository}/git/{self._claim_ref(request_id)}",
            {"sha": commit_sha, "force": False},
            check=False,
        )
        if result.returncode != 0:
            raise StateTransitionError("STATE_COMPARE_AND_SWAP_FAILED")

    def _read(self, request_id: str) -> tuple[str, AttemptRecord] | None:
        ref = self._api(
            "GET",
            f"repos/{self.repository}/git/{self._claim_ref(request_id)}",
            check=False,
        )
        if ref.returncode != 0:
            return None
        try:
            ref_value = json.loads(ref.stdout)
            sha = ref_value["object"]["sha"]
            if (
                not isinstance(sha, str)
                or len(sha) != 40
                or any(character not in "0123456789abcdef" for character in sha)
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StateTransitionError("JOURNAL_REF_RESPONSE_INVALID") from exc
        content = self._api(
            "GET",
            f"repos/{self.repository}/contents/{self.STATE_PATH}?ref={sha}",
        )
        try:
            content_value = json.loads(content.stdout)
            encoded = content_value["content"]
            if content_value.get("encoding") != "base64" or not isinstance(encoded, str):
                raise ValueError
            raw = _decode_github_contents_base64(encoded)
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
                raise ValueError
            record = AttemptRecord.from_dict(value)
            if record.request_id != request_id:
                raise ValueError
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise StateTransitionError("JOURNAL_CONTENT_RESPONSE_INVALID") from exc
        return sha, record

    def _state_commit(self, parent_sha: str, record: AttemptRecord) -> str:
        parent = json.loads(self._api("GET", f"repos/{self.repository}/git/commits/{parent_sha}").stdout)
        encoded = base64.b64encode(canonical_bytes(record.as_dict()) + b"\n").decode("ascii")
        blob = json.loads(self._api(
            "POST", f"repos/{self.repository}/git/blobs", {"content": encoded, "encoding": "base64"}
        ).stdout)["sha"]
        tree = json.loads(self._api(
            "POST",
            f"repos/{self.repository}/git/trees",
            {
                "base_tree": parent["tree"]["sha"],
                "tree": [{"path": self.STATE_PATH, "mode": "100644", "type": "blob", "sha": blob}],
            },
        ).stdout)["sha"]
        commit = json.loads(self._api(
            "POST",
            f"repos/{self.repository}/git/commits",
            {"message": f"state: {record.state.value} {record.attempt_id}", "tree": tree, "parents": [parent_sha]},
        ).stdout)
        return commit["sha"]

    def _ref_sha(self, ref: str) -> str:
        result = self._api("GET", f"repos/{self.repository}/git/ref/{ref}")
        return json.loads(result.stdout)["object"]["sha"]

    def _claim_ref(self, request_id: str) -> str:
        digest = request_id.rsplit(":", 1)[-1]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("REQUEST_ID_INVALID")
        return f"refs/heads/review-claims/{digest}"

    def _api(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = ["gh", "api", "--method", method, endpoint]
        kwargs: dict[str, Any] = {
            "text": True,
            "capture_output": True,
            "check": False,
            "shell": False,
        }
        if payload is not None:
            command.extend(["--input", "-"])
            kwargs["input"] = canonical_bytes(payload).decode("utf-8")
        result = self.runner(command, **kwargs)
        if check and result.returncode != 0:
            raise StateTransitionError("GITHUB_JOURNAL_API_FAILED")
        return result
