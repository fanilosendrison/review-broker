"""Experimental initial-dispatch values and injected protocol; no I/O adapter."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol


@dataclass(frozen=True)
class InitialDispatchTargetV3:
    worker_workflow: str
    execution_ref: str
    executable_sha: str

    def __post_init__(self) -> None:
        for value in (self.worker_workflow, self.execution_ref):
            if (type(value) is not str or not value or value.strip() != value
                    or any(character in value for character in "\r\n\0")):
                raise ValueError("INITIAL_DISPATCH_TARGET_INVALID")
        if (type(self.executable_sha) is not str
                or re.fullmatch(r"[0-9a-f]{40}", self.executable_sha) is None):
            raise ValueError("INITIAL_DISPATCH_EXECUTABLE_INVALID")


@dataclass(frozen=True)
class InitialDispatchRequestV3:
    broker_repository: str
    request_id: str
    attempt_id: str
    claim_ref: str
    reservation_id: str
    generation: int
    worker_workflow: str
    execution_ref: str
    executable_sha: str


class InitialDispatchStatusV3(str, Enum):
    OBSERVED = "OBSERVED"
    ACCEPTED_NO_RUN_ID = "ACCEPTED_NO_RUN_ID"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class InitialDispatchResultV3:
    """Injected response only, never authenticated Actions execution or Worker ID."""

    status: InitialDispatchStatusV3
    run_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not InitialDispatchStatusV3:
            raise ValueError("INITIAL_DISPATCH_RESULT_INVALID")
        if self.run_id is not None and (type(self.run_id) is not int or self.run_id < 1):
            raise ValueError("INITIAL_DISPATCH_RUN_ID_INVALID")
        if self.status is InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID and self.run_id is not None:
            raise ValueError("INITIAL_DISPATCH_RUN_ID_UNEXPECTED")


class InitialDispatchTransportV3(Protocol):
    def dispatch(self, request: InitialDispatchRequestV3) -> InitialDispatchResultV3: ...
