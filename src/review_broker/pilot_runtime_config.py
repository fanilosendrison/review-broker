"""Closed runtime configurations for prepared synthetic controller pilots."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PilotRuntimeConfig:
    """Immutable paths and entrypoint for one explicitly admitted pilot."""

    pilot_id: str
    cli_command: str
    remote_root: str
    bootstrap_root: str
    package_version: str

    @property
    def remote_wheel(self) -> str:
        return f"{self.bootstrap_root}/review_broker-{self.package_version}-py3-none-any.whl"

    @property
    def remote_venv(self) -> str:
        return f"{self.bootstrap_root}/venv"

    @property
    def remote_python(self) -> str:
        return f"{self.remote_venv}/bin/python"

    @property
    def remote_reviewctl(self) -> str:
        return f"{self.remote_venv}/bin/reviewctl"

    @property
    def artifact_paths(self) -> dict[str, str]:
        return {
            "pilot-claim.json": f"{self.remote_root}.claim.json",
            "pilot-armed.json": f"{self.remote_root}/pilot-armed.json",
            "pilot-summary.json": f"{self.remote_root}/pilot-summary.json",
            "pilot-failure.json": f"{self.remote_root}/pilot-failure.json",
            "codex-events.jsonl": f"{self.remote_root}/evidence/codex-events.jsonl",
            "codex-stderr.txt": f"{self.remote_root}/evidence/codex-stderr.txt",
            "codex-final.json": f"{self.remote_root}/evidence/codex-final.json",
            "codex-exit-code.txt": f"{self.remote_root}/evidence/codex-exit-code.txt",
        }


RB03_RUNTIME = PilotRuntimeConfig(
    pilot_id="RB-PILOT-03",
    cli_command="pilot-synthetic-03",
    remote_root="/tmp/review-broker-pilot-26-rb03",
    bootstrap_root="/tmp/review-broker-pilot-26-rb03-bootstrap",
    package_version="0.4.5",
)
RB04_RUNTIME = PilotRuntimeConfig(
    pilot_id="RB-PILOT-04",
    cli_command="pilot-synthetic-04",
    remote_root="/tmp/review-broker-pilot-26-rb04",
    bootstrap_root="/tmp/review-broker-pilot-26-rb04-bootstrap",
    package_version="0.4.5",
)


def require_runtime_config(value: PilotRuntimeConfig) -> PilotRuntimeConfig:
    """Reject caller-constructed and arbitrary pilot configurations."""
    if value is not RB03_RUNTIME and value is not RB04_RUNTIME:
        raise ValueError("PILOT_RUNTIME_CONFIG_UNSUPPORTED")
    return value
