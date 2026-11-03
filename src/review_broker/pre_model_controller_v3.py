"""Experimental initial Controller over injected admission, journal and dispatch."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from threading import Lock
from typing import Mapping, Protocol

from .admission_evidence_v3 import validate_journal_admission_v3
from .admission_v3 import PreclaimAdmissionV3
from .github_journal_transport_v3 import (
    GraphQLRefUpdateV3, JournalOutcomeV3, OutcomeStatusV3, ReadStatusV3,
    VerifiedJournalSnapshotV3,
)
from .github_journal_v3 import GitHubJournalV3, GitHubJournalV3Error
from .identity import canonical_bytes
from .journal_record_v3 import (
    PreModelControlV3, encode_journal_v2, preparation_dispatch_identity,
)
from .pre_model_dispatch_v3 import (
    InitialDispatchRequestV3, InitialDispatchResultV3, InitialDispatchStatusV3,
    InitialDispatchTargetV3, InitialDispatchTransportV3,
)
from .queue import AttemptState


@dataclass(frozen=True)
class ControllerAuthorizationV3:
    """External bounded decision, explicitly bound to all retained admission bytes."""

    authorized: bool
    broker_repository: str
    broker_repository_node_id: str
    target: InitialDispatchTargetV3
    journal_admission_bytes: bytes
    origin_body_bytes: bytes


class ControllerAuthorityV3(Protocol):
    def authorize(self, *, broker_repository: str, broker_repository_node_id: str,
                  target: InitialDispatchTargetV3, journal_admission_bytes: bytes,
                  origin_body_bytes: bytes) -> ControllerAuthorizationV3 | None: ...


class ControllerStatusV3(str, Enum):
    ADMISSION_DENIED = "ADMISSION_DENIED"
    ALREADY_HANDLED = "ALREADY_HANDLED"
    CLAIM_REJECTED = "CLAIM_REJECTED"
    CLAIM_UNRESOLVED = "CLAIM_UNRESOLVED"
    RESERVATION_REJECTED = "RESERVATION_REJECTED"
    RESERVATION_UNRESOLVED = "RESERVATION_UNRESOLVED"
    DISPATCH_OBSERVED = "DISPATCH_OBSERVED"
    DISPATCH_UNRESOLVED = "DISPATCH_UNRESOLVED"


@dataclass(frozen=True)
class ControllerResultV3:
    status: ControllerStatusV3
    reason: str
    claim_outcome: JournalOutcomeV3 | None = None
    reservation_outcome: JournalOutcomeV3 | None = None
    dispatch_request: InitialDispatchRequestV3 | None = None
    dispatch_result: InitialDispatchResultV3 | None = None


class PreModelControllerV3:
    """One initial operation per request per instance; never a retry/recovery loop.

    The local attempted set only denies replay; it grants no durable authority.
    Independent Controllers still arbitrate exclusively through the journal CAS.
    No network adapter, credential, event handler or workflow is selected here.
    """

    def __init__(self, journal: GitHubJournalV3, target: InitialDispatchTargetV3,
                 dispatch_transport: InitialDispatchTransportV3,
                 authority: ControllerAuthorityV3 | None):
        if type(journal) is not GitHubJournalV3 or type(target) is not InitialDispatchTargetV3:
            raise ValueError("INITIAL_CONTROLLER_COMPONENT_INVALID")
        self.journal = journal
        self.target = target
        self.dispatch_transport = dispatch_transport
        self.authority = authority
        self._attempted: dict[str, bytes] = {}
        self._completed: dict[str, ControllerResultV3] = {}
        self._attempt_lock = Lock()

    def _admission(self, admission: PreclaimAdmissionV3,
                   target: InitialDispatchTargetV3) -> dict[str, object]:
        if type(admission) is not PreclaimAdmissionV3:
            raise ValueError("PRECLAIM_ADMISSION_REQUIRED")
        value = validate_journal_admission_v3(
            admission.journal_admission(), admission.origin_body_bytes,
        )
        if admission.canonical_request_bytes != canonical_bytes(value["canonical_request"]):
            raise ValueError("CANONICAL_REQUEST_BYTES_MISMATCH")
        provenance = (
            (admission.origin_provenance_bytes, value["origin_observation"]),
            (admission.source_provenance_bytes, value["source_observation"]),
            (admission.requester_provenance_bytes, value["requester_authorization"]),
            (admission.history_provenance_bytes, value["history_observation"]),
        )
        if any(raw != canonical_bytes(decoded) for raw, decoded in provenance):
            raise ValueError("ADMISSION_PROVENANCE_BYTES_MISMATCH")
        if admission.requester_login_observed != value["origin_observation"]["requester_login_observed"]:
            raise ValueError("REQUESTER_OBSERVATION_MISMATCH")
        context = {
            "broker_repository": self.journal.repository,
            "broker_repository_node_id": self.journal.repository_node_id,
            "target": target,
            "journal_admission_bytes": canonical_bytes(value),
            "origin_body_bytes": admission.origin_body_bytes,
        }
        decision = None if self.authority is None else self.authority.authorize(**context)
        if (type(decision) is not ControllerAuthorizationV3
                or decision.authorized is not True
                or decision != ControllerAuthorizationV3(True, **context)):
            raise ValueError("CONTROLLER_AUTHORITY_UNTRUSTED")
        if value["origin_observation"]["repository"] != self.journal.repository:
            raise ValueError("ORIGIN_BROKER_REPOSITORY_MISMATCH")
        return value

    @staticmethod
    def _matches(snapshot: VerifiedJournalSnapshotV3,
                 admission: Mapping[str, object]) -> bool:
        return (snapshot.record.attempt.request_id == admission["request_id"]
                and canonical_bytes(snapshot.record.attempt.admission) == canonical_bytes(admission))

    @staticmethod
    def _initial(snapshot: VerifiedJournalSnapshotV3) -> bool:
        return (snapshot.record.attempt.state is AttemptState.REQUESTED
                and snapshot.record.control == PreModelControlV3.initial())

    def _reservation_attributed(self, before: VerifiedJournalSnapshotV3,
                                outcome: JournalOutcomeV3,
                                admission: Mapping[str, object], claim_ref: str) -> bool:
        """Only this synchronous reserve operation's accepted successor may dispatch."""
        snapshot = outcome.snapshot
        if (outcome.status is not OutcomeStatusV3.COMMITTED or snapshot is None
                or outcome.pending is not None or snapshot.writer_evidence_id is None
                or snapshot.repository != self.journal.repository
                or snapshot.repository_node_id != self.journal.repository_node_id
                or snapshot.claim_ref != claim_ref
                or snapshot.parent_sha != before.commit_sha
                or snapshot.commit_sha == before.commit_sha
                or not self._matches(snapshot, admission)
                or encode_journal_v2(snapshot.record) != snapshot.journal_bytes):
            return False
        control = snapshot.record.control
        if (snapshot.record.attempt.state is not AttemptState.REQUESTED
                or control.generation != 1 or control.disposition != "RESERVED"
                or control.worker is not None or control.failure_receipt_id is not None
                or control.authorization_id != admission["request_id"]
                or control.reservation_id != preparation_dispatch_identity(
                    snapshot.record.attempt.request_id, snapshot.record.attempt.attempt_id,
                    1, snapshot.record.attempt.request_id)):
            return False
        update = GraphQLRefUpdateV3(
            self.journal.repository_node_id, claim_ref,
            before.commit_sha, snapshot.commit_sha, False,
        )
        return self.journal.mutation_authority.permits(update, snapshot.writer_evidence_id) is True

    def run(self, admission: PreclaimAdmissionV3) -> ControllerResultV3:
        # Retain the exact immutable target presented to the external authority.
        target = self.target
        try:
            verified = self._admission(admission, target)
        except Exception:
            return ControllerResultV3(ControllerStatusV3.ADMISSION_DENIED,
                                      "ADMISSION_OR_CONTROLLER_AUTHORITY_INVALID")
        request_id = verified["request_id"]
        with self._attempt_lock:
            if request_id in self._attempted:
                if self._attempted[request_id] != canonical_bytes(verified):
                    return ControllerResultV3(ControllerStatusV3.CLAIM_REJECTED,
                                              "LOCAL_ADMISSION_IDENTITY_CONFLICT")
                previous = self._completed.get(request_id)
                if previous is None:
                    return ControllerResultV3(ControllerStatusV3.CLAIM_UNRESOLVED,
                                              "LOCAL_OPERATION_UNRESOLVED_NO_RETRY")
                if previous.status not in {
                    ControllerStatusV3.DISPATCH_OBSERVED, ControllerStatusV3.ALREADY_HANDLED,
                }:
                    return replace(previous, reason="PRIOR_OPERATION_RETAINED_NO_RETRY")
                return ControllerResultV3(ControllerStatusV3.ALREADY_HANDLED,
                                          "LOCAL_OPERATION_ALREADY_ATTEMPTED_NO_RETRY")
            self._attempted[request_id] = canonical_bytes(verified)
        result = self._run_verified(verified, target)
        with self._attempt_lock:
            self._completed[request_id] = result
        return result

    def _run_verified(self, verified: Mapping[str, object],
                      target: InitialDispatchTargetV3) -> ControllerResultV3:
        request_id = verified["request_id"]
        claim = None
        reservation = None
        claiming = False
        reserving = False
        try:
            claim_ref = self.journal.claim_ref(request_id)
            # The validated history owns the namespace; never accept a legacy route.
            namespace = verified["history_observation"]["namespace"]
            if claim_ref != namespace + request_id.rsplit(":", 1)[1]:
                return ControllerResultV3(ControllerStatusV3.CLAIM_REJECTED,
                                          "CONTROLLER_CLAIM_NAMESPACE_MISMATCH")
            read = self.journal.transport.read_claim(claim_ref)
            if read.status is ReadStatusV3.FOUND and read.snapshot is not None:
                current = self.journal.read(request_id)
            elif read.status is ReadStatusV3.MISSING and read.snapshot is None:
                claiming = True
                claim = self.journal.claim(verified["canonical_request"], verified)
                if claim.status is not OutcomeStatusV3.COMMITTED:
                    status = (ControllerStatusV3.CLAIM_REJECTED
                              if claim.status is OutcomeStatusV3.REJECTED
                              else ControllerStatusV3.CLAIM_UNRESOLVED)
                    return ControllerResultV3(status, "CLAIM_NOT_COMMITTED", claim)
                current = claim.snapshot
                if current is None:
                    raise ValueError("CLAIM_COMMITTED_WITHOUT_SNAPSHOT")
            else:
                return ControllerResultV3(ControllerStatusV3.CLAIM_UNRESOLVED,
                                          "CLAIM_READ_UNAVAILABLE")
            if not self._matches(current, verified):
                return ControllerResultV3(ControllerStatusV3.CLAIM_REJECTED,
                                          "CLAIM_IDENTITY_CONFLICT", claim)
            if not self._initial(current):
                return ControllerResultV3(ControllerStatusV3.ALREADY_HANDLED,
                                          "EXISTING_CLAIM_IS_NOT_INITIAL", claim)
            reserving = True
            reservation = self.journal.reserve_initial(current)
            if reservation.status is OutcomeStatusV3.REJECTED:
                return ControllerResultV3(ControllerStatusV3.RESERVATION_REJECTED,
                                          "RESERVATION_REJECTED", claim, reservation)
            if not self._reservation_attributed(current, reservation, verified, claim_ref):
                return ControllerResultV3(ControllerStatusV3.RESERVATION_UNRESOLVED,
                                          "RESERVATION_NOT_ATTRIBUTED", claim, reservation)
        except GitHubJournalV3Error as exc:
            # Decoder/identity rejection is distinct from unavailable observation.
            status = (ControllerStatusV3.RESERVATION_UNRESOLVED if reserving else
                      ControllerStatusV3.CLAIM_UNRESOLVED
                      if claiming or str(exc).startswith("JOURNAL_READ_")
                      else ControllerStatusV3.CLAIM_REJECTED)
            return ControllerResultV3(status, "JOURNAL_OPERATION_REFUSED", claim, reservation)
        except Exception:
            status = (ControllerStatusV3.RESERVATION_UNRESOLVED if reserving
                      else ControllerStatusV3.CLAIM_UNRESOLVED)
            return ControllerResultV3(status, "JOURNAL_OPERATION_UNRESOLVED", claim, reservation)
        snapshot = reservation.snapshot
        request = InitialDispatchRequestV3(
            self.journal.repository, request_id, snapshot.record.attempt.attempt_id,
            claim_ref, snapshot.record.control.reservation_id, 1,
            target.worker_workflow, target.execution_ref, target.executable_sha,
        )
        try:
            response = self.dispatch_transport.dispatch(request)
        except Exception:
            return ControllerResultV3(ControllerStatusV3.DISPATCH_UNRESOLVED,
                                      "DISPATCH_RESPONSE_UNAVAILABLE", claim, reservation, request)
        observed = (type(response) is InitialDispatchResultV3
                    and response.status is InitialDispatchStatusV3.OBSERVED
                    and type(response.run_id) is int and response.run_id > 0)
        return ControllerResultV3(
            ControllerStatusV3.DISPATCH_OBSERVED if observed else ControllerStatusV3.DISPATCH_UNRESOLVED,
            "INJECTED_RESPONSE_NOT_WORKER_AUTHENTICATION", claim, reservation, request,
            response if type(response) is InitialDispatchResultV3 else None,
        )
