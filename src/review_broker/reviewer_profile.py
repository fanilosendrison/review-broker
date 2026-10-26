"""Exact Codex permission profile for credential-isolated review execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

PROFILE_NAME = "review-broker"


class ReviewerProfileError(RuntimeError):
    """The installed reviewer permission profile is absent or untrusted."""


def profile_bytes(reviewer_home: Path, trusted_workspace: Path) -> bytes:
    home = _validated_root(reviewer_home, "REVIEWER_HOME")
    workspace = _validated_root(trusted_workspace, "TRUSTED_WORKSPACE")
    def quote(value: Path) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    return (
        f'default_permissions = "{PROFILE_NAME}"\n'
        'approval_policy = "never"\n'
        "allow_login_shell = false\n"
        "include_environment_context = false\n"
        "include_environment_context_time = false\n\n"
        "[shell_environment_policy]\n"
        'inherit = "none"\n\n'
        "[shell_environment_policy.set]\n"
        'PATH = "/usr/local/bin:/usr/bin:/bin"\n'
        f"HOME = {quote(home)}\n"
        'LANG = "C.UTF-8"\n'
        'TZ = "UTC"\n\n'
        f"[permissions.{PROFILE_NAME}.filesystem]\n"
        '"/" = "read"\n'
        f"{quote(home)} = \"deny\"\n"
        f"{quote(workspace)} = \"deny\"\n\n"
        f"[permissions.{PROFILE_NAME}.network]\n"
        "enabled = false\n"
    ).encode("utf-8")


def install_reviewer_profile(reviewer_home: Path, trusted_workspace: Path) -> Path:
    expected = profile_bytes(reviewer_home, trusted_workspace)
    codex_home = _codex_home(reviewer_home)
    _reject_base_user_config(codex_home)
    profile = codex_home / f"{PROFILE_NAME}.config.toml"
    if profile.is_symlink():
        raise ReviewerProfileError("PROFILE_SYMLINK")
    if profile.exists():
        if not profile.is_file() or profile.read_bytes() != expected:
            raise ReviewerProfileError("PROFILE_MISMATCH")
    else:
        descriptor = os.open(profile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            profile.unlink(missing_ok=True)
            raise
    verify_reviewer_profile(reviewer_home, trusted_workspace)
    return profile


def verify_reviewer_profile(reviewer_home: Path, trusted_workspace: Path) -> Path:
    expected = profile_bytes(reviewer_home, trusted_workspace)
    codex_home = _codex_home(reviewer_home)
    _reject_base_user_config(codex_home)
    profile = codex_home / f"{PROFILE_NAME}.config.toml"
    if profile.is_symlink():
        raise ReviewerProfileError("PROFILE_SYMLINK")
    if not profile.is_file() or profile.read_bytes() != expected:
        raise ReviewerProfileError("PROFILE_MISMATCH")
    metadata = profile.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ReviewerProfileError("PROFILE_MODE_INVALID")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise ReviewerProfileError("PROFILE_OWNER_INVALID")
    return profile


def reviewer_home_from_environment(environment: dict[str, str]) -> Path:
    home_value = environment.get("HOME")
    if not home_value:
        raise ReviewerProfileError("HOME_UNAVAILABLE")
    home = Path(home_value)
    codex_home_value = environment.get("CODEX_HOME")
    if codex_home_value and Path(codex_home_value) != home / ".codex":
        raise ReviewerProfileError("NONSTANDARD_CODEX_HOME_FORBIDDEN")
    return home


def _codex_home(reviewer_home: Path) -> Path:
    home = _validated_root(reviewer_home, "REVIEWER_HOME")
    codex_home = home / ".codex"
    if codex_home.is_symlink() or not codex_home.is_dir():
        raise ReviewerProfileError("CODEX_HOME_INVALID")
    return codex_home


def _reject_base_user_config(codex_home: Path) -> None:
    base_config = codex_home / "config.toml"
    if base_config.exists() or base_config.is_symlink():
        raise ReviewerProfileError("BASE_USER_CONFIG_PRESENT")


def _validated_root(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ReviewerProfileError(f"{label}_INVALID")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise ReviewerProfileError(f"{label}_ALIAS_FORBIDDEN")
    return path
