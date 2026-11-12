"""Shared candidate ReviewRequest v3 fixtures; no live authentication claims."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.request import Request

from review_broker.admission_v3 import (
    InitialHistoryDecisionV3, PullRequestObservationV3,
    RequesterAuthorizationV3, SourceRepositoryAuthorizationV3,
    SubjectSourceFeasibilityV3,
)
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_issue_origin_v3 import GitHubIssueOriginReaderV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.request_v3 import build_issue_envelope_v3

REPOSITORY = "fanilosendrison/review-broker"
REPOSITORY_ID = 1433701208
HEAD = "a" * 40
def evidence(value):
    return artifact_identity(canonical_bytes(value) + b"\n")
REQUEST = {
    "schema_version": 3,
    "subject": {
        "kind": "github_pr", "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID, "pull_request": 62,
        "expected_head_commit": HEAD,
    },
    "mission": {
        "id": "reference-contract-review", "objective": "Falsify the candidate.",
        "instructions": "Use only packet-bound sources.", "criteria": ["Find gaps."],
    },
    "reviewer": {
        "backend": "codex-cli", "model": "gpt-5.6-sol", "reasoning_effort": "xhigh",
    },
    "atomicity": False,
    "references": [],
    "review_operation": {"kind": "initial"},
}


def request(**changes):
    value = {**REQUEST, **changes}
    value["subject"] = dict(value["subject"])
    value["mission"] = dict(value["mission"])
    value["reviewer"] = dict(value["reviewer"])
    if isinstance(value["references"], list):
        value["references"] = [
            {**item, "source": dict(item["source"])} for item in value["references"]
        ]
    value["review_operation"] = dict(value["review_operation"])
    return value


class OriginApi:
    def __init__(self, value=None, *, issue_id=6106789428,
                 requester_id=30498238, login="owner"):
        self.body = build_issue_envelope_v3(value or request())
        self.issue_id, self.requester_id, self.login = issue_id, requester_id, login

    def __call__(self, request_value: Request) -> HttpResponseV3:
        if request_value.full_url.endswith("/issues/51"):
            value = {"id": self.issue_id, "number": 51, "body": self.body,
                     "user": {"id": self.requester_id, "login": self.login}}
        else:
            value = {"id": REPOSITORY_ID, "full_name": REPOSITORY}
        return HttpResponseV3(200, json.dumps(value).encode(), {})


def origin(value=None, *, issue_id=6106789428, requester_id=30498238,
           login="owner"):
    api = OriginApi(value, issue_id=issue_id, requester_id=requester_id, login=login)
    return GitHubIssueOriginReaderV3(
        "token", REPOSITORY, REPOSITORY_ID, executor=api,
        clock=lambda: datetime(2026, 10, 31, tzinfo=timezone.utc),
    )


class RequesterAuthority:
    def __init__(self, trusted=True): self.trusted = trusted
    def authorize(self, requester_id, broker_issue_id, origin_evidence_id):
        basis = {"schema_version": 1, "evidence_type": "v3-requester-authorization",
                 "requester_id": requester_id, "broker_issue_id": broker_issue_id,
                 "origin_evidence_id": origin_evidence_id}
        return (RequesterAuthorizationV3(
            requester_id, broker_issue_id, evidence(basis)
        ) if self.trusted else None)


class SourceAuthority:
    def __init__(self, trusted=True): self.trusted = trusted
    def authorize(self, repository, repository_id):
        basis = {"schema_version": 1,
                 "evidence_type": "v3-source-repository-authorization",
                 "repository": repository, "repository_id": repository_id,
                 "principal_id": "github-app:source", "installation_id": 123}
        return (SourceRepositoryAuthorizationV3(
                    repository, repository_id, "github-app:source", 123,
                    evidence(basis)) if self.trusted else None)


class PrAuthority:
    def __init__(self, *, repository_id=REPOSITORY_ID, head=HEAD, number=62,
                 source_count=2, rendered_bytes=1000, original_bytes=100):
        self.repository_id, self.head, self.number = repository_id, head, number
        self.sources = tuple(
            SubjectSourceFeasibilityV3(f"S{index:03d}", original_bytes, rendered_bytes)
            for index in range(1, source_count + 1)
        )
    def observe(self, repository, repository_id, pull_request):
        basis = {"schema_version": 1,
                 "evidence_type": "v3-pull-request-observation",
                 "repository": repository, "repository_id": self.repository_id,
                 "pull_request": self.number, "pull_request_id": 5092495139,
                 "head_sha": self.head, "base_sha": "b" * 40,
                 "subject_sources": [
                     {"source_id": item.source_id,
                      "original_bytes": item.original_bytes,
                      "rendered_bytes": item.rendered_bytes} for item in self.sources
                 ]}
        return PullRequestObservationV3(
            repository, self.repository_id, self.number, 5092495139,
            self.head, "b" * 40, self.sources, evidence(basis),
        )


class HistoryAuthority:
    def __init__(self, *, complete=True, matching=()):
        self.complete, self.matching = complete, matching
    def decide(self, request_id, review_intent_id, namespace):
        basis = {"schema_version": 1,
                 "evidence_type": "v3-initial-history-observation",
                 "request_id": request_id, "review_intent_id": review_intent_id,
                 "namespace": namespace, "scan_boundary": "d" * 40,
                 "complete": self.complete,
                 "matching_request_ids": list(self.matching)}
        return InitialHistoryDecisionV3(
            request_id, review_intent_id, namespace, "d" * 40,
            self.complete, self.matching, evidence(basis),
        )
