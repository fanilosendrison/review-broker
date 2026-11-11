"""Strict reconstruction of experimental v3 pre-claim admission evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .admission_v3 import (
    AdmissionV3CandidateError, _evidence, _receipt_id, _valid_request_id,
    _valid_sha, _valid_source_id, _validate_admitted_subset,
)
from .identity import artifact_identity, canonical_bytes
from .request_v3 import (
    inline_rendered_bound_v3, parse_issue_envelope_v3, request_identity_v3,
)
from .review_intent_v3 import review_intent_identity_v3


def validate_journal_admission_v3(
    value: Mapping[str, object], origin_body_bytes: bytes,
) -> dict[str, object]:
    """Validate closed candidate evidence before a future journal integration."""
    fields = {
        "request_id", "admission_evidence_id", "review_intent_id",
        "canonical_request", "broker_issue_id", "requester_id",
        "origin_evidence_id", "requester_authorization_evidence_id",
        "history_evidence_id", "history_scan_boundary", "repository_id",
        "resolved_subject", "source_admission_id", "origin_observation",
        "source_observation", "requester_authorization", "history_observation",
        "reference_ids",
    }
    actual_fields = set(value) if isinstance(value, dict) else set()
    optional={"reference_admissions","issue_reference_admissions","source_app_scope_evidence_id"}
    if not fields <= actual_fields or actual_fields - fields - optional:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_FIELDS_INVALID")
    request = value["canonical_request"]
    if not isinstance(request, dict):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_REQUEST_INVALID")
    request_id = request_identity_v3(request)
    intent_id = review_intent_identity_v3(request)
    reference_admissions = value.get("reference_admissions", [])
    issue_admissions = value.get("issue_reference_admissions", [])
    _validate_admitted_subset(request, allow_git_file=bool(reference_admissions),
                              allow_issue_reference=bool(issue_admissions))
    if value["request_id"] != request_id or value["review_intent_id"] != intent_id:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_REQUEST_IDENTITY_MISMATCH")
    references = tuple(reference["id"] for reference in request["references"])
    if value["reference_ids"] != list(references):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_REFERENCE_MISMATCH")
    origin, source, requester, history, resolved = (
        value["origin_observation"], value["source_observation"],
        value["requester_authorization"], value["history_observation"],
        value["resolved_subject"],
    )
    if not all(isinstance(item, dict) for item in (origin, source, requester, history, resolved)):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_PROVENANCE_INVALID")
    origin_fields = {"repository", "repository_id", "issue_number", "issue_id",
                     "requester_id", "requester_login_observed", "body_sha256",
                     "body_artifact_id", "observed_at", "api_source", "evidence_id"}
    source_fields = {"schema_version", "repository", "repository_id",
                     "source_authorization_evidence_id", "principal_id",
                     "installation_id", "pull_request", "pull_request_id",
                     "head_sha", "base_sha", "subject_sources",
                     "pr_observation_evidence_id"}
    resolved_fields = {"repository", "repository_id", "pull_request",
                       "pull_request_id", "head_commit"}
    requester_fields = {"schema_version", "evidence_type", "requester_id",
                        "broker_issue_id", "origin_evidence_id"}
    history_fields = {"schema_version", "evidence_type", "request_id",
                      "review_intent_id", "namespace", "scan_boundary",
                      "complete", "matching_request_ids"}
    if (set(origin) != origin_fields or set(source) != source_fields
            or set(resolved) != resolved_fields or set(requester) != requester_fields
            or set(history) != history_fields):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_PROVENANCE_FIELDS_INVALID")
    if not isinstance(origin_body_bytes, bytes):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ORIGIN_BODY_REQUIRED")
    try:
        origin_body = origin_body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ORIGIN_BODY_INVALID") from exc
    if parse_issue_envelope_v3(origin_body) != request:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ORIGIN_REQUEST_MISMATCH")
    for field in ("admission_evidence_id", "origin_evidence_id",
                  "requester_authorization_evidence_id", "history_evidence_id",
                  "source_admission_id"):
        _evidence(value[field], "JOURNAL_ADMISSION_EVIDENCE_ID_INVALID")
    if "source_app_scope_evidence_id" in value:
        _evidence(value["source_app_scope_evidence_id"], "JOURNAL_ADMISSION_SCOPE_EVIDENCE_INVALID")
    positive = (value["broker_issue_id"], value["requester_id"], value["repository_id"],
                origin.get("repository_id"), origin.get("issue_number"),
                origin.get("issue_id"), origin.get("requester_id"),
                source.get("repository_id"), source.get("installation_id"),
                source.get("pull_request"), source.get("pull_request_id"))
    subject_sources = source.get("subject_sources")
    if (any(type(item) is not int or item < 1 for item in positive)
            or not isinstance(subject_sources, list) or not subject_sources
            or any(not isinstance(item, dict)
                   or set(item) != {"source_id", "original_bytes", "rendered_bytes"}
                   or not _valid_source_id(item["source_id"])
                   or type(item["original_bytes"]) is not int
                   or not 0 <= item["original_bytes"] <= 2_000_000
                   or type(item["rendered_bytes"]) is not int
                   or item["rendered_bytes"] < 0 for item in subject_sources)
            or len({item["source_id"] for item in subject_sources}) != len(subject_sources)
            or not _valid_sha(value["history_scan_boundary"])):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_PROVENANCE_TYPE_INVALID")
    origin_receipt = {
        "schema_version": 1, "evidence_type": "github-issue-origin-observation",
        "repository": origin["repository"], "repository_id": origin["repository_id"],
        "issue_number": origin["issue_number"], "issue_id": origin["issue_id"],
        "requester_id": origin["requester_id"],
        "requester_login": origin["requester_login_observed"],
        "body": origin_body, "body_sha256": origin["body_sha256"],
        "observed_at": origin["observed_at"], "api_source": origin["api_source"],
    }
    if (hashlib.sha256(origin_body_bytes).hexdigest() != origin["body_sha256"]
            or _receipt_id(origin_receipt) != value["origin_evidence_id"]):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ORIGIN_EVIDENCE_MISMATCH")
    subject = request["subject"]
    if (requester.get("schema_version") != 1
            or requester.get("evidence_type") != "v3-requester-authorization"
            or history.get("schema_version") != 1
            or history.get("evidence_type") != "v3-initial-history-observation"
            or source.get("schema_version") != 1
            or not isinstance(source.get("principal_id"), str)
            or not source.get("principal_id")
            or not _valid_sha(source.get("base_sha"))):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_RECEIPT_CONTRACT_INVALID")
    if (origin.get("issue_id") != value["broker_issue_id"]
            or origin.get("requester_id") != value["requester_id"]
            or origin.get("evidence_id") != value["origin_evidence_id"]
            or origin.get("body_artifact_id") != "artifact:sha256:" + origin["body_sha256"]
            or requester.get("requester_id") != value["requester_id"]
            or requester.get("broker_issue_id") != value["broker_issue_id"]
            or requester.get("origin_evidence_id") != value["origin_evidence_id"]
            or _receipt_id(requester) != value["requester_authorization_evidence_id"]
            or history.get("request_id") != request_id
            or history.get("review_intent_id") != intent_id
            or history.get("namespace") != "refs/heads/review-claims-v3/"
            or history.get("scan_boundary") != value["history_scan_boundary"]
            or history.get("complete") is not True
            or not isinstance(history.get("matching_request_ids"), list)
            or any(not _valid_request_id(item) or item != request_id
                   for item in history.get("matching_request_ids", []))
            or _receipt_id(history) != value["history_evidence_id"]
            or source.get("repository_id") != value["repository_id"]
            or resolved.get("repository_id") != value["repository_id"]
            or source.get("repository") != subject["repository"]
            or source.get("repository_id") != subject["repository_id"]
            or source.get("pull_request") != subject["pull_request"]
            or source.get("head_sha") != subject["expected_head_commit"]
            or resolved.get("repository") != source.get("repository")
            or resolved.get("pull_request") != source.get("pull_request")
            or resolved.get("pull_request_id") != source.get("pull_request_id")
            or resolved.get("head_commit") != source.get("head_sha")):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_PROVENANCE_MISMATCH")
    principal=source["principal_id"]
    if "|scope=" in principal:
        scope_id=principal.rsplit("|scope=",1)[1]
        if value.get("source_app_scope_evidence_id")!=scope_id:
            raise AdmissionV3CandidateError("JOURNAL_ADMISSION_SOURCE_SCOPE_MISMATCH")
    elif "source_app_scope_evidence_id" in value:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_SOURCE_SCOPE_UNBOUND")
    source_auth = {
        "schema_version": 1, "evidence_type": "v3-source-repository-authorization",
        "repository": source["repository"], "repository_id": source["repository_id"],
        "principal_id": source["principal_id"], "installation_id": source["installation_id"],
    }
    pr_receipt = {
        "schema_version": 1, "evidence_type": "v3-pull-request-observation",
        "repository": source["repository"], "repository_id": source["repository_id"],
        "pull_request": source["pull_request"], "pull_request_id": source["pull_request_id"],
        "head_sha": source["head_sha"], "base_sha": source["base_sha"],
        "subject_sources": source["subject_sources"],
    }
    if (_receipt_id(source_auth) != source["source_authorization_evidence_id"]
            or _receipt_id(pr_receipt) != source["pr_observation_evidence_id"]):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_SOURCE_EVIDENCE_MISMATCH")
    inline_bound = sum(
        inline_rendered_bound_v3(item["source"]["text"])
        for item in request["references"] if item["source"]["kind"] == "inline")
    if (len(subject_sources) + len(references) > 999
            or sum(item["rendered_bytes"] for item in subject_sources)
            + inline_bound + len(canonical_bytes(request)) + 1_000_000 > 8_000_000):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_PACKET_BOUND_EXCEEDED")
    source_id = _receipt_id(source)
    if source_id != value["source_admission_id"]:
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_SOURCE_IDENTITY_MISMATCH")
    git_references = [item for item in request["references"] if item["source"]["kind"] == "git_file"]
    if len(reference_admissions) != len(git_references):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_GIT_FILE_COVERAGE_MISMATCH")
    git_fields = {"schema_version", "evidence_type", "repository", "repository_id",
        "commit_sha", "root_tree_sha", "path", "git_blob_oid", "original_byte_length",
        "sha256", "observed_at", "api_source", "qualification", "authority_evidence_id",
        "installation_id", "evidence_id"}
    for reference, observed in zip(git_references, reference_admissions):
        if (not isinstance(observed, dict) or set(observed) != git_fields
                or observed.get("schema_version") != 1
                or observed.get("evidence_type") != "github-git-file-observation"
                or not _valid_sha(observed.get("commit_sha"))
                or not _valid_sha(observed.get("root_tree_sha"))
                or not _valid_sha(observed.get("git_blob_oid"))
                or type(observed.get("original_byte_length")) is not int
                or not 0 <= observed["original_byte_length"] <= 2_000_000
                or not isinstance(observed.get("sha256"), str) or len(observed["sha256"]) != 64
                or observed.get("repository") != subject["repository"]
                or observed.get("repository_id") != subject["repository_id"]
                or observed.get("commit_sha") != reference["source"]["commit"]
                or observed.get("path") != reference["source"]["path"]
                or observed.get("qualification") != "AUTHENTICATED_READ_ONLY"
                or observed.get("authority_evidence_id") != source["source_authorization_evidence_id"]
                or observed.get("installation_id") != source["installation_id"]):
            raise AdmissionV3CandidateError("JOURNAL_ADMISSION_GIT_FILE_MISMATCH")
        basis = {key: item for key, item in observed.items() if key != "evidence_id"}
        if _receipt_id(basis) != observed.get("evidence_id"):
            raise AdmissionV3CandidateError("JOURNAL_ADMISSION_GIT_FILE_EVIDENCE_MISMATCH")
        if (request["atomicity"] is True
                and observed.get("commit_sha") != subject["expected_head_commit"]):
            raise AdmissionV3CandidateError("JOURNAL_ADMISSION_GIT_FILE_ATOMICITY_MISMATCH")
        expected = reference["source"].get("expected_sha256")
        if expected is not None and observed.get("sha256") != expected:
            raise AdmissionV3CandidateError("JOURNAL_ADMISSION_GIT_FILE_DIGEST_MISMATCH")
    mutable_refs=[item for item in request["references"] if item["source"]["kind"] in {"github_issue_body","github_issue_comment"}]
    if len(issue_admissions)!=len(mutable_refs): raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ISSUE_REFERENCE_COVERAGE_MISMATCH")
    issue_fields={"schema_version","evidence_type","source_kind","repository","repository_id","selector_id","issue_id","issue_number","comment_id","author_id","original_byte_length","sha256","observed_at","updated_at","api_source","qualification","authority_evidence_id","installation_id","evidence_id"}
    for reference, observed in zip(mutable_refs,issue_admissions):
        expected=reference["source"].get("expected_sha256")
        if (not isinstance(observed,dict) or set(observed)!=issue_fields
                or observed.get("schema_version")!=1 or observed.get("evidence_type")!="github-issue-reference-observation"
                or type(observed.get("issue_id")) is not int or observed["issue_id"]<1
                or type(observed.get("author_id")) is not int or observed["author_id"]<1
                or type(observed.get("original_byte_length")) is not int or not 0<=observed["original_byte_length"]<=2_000_000
                or not isinstance(observed.get("sha256"),str) or len(observed["sha256"])!=64
                or (expected is not None and observed.get("sha256")!=expected)
                or observed.get("source_kind")!=reference["source"]["kind"]
                or observed.get("repository")!=subject["repository"] or observed.get("repository_id")!=subject["repository_id"]
                or observed.get("selector_id")!=reference["source"].get("issue",reference["source"].get("comment_id"))
                or observed.get("qualification")!="AUTHENTICATED_READ_ONLY"
                or observed.get("authority_evidence_id")!=source["source_authorization_evidence_id"]
                or observed.get("installation_id")!=source["installation_id"]): raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ISSUE_REFERENCE_MISMATCH")
        basis={k:v for k,v in observed.items() if k!="evidence_id"}
        if _receipt_id(basis)!=observed.get("evidence_id"): raise AdmissionV3CandidateError("JOURNAL_ADMISSION_ISSUE_REFERENCE_EVIDENCE_MISMATCH")
    evidence_basis = {
        "schema_version": 1, "evidence_type": "review-request-v3-preclaim-admission",
        "request_id": request_id, "review_intent_id": intent_id,
        "origin_evidence_id": value["origin_evidence_id"],
        "broker_issue_id": value["broker_issue_id"], "requester_id": value["requester_id"],
        "requester_authorization_evidence_id": value["requester_authorization_evidence_id"],
        "source_admission_id": source_id, "history_evidence_id": value["history_evidence_id"],
        "history_scan_boundary": value["history_scan_boundary"],
        "reference_ids": list(references),
    }
    if reference_admissions: evidence_basis["reference_admissions"] = reference_admissions
    if issue_admissions: evidence_basis["issue_reference_admissions"] = issue_admissions
    if "source_app_scope_evidence_id" in value: evidence_basis["source_app_scope_evidence_id"] = value["source_app_scope_evidence_id"]
    if value["admission_evidence_id"] != _receipt_id(evidence_basis):
        raise AdmissionV3CandidateError("JOURNAL_ADMISSION_EVIDENCE_MISMATCH")
    return json.loads(canonical_bytes(value))
