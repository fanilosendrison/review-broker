"""Bounded synthetic Actions quarantine fixture. No credentials or Issue writes."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from review_broker.evidence import (
    quarantine_contaminated_evidence,
    scan_for_credentials,
)
from review_broker.publication import PublicationError, build_review_result
from review_broker.validation import validate_evidence


def main(root: Path) -> None:
    if os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"):
        raise RuntimeError("CREDENTIAL_ENVIRONMENT_PRESENT")
    negative = root / "negative" / "evidence"
    clean = root / "clean" / "evidence"
    negative.mkdir(parents=True)
    clean.mkdir(parents=True)
    canary = "sk-" + "Q" * 30  # Generated non-secret detector-shaped data.
    (negative / "codex-events.jsonl").write_text(
        json.dumps({"type": "turn.completed", "finding": canary}) + "\n", encoding="utf-8"
    )
    (negative / "codex-stderr.txt").write_text(canary + "\n", encoding="utf-8")
    request = "request:sha256:" + "1" * 64
    attempt = "attempt:sha256:" + "2" * 64
    if not scan_for_credentials(negative):
        raise RuntimeError("NEGATIVE_DETECTOR_DID_NOT_FIRE")
    if quarantine_contaminated_evidence(negative, request_id=request, attempt_id=attempt) != {"contaminated": True}:
        raise RuntimeError("NEGATIVE_QUARANTINE_DID_NOT_FIRE")
    result = validate_evidence(negative)
    if result["evidence_status"] == "VALID" or result["review_verdict"] == "GO":
        raise RuntimeError("NEGATIVE_ACCEPTED")
    try:
        build_review_result({}, {}, {}, result, current_head=None)
    except PublicationError as error:
        if str(error) != "CONTAMINATED_EVIDENCE_NOT_PUBLISHABLE":
            raise RuntimeError("NEGATIVE_WRONG_REJECTION") from error
    else:
        raise RuntimeError("NEGATIVE_RESULT_PUBLISHED")
    if scan_for_credentials(negative) or canary.encode() in b"".join(
        path.read_bytes() for path in negative.rglob("*") if path.is_file()
    ):
        raise RuntimeError("NEGATIVE_ARTIFACT_CONTAMINATED")
    if not (negative / "credential-incident.json").is_file():
        raise RuntimeError("INCIDENT_MISSING")
    (clean / "clean-evidence.json").write_text(
        json.dumps({"schema_version": 1, "status": "clean-synthetic-control"}) + "\n", encoding="utf-8"
    )
    if scan_for_credentials(clean) or quarantine_contaminated_evidence(
        clean, request_id=request, attempt_id=attempt
    ) != {"contaminated": False}:
        raise RuntimeError("CLEAN_CONTROL_REJECTED")
    print(json.dumps({"negative_status": result["evidence_status"],
                      "negative_verdict": result["review_verdict"],
                      "incident_present": True, "clean_control_present": True,
                      "canary_sha256": hashlib.sha256(canary.encode()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
