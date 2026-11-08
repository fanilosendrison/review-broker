"""Git-ref-backed durable attempt journal."""
from __future__ import annotations

import base64
from dataclasses import replace
import json
import secrets
import subprocess
from typing import Any, Callable, Mapping

from .artifact_locator import (
    validate_evidence_artifact_locator,
    validate_evidence_artifact_plan,
)
from .identity import attempt_identity, canonical_bytes
from .github_journal_http import GitHubJournalResponse, JournalReadUnknown, journal_request
from .github_journal_read import (
    JournalObservation, JournalReadKind, commit_sha, observe_journal, ref_commit_sha,
)
from .publication import validate_publication_intent, validate_publication_receipt
from .queue import (
    AttemptRecord,
    AttemptState,
    StateTransitionError,
    record_publication_transition,
    record_capacity_assessment,
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

    def claim(
        self, request_id: str, admission: dict[str, Any] | None = None,
    ) -> AttemptRecord:
        existing = self._read(request_id)
        if existing is not None:
            if admission is not None and existing[1].admission != admission:
                raise StateTransitionError("CLAIM_ADMISSION_CONFLICT")
            return existing[1]
        record = AttemptRecord(
            request_id=request_id,
            attempt_id=attempt_identity(request_id, 1),
            state=AttemptState.REQUESTED,
            admission=admission,
            history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
        )
        base_sha = self._ref_sha(f"heads/{self.base_branch}")
        commit_sha = self._state_commit(base_sha, record)
        response = self._request(
            "POST", f"repos/{self.repository}/git/refs",
            {"ref": self._claim_ref(request_id), "sha": commit_sha},
        )
        # An unknown POST outcome must never be recovered into creation authority.
        # 422 is not a typed conflict: only a separately verified *other* winner
        # can supply the existing deterministic claim, under the v1 duplicate rule.
        if response.status not in {201, 422}:
            raise JournalReadUnknown("ATOMIC_CLAIM_OUTCOME_UNKNOWN")
        if response.status == 201:
            try:
                # ACK metadata cannot supply read authority, but any supplied
                # scope must agree; exact authoritative readback is still owed.
                acknowledged = ref_commit_sha(
                    response.value, self.repository, self._claim_ref(request_id), require_url=False,
                )
                if acknowledged != commit_sha:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise JournalReadUnknown("ATOMIC_CLAIM_OUTCOME_UNKNOWN") from None
        winner = self._read(request_id)
        if winner is None:
            raise JournalReadUnknown("ATOMIC_CLAIM_NOT_OBSERVED")
        if response.status == 422 and winner[0] == commit_sha:
            raise JournalReadUnknown("ATOMIC_CLAIM_OUTCOME_UNKNOWN")
        if response.status == 201 and (winner[0] != commit_sha or winner[1] != record):
            raise JournalReadUnknown("ATOMIC_CLAIM_NOT_OBSERVED")
        if admission is not None and winner[1].admission != admission:
            raise StateTransitionError("CLAIM_ADMISSION_CONFLICT")
        return winner[1]

    def get(self, request_id: str) -> AttemptRecord:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        return found[1]

    def get_snapshot(self, request_id: str) -> tuple[str, AttemptRecord]:
        found = self._read(request_id)
        if found is None:
            raise KeyError(request_id)
        return found

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

    def record_capacity(self, request_id: str, receipt: Mapping[str, Any]) -> AttemptRecord:
        return self._record_verified_transition(
            request_id, lambda current: record_capacity_assessment(current, receipt),
        )

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
        observed = self._read(request_id)
        if observed is None or observed[0] != commit_sha or observed[1] != updated:
            raise StateTransitionError("STATE_COMPARE_AND_SWAP_NOT_OBSERVED")

    def _observe(self, request_id: str) -> JournalObservation:
        return observe_journal(
            self.repository, self.base_branch, self._claim_ref(request_id),
            request_id, self.STATE_PATH, self._request,
        )

    def _read(self, request_id: str) -> tuple[str, AttemptRecord] | None:
        observation = self._observe(request_id)
        if observation.kind is JournalReadKind.UNKNOWN:
            raise JournalReadUnknown(observation.reason)
        if observation.kind is JournalReadKind.ABSENT_AUTHENTICATED:
            return None
        if observation.snapshot is None:
            raise JournalReadUnknown("JOURNAL_SNAPSHOT_UNKNOWN")
        return observation.snapshot

    def _request(
        self, method: str, endpoint: str, payload: dict[str, Any] | None = None,
    ) -> GitHubJournalResponse:
        return journal_request(self.runner, method, endpoint, payload)

    def _state_commit(self, parent_sha: str, record: AttemptRecord) -> str:
        parent = json.loads(self._api("GET", f"repos/{self.repository}/git/commits/{parent_sha}").stdout)
        try:
            if parent["sha"] != parent_sha:
                raise ValueError
            parent_tree = commit_sha(parent["tree"]["sha"])
        except (KeyError, TypeError, ValueError):
            raise JournalReadUnknown("JOURNAL_PARENT_TREE_UNKNOWN") from None
        encoded = base64.b64encode(canonical_bytes(record.as_dict()) + b"\n").decode("ascii")
        blob = self._create_object("blobs", {"content": encoded, "encoding": "base64"})
        tree = self._create_object("trees", {
            "base_tree": parent_tree,
            "tree": [{"path": self.STATE_PATH, "mode": "100644", "type": "blob", "sha": blob}],
        })
        return self._create_object("commits", {
            "message": f"state: {record.state.value} {record.attempt_id}\n\ntransaction: {secrets.token_hex(32)}",
            "tree": tree, "parents": [parent_sha],
        })

    def _create_object(self, resource: str, payload: dict[str, Any]) -> str:
        result = self._api("POST", f"repos/{self.repository}/git/{resource}", payload)
        try:
            return commit_sha(json.loads(result.stdout)["sha"])
        except (KeyError, TypeError, ValueError):
            raise JournalReadUnknown("JOURNAL_OBJECT_RESPONSE_UNKNOWN") from None

    def _ref_sha(self, ref: str) -> str:
        result = self._api("GET", f"repos/{self.repository}/git/ref/{ref}")
        try:
            return ref_commit_sha(json.loads(result.stdout), self.repository, f"refs/{ref}")
        except (KeyError, TypeError, ValueError):
            raise JournalReadUnknown("JOURNAL_BASE_REF_UNKNOWN") from None

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
        response = self._request(method, endpoint, payload)
        expected = 201 if method == "POST" else 200
        code = 0 if response.status == expected else 1
        if check and code:
            raise JournalReadUnknown("GITHUB_JOURNAL_API_FAILED")
        return subprocess.CompletedProcess([], code, json.dumps(response.value), "")
