"""Requester-facing CLI operations and authenticated result presentation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from .github_journal import GitHubRefJournal
from .identity import canonical_bytes, request_identity
from .request import RequestContractError, build_issue_body, create_request, parse_issue_body
from .verifiedresult import read_verified_result


class CliError(RuntimeError):
    """Requester command cannot establish a safe response."""


def request(args: argparse.Namespace) -> int:
    mission = _read_json_object(args.mission_file, maximum_bytes=100_000)
    value = create_request(args.repo, args.pr, args.profile, mission)
    body = build_issue_body(value)
    title = f"Review request — {args.repo}#{args.pr} — {mission['id']}"
    outcome = _run([
        "gh", "issue", "create", "--repo", args.broker_repo,
        "--title", title, "--body", body,
    ])
    print(f"REQUEST_ID={request_identity(value)}")
    print(f"ISSUE_URL={outcome.stdout.strip()}")
    return 0


def status(args: argparse.Namespace) -> int:
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


def result(args: argparse.Namespace) -> int:
    value = read_verified_result(args.broker_repo, args.request)
    if args.json:
        print(canonical_bytes(value).decode("utf-8"))
    else:
        print(f"EXECUTION_STATUS={value['execution_status']}")
        print(f"EVIDENCE_STATUS={value['evidence_status']}")
        print(f"REVIEW_VERDICT={value['review_verdict']}")
        print(f"APPLICABILITY={value['applicability']['status']}")
    return 0


def _find_issue(repository: str, wanted_request_id: str) -> dict[str, Any]:
    outcome = _run([
        "gh", "issue", "list", "--repo", repository, "--state", "all",
        "--limit", "1000", "--json", "number,url,body,state",
    ])
    issues = json.loads(outcome.stdout)
    matches = []
    for issue in issues:
        try:
            value = parse_issue_body(issue.get("body") or "")
        except RequestContractError:
            continue
        if request_identity(value) == wanted_request_id:
            matches.append(issue)
    if not matches:
        raise CliError("REQUEST_NOT_FOUND")
    matches.sort(key=lambda item: item["number"])
    return matches[0]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    outcome = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=120, shell=False,
    )
    if outcome.returncode != 0:
        raise CliError(f"COMMAND_FAILED:{command[1]}")
    return outcome


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
