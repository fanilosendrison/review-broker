"""Factual process-dispatch observation for the synthetic pilot."""
from __future__ import annotations

import subprocess
from typing import Any, Callable

NativeRunner = Callable[..., subprocess.CompletedProcess[bytes]]


class PilotRunner:
    """Delegate one subprocess call unchanged and retain only dispatch facts."""

    def __init__(self, native_runner: NativeRunner | None = None) -> None:
        self._native_runner = subprocess.run if native_runner is None else native_runner
        self._runner_dispatches = 0
        self._process_start_status = "NOT_DISPATCHED"

    # Variadic Any mirrors subprocess.run's overloaded call surface exactly;
    # this adapter deliberately forwards every positional and keyword argument.
    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if self._runner_dispatches:
            raise RuntimeError("PILOT_RUNNER_ALREADY_DISPATCHED")
        self._runner_dispatches = 1
        try:
            result = self._native_runner(*args, **kwargs)
        except subprocess.TimeoutExpired:
            self._process_start_status = "CONFIRMED"
            raise
        except Exception:
            self._process_start_status = "UNDETERMINED"
            raise
        self._process_start_status = "CONFIRMED"
        return result

    def observation(self) -> dict[str, int | str]:
        if self._process_start_status == "CONFIRMED":
            process_invocations: int | str = 1
        elif self._process_start_status == "NOT_DISPATCHED":
            process_invocations = 0
        else:
            process_invocations = "UNDETERMINED"
        return {
            "runner_dispatches": self._runner_dispatches,
            "process_start_status": self._process_start_status,
            "inference_process_invocations": process_invocations,
        }
