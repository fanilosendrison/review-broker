"""Read-only committed-state observations for experimental v3 Git journals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Callable, Mapping, Protocol

from .github_journal_transport_v3 import (
    GitHubTransportV3, ReadStatusV3, VerifiedJournalSnapshotV3,
)
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import WorkerIdentityV3, decode_journal_v2, encode_journal_v2

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(r"^refs/heads/review-claims-v3/[0-9a-f]{64}$")
_NODE_ID = re.compile(r"^[A-Za-z0-9_=-]+$")


class GitHubRefObservationV3Error(RuntimeError):
    """The current ref and committed journal could not be established exactly."""


class IdentityBearingGitHubTransportV3(GitHubTransportV3, Protocol):
    repository: str

    def verify_repository_identity(self) -> str: ...


@dataclass(frozen=True)
class CurrentRefExpectationV3:
    repository: str
    repository_node_id: str
    claim_ref: str
    commit_sha: str
    request_id: str
    attempt_id: str
    admission: Mapping[str, object]
    journal_bytes: bytes | None = None
    journal_sha256: str | None = None
    reservation_id: str | None = None
    generation: int | None = None
    worker: WorkerIdentityV3 | None = None

    def __post_init__(self) -> None:
        if _REPOSITORY.fullmatch(self.repository) is None or ".." in self.repository:
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        if _REF.fullmatch(self.claim_ref) is None:
            raise ValueError("V3_CLAIM_REF_INVALID")
        if _SHA.fullmatch(self.commit_sha) is None:
            raise ValueError("GIT_COMMIT_SHA_INVALID")
        if _NODE_ID.fullmatch(self.repository_node_id) is None:
            raise ValueError("GITHUB_REPOSITORY_NODE_ID_INVALID")
        if (self.journal_bytes is None) == (self.journal_sha256 is None):
            raise ValueError("EXPECTED_JOURNAL_IDENTITY_REQUIRED")
        if self.journal_bytes is not None and not isinstance(self.journal_bytes, bytes):
            raise ValueError("EXPECTED_JOURNAL_BYTES_INVALID")
        if (self.journal_sha256 is not None
                and re.fullmatch(r"[0-9a-f]{64}", self.journal_sha256) is None):
            raise ValueError("EXPECTED_JOURNAL_DIGEST_INVALID")
        if self.generation is not None and (type(self.generation) is not int or self.generation < 0):
            raise ValueError("EXPECTED_GENERATION_INVALID")


@dataclass(frozen=True)
class GitHubRefObservationV3:
    repository: str
    repository_node_id: str
    claim_ref: str
    commit_sha: str
    parent_sha: str
    journal_bytes: bytes
    journal_sha256: str
    request_id: str
    attempt_id: str
    admission_evidence_id: str
    reservation_id: str | None
    generation: int
    worker: WorkerIdentityV3 | None
    observed_at: str
    evidence_id: str
    snapshot: VerifiedJournalSnapshotV3


ClockV3 = Callable[[], datetime]


class CurrentRefFreshnessBoundaryV3(Protocol):
    """Independent source required before a bounded read can authorize an effect."""

    def authenticates(self, observation: GitHubRefObservationV3) -> bool: ...


class GitHubRefObservationReaderV3:
    """Require two consecutive exact reads while making no linearizability claim."""

    def __init__(self, transport: IdentityBearingGitHubTransportV3, repository: str,
                 repository_node_id: str, *, max_read_attempts: int = 3,
                 clock: ClockV3 | None = None):
        if _REPOSITORY.fullmatch(repository) is None or ".." in repository:
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        if _NODE_ID.fullmatch(repository_node_id) is None:
            raise ValueError("GITHUB_REPOSITORY_NODE_ID_INVALID")
        if type(max_read_attempts) is not int or max_read_attempts < 2 or max_read_attempts > 5:
            raise ValueError("REF_READ_ATTEMPTS_INVALID")
        if (not isinstance(getattr(transport, "repository", None), str)
                or transport.repository != repository
                or not callable(getattr(transport, "verify_repository_identity", None))):
            raise ValueError("IDENTITY_BEARING_TRANSPORT_REQUIRED")
        self.transport = transport
        self.repository = repository
        self.repository_node_id = repository_node_id
        self.max_read_attempts = max_read_attempts
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _matches(snapshot: object, expected: CurrentRefExpectationV3) -> bool:
        if not hasattr(snapshot, "commit_sha") or not hasattr(snapshot, "journal_bytes"):
            return False
        if snapshot.commit_sha != expected.commit_sha:
            return False
        if expected.journal_bytes is not None and snapshot.journal_bytes != expected.journal_bytes:
            return False
        digest = hashlib.sha256(snapshot.journal_bytes).hexdigest()
        if expected.journal_sha256 is not None and digest != expected.journal_sha256:
            return False
        return True

    def observe(self, expected: CurrentRefExpectationV3) -> GitHubRefObservationV3:
        if (expected.repository != self.repository
                or expected.repository_node_id != self.repository_node_id):
            raise GitHubRefObservationV3Error("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
        try:
            if self.transport.verify_repository_identity() != self.repository_node_id:
                raise GitHubRefObservationV3Error("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
        except GitHubRefObservationV3Error:
            raise
        except Exception:
            raise GitHubRefObservationV3Error("GITHUB_REPOSITORY_IDENTITY_UNAVAILABLE") from None
        request_digest = expected.request_id.removeprefix("request:sha256:")
        if expected.claim_ref != "refs/heads/review-claims-v3/" + request_digest:
            raise GitHubRefObservationV3Error("V3_CLAIM_IDENTITY_MISMATCH")
        consecutive = 0
        accepted = None
        for _ in range(self.max_read_attempts):
            result = self.transport.read_claim(expected.claim_ref)
            if (result.status is ReadStatusV3.FOUND and result.snapshot is not None
                    and self._matches(result.snapshot, expected)):
                if accepted is not None and result.snapshot != accepted:
                    consecutive = 0
                accepted = result.snapshot
                consecutive += 1
                if consecutive == 2:
                    break
            else:
                accepted = None
                consecutive = 0
        if consecutive != 2 or accepted is None:
            raise GitHubRefObservationV3Error("CURRENT_REF_OBSERVATION_UNAVAILABLE")
        try:
            if self.transport.verify_repository_identity() != self.repository_node_id:
                raise GitHubRefObservationV3Error("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
        except GitHubRefObservationV3Error:
            raise
        except Exception:
            raise GitHubRefObservationV3Error("GITHUB_REPOSITORY_IDENTITY_UNAVAILABLE") from None
        try:
            record = decode_journal_v2(accepted.journal_bytes)
        except ValueError as exc:
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_INVALID") from exc
        if encode_journal_v2(record) != accepted.journal_bytes:
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_NONCANONICAL")
        attempt, control = record.attempt, record.control
        if attempt.request_id != expected.request_id or attempt.attempt_id != expected.attempt_id:
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_ATTEMPT_MISMATCH")
        if canonical_bytes(attempt.admission) != canonical_bytes(dict(expected.admission)):
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_ADMISSION_MISMATCH")
        if (expected.reservation_id is not None
                and control.reservation_id != expected.reservation_id):
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_RESERVATION_MISMATCH")
        if expected.generation is not None and control.generation != expected.generation:
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_GENERATION_MISMATCH")
        if expected.worker is not None and control.worker != expected.worker:
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_WORKER_MISMATCH")
        admission_id = attempt.admission.get("admission_evidence_id")
        if (not isinstance(admission_id, str)
                or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", admission_id) is None):
            raise GitHubRefObservationV3Error("CURRENT_JOURNAL_ADMISSION_IDENTITY_INVALID")
        observed = self._clock()
        if observed.tzinfo is None:
            raise GitHubRefObservationV3Error("GITHUB_OBSERVATION_TIME_INVALID")
        observed_at = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        journal_digest = hashlib.sha256(accepted.journal_bytes).hexdigest()
        basis = {
            "schema_version": 1,
            "evidence_type": "github-current-ref-observation",
            "repository": self.repository,
            "repository_node_id": self.repository_node_id,
            "claim_ref": expected.claim_ref,
            "commit_sha": accepted.commit_sha,
            "parent_sha": accepted.parent_sha,
            "journal_sha256": journal_digest,
            "request_id": attempt.request_id,
            "attempt_id": attempt.attempt_id,
            "admission_evidence_id": admission_id,
            "reservation_id": control.reservation_id,
            "generation": control.generation,
            "worker": None if control.worker is None else control.worker.as_dict(),
            "observed_at": observed_at,
        }
        verified = VerifiedJournalSnapshotV3(
            self.repository, self.repository_node_id, expected.claim_ref,
            accepted.commit_sha, accepted.parent_sha, accepted.journal_bytes,
            record, None,
        )
        return GitHubRefObservationV3(
            self.repository, self.repository_node_id, expected.claim_ref,
            accepted.commit_sha, accepted.parent_sha, accepted.journal_bytes,
            journal_digest, attempt.request_id, attempt.attempt_id, admission_id,
            control.reservation_id, control.generation, control.worker,
            observed_at, artifact_identity(canonical_bytes(basis) + b"\n"), verified,
        )


@dataclass(frozen=True)
class AuthenticatedCurrentJournalAuthorityV3:
    """Effect authority requires both exact reads and independent freshness."""

    reader: GitHubRefObservationReaderV3
    freshness_boundary: CurrentRefFreshnessBoundaryV3

    def is_current(self, snapshot: VerifiedJournalSnapshotV3) -> bool:
        expected = CurrentRefExpectationV3(
            repository=snapshot.repository,
            repository_node_id=snapshot.repository_node_id,
            claim_ref=snapshot.claim_ref,
            commit_sha=snapshot.commit_sha,
            request_id=snapshot.record.attempt.request_id,
            attempt_id=snapshot.record.attempt.attempt_id,
            admission=snapshot.record.attempt.admission or {},
            journal_bytes=snapshot.journal_bytes,
            reservation_id=snapshot.record.control.reservation_id,
            generation=snapshot.record.control.generation,
            worker=snapshot.record.control.worker,
        )
        try:
            observation = self.reader.observe(expected)
        except (GitHubRefObservationV3Error, ValueError):
            return False
        try:
            fresh = self.freshness_boundary.authenticates(observation)
        except Exception:
            fresh = False
        if type(fresh) is not bool or not fresh:
            return False
        return observation.snapshot == snapshot or (
            observation.snapshot.repository == snapshot.repository
            and observation.snapshot.repository_node_id == snapshot.repository_node_id
            and observation.snapshot.claim_ref == snapshot.claim_ref
            and observation.snapshot.commit_sha == snapshot.commit_sha
            and observation.snapshot.parent_sha == snapshot.parent_sha
            and observation.snapshot.journal_bytes == snapshot.journal_bytes
            and observation.snapshot.record == snapshot.record
        )
