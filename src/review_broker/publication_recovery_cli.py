"""CLI adapter for one exact publication-only artifact recovery."""
from __future__ import annotations

from typing import Any

from .artifact_resume import PublicationRecoveryBinding, recover_validated_publication
from .identity import canonical_bytes


def add_publication_recovery_command(subcommands: Any) -> None:
    command = subcommands.add_parser("internal-recover-publication")
    command.add_argument("--issue", required=True, type=int)
    command.add_argument("--request", required=True)
    command.add_argument("--attempt", required=True)
    command.add_argument("--packet-id", required=True)
    command.add_argument("--artifact-id", required=True, type=int)
    command.add_argument("--artifact-digest", required=True)
    command.add_argument("--subject-repository", required=True)
    command.add_argument("--subject-pr", required=True, type=int)
    command.add_argument("--subject-head", required=True)


def run_publication_recovery(args: Any, source_token: str | None) -> int:
    binding = PublicationRecoveryBinding(
        issue_number=args.issue,
        request_id=args.request,
        attempt_id=args.attempt,
        packet_id=args.packet_id,
        artifact_id=args.artifact_id,
        artifact_digest=args.artifact_digest,
        subject_repository=args.subject_repository,
        subject_pull_request=args.subject_pr,
        subject_head=args.subject_head,
    )
    value = recover_validated_publication(
        args.broker_repo,
        binding,
        source_token=source_token,
    )
    print(canonical_bytes(value).decode("utf-8"))
    return 0
