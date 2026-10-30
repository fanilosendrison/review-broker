"""EXPERIMENTAL/UNACCEPTED reference for #51 pre-model v3 contracts.

No network, GitHub mutation, Codespace, or model invocation is possible.
This module is under tests/, NOT src/review_broker.  External authority
is injected as explicit test evidence and is not proven by the model.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from review_broker.evidence import validate_shutdown_observation
from review_broker.identity import attempt_identity, canonical_bytes


SCHEMA_ROOT = Path(__file__).parent / "fixtures" / "pre_model_v3"
SCHEMA_FILES = {
    "journal": "journal-v2.candidate.schema.json",
    "failure": "failure-v1.candidate.schema.json",
    "recovery": "recovery-v1.candidate.schema.json",
}
SCHEMAS = {
    key: json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8"))
    for key, filename in SCHEMA_FILES.items()
}
for _schema in SCHEMAS.values():
    Draft202012Validator.check_schema(_schema)
VALIDATORS = {
    key: Draft202012Validator(schema, format_checker=FormatChecker())
    for key, schema in SCHEMAS.items()
}

REQUEST_HEX = "request:sha256:" + "a" * 64
ADMISSION_ID = "artifact:sha256:" + "1" * 64
OBSERVATION_ID = "artifact:sha256:" + "2" * 64
PACKET_ID = "artifact:sha256:" + "3" * 64
CODESPACE_NAME = "qualification-fake-codespace"
FIXED_NOW = "2026-10-30T00:00:00Z"


class ProtocolError(ValueError):
    """Refuse rather than invent a model call or trusted source evidence."""


def _check(kind: str, data: dict[str, Any]) -> None:
    errors = sorted(
        VALIDATORS[kind].iter_errors(data), key=lambda e: (list(map(str, e.path)), e.message)
    )
    if errors:
        raise ProtocolError(f"SCHEMA_{kind.upper()}_INVALID:{errors[0].message}")


def identity(prefix: str, value: dict[str, Any], *, newline: bool = False) -> str:
    data = canonical_bytes(value) + (b"\n" if newline else b"")
    return prefix + ":sha256:" + hashlib.sha256(data).hexdigest()


def dispatch_id(request_id: str, attempt_id: str, generation: int,
                authorization_id: str) -> str:
    return identity("preparation-dispatch", {
        "schema_version": 1, "request_id": request_id,
        "attempt_id": attempt_id, "generation": generation,
        "authorization_id": authorization_id,
    })


def failure_id(receipt: dict[str, Any]) -> str:
    _check("failure", receipt)
    return identity("artifact", receipt, newline=True)


def recovery_id(receipt: dict[str, Any]) -> str:
    _check("recovery", receipt)
    return identity("pre-model-recovery", receipt)


def strict_decode_v2(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ProtocolError("JOURNAL_BYTES_INVALID") from exc
    if not isinstance(parsed, dict) or canonical_bytes(parsed) + b"\n" != raw:
        raise ProtocolError("JOURNAL_NONCANONICAL")
    validate_record(parsed)
    return parsed


def validate_record(record: dict[str, Any]) -> None:
    """Schema plus semantic relationships not expressible by JSON Schema alone."""
    _check("journal", record)
    c = record["pre_model_control"]
    g = c["generation"]
    if record["attempt_id"] != attempt_identity(record["request_id"], 1):
        raise ProtocolError("ATTEMPT_ID_MISMATCH")
    if c["disposition"] in {"BLOCKED", "REFUSED_PERMANENT"}:
        receipt_id = c["failure_receipt_id"]
        matching = [
            e for e in record["history"]
            if e["kind"] == "PREMODEL_FAILED"
            and e["generation"] == g and e["evidence_id"] == receipt_id
            and isinstance(e["receipt"], dict)
        ]
        if len(matching) != 1 or failure_id(matching[0]["receipt"]) != receipt_id:
            raise ProtocolError("FAILURE_EVIDENCE_MISSING_OR_TAMPERED")
        f = matching[0]["receipt"]
        if f["request_id"] != record["request_id"] or f["attempt_id"] != record["attempt_id"]:
            raise ProtocolError("FAILURE_ATTEMPT_MISMATCH")
        if f["generation"] != g or f["reservation_id"] != c["reservation_id"]:
            raise ProtocolError("FAILURE_GENERATION_MISMATCH")
        required_class = "PERMANENT" if c["disposition"] == "REFUSED_PERMANENT" else None
        if required_class and f["classification"] != required_class:
            raise ProtocolError("FAILURE_CLASS_MISMATCH")
        if c["disposition"] == "BLOCKED" and f["classification"] not in {"TRANSIENT", "UNKNOWN"}:
            raise ProtocolError("FAILURE_CLASS_MISMATCH")
        if receipt_id not in record["evidence_ids"]:
            raise ProtocolError("FAILURE_NOT_IN_EVIDENCE_SET")
    if g > 1:
        matching = [
            e for e in record["history"]
            if e["kind"] == "RECOVERY_AUTHORIZED"
            and e["generation"] == g
            and isinstance(e["receipt"], dict)
        ]
        if len(matching) != 1 or recovery_id(matching[0]["receipt"]) != c["authorization_id"]:
            raise ProtocolError("RECOVERY_AUTHORIZATION_NOT_BOUND")
        if matching[0]["receipt"]["previous_generation"] != g - 1:
            raise ProtocolError("RECOVERY_PREDECESSOR_INVALID")
    elif g == 1 and c["authorization_id"] != record["request_id"]:
        raise ProtocolError("INITIAL_AUTHORITY_INVALID")
    if record["state"] in {"PREPARED", "ARMED"}:
        if c["disposition"] != "RESERVED" or c["worker"] is None:
            raise ProtocolError("MODEL_CAPABLE_CONTROL_INVALID")
        if record["packet_evidence_id"] not in record["evidence_ids"]:
            raise ProtocolError("PACKET_NOT_IN_EVIDENCE_SET")
    if record["state"] == "ARMED" and record["invocation_count"] != 1:
        raise ProtocolError("ARMED_INVOCATION_NOT_RESERVED")
    if c["disposition"] in {"BLOCKED", "REFUSED_PERMANENT"} and record["state"] in {"PREPARED", "ARMED"}:
        raise ProtocolError("BLOCKED_MODEL_CAPABLE_STATE")


class MemoryClaim:
    """One deterministic claim, serialized by injected compare-and-swap.

    The in-memory lock is NOT a proof that a real GitHub ref is a
    universally sufficient CAS under all network failures.
    """

    def __init__(self, request_id: str = REQUEST_HEX, admission_id: str = ADMISSION_ID):
        if not isinstance(request_id, str) or not request_id.startswith("request:sha256:"):
            raise ProtocolError("REQUEST_ID_INVALID")
        self.lock = threading.RLock()
        self.rev = 0
        self.request_id = request_id
        self.admission_id = admission_id
        self._record = {
            "schema_version": 2,
            "request_id": request_id,
            "attempt_id": attempt_identity(request_id, 1),
            "state": "REQUESTED",
            "evidence_ids": [admission_id],
            "invocation_count": 0,
            "evidence_locator_plan": None,
            "evidence_locator": None,
            "publication_intent": None,
            "publication_receipt": None,
            "admission": {"request_id": request_id, "admission_evidence_id": admission_id},
            "packet_evidence_id": None,
            "pre_model_control": {
                "schema_version": 1, "generation": 0,
                "disposition": "UNRESERVED", "reservation_id": None,
                "authorization_id": None, "worker": None,
                "failure_receipt_id": None,
            },
            "history": [{
                "kind": "CLAIMED", "generation": 0,
                "evidence_id": admission_id, "receipt": None,
            }],
        }
        validate_record(self._record)

    def read(self) -> tuple[int, dict[str, Any]]:
        with self.lock:
            return self.rev, deepcopy(self._record)

    @staticmethod
    def _append(r: dict[str, Any], kind: str, evidence_id: str | None = None,
                receipt: dict[str, Any] | None = None) -> None:
        r["history"].append({
            "kind": kind, "generation": r["pre_model_control"]["generation"],
            "evidence_id": evidence_id, "receipt": deepcopy(receipt),
        })
        if evidence_id is not None and evidence_id not in r["evidence_ids"]:
            r["evidence_ids"].append(evidence_id)

    def cas(self, expected_revision: int,
            mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self.lock:
            if expected_revision != self.rev:
                raise ProtocolError("STALE_COMPARE_AND_SWAP")
            r = deepcopy(self._record)
            mutate(r)
            validate_record(r)
            self._record = r
            self.rev += 1
            return deepcopy(r)

    def _snapshot_for(self, expected_revision: int | None) -> int:
        rev, _ = self.read()
        return rev if expected_revision is None else expected_revision

    def reserve_initial(self, *, expected_revision: int | None = None) -> dict[str, Any]:
        def change(r):
            c = r["pre_model_control"]
            if r["state"] != "REQUESTED" or c["disposition"] != "UNRESERVED" or c["generation"] != 0:
                raise ProtocolError("AUTO_DISPATCH_ALREADY_RESERVED")
            c.update(generation=1, disposition="RESERVED",
                     authorization_id=r["request_id"], worker=None,
                     failure_receipt_id=None)
            c["reservation_id"] = dispatch_id(
                r["request_id"], r["attempt_id"], 1, r["request_id"])
            self._append(r, "DISPATCH_RESERVED")
        return self.cas(self._snapshot_for(expected_revision), change)

    def worker_token(self, run_id: int = 123, run_attempt: int = 1) -> dict[str, Any]:
        _, r = self.read()
        return {
            "generation": r["pre_model_control"]["generation"],
            "reservation_id": r["pre_model_control"]["reservation_id"],
            "run_id": run_id,
            "run_attempt": run_attempt,
        }

    @staticmethod
    def _require_worker(r: dict[str, Any], token: dict[str, Any]) -> None:
        c = r["pre_model_control"]
        if (c["disposition"] != "RESERVED"
                or c["generation"] != token["generation"]
                or c["reservation_id"] != token["reservation_id"]
                or c["worker"] != {"run_id": token["run_id"], "run_attempt": token["run_attempt"]}):
            raise ProtocolError("WORKER_FENCE_REJECTED")

    def bind_worker(self, token: dict[str, Any], *, trusted_run_context: bool = False,
                    expected_revision: int | None = None) -> dict[str, Any]:
        if not trusted_run_context:
            raise ProtocolError("WORKFLOW_RUN_AUTHORITY_UNVERIFIED")
        def change(r):
            c = r["pre_model_control"]
            if (r["state"] not in {"REQUESTED","ADMITTED"} or c["disposition"] != "RESERVED"
                    or c["generation"] != token["generation"] or c["reservation_id"] != token["reservation_id"]
                    or c["worker"] is not None):
                raise ProtocolError("WORKER_BINDING_CONFLICT")
            c["worker"] = {"run_id": token["run_id"], "run_attempt": token["run_attempt"]}
            self._append(r,"WORKER_BOUND")
        return self.cas(self._snapshot_for(expected_revision), change)

    def admit(self, token: dict[str, Any], *, expected_revision: int | None = None) -> dict[str, Any]:
        def change(r):
            self._require_worker(r,token)
            if r["state"] != "REQUESTED":
                raise ProtocolError("INVALID_ADMITTED_TRANSITION")
            r["state"] = "ADMITTED"
            self._append(r,"ADMITTED",self.admission_id)
        return self.cas(self._snapshot_for(expected_revision),change)

    def can_fetch(self,token: dict[str,Any]) -> None:
        _,r=self.read()
        self._require_worker(r,token)
        if r["state"] not in {"REQUESTED","ADMITTED"}:
            raise ProtocolError("SOURCE_FETCH_NOT_PERMITTED")

    def prepare(self, token: dict[str,Any], packet_id: str = PACKET_ID,
                *, expected_revision: int | None = None) -> dict[str, Any]:
        def change(r):
            self._require_worker(r,token)  # checked under the SAME CAS as PREPARED
            if r["state"] != "ADMITTED" or r["packet_evidence_id"] is not None:
                raise ProtocolError("PREPARED_BOUNDARY_BLOCKED")
            r["state"]="PREPARED"
            r["packet_evidence_id"]=packet_id
            self._append(r,"PREPARED",packet_id)
        return self.cas(self._snapshot_for(expected_revision),change)

    def arm(self, token: dict[str,Any], *, expected_revision: int | None = None) -> dict[str, Any]:
        def change(r):
            self._require_worker(r,token)  # checked under SAME CAS as ARMED
            if r["state"] != "PREPARED" or r["invocation_count"] != 0:
                raise ProtocolError("MODEL_INVOCATION_ALREADY_RESERVED")
            r["state"]="ARMED"
            r["invocation_count"]=1
            self._append(r,"ARMED")
        return self.cas(self._snapshot_for(expected_revision),change)

    def fail(self, token: dict[str,Any], classification: str,
             reason_code: str, *, observed_evidence_id: str = OBSERVATION_ID,
             trusted_observation_id: str | None = None,
             reference_id: str | None = "contract",
             expected_revision: int | None = None) -> dict[str, Any]:
        if trusted_observation_id != observed_evidence_id:
            raise ProtocolError("FAILURE_OBSERVATION_UNVERIFIED")
        def change(r):
            self._require_worker(r,token)
            if r["state"] not in {"REQUESTED","ADMITTED"}:
                raise ProtocolError("FAILURE_AFTER_PREPARED")
            c=r["pre_model_control"]
            receipt={
                "schema_version":1,"evidence_type":"pre-model-preparation-failure",
                "request_id":r["request_id"],"attempt_id":r["attempt_id"],
                "admission_evidence_id":self.admission_id,
                "generation":c["generation"],"reservation_id":c["reservation_id"],
                "workflow_run_id":token["run_id"],"workflow_run_attempt":token["run_attempt"],
                "classification":classification,"reason_code":reason_code,
                "reference_id":reference_id,
                "observation_evidence_id":observed_evidence_id,"observed_at":FIXED_NOW,
            }
            eid=failure_id(receipt)
            c["failure_receipt_id"]=eid
            c["disposition"]="REFUSED_PERMANENT" if classification=="PERMANENT" else "BLOCKED"
            self._append(r,"PREMODEL_FAILED",eid,receipt)
        return self.cas(self._snapshot_for(expected_revision),change)

    def recover(self, authorization: dict[str,Any], *,
                trusted_actor_id: int | None = None,
                observed_quiescent: bool = False,
                trusted_run_observation_id: str | None = None,
                expected_revision: int | None = None) -> dict[str,Any]:
        _check("recovery",authorization)
        auth_id=recovery_id(authorization)
        if (trusted_actor_id != authorization["actor_github_id"]
                or trusted_run_observation_id != authorization["prior_run_observation_id"]
                or not observed_quiescent):
            raise ProtocolError("RECOVERY_AUTHORITY_OR_QUIESCENCE_UNVERIFIED")
        def change(r):
            c=r["pre_model_control"]
            if r["state"] not in {"REQUESTED","ADMITTED"} or r["packet_evidence_id"] is not None or r["invocation_count"]:
                raise ProtocolError("RECOVERY_AFTER_PREPARED_OR_ARMED")
            if c["disposition"] not in {"BLOCKED","RESERVED"}:
                raise ProtocolError("RECOVERY_DISPOSITION_INVALID")
            if (authorization["request_id"]!=r["request_id"] or authorization["attempt_id"]!=r["attempt_id"]
                    or authorization["previous_generation"]!=c["generation"]
                    or authorization["previous_reservation_id"]!=c["reservation_id"]):
                raise ProtocolError("RECOVERY_PREDECESSOR_MISMATCH")
            if any(e["kind"]=="RECOVERY_AUTHORIZED" and isinstance(e["receipt"],dict)
                   and e["receipt"]["authorization_nonce"]==authorization["authorization_nonce"]
                   for e in r["history"]):
                raise ProtocolError("RECOVERY_NONCE_REPLAY")
            c.update(generation=c["generation"]+1,disposition="RESERVED",
                     worker=None,failure_receipt_id=None,authorization_id=auth_id)
            c["reservation_id"]=dispatch_id(r["request_id"],r["attempt_id"],c["generation"],auth_id)
            evid=identity("artifact",authorization,newline=True)
            self._append(r,"RECOVERY_AUTHORIZED",evid,authorization)
            self._append(r,"DISPATCH_RESERVED")
        return self.cas(self._snapshot_for(expected_revision),change)

    def stop_permanent(self, shutdown_receipt: dict[str,Any], *,
                       observed_owner: dict[str,Any] | None = None,
                       trusted_resource_observation: bool = False,
                       expected_revision: int | None = None) -> dict[str,Any]:
        if not trusted_resource_observation:
            raise ProtocolError("RESOURCE_OWNERSHIP_UNVERIFIED")
        def change(r):
            c=r["pre_model_control"]
            if r["state"] not in {"REQUESTED","ADMITTED"} or c["disposition"]!="REFUSED_PERMANENT" or r["invocation_count"]!=0:
                raise ProtocolError("TERMINAL_PREMODEL_REFUSAL_INVALID")
            if any(e["kind"] in {"ARMED","PREPARED"} for e in r["history"]):
                raise ProtocolError("PRIOR_MODEL_CAPABLE_HISTORY")
            if shutdown_receipt.get("codespace_name")!=CODESPACE_NAME:
                raise ProtocolError("CODESPACE_IDENTITY_MISMATCH")
            if observed_owner is not None:
                if observed_owner != {
                    "request_id":r["request_id"],"attempt_id":r["attempt_id"],
                    "generation":c["generation"],"worker":c["worker"],
                }:
                    raise ProtocolError("CROSS_REQUEST_CODESPACE_OWNER_MISMATCH")
            try:
                eid=validate_shutdown_observation(shutdown_receipt,request_id=r["request_id"],attempt_id=r["attempt_id"])
            except Exception as exc:
                raise ProtocolError("SHUTDOWN_RECEIPT_INVALID") from exc
            r["state"]="STOPPED"
            self._append(r,"STOPPED",eid)
        return self.cas(self._snapshot_for(expected_revision),change)

    def sweep(self) -> str:
        """Discovery only; caller must actually dispatch after winning reservation."""
        _,r=self.read()
        c=r["pre_model_control"]
        if r["state"] == "REQUESTED" and c["disposition"] == "UNRESERVED":
            try:
                self.reserve_initial()
            except ProtocolError as exc:
                if str(exc) not in {"STALE_COMPARE_AND_SWAP","AUTO_DISPATCH_ALREADY_RESERVED"}:
                    raise
                return "OBSERVE_EXISTING_RESERVATION"
            return "DISPATCH_RESERVED_ONCE"
        if c["disposition"] == "REFUSED_PERMANENT" and r["state"] != "STOPPED":
            return "CLEANUP_ONLY"
        if c["disposition"] in {"BLOCKED","RESERVED"}:
            return "AWAIT_EXPLICIT_OBSERVATION_OR_RECOVERY"
        return "NO_ACTION"

    def encode(self) -> bytes:
        _,record=self.read()
        return canonical_bytes(record)+b"\n"
