"""Durable attempt state, atomic claims, and single-reviewer serialization."""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from enum import Enum
import json
import subprocess
import threading
from typing import Any, Callable

from .identity import attempt_identity, canonical_bytes


class AttemptState(str, Enum):
    REQUESTED = "REQUESTED"
    ADMITTED = "ADMITTED"
    PREPARED = "PREPARED"
    ARMED = "ARMED"
    TERMINAL_CAPTURED = "TERMINAL_CAPTURED"
    VALIDATED = "VALIDATED"
    REPORTED = "REPORTED"
    STOPPED = "STOPPED"
    INDETERMINATE = "INDETERMINATE"


LEGAL_TRANSITIONS = {
    AttemptState.REQUESTED: {AttemptState.ADMITTED, AttemptState.INDETERMINATE},
    AttemptState.ADMITTED: {AttemptState.PREPARED, AttemptState.INDETERMINATE},
    AttemptState.PREPARED: {AttemptState.ARMED, AttemptState.INDETERMINATE},
    AttemptState.ARMED: {AttemptState.TERMINAL_CAPTURED, AttemptState.INDETERMINATE},
    AttemptState.TERMINAL_CAPTURED: {AttemptState.VALIDATED, AttemptState.INDETERMINATE},
    AttemptState.VALIDATED: {AttemptState.REPORTED, AttemptState.INDETERMINATE},
    AttemptState.REPORTED: {AttemptState.STOPPED, AttemptState.INDETERMINATE},
    AttemptState.INDETERMINATE: {AttemptState.STOPPED},
    AttemptState.STOPPED: set(),
}


class StateTransitionError(RuntimeError):
    pass


class ReviewerBusy(StateTransitionError):
    pass


@dataclass(frozen=True)
class AttemptRecord:
    request_id: str
    attempt_id: str
    state: AttemptState
    evidence_ids: tuple[str, ...] = ()
    invocation_count: int = 0
    history: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_id": self.request_id,
            "attempt_id": self.attempt_id,
            "state": self.state.value,
            "evidence_ids": list(self.evidence_ids),
            "invocation_count": self.invocation_count,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AttemptRecord":
        return cls(
            request_id=value["request_id"],
            attempt_id=value["attempt_id"],
            state=AttemptState(value["state"]),
            evidence_ids=tuple(value.get("evidence_ids", [])),
            invocation_count=value.get("invocation_count", 0),
            history=tuple(value.get("history", [])),
        )


class InMemoryJournal:
    """Deterministic test journal with the same transition invariants as GitHub refs."""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_request: dict[str, AttemptRecord] = {}
        self._by_attempt: dict[str, AttemptRecord] = {}
        self._armed_attempt: str | None = None

    @property
    def attempt_count(self) -> int:
        with self._lock:
            return len(self._by_attempt)

    def claim(self, request_id: str) -> AttemptRecord:
        with self._lock:
            existing = self._by_request.get(request_id)
            if existing is not None:
                return existing
            record = AttemptRecord(
                request_id=request_id,
                attempt_id=attempt_identity(request_id, 1),
                state=AttemptState.REQUESTED,
                history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
            )
            self._save(record)
            return record

    def get(self, attempt_id: str) -> AttemptRecord:
        with self._lock:
            return self._by_attempt[attempt_id]

    def transition(
        self,
        attempt_id: str,
        target: AttemptState,
        evidence_ids: list[str] | tuple[str, ...],
    ) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            updated = transition_record(current, target, evidence_ids)
            if target is AttemptState.ARMED:
                if self._armed_attempt not in (None, attempt_id):
                    raise ReviewerBusy("SINGLE_REVIEWER_BUSY")
                self._armed_attempt = attempt_id
            if target is AttemptState.STOPPED and self._armed_attempt == attempt_id:
                self._armed_attempt = None
            self._save(updated)
            return updated

    def record_invocation(self, attempt_id: str) -> AttemptRecord:
        with self._lock:
            current = self._by_attempt[attempt_id]
            if current.state is not AttemptState.ARMED or current.invocation_count != 0:
                raise StateTransitionError("INVOCATION_NOT_PERMITTED")
            updated = replace(current, invocation_count=1)
            self._save(updated)
            return updated

    def _save(self, record: AttemptRecord) -> None:
        self._by_request[record.request_id] = record
        self._by_attempt[record.attempt_id] = record


def transition_record(
    current: AttemptRecord,
    target: AttemptState,
    evidence_ids: list[str] | tuple[str, ...],
) -> AttemptRecord:
    evidence = tuple(evidence_ids)
    if not evidence:
        raise StateTransitionError("EVIDENCE_REQUIRED")
    if target not in LEGAL_TRANSITIONS[current.state]:
        raise StateTransitionError(f"ILLEGAL_TRANSITION:{current.state.value}->{target.value}")
    history_entry = {"state": target.value, "evidence_ids": list(evidence)}
    return replace(
        current,
        state=target,
        evidence_ids=current.evidence_ids + evidence,
        history=current.history + (history_entry,),
    )


Runner = Callable[..., subprocess.CompletedProcess[str]]


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
        ref = self._api("GET", f"repos/{self.repository}/git/{self._claim_ref(request_id)}", check=False)
        if ref.returncode != 0:
            return None
        sha = json.loads(ref.stdout)["object"]["sha"]
        branch = self._claim_ref(request_id).removeprefix("refs/heads/")
        content = self._api(
            "GET",
            f"repos/{self.repository}/contents/{self.STATE_PATH}?ref={branch}",
        )
        encoded = json.loads(content.stdout)["content"]
        value = json.loads(base64.b64decode(encoded).decode("utf-8"))
        return sha, AttemptRecord.from_dict(value)

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
