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
from .identity import canonical_bytes, request_identity
from .orchestration import prepare_issue, publish_validated_result, reconcile_repository
from .packets import verify_packet
from .publication import extract_result_comment
from .queue import AttemptState, GitHubRefJournal
from .request import RequestContractError, build_issue_body, create_request, parse_issue_body
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

    invoke = subcommands.add_parser("internal-invoke")
    invoke.add_argument("--packet-dir", required=True, type=Path)
    invoke.add_argument("--schema", required=True, type=Path)
    invoke.add_argument("--attempt", required=True)

    validate = subcommands.add_parser("internal-validate")
    validate.add_argument("--packet-dir", required=True, type=Path)

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
    try:
        if args.command == "request":
            return _request(args)
        if args.command == "status":
            return _status(args)
        if args.command == "result":
            return _result(args)
        if args.command == "internal-prepare":
            value = prepare_issue(args.broker_repo, args.issue, args.output)
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
        if args.command == "internal-invoke":
            invoke_once(args.packet_dir, args.schema, args.attempt)
            return 0
        if args.command == "internal-validate":
            print(canonical_bytes(validate_evidence(args.packet_dir)).decode("utf-8"))
            return 0
        if args.command == "internal-transition":
            GitHubRefJournal(args.broker_repo).transition(
                args.request, AttemptState(args.state), [args.evidence]
            )
            return 0
        if args.command == "internal-publish":
            print(canonical_bytes(publish_validated_result(args.broker_repo, args.packet_dir)).decode("utf-8"))
            return 0
        if args.command == "internal-reconcile":
            print(canonical_bytes(reconcile_repository(args.broker_repo, args.codespace)).decode("utf-8"))
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
