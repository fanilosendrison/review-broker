"""Exact Git raw tree-delta observation without rename/copy similarity heuristics."""
from __future__ import annotations

from typing import Callable


class GitChangeScopeError(ValueError):
    """The actual path delta is not exclusively new regular/symlink blob entries."""


def added_change_modes(git: Callable[..., bytes], merge_base: str, head: str) -> dict[str, str]:
    raw = git("diff", "--raw", "--no-renames", "--no-abbrev", "-z", merge_base, head, "--")
    parts = raw.split(b"\0")
    if not raw.endswith(b"\0") or not raw or len(parts[:-1]) % 2:
        raise GitChangeScopeError("ACTUAL_ADDED_SCOPE_INVALID")
    result: dict[str, str] = {}
    try:
        for position in range(0, len(parts) - 1, 2):
            before_mode, after_mode, before_oid, after_oid, status = parts[position].decode("ascii").split(" ")
            path = parts[position + 1].decode("ascii")
            if (before_mode != ":000000" or status != "A" or path in result
                or after_mode not in {"100644", "100755", "120000"}
                or len(before_oid) not in {40, 64} or set(before_oid) != {"0"}
                or len(after_oid) != len(before_oid) or any(c not in "0123456789abcdef" for c in after_oid)):
                raise ValueError
            result[path] = after_mode
    except (ValueError, UnicodeError) as exc:
        raise GitChangeScopeError("ACTUAL_CHANGE_NOT_EXCLUSIVELY_ADDED") from exc
    return result
