"""Controlled non-secret probe of the effective Codex reviewer sandbox."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping

from .codex import sanitized_environment
from .codex_runtime_identity import verify_codex_runtime
from .reviewer_profile import (
    profile_name,
    reviewer_home_from_environment,
    verify_reviewer_profile,
)


class SecurityProbeError(RuntimeError):
    """The reviewer sandbox probe did not establish the required boundary."""


Runner = Callable[..., subprocess.CompletedProcess[str]]

_REQUIRED_OBSERVATIONS = {
    "packet_canary_readable": True,
    "auth_parent_canary_readable": False,
    "trusted_workspace_readable": False,
    "packet_directory_writable": False,
    "unauthorized_network_connect": False,
    "sensitive_environment_visible": False,
    "process_canary_visible": False,
    "outside_packet_canary_readable": False,
    "symlink_to_auth_parent_canary_readable": False,
    "hardlink_to_auth_parent_canary_readable": False,
    "hardlink_created": True,
}


def run_reviewer_isolation_probe(
    reviewer_home: Path,
    trusted_workspace: Path,
    packet_directory: Path,
    codex_executable: Path,
    *,
    runner: Runner = subprocess.run,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    python_executable = _probe_python_executable()
    profile = verify_reviewer_profile(reviewer_home, trusted_workspace, packet_directory)
    name = profile_name(packet_directory)
    codex_home = profile.parent
    adjacent_canary = codex_home / "review-broker-auth-parent-canary.txt"
    if adjacent_canary.exists() or adjacent_canary.is_symlink():
        raise SecurityProbeError("AUTH_PARENT_CANARY_COLLISION")
    descriptor = os.open(adjacent_canary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"non-secret-auth-parent-canary\n")
            stream.flush()
            os.fsync(stream.fileno())
        with tempfile.TemporaryDirectory(prefix="review-broker-security-probe-", dir=packet_directory) as temporary, \
             tempfile.TemporaryDirectory(prefix="review-broker-outside-canary-") as outside:
            probe_root = Path(temporary)
            outside_canary = Path(outside) / "outside-canary.txt"
            outside_canary.write_text("non-secret-outside-canary\n", encoding="utf-8")
            symlink_canary = probe_root / "auth-parent-alias.txt"
            symlink_canary.symlink_to(adjacent_canary)
            hardlink_canary = probe_root / "auth-parent-hardlink.txt"
            try:
                os.link(outside_canary, hardlink_canary)
            except OSError:
                pass  # Filesystem may not support cross-mount hard links.
            packet_canary = probe_root / "packet-canary.txt"
            packet_canary.write_text("non-secret-packet-canary\n", encoding="utf-8")
            script = probe_root / "probe.py"
            script.write_text(
                _probe_script(
                    packet_canary,
                    adjacent_canary,
                    trusted_workspace / "README.md",
                    probe_root,
                    outside_canary,
                    symlink_canary,
                    hardlink_canary,
                ),
                encoding="utf-8",
            )
            source_environment = dict(environment or os.environ)
            source_environment["REVIEW_BROKER_PROCESS_CANARY"] = "non-secret-process-canary"
            child_environment, _ = sanitized_environment(source_environment)
            result = runner(
                [
                    str(codex_executable), "sandbox",
                    "-p", name,
                    "-P", name,
                    "-C", str(probe_root),
                    str(python_executable), str(script),
                ],
                cwd=str(probe_root),
                env=child_environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
                shell=False,
            )
            if result.returncode != 0:
                raise SecurityProbeError("SANDBOX_PROBE_EXECUTION_FAILED")
            observation = _parse_observation(result.stdout)
    finally:
        adjacent_canary.unlink(missing_ok=True)
    mismatches = [
        name for name, expected in _REQUIRED_OBSERVATIONS.items()
        if observation.get(name) is not expected
    ]
    receipt = {
        "schema_version": 1,
        "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "permission_profile": name,
        "permission_profile_sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
        "observations": observation,
        "required_observations": _REQUIRED_OBSERVATIONS,
        "qualified": not mismatches,
        "mismatches": mismatches,
        "limitations": [
            "This probe uses non-secret canaries and does not read credential contents.",
            "Hard-link denial is untested when the controlled link could not be created.",
            "Direct sandbox behavior is not an authenticated model-tool observation.",
            "Independent review is still required before authenticated model execution.",
        ],
    }
    if mismatches:
        raise SecurityProbeError("SECURITY_BOUNDARY_NOT_QUALIFIED:" + ",".join(mismatches))
    return receipt


def _probe_python_executable() -> Path:
    candidate = Path(sys.executable)
    try:
        resolved = candidate.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise SecurityProbeError("PROBE_PYTHON_EXECUTABLE_INVALID") from exc
    if not candidate.is_absolute() or not stat.S_ISREG(metadata.st_mode):
        raise SecurityProbeError("PROBE_PYTHON_EXECUTABLE_INVALID")
    if not os.access(resolved, os.X_OK):
        raise SecurityProbeError("PROBE_PYTHON_EXECUTABLE_INVALID")
    return resolved


def run_installed_reviewer_isolation_probe(
    trusted_workspace: Path,
    packet_directory: Path,
    codex_runtime_root: Path,
    *,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    child_environment, _ = sanitized_environment(environment)
    home = reviewer_home_from_environment(child_environment)
    runtime = verify_codex_runtime(child_environment, codex_runtime_root)
    return run_reviewer_isolation_probe(
        home,
        trusted_workspace,
        packet_directory,
        runtime.executable,
        environment=child_environment,
    )


def validate_probe_receipt(receipt: dict[str, Any], profile_sha256: str, profile_identity: str) -> list[str]:
    errors: list[str] = []
    if receipt.get("qualified") is not True:
        errors.append("SECURITY_PROBE_NOT_QUALIFIED")
    if receipt.get("permission_profile") != profile_identity:
        errors.append("SECURITY_PROBE_PROFILE_MISMATCH")
    if receipt.get("permission_profile_sha256") != profile_sha256:
        errors.append("SECURITY_PROBE_PROFILE_SHA256_MISMATCH")
    if receipt.get("mismatches") != []:
        errors.append("SECURITY_PROBE_MISMATCHES_PRESENT")
    observations = receipt.get("observations")
    if not isinstance(observations, dict):
        errors.append("SECURITY_PROBE_OBSERVATIONS_INVALID")
    else:
        for name, expected in _REQUIRED_OBSERVATIONS.items():
            if observations.get(name) is not expected:
                errors.append("SECURITY_PROBE_OBSERVATION_INVALID:" + name)
    return errors


def _parse_observation(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise SecurityProbeError("SANDBOX_PROBE_OUTPUT_INVALID")


def _probe_script(
    packet_canary: Path,
    adjacent_canary: Path,
    trusted_marker: Path,
    probe_root: Path,
    outside_canary: Path,
    symlink_canary: Path,
    hardlink_canary: Path,
) -> str:
    paths = {
        "packet": str(packet_canary),
        "adjacent": str(adjacent_canary),
        "trusted": str(trusted_marker),
        "write": str(probe_root / "write-canary.txt"),
        "outside": str(outside_canary),
        "alias": str(symlink_canary),
        "hardlink": str(hardlink_canary),
    }
    return f'''from pathlib import Path
import json
import os
import socket

paths = {{name: Path(value) for name, value in {json.dumps(paths)}.items()}}


def reads_exact(path, expected):
    try:
        return path.read_text(encoding="utf-8").strip() == expected
    except OSError:
        return False


def writes(path):
    try:
        path.write_text("non-secret-write-canary", encoding="utf-8")
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def connects():
    try:
        with socket.create_connection(("example.com", 443), timeout=3):
            return True
    except OSError:
        return False

sensitive = ("OPENAI_API_KEY", "CODEX_API_KEY", "GH_TOKEN", "GITHUB_TOKEN")
observation = {{
    "packet_canary_readable": reads_exact(paths["packet"], "non-secret-packet-canary"),
    "auth_parent_canary_readable": reads_exact(paths["adjacent"], "non-secret-auth-parent-canary"),
    "trusted_workspace_readable": os.access(paths["trusted"], os.R_OK),
    "packet_directory_writable": writes(paths["write"]),
    "unauthorized_network_connect": connects(),
    "sensitive_environment_visible": any(bool(os.environ.get(name)) for name in sensitive),
    "process_canary_visible": bool(os.environ.get("REVIEW_BROKER_PROCESS_CANARY")),
    "outside_packet_canary_readable": reads_exact(paths["outside"], "non-secret-outside-canary"),
    "symlink_to_auth_parent_canary_readable": reads_exact(
        paths["alias"], "non-secret-auth-parent-canary"
    ),
    "hardlink_created": paths["hardlink"].is_file(),
    "hardlink_to_auth_parent_canary_readable": reads_exact(
        paths["hardlink"], "non-secret-outside-canary"
    ),
    "visible_proc_pid_count": sum(name.isdigit() for name in os.listdir("/proc")),
    "parent_process_environment_os_access_readable": os.access(
        f"/proc/{{os.getppid()}}/environ", os.R_OK
    ),
}}
print(json.dumps(observation, sort_keys=True, separators=(",", ":")))
'''
