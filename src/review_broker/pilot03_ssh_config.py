"""Bounded validation of the controlled GitHub Codespaces OpenSSH stanza."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

from .fileobservation import FileObservationError, read_regular_file_bounded

_ALIAS = re.compile(r"[A-Za-z0-9._-]+\Z")
_CONFIG_LIMIT = 64 * 1024


class Pilot03SshConfigError(ValueError):
    """The supplied SSH alias or controlled configuration is unusable."""


def validate_ssh_host_alias(
    *, codespace_identity: str, ssh_host_alias: str, ssh_config: Path,
) -> str:
    """Bind one literal Host stanza to the expected GitHub Codespace proxy."""
    if not isinstance(ssh_host_alias, str) or not _ALIAS.fullmatch(ssh_host_alias):
        raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_INVALID")
    if not isinstance(codespace_identity, str) or not re.fullmatch(
        r"[A-Za-z0-9-]+", codespace_identity,
    ):
        raise Pilot03SshConfigError("RB03_SSH_CODESPACE_BINDING_MISMATCH")
    path = Path(ssh_config)
    try:
        metadata = path.lstat()
        if (
            not path.is_absolute() or not stat.S_ISREG(metadata.st_mode)
            or path.is_symlink() or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.getuid()
        ):
            raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_UNAVAILABLE")
        text = read_regular_file_bounded(path, _CONFIG_LIMIT).decode("utf-8")
    except Pilot03SshConfigError:
        raise
    except (OSError, UnicodeError, FileObservationError) as exc:
        raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_UNAVAILABLE") from exc
    stanza = _literal_host_stanza(text, ssh_host_alias)
    _require_codespace_proxy(stanza, codespace_identity)
    return ssh_host_alias


def _literal_host_stanza(text: str, alias: str) -> list[str]:
    lines = text.splitlines()
    matches: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition(" ")
        if key.lower() in {"include", "match"}:
            raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_UNAVAILABLE")
        if key.lower() != "host":
            continue
        patterns = value.split()
        if any("*" in item or "?" in item or "!" in item for item in patterns):
            if alias in patterns:
                raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_INVALID")
            continue
        if alias in patterns:
            if patterns != [alias]:
                raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_INVALID")
            end = len(lines)
            for candidate in range(index + 1, len(lines)):
                directive = lines[candidate].strip().split(maxsplit=1)
                if directive and directive[0].lower() in {"host", "match"}:
                    end = candidate
                    break
            matches.append((index + 1, end))
    if len(matches) != 1:
        raise Pilot03SshConfigError("RB03_SSH_HOST_ALIAS_UNAVAILABLE")
    start, end = matches[0]
    return lines[start:end]


def _require_codespace_proxy(stanza: list[str], codespace_identity: str) -> None:
    proxy_values: list[str] = []
    for line in stanza:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(maxsplit=1)
        if parts[0].lower() == "proxycommand" and len(parts) == 2:
            proxy_values.append(parts[1])
        if parts[0].lower() in {"proxyjump", "include", "match"}:
            raise Pilot03SshConfigError("RB03_SSH_CODESPACE_BINDING_MISMATCH")
    if len(proxy_values) != 1:
        raise Pilot03SshConfigError("RB03_SSH_CODESPACE_BINDING_MISMATCH")
    separator = r"[ \t]+"
    pattern = (
        r"gh" + separator
        + r"(?:cs|codespace)" + separator
        + r"ssh" + separator
        + r"(?:-c|--codespace)" + separator
        + re.escape(codespace_identity) + separator
        + r"--stdio"
    )
    if re.fullmatch(pattern, proxy_values[0]) is None:
        raise Pilot03SshConfigError("RB03_SSH_CODESPACE_BINDING_MISMATCH")
