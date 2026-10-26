"""Git-ref-backed durable attempt journal."""
from __future__ import annotations

import base64
from dataclasses import replace
import json
import subprocess
from typing import Any, Callable, Mapping

from .identity import attempt_identity, canonical_bytes
from .queue import (
    AttemptRecord,
    AttemptState,
    StateTransitionError,
    record_shutdown_transition,
    record_terminal_capture_transition,
    transition_record,
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
