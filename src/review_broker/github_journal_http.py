"""Bounded, status-bearing gh transport for the trusted GitHub journal."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import subprocess
from typing import Any, Callable

from .identity import canonical_bytes
from .queue import StateTransitionError

Runner = Callable[..., subprocess.CompletedProcess[str]]


class JournalReadUnknown(StateTransitionError):
    """No authoritative observation; never absence or execution permission."""

    outcome = 'UNKNOWN'


@dataclass(frozen=True)
class GitHubJournalResponse:
    status: int
    value: Any  # GitHub JSON is untrusted until the endpoint-specific validator.


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # Any is untrusted JSON; duplicate names are ambiguous transport evidence.
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError


def journal_request(
    runner: Runner, method: str, endpoint: str, payload: dict[str, Any] | None = None,
) -> GitHubJournalResponse:
    command = ['gh', 'api', '--method', method, endpoint, '--include',
               '--hostname', 'github.com', '--header', 'Accept: application/vnd.github+json']
    kwargs: dict[str, Any] = dict(text=True, capture_output=True, check=False,
                                  shell=False, timeout=30)
    if payload is not None:
        command.extend(['--input', '-'])
        kwargs['input'] = canonical_bytes(payload).decode('utf-8')
    try:
        result = runner(command, **kwargs)
    except Exception:  # The transport boundary converts every adapter failure without raw diagnostics.
        raise JournalReadUnknown('GITHUB_JOURNAL_TRANSPORT_UNKNOWN') from None
    try:
        # --include emits one status/header block, even on HTTP errors. Reject
        # redirects, partial/multiple responses and contradictory exit/status.
        text = result.stdout.replace('\r\n', '\n')
        headers, body = text.split('\n\n', 1)
        lines = headers.split('\n')
        match = re.fullmatch(r'HTTP/(?:1\.[01]|2(?:\.0)?) ([1-5][0-9]{2})(?: [^\r\n]*)?', lines[0])
        if match is None or any(':' not in line for line in lines[1:]):
            raise ValueError
        status = int(match[1])
        if result.returncode != (1 if status >= 400 else 0):
            raise ValueError
        if status < 200 or 300 <= status < 400:
            raise ValueError
        value = json.loads(body, object_pairs_hook=_unique_members, parse_constant=_reject_nonfinite)
    except (AttributeError, TypeError, ValueError, RecursionError):
        raise JournalReadUnknown('GITHUB_JOURNAL_HTTP_UNKNOWN') from None
    return GitHubJournalResponse(status, value)
