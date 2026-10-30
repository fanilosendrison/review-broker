"""Isolated v2 wrapper over the REAL v1 AttemptRecord representation.

No installed broker mutation, GitHub network, Codespace or inference.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import RLock

from jsonschema import Draft202012Validator
from review_broker.identity import artifact_identity, attempt_identity, canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, transition_record, StateTransitionError
from tests.reference_pre_model_v3 import dispatch_id


class MigrationError(ValueError):
    pass


_SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "pre_model_v3"
     / "journal-v2.compat.candidate.schema.json").read_text(encoding="utf-8")
)
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


def _validate(value):
    problems = list(_VALIDATOR.iter_errors(value))
    if problems:
        raise MigrationError("JOURNAL_V2_SCHEMA_INVALID:" + problems[0].message)
    if value["attempt_id"] != attempt_identity(value["request_id"], 1):
        raise MigrationError("JOURNAL_V2_ATTEMPT_MISMATCH")


def control_initial():
    return {"schema_version": 1, "generation": 0, "disposition": "UNRESERVED",
            "reservation_id": None, "authorization_id": None,
            "worker": None, "failure_receipt_id": None}


def encode(legacy: AttemptRecord, control: dict) -> bytes:
    value = legacy.as_dict()
    value["schema_version"] = 2
    value["pre_model_control"] = deepcopy(control)
    _validate(value)
    return canonical_bytes(value) + b"\n"


def decode(raw: bytes):
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise MigrationError("JOURNAL_V2_JSON_INVALID") from exc
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw:
        raise MigrationError("JOURNAL_V2_NONCANONICAL")
    _validate(value)
    legacy_data = {k: deepcopy(v) for k, v in value.items()
                   if k not in {"schema_version", "pre_model_control"}}
    legacy_data["schema_version"] = 1
    legacy = AttemptRecord.from_dict(legacy_data)
    if legacy.as_dict() != legacy_data:
        raise MigrationError("JOURNAL_V1_FIELDS_NOT_PRESERVED")
    return legacy, deepcopy(value["pre_model_control"])


def _event(record, kind, generation, reservation_id):
    evidence_id = artifact_identity(canonical_bytes({
        "event": kind, "request_id": record.request_id,
        "attempt_id": record.attempt_id, "generation": generation,
        "prior_history_count": len(record.history),
    }) + b"\n")
    return replace(
        record,
        evidence_ids=record.evidence_ids + (evidence_id,),
        history=record.history + ({
            "event": kind, "evidence_ids": [evidence_id],
            "pre_model": {"generation": generation,
                          "reservation_id": reservation_id},
        },),
    )


class CompatCAS:
    """Version-aware in-memory CAS using real production transition_record."""

    def __init__(self, legacy: AttemptRecord):
        if legacy.state is not AttemptState.REQUESTED or legacy.admission is None:
            raise MigrationError("INITIAL_ADMISSION_REQUIRED")
        self._lock = RLock()
        self.revision = 0
        self.legacy = legacy
        self.control = control_initial()
        encode(self.legacy, self.control)

    def snapshot(self):
        with self._lock:
            return self.revision, self.legacy, deepcopy(self.control)

    def cas(self, revision, operation):
        with self._lock:
            if revision != self.revision:
                raise MigrationError("STALE_CAS")
            legacy, control = operation(self.legacy, deepcopy(self.control))
            encode(legacy, control)
            self.legacy, self.control = legacy, control
            self.revision += 1
            return legacy, deepcopy(control)

    def reserve(self, revision=None):
        revision = self.snapshot()[0] if revision is None else revision
        def op(legacy, c):
            if c["disposition"] != "UNRESERVED" or legacy.state is not AttemptState.REQUESTED:
                raise MigrationError("ALREADY_RESERVED")
            c["generation"] = 1
            c["disposition"] = "RESERVED"
            c["authorization_id"] = legacy.request_id
            c["reservation_id"] = dispatch_id(
                legacy.request_id, legacy.attempt_id, 1, legacy.request_id
            )
            return _event(legacy, "PRE_MODEL_DISPATCH_RESERVED", 1,
                          c["reservation_id"]), c
        return self.cas(revision, op)[1]["reservation_id"]

    def worker(self, run_id=123, run_attempt=1, revision=None):
        revision = self.snapshot()[0] if revision is None else revision
        def op(legacy, c):
            if c["disposition"] != "RESERVED" or c["worker"] is not None:
                raise MigrationError("WORKER_CONFLICT")
            if type(run_id) is not int or type(run_attempt) is not int or min(run_id, run_attempt) < 1:
                raise MigrationError("WORKER_ID_INVALID")
            c["worker"] = {"run_id": run_id, "run_attempt": run_attempt}
            return _event(legacy, "PRE_MODEL_WORKER_BOUND", c["generation"],
                          c["reservation_id"]), c
        self.cas(revision, op)

    def token(self):
        _, _, c = self.snapshot()
        return {k: deepcopy(c[k]) for k in ("generation", "reservation_id", "worker")}

    def transition(self, target, evidence_id, token, revision=None):
        revision = self.snapshot()[0] if revision is None else revision
        def op(legacy, c):
            if (c["disposition"] != "RESERVED"
                or any(c[k] != token[k] for k in ("generation","reservation_id","worker"))
                or c["worker"] is None):
                raise MigrationError("WORKER_GENERATION_FENCED")
            if target not in {AttemptState.ADMITTED, AttemptState.PREPARED, AttemptState.ARMED}:
                raise MigrationError("UNSUPPORTED_TRANSITION")
            try:
                return transition_record(legacy, target, [evidence_id]), c
            except StateTransitionError as exc:
                raise MigrationError("REAL_TRANSITION_DENIED") from exc
        self.cas(revision, op)

    def invoked(self, token, revision=None):
        revision = self.snapshot()[0] if revision is None else revision
        def op(legacy, c):
            if (c["disposition"] != "RESERVED"
                or c["worker"] != token["worker"]
                or c["generation"] != token["generation"]
                or c["reservation_id"] != token["reservation_id"]):
                raise MigrationError("WORKER_GENERATION_FENCED")
            if legacy.state is not AttemptState.ARMED or legacy.invocation_count != 0:
                raise MigrationError("INVOCATION_ALREADY_USED")
            return replace(legacy, invocation_count=1), c
        self.cas(revision, op)

    def encoded(self):
        _, legacy, control = self.snapshot()
        return encode(legacy, control)
