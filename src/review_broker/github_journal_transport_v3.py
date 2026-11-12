"""Injected transport and authority contracts for the experimental v3 journal."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Mapping, Protocol

from .journal_record_v3 import JournalRecordV3, WorkerIdentityV3


JOURNAL_REPOSITORY_QUERY_V3 = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id nameWithOwner}}"

JOURNAL_COMMIT_MESSAGE_V3 = "review-broker: experimental v3 journal transition"

JOURNAL_UPDATE_REFS_QUERY_V3 = "mutation($repositoryId:ID!,$name:GitRefname!,$beforeOid:GitObjectID!,$afterOid:GitObjectID!,$force:Boolean!){updateRefs(input:{repositoryId:$repositoryId,refUpdates:[{name:$name,beforeOid:$beforeOid,afterOid:$afterOid,force:$force}]}){clientMutationId}}"


def encode_journal_http_payload_v3(payload):
    return json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8')


def decode_journal_http_payload_v3(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('JOURNAL_REQUEST_DUPLICATE_JSON_FIELD')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique)


class ReadStatusV3(str, Enum):
    FOUND = "FOUND"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"


class CreateRefStatusV3(str, Enum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    UNKNOWN = "UNKNOWN"


class OutcomeStatusV3(str, Enum):
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class TransportSnapshotV3:
    commit_sha: str
    parent_sha: str
    journal_bytes: bytes


@dataclass(frozen=True)
class ReadResultV3:
    status: ReadStatusV3
    snapshot: TransportSnapshotV3 | None = None


@dataclass(frozen=True)
class CreateRefResultV3:
    status: CreateRefStatusV3
    writer_evidence_id: str | None = None


@dataclass(frozen=True)
class GraphQLUpdateResultV3:
    http_status: int | None
    errors: tuple[str, ...]
    writer_evidence_id: str | None = None
    expected_old_rejected: bool = False
    rejection_evidence_id: str | None = None


@dataclass(frozen=True)
class GraphQLRefUpdateV3:
    repository_id: str
    name: str
    before_oid: str
    after_oid: str
    force: bool = False


class GitHubTransportV3(Protocol):
    """Narrow injected transport; no concrete network implementation is activated."""

    def read_claim(self, claim_ref: str) -> ReadResultV3: ...

    def read_journal_commit(self, commit_sha: str) -> ReadResultV3: ...

    def create_journal_commit(self, parent_sha: str, journal_bytes: bytes) -> str: ...

    def create_ref(self, claim_ref: str, commit_sha: str) -> CreateRefResultV3: ...

    def update_ref(self, update: GraphQLRefUpdateV3) -> GraphQLUpdateResultV3: ...


class AdmissionAuthorityV3(Protocol):
    def evidence_id(self, *, repository: str, request: Mapping[str, object],
                    admission: Mapping[str, object]) -> str | None: ...

    def permits_evidence(self, *, repository: str, request_id: str,
                         admission: Mapping[str, object],
                         evidence_id: str) -> bool: ...


class WorkerAuthorityV3(Protocol):
    def evidence_id(self, *, repository: str, request_id: str, attempt_id: str,
                    reservation_id: str, generation: int,
                    worker: WorkerIdentityV3) -> str | None: ...


class MutationAuthorityV3(Protocol):
    def permits(self, update: GraphQLRefUpdateV3, evidence_id: str) -> bool: ...


class RejectionAuthorityV3(Protocol):
    def permits(self, update: GraphQLRefUpdateV3, evidence_id: str) -> bool: ...


class PredecessorAuthorityV3(Protocol):
    def evidence_id(self, *, repository: str, claim_ref: str,
                    snapshot: TransportSnapshotV3) -> str | None: ...

    def permits_evidence(self, *, repository: str, claim_ref: str,
                         snapshot: TransportSnapshotV3,
                         evidence_id: str) -> bool: ...


class PacketAuthorityV3(Protocol):
    def permits(self, *, snapshot: "VerifiedJournalSnapshotV3",
                packet_evidence_id: str, reservation_id: str,
                generation: int, worker: WorkerIdentityV3) -> bool: ...


class FailureAuthorityV3(Protocol):
    def permits(self, receipt: Mapping[str, object]) -> bool: ...


@dataclass(frozen=True)
class VerifiedJournalSnapshotV3:
    repository: str
    repository_node_id: str
    claim_ref: str
    commit_sha: str
    parent_sha: str
    journal_bytes: bytes
    record: JournalRecordV3
    writer_evidence_id: str | None = None


@dataclass(frozen=True)
class PendingWriteV3:
    repository: str
    claim_ref: str
    predecessor_sha: str | None
    intended_sha: str
    request_id: str
    admission: Mapping[str, object]
    mutation_kind: str
    writer_evidence_id: str | None = None
    application_errors: tuple[str, ...] = ()
    expected_old_rejected: bool = False
    rejection_evidence_id: str | None = None
    creation_evidence_id: str | None = None
    creation_may_reuse_existing: bool = False


@dataclass(frozen=True)
class JournalOutcomeV3:
    status: OutcomeStatusV3
    snapshot: VerifiedJournalSnapshotV3 | None = None
    pending: PendingWriteV3 | None = None
    reason: str | None = None
