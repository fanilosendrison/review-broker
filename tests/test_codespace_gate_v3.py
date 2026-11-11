from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from review_broker.codespace_gate_v3 import (
    CodespaceAccessRequestV3,
    CodespaceEffectV3,
    TrustedWorkerContextV3,
    authorize_codespace_effect_v3,
)
from review_broker.github_journal_v3 import VerifiedJournalSnapshotV3
from review_broker.identity import artifact_identity, canonical_bytes, request_identity
from review_broker.journal_record_v3 import (
    JournalRecordV3,
    WorkerIdentityV3,
    encode_journal_v2,
    initial_record,
)
from review_broker.pre_model_control_v3 import (
    refuse_permanently,
    register_worker,
    reserve_initial,
    transition_state,
)
from review_broker.queue import AttemptState, transition_record


REPOSITORY = "example/review-broker"
REQUEST = {"schema_version": 3, "subject": {"repository": REPOSITORY}, "references": []}
REQUEST_ID = request_identity(REQUEST)
ADMISSION_ID = "artifact:sha256:" + "1" * 64
ADMISSION = {"request_id": REQUEST_ID, "admission_evidence_id": ADMISSION_ID,
             "repository_id": 123, "subject": "exact", "reference_ids": ["contract"]}
PACKET_ID = "artifact:sha256:" + "2" * 64
OBSERVATION_ID = "artifact:sha256:" + "3" * 64
CODESPACE = "experimental-codespace"
WORKER = WorkerIdentityV3(500, 1)


def build_record(stage: str = "PREPARED") -> JournalRecordV3:
    record = initial_record(REQUEST_ID, ADMISSION)
    if stage == "REQUESTED":
        return record
    record = reserve_initial(record)
    control = record.control
    record = register_worker(
        record, control.reservation_id, 1, WORKER,
        "artifact:sha256:" + "5" * 64,
    )
    if stage == "BOUND":
        return record
    record = transition_state(
        record, AttemptState.ADMITTED, ADMISSION_ID,
        record.control.reservation_id, 1, WORKER,
    )
    if stage == "ADMITTED":
        return record
    if stage == "REFUSED":
        receipt: dict[str, object] = {
            "schema_version": 1,
            "evidence_type": "pre-model-preparation-failure",
            "request_id": REQUEST_ID,
            "attempt_id": record.attempt.attempt_id,
            "admission_evidence_id": None,
            "generation": 1,
            "reservation_id": record.control.reservation_id,
            "workflow_run_id": WORKER.run_id,
            "workflow_run_attempt": WORKER.run_attempt,
            "classification": "PERMANENT",
            "reason_code": "SOURCE_DIGEST_MISMATCH",
            "reference_id": "contract",
            "observation_evidence_id": OBSERVATION_ID,
            "observed_at": "2026-10-30T00:00:00Z",
        }
        receipt["admission_evidence_id"] = ADMISSION.get("admission_evidence_id")
        failure_id = artifact_identity(canonical_bytes(receipt) + b"\n")
        return refuse_permanently(
            record, failure_id, receipt, record.control.reservation_id, 1, WORKER,
        )
    return transition_state(
        record, AttemptState.PREPARED, PACKET_ID,
        record.control.reservation_id, 1, WORKER,
    )


def snapshot(record: JournalRecordV3 | None = None) -> VerifiedJournalSnapshotV3:
    record = record or build_record()
    return VerifiedJournalSnapshotV3(
        REPOSITORY, "R_example",
        "refs/heads/review-claims-v3/" + REQUEST_ID.rsplit(":", 1)[1],
        "a" * 40, "b" * 40, encode_journal_v2(record), record,
    )


def access(operation: CodespaceEffectV3 = CodespaceEffectV3.START,
           worker: WorkerIdentityV3 = WORKER) -> CodespaceAccessRequestV3:
    record = build_record()
    return CodespaceAccessRequestV3(
        REPOSITORY, REQUEST_ID, record.attempt.attempt_id,
        "refs/heads/review-claims-v3/" + REQUEST_ID.rsplit(":", 1)[1],
        record.control.reservation_id, 1, worker, CODESPACE, operation, ADMISSION,
    )


class InjectedCurrentJournal:
    def __init__(self, current: bool = True):
        self.current = current
        self.calls = 0

    def is_current(self, snapshot: VerifiedJournalSnapshotV3) -> bool:
        self.calls += 1
        return self.current and snapshot.commit_sha == "a" * 40


class InjectedTrustedContexts:
    def __init__(self, trusted: bool = True, replacement: dict[str, object] | None = None):
        self.trusted = trusted
        self.replacement = replacement or {}

    def authenticate(self, request: CodespaceAccessRequestV3):
        if not self.trusted:
            return None
        values = {
            "broker_repository": request.broker_repository,
            "request_id": request.request_id,
            "attempt_id": request.attempt_id,
            "claim_ref": request.claim_ref,
            "reservation_id": request.reservation_id,
            "generation": request.generation,
            "worker": request.worker,
            "codespace_identity": request.codespace_identity,
            "operation": request.operation,
        }
        values.update(self.replacement)
        return TrustedWorkerContextV3(**values)


class InjectedOwnership:
    def __init__(self, owned: bool):
        self.owned = owned

    def owns_resource(self, context: TrustedWorkerContextV3) -> bool:
        return self.owned and context.codespace_identity == CODESPACE


class FakeEffectSink:
    def __init__(self) -> None:
        self.effects: list[CodespaceEffectV3] = []

    def attempt(self, decision, operation: CodespaceEffectV3) -> None:
        if decision.allowed:
            self.effects.append(operation)


class CodespaceGateV3Tests(unittest.TestCase):
    def decide(self, record: JournalRecordV3, request: CodespaceAccessRequestV3 | None = None,
               contexts: InjectedTrustedContexts | None = None,
               ownership: InjectedOwnership | None = None):
        return authorize_codespace_effect_v3(
            snapshot(record), request or access(), InjectedCurrentJournal(),
            contexts or InjectedTrustedContexts(), ownership
        )

    def test_every_recognized_effect_class_is_fail_closed_before_prepared(self):
        sink = FakeEffectSink()
        for operation in CodespaceEffectV3:
            with self.subTest(operation=operation):
                decision = self.decide(build_record("ADMITTED"), access(operation))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "COMMITTED_PREPARED_REQUIRED")
                sink.attempt(decision, operation)
        self.assertEqual(sink.effects, [])

    def test_permanent_pre_model_refusal_has_no_codespace_effect(self):
        sink = FakeEffectSink()
        for operation in CodespaceEffectV3:
            decision = self.decide(build_record("REFUSED"), access(operation))
            self.assertFalse(decision.allowed)
            sink.attempt(decision, operation)
        self.assertEqual(sink.effects, [])

    def test_valid_committed_prepared_matching_trusted_worker_allows_non_stop(self):
        for operation in CodespaceEffectV3:
            if operation is CodespaceEffectV3.STOP:
                continue
            with self.subTest(operation=operation):
                decision = self.decide(build_record(), access(operation))
                self.assertTrue(decision.allowed)

    def test_missing_or_spoofed_worker_authority_is_rejected(self):
        missing = self.decide(build_record(), contexts=InjectedTrustedContexts(False))
        spoofed = self.decide(
            build_record(), contexts=InjectedTrustedContexts(
                replacement={"worker": WorkerIdentityV3(999, 1)}
            )
        )
        self.assertEqual(missing.reason, "WORKER_AUTHORITY_UNTRUSTED")
        self.assertEqual(spoofed.reason, "WORKER_AUTHORITY_UNTRUSTED")

    def test_wrong_run_attempt_generation_and_reservation_are_rejected(self):
        cases = (
            replace(access(), worker=WorkerIdentityV3(500, 2)),
            replace(access(), generation=2),
            replace(access(), reservation_id="preparation-dispatch:sha256:" + "f" * 64),
        )
        for request in cases:
            with self.subTest(request=request):
                self.assertEqual(
                    self.decide(build_record(), request).reason,
                    "WORKER_GENERATION_FENCED",
                )

    def test_unrelated_request_and_admission_identity_are_rejected(self):
        unrelated = replace(access(), request_id="request:sha256:" + "f" * 64)
        admission = replace(access(), expected_admission={"request_id": REQUEST_ID, "wrong": True})
        self.assertEqual(self.decide(build_record(), unrelated).reason,
                         "V3_CLAIM_NAMESPACE_REQUIRED")
        self.assertEqual(self.decide(build_record(), admission).reason,
                         "ADMISSION_IDENTITY_MISMATCH")

    def test_legacy_namespace_is_rejected(self):
        request = replace(access(), claim_ref="refs/heads/review-claims/" + "a" * 64)
        self.assertEqual(self.decide(build_record(), request).reason,
                         "V3_CLAIM_NAMESPACE_REQUIRED")

    def test_later_state_without_prepared_history_is_rejected(self):
        bound = build_record("BOUND")
        indeterminate = JournalRecordV3(
            transition_record(bound.attempt, AttemptState.INDETERMINATE,
                              ["artifact:sha256:" + "4" * 64]),
            bound.control,
        )
        self.assertEqual(
            self.decide(indeterminate, access()).reason,
            "COMMITTED_PREPARED_REQUIRED",
        )

    def test_stale_worker_after_competing_transition_is_rejected(self):
        replacement_worker = WorkerIdentityV3(600, 1)
        competing = initial_record(REQUEST_ID, ADMISSION)
        competing = reserve_initial(competing)
        competing = register_worker(
            competing, competing.control.reservation_id, 1, replacement_worker,
            "artifact:sha256:" + "6" * 64,
        )
        competing = transition_state(
            competing, AttemptState.ADMITTED, ADMISSION_ID,
            competing.control.reservation_id, 1, replacement_worker,
        )
        competing = transition_state(
            competing, AttemptState.PREPARED, PACKET_ID,
            competing.control.reservation_id, 1, replacement_worker,
        )
        self.assertEqual(self.decide(competing, access()).reason, "WORKER_GENERATION_FENCED")

    def test_boolean_generation_is_rejected_before_authority(self):
        with self.assertRaisesRegex(ValueError, "CODESPACE_GENERATION_INVALID"):
            replace(access(), generation=True)

    def test_non_enum_operation_and_string_stop_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "CODESPACE_EFFECT_CLASS_INVALID"):
            replace(access(), operation="STOP")
        with self.assertRaisesRegex(ValueError, "CODESPACE_EFFECT_CLASS_INVALID"):
            replace(access(), operation="ARBITRARY")

    def test_stop_requires_separate_matching_resource_ownership(self):
        request = access(CodespaceEffectV3.STOP)
        no_evidence = self.decide(build_record(), request)
        denied = self.decide(build_record(), request, ownership=InjectedOwnership(False))
        allowed = self.decide(build_record(), request, ownership=InjectedOwnership(True))
        self.assertEqual(no_evidence.reason, "RESOURCE_OWNERSHIP_REQUIRED")
        self.assertEqual(denied.reason, "RESOURCE_OWNERSHIP_REQUIRED")
        self.assertTrue(allowed.allowed)

    def test_denied_decision_produces_zero_fake_external_effects(self):
        sink = FakeEffectSink()
        denied = self.decide(build_record("REQUESTED"), access(CodespaceEffectV3.SSH))
        sink.attempt(denied, CodespaceEffectV3.SSH)
        self.assertEqual(sink.effects, [])

    def test_cached_record_python_equality_cannot_bypass_canonical_identity(self):
        integer_record = build_record()
        integer_admission = dict(ADMISSION, trust_marker=1)
        integer_record = JournalRecordV3(
            replace(integer_record.attempt, admission=integer_admission),
            integer_record.control,
        )
        verified = snapshot(integer_record)
        boolean_admission = dict(ADMISSION, trust_marker=True)
        forged_record = JournalRecordV3(
            replace(integer_record.attempt, admission=boolean_admission),
            integer_record.control,
        )
        forged = replace(verified, record=forged_record)
        request = replace(access(), expected_admission=integer_admission)
        decision = authorize_codespace_effect_v3(
            forged, request, InjectedCurrentJournal(), InjectedTrustedContexts()
        )
        self.assertEqual(decision.reason, "JOURNAL_SNAPSHOT_MISMATCH")

    def test_tampered_snapshot_bytes_fail_closed(self):
        prepared = snapshot()
        tampered = replace(prepared, journal_bytes=prepared.journal_bytes[:-1])
        decision = authorize_codespace_effect_v3(
            tampered, access(), InjectedCurrentJournal(), InjectedTrustedContexts()
        )
        self.assertEqual(decision.reason, "JOURNAL_UNTRUSTED")

    def test_forged_snapshot_ref_is_rejected_before_current_authority_call(self):
        authority = InjectedCurrentJournal()
        forged = replace(snapshot(), claim_ref="refs/heads/dev")
        decision = authorize_codespace_effect_v3(
            forged, access(), authority, InjectedTrustedContexts()
        )
        self.assertEqual(decision.reason, "CLAIM_REF_MISMATCH")
        self.assertEqual(authority.calls, 0)

    def test_truthy_non_boolean_current_proof_is_rejected(self):
        class WrongTypedCurrent:
            def is_current(self, snapshot):
                return 1

        decision = authorize_codespace_effect_v3(
            snapshot(), access(), WrongTypedCurrent(), InjectedTrustedContexts()
        )
        self.assertEqual(decision.reason, "CURRENT_JOURNAL_AUTHORITY_UNVERIFIED")

    def test_cached_snapshot_without_current_ref_authority_is_rejected(self):
        decision = authorize_codespace_effect_v3(
            snapshot(), access(), InjectedCurrentJournal(False), InjectedTrustedContexts()
        )
        self.assertEqual(decision.reason, "CURRENT_JOURNAL_AUTHORITY_UNVERIFIED")

    def test_effect_surface_inventory_is_explicitly_confronted(self):
        inventory_path = Path(__file__).parent / "fixtures/pre_model_v3/codespace_effect_surface_inventory.v1.json"
        inventory = json.loads(inventory_path.read_text())
        mechanisms = " ".join(item["mechanism"] for item in inventory["scanned_effect_surfaces"])
        for term in ("start", "stop", "ssh", "copy", "recover"):
            self.assertIn(term, mechanisms)
        self.assertEqual(
            {item.value for item in CodespaceEffectV3},
            {"START", "SSH", "COPY_TO", "COPY_FROM", "REMOTE_EXECUTE", "RECOVER", "STOP"},
        )
        self.assertFalse(inventory["full_runtime_prepared_gate_qualified"])
        self.assertFalse(inventory["old_workers_excluded"])
        self.assertFalse(inventory["resource_owner_exclusivity_qualified"])


if __name__ == "__main__":
    unittest.main()
