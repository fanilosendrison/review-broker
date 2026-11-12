"""Operator-only projected evidence admission; never imported by broker runtime.

jq owns projection syntax. These checks are a retention guard, not a universal
secret detector or permission to collect arbitrary provider objects. No raw
input, field value or external-program diagnostic is emitted on rejection.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SENSITIVE = re.compile(r"token|authorization|password|privatekey|secret|cookie|credential", re.I)
SAFE_COUNTERS = frozenset({"sourceapptokenmints", "tokenmintcount"})
REDACTED = frozenset({"[REDACTED]", "[REDACTED_PROVIDER_TEMP_CLONE_TOKEN]"})
HEADER = re.compile(r"(?:proxy-)?authorization\s*:\s*(?:bearer|basic|token)\s+[^\s\"']+", re.I)
FIELD = re.compile(r'''["']([A-Za-z0-9_. -]+)["']\s*:\s*(["'])([^\r\n]*?)\2''')
MAX_BYTES = 16_000_000
MAX_DEPTH = 80


def _name(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def _nonempty(value: object) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _field(key: str, value: object) -> None:
    normalized = _name(key)
    if not SENSITIVE.search(normalized):
        return
    if normalized in SAFE_COUNTERS:
        if type(value) is int and value >= 0:
            return
        raise ValueError("EVIDENCE_NONSECRET_COUNTER_INVALID")
    if _nonempty(value) and not (isinstance(value, str) and value in REDACTED):
        raise ValueError("EVIDENCE_SENSITIVE_FIELD_REJECTED")


def check_json(value: object, *, _depth: int = 0) -> None:
    """Reject unsafe structured values, including JSON embedded in trace strings."""
    if _depth > MAX_DEPTH:
        raise ValueError("EVIDENCE_NESTING_LIMIT")
    if isinstance(value, dict):
        for key, child in value.items():
            _field(key, child)
            check_json(child, _depth=_depth + 1)
    elif isinstance(value, list):
        for child in value:
            check_json(child, _depth=_depth + 1)
    elif isinstance(value, str):
        check_text(value, _depth=_depth + 1)


def check_text(text: str, *, _depth: int = 0) -> None:
    """Inspect headers, JSON/JSONL and quoted structured fragments in logs."""
    if _depth > MAX_DEPTH:
        raise ValueError("EVIDENCE_NESTING_LIMIT")
    if HEADER.search(text):
        raise ValueError("EVIDENCE_AUTHORIZATION_HEADER_REJECTED")
    for match in FIELD.finditer(text):
        key, _, value = match.groups()
        # String fragments may not establish a safe integer counter.
        _field(key, value)
    try:
        value = json.loads(text)
    except (ValueError, RecursionError):
        value = None
    if isinstance(value, (dict, list, str)):
        check_json(value, _depth=_depth + 1)
        return
    # A log prefix must not hide an object/array or a non-string sensitive value.
    # Decode with the standard JSON parser, not a second object/value grammar.
    decoder = json.JSONDecoder()
    position = 0
    for _ in range(10_000):
        start = re.search(r'[\[{]', text[position:])
        if start is None:
            return
        position += start.start()
        try:
            fragment, end = decoder.raw_decode(text, position)
        except ValueError:
            position += 1
            continue
        except RecursionError:
            raise ValueError("EVIDENCE_NESTING_LIMIT") from None
        check_json(fragment, _depth=_depth + 1)
        position = end
    raise ValueError("EVIDENCE_FRAGMENT_LIMIT")


def project_json(value: object, selector: str) -> object:
    """Apply an explicit bounded jq projection while the provider input is ephemeral."""
    if not isinstance(selector, str) or not selector.strip().startswith(("{", "[")):
        raise ValueError("EVIDENCE_EXPLICIT_PROJECTION_REQUIRED")
    try:
        result = subprocess.run(["jq", "-cM", selector], input=json.dumps(value),
                                text=True, capture_output=True, timeout=30, check=True)
        projected = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ValueError("EVIDENCE_PROJECTION_REJECTED") from None
    check_json(projected)
    return projected


def write_projected(path: Path, value: object) -> None:
    """Validate before opening the private, exclusive destination."""
    check_json(value)
    encoded = (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project")
    project.add_argument("--filter", required=True, help="explicit jq object/array projection")
    project.add_argument("--output", required=True, type=Path)
    scan = commands.add_parser("scan")
    scan.add_argument("paths", nargs="+", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == "project":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("EVIDENCE_INPUT_LIMIT")
            write_projected(arguments.output, project_json(json.loads(raw), arguments.filter))
        else:
            for path in arguments.paths:
                if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
                    raise ValueError("EVIDENCE_FILE_REJECTED")
                check_text(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        sys.stderr.write("EVIDENCE_ADMISSION_REJECTED\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
