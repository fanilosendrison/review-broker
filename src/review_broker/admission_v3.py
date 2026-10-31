"""Read-only pre-claim admission for the experimental initial/inline v3 subset."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Protocol

from .github_issue_origin_v3 import GitHubIssueOriginObservationV3, GitHubIssueOriginReaderV3
from .github_git_file_v3 import GitHubGitFileObservationV3, GitHubGitFileReaderV3
from .git_file_admission_v3 import GitFileAdmissionV3Error, acquire_git_file_admissions_v3
from .identity import artifact_identity, canonical_bytes
from .request_v3 import (
    inline_rendered_bound_v3, parse_issue_envelope_v3, request_identity_v3,
)
from .review_intent_v3 import review_intent_identity_v3
class AdmissionV3CandidateError(ValueError):
    """The candidate request cannot cross the bounded pre-claim boundary."""
def _evidence(value: object, marker: str) -> str:
    if (not isinstance(value, str) or not value.startswith("artifact:sha256:")
            or len(value) != 80
            or any(character not in "0123456789abcdef" for character in value[16:])):
        raise AdmissionV3CandidateError(marker)
    return value


def _receipt_id(value: Mapping[str, object]) -> str:
    return artifact_identity(canonical_bytes(value) + b"\n")


def _valid_sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 40
            and all(character in "0123456789abcdef" for character in value))


def _valid_source_id(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 4 and value[0] == "S"
            and all(character in "0123456789" for character in value[1:])
            and value != "S000")


def _valid_request_id(value: object) -> bool:
    return (isinstance(value, str) and value.startswith("request:sha256:")
            and len(value) == 79
            and all(character in "0123456789abcdef" for character in value[15:]))


@dataclass(frozen=True)
class RequesterAuthorizationV3:
    requester_id: int
    broker_issue_id: int
    evidence_id: str


class RequesterAuthorizationAuthorityV3(Protocol):
    def authorize(self, requester_id: int, broker_issue_id: int,
                  origin_evidence_id: str) -> RequesterAuthorizationV3 | None: ...


@dataclass(frozen=True)
class SubjectSourceFeasibilityV3:
    source_id: str
    original_bytes: int
    rendered_bytes: int


@dataclass(frozen=True)
class PullRequestObservationV3:
    repository: str
    repository_id: int
    pull_request: int
    pull_request_id: int
    head_sha: str
    base_sha: str
    subject_sources: tuple[SubjectSourceFeasibilityV3, ...]
    evidence_id: str


class PullRequestObservationAuthorityV3(Protocol):
    def observe(self, repository: str, repository_id: int,
                pull_request: int) -> PullRequestObservationV3 | None: ...


@dataclass(frozen=True)
class SourceRepositoryAuthorizationV3:
    repository: str
    repository_id: int
    principal_id: str
    installation_id: int
    evidence_id: str


class SourceRepositoryAuthorityV3(Protocol):
    def authorize(self, repository: str,
                  repository_id: int) -> SourceRepositoryAuthorizationV3 | None: ...


@dataclass(frozen=True)
class InitialHistoryDecisionV3:
    request_id: str
    review_intent_id: str
    namespace: str
    scan_boundary: str
    complete: bool
    matching_request_ids: tuple[str, ...]
    evidence_id: str


class InitialHistoryAuthorityV3(Protocol):
    def decide(self, request_id: str, review_intent_id: str,
               namespace: str) -> InitialHistoryDecisionV3 | None: ...


@dataclass(frozen=True)
class PreclaimAdmissionV3:
    canonical_request_bytes: bytes
    request_id: str
    review_intent_id: str
    broker_issue_id: int
    requester_id: int
    requester_login_observed: str
    repository: str
    repository_id: int
    pull_request: int
    pull_request_id: int
    head_sha: str
    source_admission_id: str
    reference_ids: tuple[str, ...]
    origin_body_bytes: bytes
    origin_provenance_bytes: bytes
    source_provenance_bytes: bytes
    requester_provenance_bytes: bytes
    history_provenance_bytes: bytes
    origin_evidence_id: str
    requester_authorization_evidence_id: str
    history_evidence_id: str
    history_scan_boundary: str
    admission_evidence_id: str
    git_file_observations: tuple[GitHubGitFileObservationV3, ...] = ()

    @property
    def request(self) -> dict[str, object]:
        return json.loads(self.canonical_request_bytes)

    def journal_admission(self) -> dict[str, object]:
        value = {
            "request_id": self.request_id,
            "admission_evidence_id": self.admission_evidence_id,
            "review_intent_id": self.review_intent_id,
            "canonical_request": self.request,
            "broker_issue_id": self.broker_issue_id,
            "requester_id": self.requester_id,
            "origin_evidence_id": self.origin_evidence_id,
            "requester_authorization_evidence_id": self.requester_authorization_evidence_id,
            "history_evidence_id": self.history_evidence_id,
            "history_scan_boundary": self.history_scan_boundary,
            "repository_id": self.repository_id,
            "resolved_subject": {
                "repository": self.repository, "repository_id": self.repository_id,
                "pull_request": self.pull_request, "pull_request_id": self.pull_request_id,
                "head_commit": self.head_sha,
            },
            "source_admission_id": self.source_admission_id,
            "origin_observation": json.loads(self.origin_provenance_bytes),
            "source_observation": json.loads(self.source_provenance_bytes),
            "requester_authorization": json.loads(self.requester_provenance_bytes),
            "history_observation": json.loads(self.history_provenance_bytes),
            "reference_ids": list(self.reference_ids),
        }
        if self.git_file_observations:
            value["reference_admissions"] = [item.provenance_basis() | {"evidence_id": item.evidence_id}
                                                for item in self.git_file_observations]
        return value


def _validate_admitted_subset(request: Mapping[str, object], *, allow_git_file: bool = False) -> None:
    operation = request["review_operation"]["kind"]
    if operation == "changed_head":
        raise AdmissionV3CandidateError("CHANGED_HEAD_ADMISSION_NOT_YET_QUALIFIED")
    if operation == "repeat_same_head":
        raise AdmissionV3CandidateError("REPEAT_SAME_HEAD_ADMISSION_NOT_YET_QUALIFIED")
    remote = {item["source"]["kind"] for item in request["references"]
              if item["source"]["kind"] != "inline"}
    if request["atomicity"] is True and remote.intersection(
        {"github_issue_body", "github_issue_comment"}
    ):
        raise AdmissionV3CandidateError("ATOMICITY_MUTABLE_REFERENCE_FORBIDDEN")
    if remote - ({"git_file"} if allow_git_file else set()):
        raise AdmissionV3CandidateError("REMOTE_SOURCE_ADMISSION_NOT_YET_QUALIFIED")


def _subject_sources(pr: PullRequestObservationV3) -> list[dict[str, object]]:
    return [{"source_id": item.source_id, "original_bytes": item.original_bytes,
             "rendered_bytes": item.rendered_bytes} for item in pr.subject_sources]


def admit_initial_inline_v3(
    origin_reader: GitHubIssueOriginReaderV3, *, broker_issue_number: int,
    expected_broker_issue_id: int, expected_requester_id: int,
    requester_authority: RequesterAuthorizationAuthorityV3,
    pr_authority: PullRequestObservationAuthorityV3,
    source_authority: SourceRepositoryAuthorityV3,
    history_authority: InitialHistoryAuthorityV3,
    git_file_readers: Mapping[str, GitHubGitFileReaderV3] | None = None,
) -> PreclaimAdmissionV3:
    """Admit no claim; return retained evidence for the bounded candidate subset."""
    if type(origin_reader) is not GitHubIssueOriginReaderV3:
        raise AdmissionV3CandidateError("TRUSTED_ORIGIN_READER_REQUIRED")
    if any(type(value) is not int or value < 1 for value in (
        broker_issue_number, expected_broker_issue_id, expected_requester_id
    )):
        raise AdmissionV3CandidateError("EXPECTED_ORIGIN_IDENTITY_INVALID")
    try:
        origin = origin_reader.observe(broker_issue_number)
    except Exception:
        raise AdmissionV3CandidateError("ORIGIN_ISSUE_OBSERVATION_UNAVAILABLE") from None
    if (not isinstance(origin, GitHubIssueOriginObservationV3)
            or any(type(value) is not int for value in (
                origin.issue_id, origin.requester_id, origin.repository_id))):
        raise AdmissionV3CandidateError("ORIGIN_IDENTITY_TYPE_INVALID")
    if origin.issue_id != expected_broker_issue_id:
        raise AdmissionV3CandidateError("ORIGIN_ISSUE_ID_MISMATCH")
    if origin.requester_id != expected_requester_id:
        raise AdmissionV3CandidateError("ORIGIN_REQUESTER_ID_MISMATCH")
    if origin.body is None:
        raise AdmissionV3CandidateError("ORIGIN_REQUEST_BODY_UNAVAILABLE")
    body_bytes = origin.body.encode("utf-8")
    if hashlib.sha256(body_bytes).hexdigest() != origin.body_sha256:
        raise AdmissionV3CandidateError("ORIGIN_BODY_IDENTITY_MISMATCH")
    origin_evidence = _evidence(origin.evidence_id, "ORIGIN_EVIDENCE_INVALID")
    origin_receipt = {
        "schema_version": 1, "evidence_type": "github-issue-origin-observation",
        "repository": origin.repository, "repository_id": origin.repository_id,
        "issue_number": origin.issue_number, "issue_id": origin.issue_id,
        "requester_id": origin.requester_id, "requester_login": origin.requester_login,
        "body": origin.body, "body_sha256": origin.body_sha256,
        "observed_at": origin.observed_at, "api_source": origin.api_source,
    }
    if _receipt_id(origin_receipt) != origin_evidence:
        raise AdmissionV3CandidateError("ORIGIN_EVIDENCE_MISMATCH")
    origin_basis = {
        "repository": origin.repository, "repository_id": origin.repository_id,
        "issue_number": origin.issue_number, "issue_id": origin.issue_id,
        "requester_id": origin.requester_id,
        "requester_login_observed": origin.requester_login,
        "body_sha256": origin.body_sha256,
        "body_artifact_id": artifact_identity(body_bytes),
        "observed_at": origin.observed_at, "api_source": origin.api_source,
        "evidence_id": origin_evidence,
    }
    request = parse_issue_envelope_v3(origin.body)
    request_id, intent_id = request_identity_v3(request), review_intent_identity_v3(request)
    _validate_admitted_subset(request, allow_git_file=git_file_readers is not None)
    try:
        authorization = requester_authority.authorize(
            origin.requester_id, origin.issue_id, origin_evidence)
    except Exception:
        authorization = None
    if (not isinstance(authorization, RequesterAuthorizationV3)
            or type(authorization.requester_id) is not int
            or type(authorization.broker_issue_id) is not int
            or authorization.requester_id != origin.requester_id
            or authorization.broker_issue_id != origin.issue_id):
        raise AdmissionV3CandidateError("REQUESTER_AUTHORIZATION_UNTRUSTED")
    requester_evidence = _evidence(
        authorization.evidence_id, "REQUESTER_AUTHORIZATION_EVIDENCE_INVALID")
    requester_receipt = {
        "schema_version": 1, "evidence_type": "v3-requester-authorization",
        "requester_id": authorization.requester_id,
        "broker_issue_id": authorization.broker_issue_id,
        "origin_evidence_id": origin_evidence,
    }
    if _receipt_id(requester_receipt) != requester_evidence:
        raise AdmissionV3CandidateError("REQUESTER_AUTHORIZATION_EVIDENCE_MISMATCH")
    subject = request["subject"]
    try:
        source = source_authority.authorize(subject["repository"], subject["repository_id"])
    except Exception:
        source = None
    if (not isinstance(source, SourceRepositoryAuthorizationV3)
            or type(source.repository_id) is not int
            or type(source.installation_id) is not int or source.installation_id < 1
            or not isinstance(source.principal_id, str) or not source.principal_id
            or source.repository != subject["repository"]
            or source.repository_id != subject["repository_id"]):
        raise AdmissionV3CandidateError("SOURCE_REPOSITORY_UNAUTHORIZED")
    source_evidence = _evidence(source.evidence_id, "SOURCE_AUTHORIZATION_EVIDENCE_INVALID")
    source_receipt = {
        "schema_version": 1, "evidence_type": "v3-source-repository-authorization",
        "repository": source.repository, "repository_id": source.repository_id,
        "principal_id": source.principal_id, "installation_id": source.installation_id,
    }
    if _receipt_id(source_receipt) != source_evidence:
        raise AdmissionV3CandidateError("SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH")
    try:
        pr = pr_authority.observe(
            subject["repository"], subject["repository_id"], subject["pull_request"])
    except Exception:
        pr = None
    if not isinstance(pr, PullRequestObservationV3):
        raise AdmissionV3CandidateError("PULL_REQUEST_OBSERVATION_UNAVAILABLE")
    if (pr.repository != subject["repository"] or type(pr.repository_id) is not int
            or type(pr.pull_request) is not int or pr.repository_id != subject["repository_id"]
            or pr.pull_request != subject["pull_request"]
            or type(pr.pull_request_id) is not int or pr.pull_request_id < 1
            or not isinstance(pr.subject_sources, tuple) or not pr.subject_sources
            or any(not isinstance(item, SubjectSourceFeasibilityV3)
                   or not _valid_source_id(item.source_id)
                   or type(item.original_bytes) is not int or item.original_bytes < 0
                   or type(item.rendered_bytes) is not int or item.rendered_bytes < 0
                   for item in pr.subject_sources)
            or len({item.source_id for item in pr.subject_sources}) != len(pr.subject_sources)
            or pr.head_sha != subject["expected_head_commit"]
            or not _valid_sha(pr.head_sha) or not _valid_sha(pr.base_sha)):
        raise AdmissionV3CandidateError("PULL_REQUEST_IDENTITY_MISMATCH")
    pr_evidence = _evidence(pr.evidence_id, "PULL_REQUEST_EVIDENCE_INVALID")
    pr_receipt = {
        "schema_version": 1, "evidence_type": "v3-pull-request-observation",
        "repository": pr.repository, "repository_id": pr.repository_id,
        "pull_request": pr.pull_request, "pull_request_id": pr.pull_request_id,
        "head_sha": pr.head_sha, "base_sha": pr.base_sha,
        "subject_sources": _subject_sources(pr),
    }
    if _receipt_id(pr_receipt) != pr_evidence:
        raise AdmissionV3CandidateError("PULL_REQUEST_EVIDENCE_MISMATCH")
    try:
        history = history_authority.decide(
            request_id, intent_id, "refs/heads/review-claims-v3/")
    except Exception:
        history = None
    if (not isinstance(history, InitialHistoryDecisionV3)
            or history.request_id != request_id or history.review_intent_id != intent_id
            or history.namespace != "refs/heads/review-claims-v3/"
            or not _valid_sha(history.scan_boundary) or history.complete is not True
            or not isinstance(history.matching_request_ids, tuple)
            or any(not _valid_request_id(item) for item in history.matching_request_ids)):
        raise AdmissionV3CandidateError("INITIAL_HISTORY_UNTRUSTED")
    history_evidence = _evidence(history.evidence_id, "INITIAL_HISTORY_EVIDENCE_INVALID")
    history_receipt = {
        "schema_version": 1, "evidence_type": "v3-initial-history-observation",
        "request_id": history.request_id, "review_intent_id": history.review_intent_id,
        "namespace": history.namespace, "scan_boundary": history.scan_boundary,
        "complete": history.complete,
        "matching_request_ids": list(history.matching_request_ids),
    }
    if _receipt_id(history_receipt) != history_evidence:
        raise AdmissionV3CandidateError("INITIAL_HISTORY_EVIDENCE_MISMATCH")
    if any(item != request_id for item in history.matching_request_ids):
        raise AdmissionV3CandidateError("INITIAL_REVIEW_INTENT_ALREADY_EXISTS")
    source_basis = {
        "schema_version": 1, "repository": source.repository,
        "repository_id": source.repository_id,
        "source_authorization_evidence_id": source_evidence,
        "principal_id": source.principal_id, "installation_id": source.installation_id,
        "pull_request": pr.pull_request, "pull_request_id": pr.pull_request_id,
        "head_sha": pr.head_sha, "base_sha": pr.base_sha,
        "subject_sources": _subject_sources(pr),
        "pr_observation_evidence_id": pr_evidence,
    }
    source_admission_id = _receipt_id(source_basis)
    reference_ids = tuple(reference["id"] for reference in request["references"])
    inline_bound = sum(
        inline_rendered_bound_v3(item["source"]["text"])
        for item in request["references"] if item["source"]["kind"] == "inline")
    if any(item.original_bytes > 2_000_000 for item in pr.subject_sources):
        raise AdmissionV3CandidateError("EVENTUAL_SUBJECT_SOURCE_BYTES_EXCEEDED")
    if len(pr.subject_sources) + len(reference_ids) > 999:
        raise AdmissionV3CandidateError("EVENTUAL_SOURCE_COUNT_EXCEEDED")
    eventual = (sum(item.rendered_bytes for item in pr.subject_sources) + inline_bound
                + len(canonical_bytes(request)) + 1_000_000)
    if eventual > 8_000_000:
        raise AdmissionV3CandidateError("EVENTUAL_RENDERED_PACKET_EXCEEDED")
    try: observations = acquire_git_file_admissions_v3(
        request, subject, git_file_readers, source_evidence, source.installation_id)
    except GitFileAdmissionV3Error as exc: raise AdmissionV3CandidateError(str(exc)) from None
    reference_admissions = [item.provenance_basis() | {"evidence_id": item.evidence_id}
                            for item in observations]
    evidence_basis = {
        "schema_version": 1, "evidence_type": "review-request-v3-preclaim-admission",
        "request_id": request_id, "review_intent_id": intent_id,
        "origin_evidence_id": origin_evidence, "broker_issue_id": origin.issue_id,
        "requester_id": origin.requester_id,
        "requester_authorization_evidence_id": requester_evidence,
        "source_admission_id": source_admission_id,
        "history_evidence_id": history_evidence,
        "history_scan_boundary": history.scan_boundary,
        "reference_ids": list(reference_ids),
    }
    if reference_admissions:
        evidence_basis["reference_admissions"] = reference_admissions
    return PreclaimAdmissionV3(
        canonical_bytes(request), request_id, intent_id, origin.issue_id,
        origin.requester_id, origin.requester_login, pr.repository,
        pr.repository_id, pr.pull_request, pr.pull_request_id, pr.head_sha,
        source_admission_id, reference_ids, body_bytes, canonical_bytes(origin_basis),
        canonical_bytes(source_basis), canonical_bytes(requester_receipt),
        canonical_bytes(history_receipt), origin_evidence, requester_evidence,
        history_evidence, history.scan_boundary, _receipt_id(evidence_basis), observations,
    )
