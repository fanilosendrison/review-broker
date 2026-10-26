"""Evidence inventory, byte identities, and credential-leak rejection."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

REQUIRED_EVIDENCE_FILES = (
    "attempt.json",
    "input-manifest.json",
    "prompt.sha256",
    "codex-events.jsonl",
    "codex-stderr.txt",
    "codex-final.json",
    "codex-exit-code.txt",
    "input-before.sha256",
    "input-after.sha256",
    "reviewer-security-probe.json",
    "validation.json",
)

_CREDENTIAL_PATTERNS = (
    re.compile(rb'"(?:access_token|refresh_token|session_cookie|authorization)"\s*:', re.IGNORECASE),
    re.compile(rb"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
)


def evidence_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_EVIDENCE_FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            manifest[name] = {"present": False, "byte_length": 0, "sha256": None}
            continue
        data = path.read_bytes()
        manifest[name] = {
            "present": True,
            "byte_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return manifest


def missing_evidence(directory: Path) -> list[str]:
    return [name for name, entry in evidence_manifest(directory).items() if not entry["present"]]


def scan_for_credentials(directory: Path) -> list[str]:
    contaminated: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in _CREDENTIAL_PATTERNS):
            contaminated.append(path.name)
    return contaminated
