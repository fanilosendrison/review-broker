"""Reviewer Packet v2 subject capture value object."""
from dataclasses import dataclass
from pathlib import Path
from .packets import SourceRecord
@dataclass(frozen=True)
class SubjectCaptureV2:
    repository: str; repository_id: int
    pull_request: int; pull_request_id: int
    head_sha: str; base_sha: str; merge_base_sha: str
    changes: tuple[dict[str, object], ...]
    records: tuple[SourceRecord, ...]
    diff: bytes; evidence_id: str; repository_root: Path
    verification: str = "SYNTHETIC_OFFLINE_VERIFIED"
    source_authorization_evidence_id: str | None = None
    pr_observation_evidence_id: str | None = None
