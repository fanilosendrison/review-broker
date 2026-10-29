"""Credential-separated environment construction for private source reads."""
from __future__ import annotations

import os


class SourceAuthorizationError(RuntimeError):
    """Dedicated private-source authority is missing or unusable."""


def require_private_source_environment(
    repository: str,
    private_repositories: frozenset[str],
    source_token: str | None,
) -> dict[str, str]:
    if repository not in private_repositories:
        raise SourceAuthorizationError("PRIVATE_SOURCE_REPOSITORY_NOT_AUTHORIZED")
    if not source_token:
        raise SourceAuthorizationError("PRIVATE_SOURCE_CREDENTIAL_REQUIRED")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "PATH", "XDG_CONFIG_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    }
    environment.update({
        "GH_TOKEN": source_token,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_1": "!gh auth git-credential",
    })
    return environment


def _source_environment_for_repository(
    repository: str,
    private_repositories: frozenset[str],
    source_token: str | None,
) -> dict[str, str] | None:
    if repository not in private_repositories:
        return None
    return require_private_source_environment(
        repository, private_repositories, source_token
    )
