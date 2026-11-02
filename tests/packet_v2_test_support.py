"""Synthetic offline packet-v2 fixtures; never live acquisition evidence."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess

from tests.request_v3_test_support import (
    HistoryAuthority, PrAuthority, RequesterAuthority, SourceAuthority, origin, request,
)
from review_broker.admission_v3 import (
    PullRequestObservationV3, SubjectSourceFeasibilityV3, admit_initial_inline_v3,
)
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.packet_v2 import (
    SubjectCaptureV2, TechnicalProfileSnapshotV2, subject_capture_evidence_id_v2,
)
from review_broker.packets import GitSourceReader, SourceSpec


def admitted(request_value=None, *, capture=None, head=None, git_file_readers=None,
             issue_reference_readers=None, source_authority_override=None):
    authority = PrAuthority(head=head or "a" * 40)
    if capture is not None:
        sources = tuple(SubjectSourceFeasibilityV3(
            f"S{index:03d}", len(record.original_bytes),
            sum(len(line.encode("utf-8")) + 9 for line in record.lines))
            for index, record in enumerate(capture.records, 1))
        class CaptureAuthority:
            def observe(self, repository, repository_id, pull_request):
                basis = {"schema_version": 1, "evidence_type": "v3-pull-request-observation",
                    "repository": repository, "repository_id": repository_id,
                    "pull_request": pull_request, "pull_request_id": capture.pull_request_id,
                    "head_sha": capture.head_sha, "base_sha": capture.base_sha,
                    "subject_sources": [{"source_id": item.source_id,
                        "original_bytes": item.original_bytes, "rendered_bytes": item.rendered_bytes}
                        for item in sources]}
                evidence_id = artifact_identity(canonical_bytes(basis) + b"\n")
                return PullRequestObservationV3(repository, repository_id, pull_request,
                    capture.pull_request_id, capture.head_sha, capture.base_sha, sources, evidence_id)
        authority = CaptureAuthority()
    return admit_initial_inline_v3(
        origin(request_value), broker_issue_number=51,
        expected_broker_issue_id=6106789428, expected_requester_id=30498238,
        requester_authority=RequesterAuthority(), pr_authority=authority,
        source_authority=(SourceAuthority() if source_authority_override is None
                          else source_authority_override), history_authority=HistoryAuthority(),
        git_file_readers=git_file_readers, issue_reference_readers=issue_reference_readers,
    )


def inline(identifier="context", text="alpha\nbeta\n", required=True):
    return {"id": identifier, "required": required,
            "source": {"kind": "inline", "text": text}}


def git_capture(root: Path, *, source_authority_override=None) -> SubjectCaptureV2:
    repository = root / "subject"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test"], check=True)
    (repository / "review.md").write_bytes(b"before\r\n")
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", "base"], check=True)
    base = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
    (repository / "review.md").write_bytes(b"after\n")
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", "head"], check=True)
    head = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
    reader = GitSourceReader(repository)
    records = (
        reader.read(SourceSpec("fanilosendrison/review-broker", base, "review.md")),
        reader.read(SourceSpec("fanilosendrison/review-broker", head, "review.md")),
    )
    value = SubjectCaptureV2(
        "fanilosendrison/review-broker", 1433701208, 62, 5092495139,
        head, base, base,
        ({"status": "modified", "path": "review.md", "previous_path": None},),
        records, reader.diff(base, head), "", repository,
    )
    if source_authority_override is not None:
        from tests.issue69_test_support import PullApi, local_acquirer, TOKEN
        from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
        from review_broker.github_subject_capture_v3 import capture_authenticated_subject_v3, bind_authenticated_capture_v3
        source = source_authority_override
        api = PullApi(base, head, base, [{"status": "modified", "filename": "review.md"}])
        observer = GitHubPullRequestObservationReaderV3(TOKEN, value.repository,
            value.repository_id, 71, head, source_authority=source, executor=api)
        scope = observer.observe_scope()
        authorization = source.authorize(value.repository, value.repository_id)
        capture = capture_authenticated_subject_v3(scope, observer, authorization,
            source.scope_observation.evidence_id, TOKEN, root / "authenticated-capture",
            acquire_repository=local_acquirer(repository))
        final = observer.finalize(scope, capture)
        return bind_authenticated_capture_v3(capture, authorization.evidence_id, final.evidence_id)
    return replace(value, evidence_id=subject_capture_evidence_id_v2(value))


def request_for_capture(capture, references=(), **changes):
    subject = {
        "kind": "github_pr", "repository": capture.repository,
        "repository_id": capture.repository_id, "pull_request": capture.pull_request,
        "expected_head_commit": capture.head_sha,
    }
    return request(subject=subject, references=list(references), **changes)


def profile(data=b'{"allow":"read-only"}\n', name="review-broker-test-profile"):
    return TechnicalProfileSnapshotV2(name, name, data, artifact_identity(data))
