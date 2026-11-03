"""Exact Codex permission profile for credential-isolated review execution."""
from __future__ import annotations

from .arm_authority_contract import AUTHORITY_ROOT, STATE_DIRECTORY

import hashlib
import json
import os
from pathlib import Path
import stat

PROFILE_NAME = "review-broker"


class ReviewerProfileError(RuntimeError):
    """The installed reviewer permission profile is absent or untrusted."""


def profile_name(packet_directory: Path) -> str:
    packet = _validated_root(packet_directory, "PACKET_DIRECTORY")
    return PROFILE_NAME + "-" + hashlib.sha256(os.fsencode(packet)).hexdigest()


def profile_bytes(reviewer_home: Path, trusted_workspace: Path, packet_directory: Path) -> bytes:
    home = _validated_root(reviewer_home, "REVIEWER_HOME")
    workspace = _validated_root(trusted_workspace, "TRUSTED_WORKSPACE")
    packet = _validated_root(packet_directory, "PACKET_DIRECTORY")
    if any(packet == root or packet.is_relative_to(root) or root.is_relative_to(packet)
           for root in (home, workspace)):
        raise ReviewerProfileError("PACKET_PRIVILEGED_ROOT_OVERLAP")
    def quote(value: Path) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    name = profile_name(packet)
    return (
        f'default_permissions = "{name}"\n'
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
        f"[permissions.{name}.filesystem]\n"
        '":minimal" = "read"\n'
        f"{quote(packet)} = \"read\"\n"
        f"{quote(home)} = \"deny\"\n"
        f"{quote(workspace)} = \"deny\"\n"
        f"{quote(AUTHORITY_ROOT)} = \"deny\"\n"
        f"{quote(STATE_DIRECTORY)} = \"deny\"\n\n"
        f"[permissions.{name}.network]\n"
        "enabled = false\n"
    ).encode("utf-8")


def install_reviewer_profile(
    reviewer_home: Path, trusted_workspace: Path, packet_directory: Path,
) -> Path:
    expected = profile_bytes(reviewer_home, trusted_workspace, packet_directory)
    codex_home = _codex_home(reviewer_home)
    _reject_base_user_config(codex_home)
    profile = codex_home / f"{profile_name(packet_directory)}.config.toml"
    try:
        descriptor = os.open(profile, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        # Existing profiles are immutable: accept exact bytes only, never migrate.
        verify_reviewer_profile(reviewer_home, trusted_workspace, packet_directory)
    else:
        # A partial write remains a rejecting conflict; never unlink a file another
        # installer or an invocation could have started using.
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(codex_home, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    verify_reviewer_profile(reviewer_home, trusted_workspace, packet_directory)
    return profile


def verify_reviewer_profile(
    reviewer_home: Path, trusted_workspace: Path, packet_directory: Path,
) -> Path:
    expected = profile_bytes(reviewer_home, trusted_workspace, packet_directory)
    codex_home = _codex_home(reviewer_home)
    _reject_base_user_config(codex_home)
    profile = codex_home / f"{profile_name(packet_directory)}.config.toml"
    if profile.is_symlink():
        raise ReviewerProfileError("PROFILE_SYMLINK")
    try:
        descriptor = os.open(profile, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ReviewerProfileError("PROFILE_UNAVAILABLE") from exc
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ReviewerProfileError("PROFILE_TYPE_INVALID")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ReviewerProfileError("PROFILE_MODE_INVALID")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ReviewerProfileError("PROFILE_OWNER_INVALID")
        if stream.read() != expected:
            raise ReviewerProfileError("PROFILE_MISMATCH")
        try:
            current = profile.lstat()
        except OSError as exc:
            raise ReviewerProfileError("PROFILE_CHANGED") from exc
        if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_size) != (
            metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_size
        ):
            raise ReviewerProfileError("PROFILE_CHANGED")
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
    metadata = codex_home.stat()
    if (hasattr(os, "getuid") and metadata.st_uid != os.getuid()) or metadata.st_mode & 0o022:
        raise ReviewerProfileError("CODEX_HOME_UNTRUSTED")
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
