"""Injected transport and authority fixtures for experimental v3 journal tests."""
from __future__ import annotations

import hashlib
import threading

from review_broker.github_journal_transport_v3 import (
    CreateRefResultV3,
    CreateRefStatusV3,
    GraphQLRefUpdateV3,
    GraphQLUpdateResultV3,
    ReadResultV3,
    ReadStatusV3,
    TransportSnapshotV3,
)
from review_broker.identity import artifact_identity, canonical_bytes, request_identity
from review_broker.journal_record_v3 import WorkerIdentityV3


BASE_SHA = "b" * 40
REPOSITORY = "example/review-broker"
NODE_ID = "R_example"
PACKET_ID = "artifact:sha256:" + "9" * 64
ADMISSION_ID = "artifact:sha256:" + "8" * 64
OBSERVATION_ID = "artifact:sha256:" + "7" * 64
WRITER_EVIDENCE_ID = "artifact:sha256:" + "6" * 64
REJECTION_EVIDENCE_ID = "artifact:sha256:" + "4" * 64
REQUEST = {
    "schema_version": 3,
    "subject": {"kind": "github_pr", "repository": REPOSITORY,
                "repository_id": 123, "pull_request": 4,
                "expected_head_commit": "a" * 40},
    "mission": {"id": "bounded", "objective": "test", "instructions": "test",
                "criteria": ["test"]},
    "reviewer": {"backend": "codex-cli", "model": "gpt-5.6-sol",
                 "reasoning_effort": "xhigh"},
    "atomicity": False,
    "references": [],
    "review_operation": {"kind": "initial"},
}
REQUEST_ID = request_identity(REQUEST)
ADMISSION = {"request_id": REQUEST_ID, "admission_evidence_id": ADMISSION_ID,
             "repository_id": 123, "resolved_subject": "exact",
             "reference_ids": ["contract"]}


def failure_receipt(attempt_id: str, reservation_id: str,
                    worker: WorkerIdentityV3) -> tuple[str, dict[str, object]]:
    receipt: dict[str, object] = {
        "schema_version": 1,
        "evidence_type": "pre-model-preparation-failure",
        "request_id": REQUEST_ID,
        "attempt_id": attempt_id,
        "admission_evidence_id": ADMISSION_ID,
        "generation": 1,
        "reservation_id": reservation_id,
        "workflow_run_id": worker.run_id,
        "workflow_run_attempt": worker.run_attempt,
        "classification": "PERMANENT",
        "reason_code": "SOURCE_DIGEST_MISMATCH",
        "reference_id": "contract",
        "observation_evidence_id": OBSERVATION_ID,
        "observed_at": "2026-10-30T00:00:00Z",
    }
    return artifact_identity(canonical_bytes(receipt) + b"\n"), receipt


class FakeGitHubTransportV3:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.refs: dict[str, str] = {}
        self.commits: dict[str, TransportSnapshotV3] = {}
        self.read_calls: list[str] = []
        self.create_statuses: list[CreateRefStatusV3] = []
        self.updates: list[GraphQLRefUpdateV3] = []
        self.create_barrier: threading.Barrier | None = None
        self.created_wrong_target = False
        self.graphql_application_error = False
        self.graphql_error_after_apply = False
        self.ambiguous_expected_old_after_apply = False
        self.competing_descendant_after_update = False
        self.lose_update_acknowledgment = False
        self.read_unavailable = 0
        self.stale_reads: dict[str, tuple[str, int]] = {}
        self.counter = 0

    def read_claim(self, claim_ref: str) -> ReadResultV3:
        with self.lock:
            self.read_calls.append(claim_ref)
            if self.read_unavailable:
                self.read_unavailable -= 1
                return ReadResultV3(ReadStatusV3.UNAVAILABLE)
            stale = self.stale_reads.get(claim_ref)
            if stale is not None and stale[1] > 0:
                self.stale_reads[claim_ref] = (stale[0], stale[1] - 1)
                return ReadResultV3(ReadStatusV3.FOUND, self.commits[stale[0]])
            sha = self.refs.get(claim_ref)
            if sha is None:
                return ReadResultV3(ReadStatusV3.MISSING)
            return ReadResultV3(ReadStatusV3.FOUND, self.commits[sha])

    def create_journal_commit(self, parent_sha: str, journal_bytes: bytes) -> str:
        with self.lock:
            self.counter += 1
            sha = hashlib.sha1(
                parent_sha.encode() + journal_bytes + str(self.counter).encode(),
                usedforsecurity=False,
            ).hexdigest()
            self.commits[sha] = TransportSnapshotV3(sha, parent_sha, journal_bytes)
            return sha

    def create_ref(self, claim_ref: str, commit_sha: str) -> CreateRefResultV3:
        if self.create_barrier is not None:
            self.create_barrier.wait()
        with self.lock:
            if claim_ref in self.refs:
                status = CreateRefStatusV3.ALREADY_EXISTS
            else:
                target = commit_sha
                if self.created_wrong_target:
                    self.counter += 1
                    intended = self.commits[commit_sha]
                    target = hashlib.sha1(
                        commit_sha.encode() + str(self.counter).encode(),
                        usedforsecurity=False,
                    ).hexdigest()
                    self.commits[target] = TransportSnapshotV3(
                        target, intended.parent_sha, intended.journal_bytes
                    )
                self.refs[claim_ref] = target
                status = CreateRefStatusV3.CREATED
            self.create_statuses.append(status)
            evidence = WRITER_EVIDENCE_ID if status is CreateRefStatusV3.CREATED else None
            return CreateRefResultV3(status, evidence)

    def update_ref(self, update: GraphQLRefUpdateV3) -> GraphQLUpdateResultV3:
        with self.lock:
            self.updates.append(update)
            if self.graphql_application_error:
                return GraphQLUpdateResultV3(200, ("application error",))
            if self.refs.get(update.name) != update.before_oid:
                return GraphQLUpdateResultV3(
                    200, ("beforeOid mismatch",), expected_old_rejected=True,
                    rejection_evidence_id=REJECTION_EVIDENCE_ID,
                )
            if self.commits[update.after_oid].parent_sha != update.before_oid:
                return GraphQLUpdateResultV3(200, ("non-direct successor",))
            self.refs[update.name] = update.after_oid
            if self.competing_descendant_after_update:
                self.counter += 1
                descendant = hashlib.sha1(
                    update.after_oid.encode() + str(self.counter).encode(),
                    usedforsecurity=False,
                ).hexdigest()
                intended = self.commits[update.after_oid]
                self.commits[descendant] = TransportSnapshotV3(
                    descendant, update.after_oid, intended.journal_bytes
                )
                self.refs[update.name] = descendant
            if self.graphql_error_after_apply:
                return GraphQLUpdateResultV3(200, ("ambiguous application error",))
            if self.ambiguous_expected_old_after_apply:
                return GraphQLUpdateResultV3(
                    None, ("untrusted expected-old error",), expected_old_rejected=True
                )
            if self.lose_update_acknowledgment:
                return GraphQLUpdateResultV3(None, ())
            return GraphQLUpdateResultV3(200, (), WRITER_EVIDENCE_ID)


class TrustedMutationAuthority:
    def __init__(self, trusted: bool = True) -> None:
        self.trusted = trusted

    def permits(self, update: object, evidence_id: str) -> bool:
        return self.trusted and evidence_id == WRITER_EVIDENCE_ID


class TrustedRejectionAuthority:
    def permits(self, update: object, evidence_id: str) -> bool:
        return evidence_id == REJECTION_EVIDENCE_ID


class TrustedPredecessorAuthority:
    def __init__(self, trusted: bool = True, readback: bool = True) -> None:
        self.trusted = trusted
        self.readback = readback

    def evidence_id(self, **values: object) -> str | None:
        return WRITER_EVIDENCE_ID if self.trusted and self.readback else None

    def permits_evidence(self, **values: object) -> bool:
        return (self.trusted
                and values["evidence_id"] in {
                    WRITER_EVIDENCE_ID, "artifact:sha256:" + "3" * 64,
                })


class TrustedPacketAuthority:
    def __init__(self, trusted: bool = True) -> None:
        self.trusted = trusted

    def permits(self, **values: object) -> bool:
        return self.trusted and values["packet_evidence_id"] == PACKET_ID


class TrustedAdmissionAuthority:
    def __init__(self, trusted: bool = True) -> None:
        self.trusted = trusted

    def evidence_id(self, **values: object) -> str | None:
        if self.trusted and values["repository"] == REPOSITORY:
            return "artifact:sha256:" + "3" * 64
        return None

    def permits_evidence(self, **values: object) -> bool:
        return (self.trusted and values["repository"] == REPOSITORY
                and values["evidence_id"] == "artifact:sha256:" + "3" * 64
                and values["admission"] == ADMISSION)


class TrustedFailureAuthority:
    def __init__(self, trusted: bool = True) -> None:
        self.trusted = trusted

    def permits(self, receipt: object) -> bool:
        return self.trusted and isinstance(receipt, dict)


class TrustedWorkerAuthority:
    def __init__(self, worker: WorkerIdentityV3, trusted: bool = True) -> None:
        self.worker = worker
        self.trusted = trusted

    def evidence_id(self, **values: object) -> str | None:
        if self.trusted and values["worker"] == self.worker:
            return "artifact:sha256:" + "5" * 64
        return None
