"""Universal requester CLI and trusted workflow entry points."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .codex import invoke_once
from .codespace import CodespaceController
from .execution_recovery import (
    capture_terminal_transition,
    finalize_durable_evidence_artifact,
    mark_ambiguous_execution_indeterminate,
    plan_durable_evidence_artifact,
    record_stopped_transition,
    recover_runtime_evidence,
    stop_and_observe_shutdown,
    workflow_context,
)
from .github_journal import GitHubRefJournal
from .identity import canonical_bytes, request_identity
from .orchestration import prepare_issue, publish_validated_result
from .reconciliation import reconcile_repository
from .packets import verify_packet
from .publication import extract_result_comment
from .queue import AttemptState
from .request import RequestContractError, build_issue_body, create_request, parse_issue_body
from .reviewer_profile import install_reviewer_profile, reviewer_home_from_environment
from .security_probe import run_reviewer_isolation_probe
from .validation import validate_evidence

DEFAULT_BROKER_REPOSITORY = "fanilosendrison/review-broker"


class CliError(RuntimeError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reviewctl")
    parser.add_argument(
        "--broker-repo",
        default=os.environ.get("REVIEW_BROKER_REPOSITORY", DEFAULT_BROKER_REPOSITORY),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    request = subcommands.add_parser("request")
    request.add_argument("--repo", required=True)
    request.add_argument("--pr", required=True, type=int)
    request.add_argument("--profile", required=True)
    request.add_argument("--mission-file", required=True, type=Path)

    status = subcommands.add_parser("status")
    status.add_argument("--request", required=True)

    result = subcommands.add_parser("result")
    result.add_argument("--request", required=True)
    result.add_argument("--json", action="store_true")

    prepare = subcommands.add_parser("internal-prepare")
    prepare.add_argument("--issue", required=True, type=int)
    prepare.add_argument("--output", required=True, type=Path)

    verify = subcommands.add_parser("internal-verify-packet")
    verify.add_argument("--packet-dir", required=True, type=Path)

    arm = subcommands.add_parser("internal-arm")
    arm.add_argument("--request", required=True)
    arm.add_argument("--packet-id", required=True)

    install_profile = subcommands.add_parser("internal-install-reviewer-profile")
    install_profile.add_argument("--trusted-workspace", required=True, type=Path)
    probe_profile = subcommands.add_parser("internal-probe-reviewer-profile")
    probe_profile.add_argument("--trusted-workspace", required=True, type=Path)
    invoke = subcommands.add_parser("internal-invoke")
    invoke.add_argument("--packet-dir", required=True, type=Path)
    invoke.add_argument("--schema", required=True, type=Path)
    invoke.add_argument("--attempt", required=True)
    invoke.add_argument("--broker-wheel-sha256", required=True)
    invoke.add_argument("--trusted-workspace", required=True, type=Path)
    recover = subcommands.add_parser("internal-recover")
    recover.add_argument("--codespace", required=True)
    recover.add_argument("--remote-dir", required=True)
    recover.add_argument("--output", required=True, type=Path)
    recover.add_argument("--request", required=True)
    recover.add_argument("--attempt", required=True)
    capture = subcommands.add_parser("internal-capture-terminal")
    capture.add_argument("--packet-dir", required=True, type=Path)
    capture.add_argument("--request", required=True)
    capture.add_argument("--attempt", required=True)
    capture.add_argument("--packet-id", required=True)
    plan_artifact = subcommands.add_parser("internal-plan-evidence-artifact")
    plan_artifact.add_argument("--evidence-dir", required=True, type=Path)
    plan_artifact.add_argument("--output", required=True, type=Path)
    plan_artifact.add_argument("--artifact-name", required=True)
    finalize_artifact = subcommands.add_parser("internal-finalize-evidence-artifact")
    finalize_artifact.add_argument("--plan", required=True, type=Path)
    finalize_artifact.add_argument("--output", required=True, type=Path)
    finalize_artifact.add_argument("--artifact-id", required=True, type=int)
    finalize_artifact.add_argument("--artifact-digest", required=True)
    indeterminate = subcommands.add_parser("internal-mark-indeterminate")
    indeterminate.add_argument("--recovery-manifest", required=True, type=Path)
    indeterminate.add_argument("--request", required=True)
    indeterminate.add_argument("--attempt", required=True)
    validate = subcommands.add_parser("internal-validate")
    validate.add_argument("--packet-dir", required=True, type=Path)
    stop = subcommands.add_parser("internal-stop-codespace")
    stop.add_argument("--codespace", required=True)
    stop.add_argument("--output", required=True, type=Path)
    stop.add_argument("--request", required=True)
    stop.add_argument("--attempt", required=True)
    stopped = subcommands.add_parser("internal-record-stopped")
    stopped.add_argument("--observation", required=True, type=Path)
    stopped.add_argument("--codespace", required=True)
    stopped.add_argument("--request", required=True)
    stopped.add_argument("--attempt", required=True)
    transition = subcommands.add_parser("internal-transition")
    transition.add_argument("--request", required=True)
    transition.add_argument("--state", required=True, choices=[state.value for state in AttemptState])
    transition.add_argument("--evidence", required=True)
    publish = subcommands.add_parser("internal-publish")
    publish.add_argument("--packet-dir", required=True, type=Path)

    reconcile = subcommands.add_parser("internal-reconcile")
    reconcile.add_argument("--codespace", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_token = os.environ.pop("REVIEW_BROKER_SOURCE_TOKEN", None)
    try:
        if args.command == "request":
            return _request(args)
        if args.command == "status":
            return _status(args)
        if args.command == "result":
            return _result(args)
        if args.command == "internal-prepare":
            value = prepare_issue(
                args.broker_repo,
                args.issue,
                args.output,
                source_token=source_token,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-verify-packet":
            print(canonical_bytes(verify_packet(args.packet_dir)).decode("utf-8"))
            return 0
        if args.command == "internal-arm":
            journal = GitHubRefJournal(args.broker_repo)
            journal.transition(args.request, AttemptState.ARMED, [args.packet_id])
            journal.record_invocation(args.request)
            return 0
        if args.command == "internal-install-reviewer-profile":
            home = reviewer_home_from_environment(dict(os.environ))
            install_reviewer_profile(home, args.trusted_workspace)
            return 0
        if args.command == "internal-probe-reviewer-profile":
            home = reviewer_home_from_environment(dict(os.environ))
            receipt = run_reviewer_isolation_probe(home, args.trusted_workspace)
            print(canonical_bytes(receipt).decode("utf-8"))
            return 0
        if args.command == "internal-invoke":
            invoke_once(
                args.packet_dir,
                args.schema,
                args.attempt,
                broker_wheel_sha256=args.broker_wheel_sha256,
                trusted_workspace=args.trusted_workspace,
            )
            return 0
        if args.command == "internal-recover":
            value = recover_runtime_evidence(
                CodespaceController(args.codespace),
                args.remote_dir,
                args.output,
                request_id=args.request,
                attempt_id=args.attempt,
                context=workflow_context(os.environ, source="review-workflow-recovery"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-capture-terminal":
            value = capture_terminal_transition(
                args.broker_repo,
                args.packet_dir,
                request_id=args.request,
                attempt_id=args.attempt,
                packet_id=args.packet_id,
                context=workflow_context(os.environ, source="review-workflow-capture"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-plan-evidence-artifact":
            value = plan_durable_evidence_artifact(
                args.broker_repo,
                args.evidence_dir,
                args.output,
                artifact_name=args.artifact_name,
                workflow_run_id=os.environ.get("GITHUB_RUN_ID", ""),
                workflow_run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-finalize-evidence-artifact":
            value = finalize_durable_evidence_artifact(
                args.broker_repo,
                args.plan,
                args.output,
                artifact_id=args.artifact_id,
                artifact_digest=args.artifact_digest,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-mark-indeterminate":
            value = mark_ambiguous_execution_indeterminate(
                args.broker_repo,
                args.recovery_manifest,
                request_id=args.request,
                attempt_id=args.attempt,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-validate":
            print(canonical_bytes(validate_evidence(args.packet_dir)).decode("utf-8"))
            return 0
        if args.command == "internal-stop-codespace":
            value = stop_and_observe_shutdown(
                CodespaceController(args.codespace),
                args.output,
                request_id=args.request,
                attempt_id=args.attempt,
                context=workflow_context(os.environ, source="review-workflow-cleanup"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-record-stopped":
            value = record_stopped_transition(
                args.broker_repo,
                args.observation,
                request_id=args.request,
                attempt_id=args.attempt,
                codespace_name=args.codespace,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-transition":
            GitHubRefJournal(args.broker_repo).transition(
                args.request, AttemptState(args.state), [args.evidence]
            )
            return 0
        if args.command == "internal-publish":
            print(canonical_bytes(publish_validated_result(
                args.broker_repo,
                args.packet_dir,
                source_token=source_token,
            )).decode("utf-8"))
            return 0
        if args.command == "internal-reconcile":
            codespace_token = os.environ.get("REVIEW_BROKER_CODESPACE_TOKEN")
            if not codespace_token:
                raise CliError("CODESPACE_CREDENTIAL_MISSING")
            codespace_environment = dict(os.environ)
            codespace_environment["GH_TOKEN"] = codespace_token
            codespace_environment.pop("GITHUB_TOKEN", None)
            result = reconcile_repository(
                args.broker_repo,
                args.codespace,
                codespace_environment=codespace_environment,
                source_token=source_token,
            )
            print(canonical_bytes(result).decode("utf-8"))
            if any(
                item.get("outcome") == "INFRASTRUCTURE_INCIDENT"
                for item in result
            ):
                return 1
            return 0
    except Exception as exc:  # CLI boundary converts typed failures into a non-secret status.
        print(f"REVIEWCTL_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable")


def _request(args: argparse.Namespace) -> int:
    mission = _read_json_object(args.mission_file, maximum_bytes=100_000)
    request = create_request(args.repo, args.pr, args.profile, mission)
    body = build_issue_body(request)
    title = f"Review request — {args.repo}#{args.pr} — {mission['id']}"
    result = _run([
        "gh", "issue", "create", "--repo", args.broker_repo,
        "--title", title, "--body", body,
    ])
    print(f"REQUEST_ID={request_identity(request)}")
    print(f"ISSUE_URL={result.stdout.strip()}")
    return 0


def _status(args: argparse.Namespace) -> int:
    issue = _find_issue(args.broker_repo, args.request)
    try:
        attempt = GitHubRefJournal(args.broker_repo).get(args.request)
        state = attempt.state.value
        attempt_id = attempt.attempt_id
    except KeyError:
        state = "REQUESTED"
        attempt_id = "UNDETERMINED"
    print(f"REQUEST_ID={args.request}")
    print(f"ISSUE={issue['url']}")
    print(f"STATE={state}")
    print(f"ATTEMPT_ID={attempt_id}")
    return 0


def _result(args: argparse.Namespace) -> int:
    issue = _find_issue(args.broker_repo, args.request)
    comments = _gh_json(f"repos/{args.broker_repo}/issues/{issue['number']}/comments?per_page=100")
    results = [
        value for value in (extract_result_comment(comment.get("body", "")) for comment in comments)
        if value is not None and value.get("request_id") == args.request
    ]
    if not results:
        raise CliError("RESULT_UNAVAILABLE")
    value = results[-1]
    if args.json:
        print(canonical_bytes(value).decode("utf-8"))
    else:
        print(f"EXECUTION_STATUS={value['execution_status']}")
        print(f"EVIDENCE_STATUS={value['evidence_status']}")
        print(f"REVIEW_VERDICT={value['review_verdict']}")
        print(f"APPLICABILITY={value['applicability']['status']}")
    return 0


def _find_issue(repository: str, wanted_request_id: str) -> dict[str, Any]:
    result = _run([
        "gh", "issue", "list", "--repo", repository, "--state", "all",
        "--limit", "1000", "--json", "number,url,body,state",
    ])
    issues = json.loads(result.stdout)
    matches = []
    for issue in issues:
        try:
            request = parse_issue_body(issue.get("body") or "")
        except RequestContractError:
            continue
        if request_identity(request) == wanted_request_id:
            matches.append(issue)
    if not matches:
        raise CliError("REQUEST_NOT_FOUND")
    matches.sort(key=lambda item: item["number"])
    return matches[0]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        shell=False,
    )
    if result.returncode != 0:
        raise CliError(f"COMMAND_FAILED:{command[1]}")
    return result


def _gh_json(endpoint: str) -> Any:
    result = _run(["gh", "api", endpoint])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CliError("GITHUB_RESPONSE_INVALID") from exc


def _read_json_object(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
        raise CliError("MISSION_FILE_INVALID")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("MISSION_FILE_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise CliError("MISSION_FILE_NOT_OBJECT")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
