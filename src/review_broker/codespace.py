"""Bounded GitHub Codespace lifecycle and transport control."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Mapping


class CodespaceError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


class CodespaceController:
    def __init__(
        self,
        name: str,
        *,
        runner: Runner = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        environment: Mapping[str, str] | None = None,
    ):
        if not re.fullmatch(r"[A-Za-z0-9-]+", name):
            raise ValueError("CODESPACE_NAME_INVALID")
        self.name = name
        self.runner = runner
        self.sleep = sleep
        self.environment = dict(environment) if environment is not None else None

    def start(self, *, attempts: int = 30, interval_seconds: float = 5) -> None:
        self._run(["gh", "api", "--method", "POST", f"user/codespaces/{self.name}/start", "--silent"])
        self.wait_for("Available", attempts=attempts, interval_seconds=interval_seconds)

    def state(self) -> str:
        result = self._run(
            ["gh", "codespace", "view", "-c", self.name, "--json", "state"]
        )
        try:
            return json.loads(result.stdout)["state"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CodespaceError("CODESPACE_STATE_INVALID") from exc

    def wait_for(self, desired: str, *, attempts: int, interval_seconds: float) -> None:
        if attempts < 1:
            raise ValueError("attempts must be positive")
        observed = "UNOBSERVED"
        for index in range(attempts):
            observed = self.state()
            if observed == desired:
                return
            if index + 1 < attempts:
                self.sleep(interval_seconds)
        raise CodespaceError(f"CODESPACE_STATE_TIMEOUT:expected={desired}:actual={observed}")

    def transfer(self, source: Path, remote_directory: str) -> None:
        source = source.resolve(strict=True)
        if source.is_symlink() or not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_directory):
            raise CodespaceError("TRANSFER_PATH_INVALID")
        self._run([
            "gh", "codespace", "cp", "-c", self.name, "-r",
            str(source), f"remote:{remote_directory}",
        ])

    def recover(self, remote_path: str, destination: Path) -> None:
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_path):
            raise CodespaceError("RECOVERY_PATH_INVALID")
        destination = destination.resolve()
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._run([
            "gh", "codespace", "cp", "-c", self.name, "-r",
            f"remote:{remote_path}", str(destination),
        ])

    def execute(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        if not arguments or any("\x00" in argument for argument in arguments):
            raise CodespaceError("REMOTE_ARGUMENT_INVALID")
        return self._run(["gh", "codespace", "ssh", "-c", self.name, "--", *arguments])

    def stop(self, *, attempts: int = 30, interval_seconds: float = 5) -> None:
        self._run(["gh", "codespace", "stop", "-c", self.name])
        try:
            self.wait_for("Shutdown", attempts=attempts, interval_seconds=interval_seconds)
        except CodespaceError as exc:
            raise CodespaceError("SHUTDOWN_NOT_CONFIRMED") from exc

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = self.runner(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            shell=False,
            env=self.environment,
        )
        if result.returncode != 0:
            raise CodespaceError(f"COMMAND_FAILED:{command[1]}:{command[2]}")
        return result
