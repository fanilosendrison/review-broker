"""Official npm artifact and protected Codex runtime identity verification."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
from importlib import resources
import json
import os
from pathlib import Path
import platform
import stat
from typing import Any, Mapping


class CodexRuntimeIdentityError(ValueError):
    """The installed or execution Codex runtime is not the trusted release."""


@dataclass(frozen=True)
class VerifiedCodexRuntime:
    executable: Path
    launcher_selected: Path
    launcher_resolved: Path
    launcher_sha256: str
    installed_native: Path
    native_sha256: str
    protected_runtime_root: Path
    distribution: str
    distribution_version: str
    platform_alias: str
    platform_version: str
    root_dist_integrity: str
    platform_dist_integrity: str

    def evidence(self) -> dict[str, Any]:
        return {
            "runtime_identity_verification": "VERIFIED_OFFICIAL_NPM_ARTIFACT",
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "platform_alias": self.platform_alias,
            "platform_version": self.platform_version,
            "launcher_selected": str(self.launcher_selected),
            "launcher_resolved": str(self.launcher_resolved),
            "codex_launcher_sha256": self.launcher_sha256,
            "installed_native": str(self.installed_native),
            "codex_native_sha256": self.native_sha256,
            "execution_native": str(self.executable),
            "protected_runtime_root": str(self.protected_runtime_root),
            "root_dist_integrity": self.root_dist_integrity,
            "platform_dist_integrity": self.platform_dist_integrity,
            "node_interpreter_used": False,
            "execution_stability": "ROOT_OWNED_NON_WRITABLE_PACKAGE_LAYOUT",
        }


def load_codex_release_trust() -> dict[str, Any]:
    record = resources.files("review_broker.trust").joinpath("codex-release-v1.json")
    value = json.loads(record.read_text(encoding="utf-8"))
    _validate_trust_record(value)
    return value


def verify_codex_runtime(
    environment: Mapping[str, str],
    protected_runtime_root: Path,
    *,
    _trust: dict[str, Any] | None = None,
    _system: str | None = None,
    _machine: str | None = None,
    _expected_owner_uid: int = 0,
    _protection_anchor: Path = Path("/"),
) -> VerifiedCodexRuntime:
    """Bind PATH-selected npm release metadata to a protected native executable."""
    trust = load_codex_release_trust() if _trust is None else _trust
    _validate_trust_record(trust)
    system = platform.system() if _system is None else _system
    machine = platform.machine() if _machine is None else _machine
    platform_trust = _platform_trust(trust, system, machine)

    selected, launcher = _resolve_unambiguous_launcher(environment)
    distribution = trust["distribution"]
    package_root = launcher.parent.parent
    if launcher != package_root / distribution["launcher_entry"]:
        raise CodexRuntimeIdentityError("CODEX_LAUNCHER_LAYOUT_INVALID")
    launcher_sha256 = _verified_file_sha256(
        launcher, distribution["launcher_sha256"], "CODEX_LAUNCHER_IDENTITY_MISMATCH"
    )
    root_manifest = _verified_json_file(
        package_root / "package.json",
        distribution["package_json_sha256"],
        "CODEX_ROOT_PACKAGE_IDENTITY_MISMATCH",
    )
    if (
        root_manifest.get("name") != distribution["name"]
        or root_manifest.get("version") != distribution["version"]
        or root_manifest.get("bin") != {"codex": distribution["launcher_entry"]}
        or root_manifest.get("optionalDependencies", {}).get(platform_trust["npm_alias"])
        != platform_trust["npm_spec"]
    ):
        raise CodexRuntimeIdentityError("CODEX_ROOT_PACKAGE_METADATA_MISMATCH")

    platform_root = package_root / platform_trust["package_relative_path"]
    _reject_symlink_components(package_root, platform_root)
    platform_manifest = _verified_json_file(
        platform_root / "package.json",
        platform_trust["package_json_sha256"],
        "CODEX_PLATFORM_PACKAGE_IDENTITY_MISMATCH",
    )
    if (
        platform_manifest.get("name") != platform_trust["published_name"]
        or platform_manifest.get("version") != platform_trust["published_version"]
        or platform_manifest.get("os") != ["linux"]
        or platform_manifest.get("cpu") != ["x64"]
    ):
        raise CodexRuntimeIdentityError("CODEX_PLATFORM_PACKAGE_METADATA_MISMATCH")

    target_manifest = _verified_json_file(
        platform_root / platform_trust["target_manifest_entry"],
        platform_trust["target_manifest_sha256"],
        "CODEX_TARGET_MANIFEST_IDENTITY_MISMATCH",
    )
    if (
        target_manifest.get("layoutVersion") != 1
        or target_manifest.get("version") != distribution["version"]
        or target_manifest.get("target") != platform_trust["target"]
        or target_manifest.get("entrypoint") != "bin/codex"
    ):
        raise CodexRuntimeIdentityError("CODEX_TARGET_MANIFEST_METADATA_MISMATCH")
    installed_native = platform_root / platform_trust["native_entry"]
    native_sha256 = _verified_file_sha256(
        installed_native,
        platform_trust["native_sha256"],
        "CODEX_NATIVE_IDENTITY_MISMATCH",
        executable=True,
    )

    protected_root = protected_runtime_root.absolute()
    if protected_root.name != platform_trust["protected_runtime_directory"]:
        raise CodexRuntimeIdentityError("CODEX_PROTECTED_RUNTIME_PATH_INVALID")
    _verify_protected_ancestry(
        protected_root,
        expected_owner_uid=_expected_owner_uid,
        protection_anchor=_protection_anchor,
    )
    protected_manifest = _verified_json_file(
        protected_root / "codex-package.json",
        platform_trust["target_manifest_sha256"],
        "CODEX_PROTECTED_MANIFEST_IDENTITY_MISMATCH",
        owner_uid=_expected_owner_uid,
    )
    if protected_manifest != target_manifest:
        raise CodexRuntimeIdentityError("CODEX_PROTECTED_MANIFEST_METADATA_MISMATCH")
    executable = protected_root / "bin" / "codex"
    _verify_protected_ancestry(
        executable.parent,
        expected_owner_uid=_expected_owner_uid,
        protection_anchor=_protection_anchor,
    )
    protected_sha256 = _verified_file_sha256(
        executable,
        platform_trust["native_sha256"],
        "CODEX_PROTECTED_NATIVE_IDENTITY_MISMATCH",
        executable=True,
        owner_uid=_expected_owner_uid,
    )
    if protected_sha256 != native_sha256:
        raise CodexRuntimeIdentityError("CODEX_INSTALLED_AND_PROTECTED_NATIVE_MISMATCH")

    return VerifiedCodexRuntime(
        executable=executable,
        launcher_selected=selected,
        launcher_resolved=launcher,
        launcher_sha256=launcher_sha256,
        installed_native=installed_native,
        native_sha256=native_sha256,
        protected_runtime_root=protected_root,
        distribution=distribution["name"],
        distribution_version=distribution["version"],
        platform_alias=platform_trust["npm_alias"],
        platform_version=platform_trust["published_version"],
        root_dist_integrity=distribution["dist_integrity"],
        platform_dist_integrity=platform_trust["dist_integrity"],
    )


def verify_codex_release_archive(path: Path, expected_integrity: str) -> str:
    """Verify an official Codex archive against registry SHA-512 integrity."""
    if not expected_integrity.startswith("sha512-"):
        raise CodexRuntimeIdentityError("CODEX_RELEASE_INTEGRITY_FORMAT_INVALID")
    expected = expected_integrity.removeprefix("sha512-")
    sha512 = hashlib.sha512()
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha512.update(block)
            sha256.update(block)
    observed = base64.b64encode(sha512.digest()).decode("ascii")
    if not hmac.compare_digest(observed, expected):
        raise CodexRuntimeIdentityError("CODEX_RELEASE_INTEGRITY_MISMATCH")
    return sha256.hexdigest()


def _resolve_unambiguous_launcher(environment: Mapping[str, str]) -> tuple[Path, Path]:
    path_value = environment.get("PATH")
    if not path_value:
        raise CodexRuntimeIdentityError("CODEX_PATH_UNAVAILABLE")
    candidates: list[tuple[Path, Path, tuple[int, int]]] = []
    for entry in path_value.split(os.pathsep):
        directory = Path(entry)
        if not entry or not directory.is_absolute():
            raise CodexRuntimeIdentityError("CODEX_PATH_ENTRY_UNTRUSTED")
        candidate = directory / "codex"
        if not (candidate.exists() or candidate.is_symlink()):
            continue
        try:
            resolved = candidate.resolve(strict=True)
            metadata = resolved.stat()
        except OSError as exc:
            raise CodexRuntimeIdentityError("CODEX_LAUNCHER_UNAVAILABLE") from exc
        if not stat.S_ISREG(metadata.st_mode) or not os.access(resolved, os.X_OK):
            raise CodexRuntimeIdentityError("CODEX_LAUNCHER_TYPE_INVALID")
        candidates.append((candidate.absolute(), resolved, (metadata.st_dev, metadata.st_ino)))
    if not candidates:
        raise CodexRuntimeIdentityError("CODEX_LAUNCHER_NOT_FOUND")
    identities = {candidate[2] for candidate in candidates}
    if len(identities) != 1:
        raise CodexRuntimeIdentityError("CODEX_LAUNCHER_AMBIGUOUS")
    return candidates[0][0], candidates[0][1]


def _verified_json_file(
    path: Path,
    expected_sha256: str,
    error: str,
    *,
    owner_uid: int | None = None,
) -> dict[str, Any]:
    content = bytearray()
    _verified_file_sha256(
        path, expected_sha256, error, owner_uid=owner_uid, _capture=content
    )
    try:
        value = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexRuntimeIdentityError(error) from exc
    if not isinstance(value, dict):
        raise CodexRuntimeIdentityError(error)
    return value


def _verified_file_sha256(
    path: Path,
    expected_sha256: str,
    error: str,
    *,
    executable: bool = False,
    owner_uid: int | None = None,
    _capture: bytearray | None = None,
) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CodexRuntimeIdentityError(error) from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (executable and not before.st_mode & stat.S_IXUSR)
            or (owner_uid is not None and before.st_uid != owner_uid)
            or (owner_uid is not None and stat.S_IMODE(before.st_mode) & 0o022)
        ):
            raise CodexRuntimeIdentityError(error)
        digest = hashlib.sha256()
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
                if _capture is not None:
                    _capture.extend(block)
        after = os.fstat(descriptor)
        if _stat_identity(before) != _stat_identity(after):
            raise CodexRuntimeIdentityError(error)
    finally:
        os.close(descriptor)
    observed = digest.hexdigest()
    if not hmac.compare_digest(observed, expected_sha256):
        raise CodexRuntimeIdentityError(error)
    return observed


def _verify_protected_ancestry(
    runtime_root: Path,
    *,
    expected_owner_uid: int,
    protection_anchor: Path,
) -> None:
    try:
        anchor = protection_anchor.resolve(strict=True)
        resolved = runtime_root.resolve(strict=True)
    except OSError as exc:
        raise CodexRuntimeIdentityError("CODEX_PROTECTED_RUNTIME_UNAVAILABLE") from exc
    if resolved != runtime_root or not resolved.is_relative_to(anchor):
        raise CodexRuntimeIdentityError("CODEX_PROTECTED_RUNTIME_PATH_INVALID")
    current = resolved
    while True:
        metadata = current.lstat()
        if (
            current.is_symlink()
            or metadata.st_uid != expected_owner_uid
            or stat.S_IMODE(metadata.st_mode) & 0o022
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            raise CodexRuntimeIdentityError("CODEX_PROTECTED_RUNTIME_MUTABLE")
        if current == anchor:
            break
        if current.parent == current:
            raise CodexRuntimeIdentityError("CODEX_PROTECTED_RUNTIME_PATH_INVALID")
        current = current.parent


def _reject_symlink_components(root: Path, child: Path) -> None:
    try:
        relative = child.relative_to(root)
    except ValueError as exc:
        raise CodexRuntimeIdentityError("CODEX_PLATFORM_PACKAGE_LAYOUT_INVALID") from exc
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise CodexRuntimeIdentityError("CODEX_PLATFORM_PACKAGE_SYMLINK")


def _platform_trust(trust: dict[str, Any], system: str, machine: str) -> dict[str, Any]:
    matches = [
        value for value in trust["platforms"].values()
        if value.get("system") == system and value.get("machine") == machine
    ]
    if len(matches) != 1:
        raise CodexRuntimeIdentityError("CODEX_PLATFORM_UNSUPPORTED")
    return matches[0]


def _validate_trust_record(value: dict[str, Any]) -> None:
    try:
        distribution = value["distribution"]
        platforms = value["platforms"]
        required_distribution = {
            "name", "version", "registry_metadata_url", "tarball_url",
            "dist_integrity", "archive_sha256", "package_json_sha256",
            "launcher_entry", "launcher_sha256",
        }
        if value["schema_version"] != 1 or set(distribution) != required_distribution:
            raise ValueError
        if not isinstance(platforms, dict) or not platforms:
            raise ValueError
        hashes = [
            distribution["archive_sha256"], distribution["package_json_sha256"],
            distribution["launcher_sha256"],
        ]
        for platform_value in platforms.values():
            hashes.extend(platform_value[key] for key in (
                "archive_sha256", "package_json_sha256",
                "target_manifest_sha256", "native_sha256",
            ))
            if not platform_value["dist_integrity"].startswith("sha512-"):
                raise ValueError
        if not distribution["dist_integrity"].startswith("sha512-") or any(
            not isinstance(item, str) or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
            for item in hashes
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise CodexRuntimeIdentityError("CODEX_RELEASE_TRUST_RECORD_INVALID") from exc


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns
