"""Controlled Codespace lifecycle and OpenSSH stdin transport for RB-PILOT-03."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Callable

from .codespace import CodespaceController
from .pilot03_remote_artifacts import Pilot03RemoteArtifacts
from .pilot03_remote_preflight import (
    REMOTE_PATH,
    run_remote_preflight,
)
from .pilot03_ssh_config import validate_ssh_host_alias
from .pilot_runtime_config import PilotRuntimeConfig, RB03_RUNTIME, require_runtime_config


def _remote_entrypoint(runtime: PilotRuntimeConfig) -> str:
    return f'''import os
os.execve("{runtime.remote_reviewctl}", ["{runtime.remote_reviewctl}", "{runtime.cli_command}", "--broker-wheel-sha256", os.environ["RB03_WHEEL_SHA256"]], {{"HOME":os.environ["HOME"],"PATH":os.environ["PATH"],"CODEX_HOME":os.environ["CODEX_HOME"],"LANG":"C.UTF-8","TZ":"UTC"}})
'''


class Pilot03CodespaceTransport:
    """Own one Codespace lifecycle while exposing one model-capable emission."""

    def __init__(
        self,
        codespace: str,
        ssh_host_alias: str,
        ssh_config: Path,
        *,
        runner: Callable[..., Any] = subprocess.run,
        lifecycle: CodespaceController | None = None,
        runtime: PilotRuntimeConfig = RB03_RUNTIME,
    ) -> None:
        self.codespace = codespace
        self.runtime = require_runtime_config(runtime)
        self.ssh_config = Path(ssh_config)
        self.ssh_host_alias = validate_ssh_host_alias(
            codespace_identity=codespace,
            ssh_host_alias=ssh_host_alias,
            ssh_config=self.ssh_config,
        )
        self.runner = runner
        self.lifecycle = lifecycle or CodespaceController(codespace, runner=runner)
        self.artifact_source = Pilot03RemoteArtifacts(
            codespace, self.ssh_host_alias, ssh_config,
            remote_python=self.runtime.remote_python, runner=runner, runtime=self.runtime,
        )
        self._emitted = False
        self._shutdown_observed = False

    def prepare(self) -> None:
        self.lifecycle.start()

    def preflight(
        self, *, source_sha: str, wheel_path: Path, wheel_sha256: str,
    ) -> None:
        if self.lifecycle.state() != "Available":
            raise RuntimeError("RB03_CODESPACE_NOT_AVAILABLE")
        if len(source_sha) != 40:
            raise RuntimeError("RB03_TRANSPORT_PREFLIGHT_FAILED")
        run_remote_preflight(
            codespace=self.codespace,
            ssh_host_alias=self.ssh_host_alias,
            ssh_config=self.ssh_config,
            wheel_path=wheel_path,
            wheel_sha256=wheel_sha256,
            runner=self.runner,
            runtime=self.runtime,
        )

    def emit_once(self, *, wheel_sha256: str) -> int:
        if self._emitted:
            raise RuntimeError("RB03_REMOTE_COMMAND_ALREADY_EMITTED")
        self._emitted = True
        result = self.runner(
            ["ssh", "-F", str(self.ssh_config), "-o", "BatchMode=yes", self.ssh_host_alias,
             "/usr/bin/env", "-i", "HOME=/home/codespace",
             "CODEX_HOME=/home/codespace/.codex", f"PATH={REMOTE_PATH}",
             f"RB03_WHEEL_SHA256={wheel_sha256}", self.runtime.remote_python, "-P", "-"],
            input=_remote_entrypoint(self.runtime), text=True, capture_output=True, check=False,
            timeout=3600, shell=False,
        )
        return result.returncode

    def shutdown(self) -> None:
        self.lifecycle.stop()
        self._shutdown_observed = self.lifecycle.state() == "Shutdown"

    def shutdown_observed(self) -> bool:
        return self._shutdown_observed
