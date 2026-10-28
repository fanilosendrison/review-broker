"""Controlled Codespace lifecycle and OpenSSH stdin transport for RB-PILOT-03."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Callable

from .codespace import CodespaceController
from .pilot03_remote_artifacts import Pilot03RemoteArtifacts

_REMOTE_ENTRYPOINT = r'''import os
os.execvpe("reviewctl", ["reviewctl", "pilot-synthetic-03", "--broker-wheel-sha256", os.environ["RB03_WHEEL_SHA256"]], {"HOME":os.environ["HOME"],"PATH":os.environ["PATH"],"CODEX_HOME":os.environ["CODEX_HOME"],"LANG":"C.UTF-8","TZ":"UTC"})
'''


class Pilot03CodespaceTransport:
    """Own one Codespace lifecycle while exposing one model-capable emission."""

    def __init__(
        self,
        codespace: str,
        ssh_config: Path,
        *,
        runner: Callable[..., Any] = subprocess.run,
        lifecycle: CodespaceController | None = None,
    ) -> None:
        self.codespace = codespace
        self.ssh_config = Path(ssh_config)
        self.runner = runner
        self.lifecycle = lifecycle or CodespaceController(codespace, runner=runner)
        self.artifact_source = Pilot03RemoteArtifacts(codespace, ssh_config, runner=runner)
        self._emitted = False
        self._shutdown_observed = False

    def prepare(self) -> None:
        self.lifecycle.start()

    def preflight(self, *, source_sha: str, wheel_sha256: str) -> None:
        if self.lifecycle.state() != "Available":
            raise RuntimeError("RB03_CODESPACE_NOT_AVAILABLE")
        if len(source_sha) != 40 or len(wheel_sha256) != 64 or not self.ssh_config.is_file():
            raise RuntimeError("RB03_TRANSPORT_PREFLIGHT_FAILED")

    def emit_once(self, *, wheel_sha256: str) -> int:
        if self._emitted:
            raise RuntimeError("RB03_REMOTE_COMMAND_ALREADY_EMITTED")
        self._emitted = True
        result = self.runner(
            ["ssh", "-F", str(self.ssh_config), "-o", "BatchMode=yes", self.codespace,
             "/usr/bin/env", "-i", "HOME=/home/codespace",
             "CODEX_HOME=/home/codespace/.codex", "PATH=/usr/local/bin:/usr/bin:/bin",
             f"RB03_WHEEL_SHA256={wheel_sha256}", "python3", "-P", "-"],
            input=_REMOTE_ENTRYPOINT, text=True, capture_output=True, check=False,
            timeout=3600, shell=False,
        )
        return result.returncode

    def shutdown(self) -> None:
        self.lifecycle.stop()
        self._shutdown_observed = self.lifecycle.state() == "Shutdown"

    def shutdown_observed(self) -> bool:
        return self._shutdown_observed
