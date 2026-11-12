"""Exact logical Review Intent identity for the isolated v3 candidate."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .identity import canonical_bytes
from .request_v3 import validate_request_v3


def review_intent_basis_v3(request: Mapping[str, Any]) -> dict[str, Any]:
    value = validate_request_v3(request)
    subject = value["subject"]
    references = []
    for reference in value["references"]:
        source = reference["source"]
        kind = source["kind"]
        if kind == "inline":
            logical_source = {"kind": kind}
        elif kind == "git_file":
            logical_source = {
                "kind": kind,
                "repository": source["repository"],
                "path": source["path"],
            }
        elif kind == "github_issue_body":
            logical_source = {
                "kind": kind,
                "repository": source["repository"],
                "issue": source["issue"],
            }
        else:
            logical_source = {
                "kind": kind,
                "repository": source["repository"],
                "comment_id": source["comment_id"],
            }
        references.append({
            "id": reference["id"],
            "required": reference["required"],
            "source": logical_source,
        })
    return {
        "intent_schema_version": 3,
        "subject": {
            "kind": subject["kind"],
            "repository": subject["repository"],
            "repository_id": subject["repository_id"],
            "pull_request": subject["pull_request"],
        },
        "mission": value["mission"],
        "reviewer": value["reviewer"],
        "atomicity": value["atomicity"],
        "references": references,
    }


def review_intent_identity_v3(request: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(review_intent_basis_v3(request))).hexdigest()
    return "review-intent:sha256:" + digest
