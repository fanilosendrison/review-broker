"""Canonical pinned reviewer command policy and credential-separated child environment."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class InvocationError(RuntimeError):
    """Codex invocation was rejected or did not complete successfully."""

    def __init__(self, message: str, *,
                 failure_observation: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.failure_observation = (
            dict(failure_observation) if failure_observation is not None else None
        )


@dataclass(frozen=True)
class CodexPolicy:
    distribution: str = "@openai/codex"
    distribution_version: str = "0.164.0"
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "xhigh"
    sandbox: str = "credential-isolated-read-only"


REQUIRED_FLAGS = (
    "--json", "--ephemeral", "--profile", "--strict-config", "--ignore-rules",
    "--skip-git-repo-check", "--model", "--output-schema", "--output-last-message",
)
REMOVED_ENVIRONMENT_KEYS = (
    "OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID", "GH_TOKEN", "GITHUB_TOKEN", "NODE_OPTIONS", "NODE_PATH",
    "CODEX_MANAGED_PACKAGE_ROOT", "CODEX_MANAGED_BY_BUN", "CODEX_MANAGED_BY_PNPM",
    "CODEX_MANAGED_BY_VITE_PLUS", "CODESPACE_NAME",
)
REMOVED_ENVIRONMENT_PREFIXES = ("LD_", "DYLD_", "ACTIONS_ID_TOKEN_")


def build_command(
    executable: Path, schema_path: Path, output_path: Path,
    policy: CodexPolicy, permission_profile: str,
) -> list[str]:
    if not executable.is_absolute():
        raise InvocationError("CODEX_EXECUTABLE_PATH_INVALID")
    return [
        str(executable), "exec", "--json", "--ephemeral", "--profile", permission_profile,
        "--strict-config", "--ignore-rules", "--skip-git-repo-check", "--model", policy.model,
        "-c", "features.shell_tool=false", "-c", f'model_reasoning_effort="{policy.reasoning_effort}"',
        "--output-schema", str(schema_path.resolve()), "--output-last-message", str(output_path.resolve()), "-",
    ]


def ensure_cli_compatibility(help_text: str) -> None:
    for flag in REQUIRED_FLAGS:
        if flag not in help_text:
            raise InvocationError(f"UNSUPPORTED_FLAG:{flag}")


def sanitized_environment(source: Mapping[str, str]) -> tuple[dict[str, str], tuple[str, ...]]:
    environment = dict(source)
    removed: list[str] = []
    for key in tuple(environment):
        if key in REMOVED_ENVIRONMENT_KEYS or key.startswith(REMOVED_ENVIRONMENT_PREFIXES):
            removed.append(key)
            environment.pop(key)
    environment["CODEX_MANAGED_BY_NPM"] = "1"
    return environment, tuple(sorted(removed))
