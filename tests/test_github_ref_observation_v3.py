from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import unittest

from review_broker.codespace_gate_v3 import (
    CodespaceAccessRequestV3, CodespaceEffectV3, authorize_codespace_effect_v3,
)
from review_broker.github_actions_identity_v3 import (
    GitHubActionsIdentityReaderV3, GitHubActionsTrustedContextProviderV3,
)
from review_broker.github_journal_transport_v3 import (
    ReadResultV3, ReadStatusV3, TransportSnapshotV3, VerifiedJournalSnapshotV3,
)
from review_broker.github_ref_observation_v3 import (
    AuthenticatedCurrentJournalAuthorityV3, CurrentRefExpectationV3,
    GitHubRefObservationReaderV3, GitHubRefObservationV3Error,
)
from review_broker.identity import attempt_identity
from review_broker.journal_record_v3 import (
    WorkerIdentityV3, encode_journal_v2, initial_record,
)
from review_broker.pre_model_control_v3 import (
    register_worker, reserve_initial, transition_state,
)
from review_broker.queue import AttemptState
from tests.test_github_actions_identity_v3 import (
    ActionsApi, Boundary as ActionsBoundary, claim as actions_claim,
    expectation as actions_expectation,
)


REPOSITORY = "fanilosendrison/review-broker"
NODE_ID = "R_repo"
REQUEST_ID = "request:sha256:" + "a" * 64
ATTEMPT_ID = attempt_identity(REQUEST_ID, 1)
ADMISSION_ID = "artifact:sha256:" + "8" * 64
PACKET_ID = "artifact:sha256:" + "9" * 64
WORKER_AUTHORITY = "artifact:sha256:" + "5" * 64
ADMISSION = {
    "request_id": REQUEST_ID,
    "admission_evidence_id": ADMISSION_ID,
    "repository_id": 1433701208,
    "reference_ids": [],
}
WORKER = WorkerIdentityV3(1234, 2)
COMMIT = "c" * 40
PARENT = "b" * 40
REF = "refs/heads/review-claims-v3/" + "a" * 64
NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def prepared_record():
    record = reserve_initial(initial_record(REQUEST_ID, ADMISSION))
    reservation = record.control.reservation_id
    assert reservation is not None
    record = register_worker(record, reservation, 1, WORKER, WORKER_AUTHORITY)
    record = transition_state(record, AttemptState.ADMITTED, ADMISSION_ID, reservation, 1, WORKER)
    record = transition_state(record, AttemptState.PREPARED, PACKET_ID, reservation, 1, WORKER)
    return record


class SequenceTransport:
    def __init__(self, results: list[ReadResultV3]):
        self.results = list(results)
        self.calls: list[str] = []
        self.mutations = 0
        self.repository = REPOSITORY
        self.node_id = NODE_ID
        self.identity_calls = 0
        self.identity_drift_after: int | None = None

    def verify_repository_identity(self) -> str:
        self.identity_calls += 1
        if (self.identity_drift_after is not None
                and self.identity_calls > self.identity_drift_after):
            return "R_replacement"
        return self.node_id

    def read_claim(self, claim_ref: str) -> ReadResultV3:
        self.calls.append(claim_ref)
        if not self.results:
            return ReadResultV3(ReadStatusV3.UNAVAILABLE)
        return self.results.pop(0)

    def create_journal_commit(self, parent_sha: str, journal_bytes: bytes) -> str:
        self.mutations += 1
        raise AssertionError("mutation forbidden")

    def create_ref(self, claim_ref: str, commit_sha: str):
        self.mutations += 1
        raise AssertionError("mutation forbidden")

    def update_ref(self, update: object):
        self.mutations += 1
        raise AssertionError("mutation forbidden")


class FreshnessBoundary:
    def __init__(self, trusted: bool = True):
        self.trusted = trusted

    def authenticates(self, observation) -> bool:
        return self.trusted and observation.commit_sha == COMMIT


class WorkerBinding:
    def __init__(self, trusted: bool = True):
        self.trusted = trusted

    def authenticates(self, request, observation) -> bool:
        return (self.trusted and request.request_id == REQUEST_ID
                and request.attempt_id == ATTEMPT_ID
                and request.claim_ref == REF
                and request.reservation_id == prepared_record().control.reservation_id
                and request.generation == 1 and request.worker == WORKER
                and observation.repository_id == ADMISSION["repository_id"]
                and observation.workflow_id == 77
                and observation.workflow_path.endswith("v3-authority-observation-qualification.yml")
                and observation.runtime_job_key == "qualify"
                and observation.job_name == "qualify"
                and observation.executing_source_sha == "a" * 40)


class GitHubRefObservationV3Tests(unittest.TestCase):
    def snapshot(self, record=None, commit: str = COMMIT) -> TransportSnapshotV3:
        raw = encode_journal_v2(record or prepared_record())
        return TransportSnapshotV3(commit, PARENT, raw)

    def expectation(self, snapshot: TransportSnapshotV3, **changes) -> CurrentRefExpectationV3:
        values = dict(
            repository=REPOSITORY, repository_node_id=NODE_ID, claim_ref=REF,
            commit_sha=snapshot.commit_sha, request_id=REQUEST_ID,
            attempt_id=ATTEMPT_ID, admission=ADMISSION,
            journal_bytes=snapshot.journal_bytes,
            reservation_id=prepared_record().control.reservation_id,
            generation=1, worker=WORKER,
        )
        values.update(changes)
        return CurrentRefExpectationV3(**values)

    def reader(self, transport: SequenceTransport) -> GitHubRefObservationReaderV3:
        return GitHubRefObservationReaderV3(
            transport, REPOSITORY, NODE_ID, clock=lambda: NOW
        )

    def test_exact_canonical_journal_requires_two_consecutive_reads(self) -> None:
        snapshot = self.snapshot()
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        observed = self.reader(transport).observe(self.expectation(snapshot))
        self.assertEqual(observed.commit_sha, COMMIT)
        self.assertEqual(observed.request_id, REQUEST_ID)
        self.assertEqual(observed.worker, WORKER)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.mutations, 0)

    def test_transport_repository_and_node_identity_are_authenticated(self) -> None:
        snapshot = self.snapshot()
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        transport.repository = "other/repository"
        with self.assertRaisesRegex(ValueError, "IDENTITY_BEARING_TRANSPORT_REQUIRED"):
            self.reader(transport)
        transport.repository = REPOSITORY
        transport.node_id = "R_replacement"
        with self.assertRaisesRegex(GitHubRefObservationV3Error, "IDENTITY_MISMATCH"):
            self.reader(transport).observe(self.expectation(snapshot))

    def test_repository_identity_drift_after_reads_fails_closed(self) -> None:
        snapshot = self.snapshot()
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        transport.identity_drift_after = 1
        with self.assertRaisesRegex(GitHubRefObservationV3Error, "IDENTITY_MISMATCH"):
            self.reader(transport).observe(self.expectation(snapshot))
        self.assertEqual(transport.identity_calls, 2)
        self.assertEqual(len(transport.calls), 2)

    def test_one_lagging_read_may_reconcile_without_linearizability_claim(self) -> None:
        snapshot = self.snapshot()
        stale = replace(snapshot, commit_sha="1" * 40)
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, stale),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        self.assertEqual(self.reader(transport).observe(self.expectation(snapshot)).commit_sha, COMMIT)

    def test_absent_changed_or_unreadable_ref_denies_positive_observation(self) -> None:
        snapshot = self.snapshot()
        cases = [
            [ReadResultV3(ReadStatusV3.MISSING)] * 3,
            [ReadResultV3(ReadStatusV3.UNAVAILABLE)] * 3,
            [ReadResultV3(ReadStatusV3.FOUND, replace(snapshot, commit_sha="1" * 40))] * 3,
        ]
        for results in cases:
            with self.subTest(status=results[0].status):
                with self.assertRaisesRegex(GitHubRefObservationV3Error, "OBSERVATION_UNAVAILABLE"):
                    self.reader(SequenceTransport(results)).observe(self.expectation(snapshot))

    def test_wrong_journal_identity_fields_fail_closed(self) -> None:
        snapshot = self.snapshot()
        changes = (
            {"request_id": "request:sha256:" + "f" * 64},
            {"attempt_id": "attempt:sha256:" + "f" * 64},
            {"reservation_id": "preparation-dispatch:sha256:" + "f" * 64},
            {"generation": 0},
            {"worker": WorkerIdentityV3(999, 1)},
            {"admission": {**ADMISSION, "repository_id": 1}},
        )
        for change in changes:
            with self.subTest(change=change):
                transport = SequenceTransport([
                    ReadResultV3(ReadStatusV3.FOUND, snapshot),
                    ReadResultV3(ReadStatusV3.FOUND, snapshot),
                ])
                with self.assertRaises((GitHubRefObservationV3Error, ValueError)):
                    self.reader(transport).observe(self.expectation(snapshot, **change))

    def test_legacy_or_qualification_namespace_is_rejected_before_read(self) -> None:
        snapshot = self.snapshot()
        transport = SequenceTransport([])
        for ref in (
            "refs/heads/review-claims/" + "a" * 64,
            "refs/heads/review-claims-v3/qualification-transport-1-1",
        ):
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(ValueError, "V3_CLAIM_REF_INVALID"):
                    self.expectation(snapshot, claim_ref=ref)
        self.assertEqual(transport.calls, [])

    def test_digest_expectation_is_supported_but_still_strictly_decoded(self) -> None:
        snapshot = self.snapshot()
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        expected = self.expectation(
            snapshot, journal_bytes=None,
            journal_sha256=hashlib.sha256(snapshot.journal_bytes).hexdigest(),
        )
        self.reader(transport).observe(expected)

    def test_pre_effect_gate_requires_current_ref_and_authenticated_run(self) -> None:
        record = prepared_record()
        snapshot = self.snapshot(record)
        verified = VerifiedJournalSnapshotV3(
            REPOSITORY, NODE_ID, REF, COMMIT, PARENT, snapshot.journal_bytes, record, None
        )
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        current = AuthenticatedCurrentJournalAuthorityV3(
            self.reader(transport), FreshnessBoundary()
        )
        runtime = actions_claim()
        expected = actions_expectation()
        actions_api = ActionsApi()
        contexts = GitHubActionsTrustedContextProviderV3(
            GitHubActionsIdentityReaderV3(
                "token", REPOSITORY, 1433701208,
                executor=actions_api, clock=lambda: NOW,
            ), runtime, expected, ActionsBoundary(runtime), WorkerBinding(),
            "trusted-space", CodespaceEffectV3.START,
        )
        request = CodespaceAccessRequestV3(
            REPOSITORY, REQUEST_ID, ATTEMPT_ID, REF,
            record.control.reservation_id or "", 1, WORKER, "trusted-space",
            CodespaceEffectV3.START, ADMISSION,
        )
        decision = authorize_codespace_effect_v3(verified, request, current, contexts)
        self.assertTrue(decision.allowed)
        trusted = contexts.authenticate(request)
        self.assertIsNotNone(trusted)
        self.assertEqual(trusted.worker, WORKER)
        self.assertEqual(trusted.codespace_identity, "trusted-space")
        self.assertEqual(transport.mutations, 0)

    def test_matching_reads_without_independent_freshness_deny_effect_authority(self) -> None:
        record = prepared_record()
        snapshot = self.snapshot(record)
        verified = VerifiedJournalSnapshotV3(
            REPOSITORY, NODE_ID, REF, COMMIT, PARENT, snapshot.journal_bytes, record, None
        )
        transport = SequenceTransport([
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
            ReadResultV3(ReadStatusV3.FOUND, snapshot),
        ])
        authority = AuthenticatedCurrentJournalAuthorityV3(
            self.reader(transport), FreshnessBoundary(False)
        )
        self.assertFalse(authority.is_current(verified))

    def test_actions_context_cannot_be_transplanted_across_repositories(self) -> None:
        runtime, expected = actions_claim(), actions_expectation()
        contexts = GitHubActionsTrustedContextProviderV3(
            GitHubActionsIdentityReaderV3(
                "token", REPOSITORY, 1433701208,
                executor=ActionsApi(), clock=lambda: NOW,
            ), runtime, expected, ActionsBoundary(runtime), WorkerBinding(),
            "trusted-space", CodespaceEffectV3.START,
        )
        record = prepared_record()
        request = CodespaceAccessRequestV3(
            "other/repository", REQUEST_ID, ATTEMPT_ID, REF,
            record.control.reservation_id or "", 1, WORKER, "trusted-space",
            CodespaceEffectV3.START, ADMISSION,
        )
        self.assertIsNone(contexts.authenticate(request))

    def test_missing_execution_context_preprepared_and_stop_all_deny(self) -> None:
        prepared = prepared_record()
        prepared_snapshot = self.snapshot(prepared)
        verified = VerifiedJournalSnapshotV3(
            REPOSITORY, NODE_ID, REF, COMMIT, PARENT,
            prepared_snapshot.journal_bytes, prepared, None,
        )
        runtime = actions_claim()
        expected = actions_expectation()
        request = CodespaceAccessRequestV3(
            REPOSITORY, REQUEST_ID, ATTEMPT_ID, REF,
            prepared.control.reservation_id or "", 1, WORKER, "trusted-space",
            CodespaceEffectV3.START, ADMISSION,
        )
        for binding, effect, reason in (
            (WorkerBinding(False), CodespaceEffectV3.START, "WORKER_AUTHORITY_UNTRUSTED"),
            (WorkerBinding(), CodespaceEffectV3.STOP, "RESOURCE_OWNERSHIP_REQUIRED"),
        ):
            with self.subTest(reason=reason):
                effect_request = replace(request, operation=effect)
                transport = SequenceTransport([
                    ReadResultV3(ReadStatusV3.FOUND, prepared_snapshot),
                    ReadResultV3(ReadStatusV3.FOUND, prepared_snapshot),
                ])
                contexts = GitHubActionsTrustedContextProviderV3(
                    GitHubActionsIdentityReaderV3(
                        "token", REPOSITORY, 1433701208,
                        executor=ActionsApi(), clock=lambda: NOW,
                    ), runtime, expected, ActionsBoundary(runtime), binding,
                    "trusted-space", effect,
                )
                decision = authorize_codespace_effect_v3(
                    verified, effect_request,
                    AuthenticatedCurrentJournalAuthorityV3(
                        self.reader(transport), FreshnessBoundary()
                    ), contexts,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, reason)
        initial = initial_record(REQUEST_ID, ADMISSION)
        initial_raw = encode_journal_v2(initial)
        initial_verified = VerifiedJournalSnapshotV3(
            REPOSITORY, NODE_ID, REF, COMMIT, PARENT, initial_raw, initial, None
        )
        decision = authorize_codespace_effect_v3(
            initial_verified, request,
            AuthenticatedCurrentJournalAuthorityV3(
                self.reader(SequenceTransport([])), FreshnessBoundary()
            ),
            GitHubActionsTrustedContextProviderV3(
                GitHubActionsIdentityReaderV3(
                    "token", REPOSITORY, 1433701208,
                    executor=ActionsApi(), clock=lambda: NOW,
                ), runtime, expected, ActionsBoundary(runtime), WorkerBinding(),
                "trusted-space", CodespaceEffectV3.START,
            ),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "CURRENT_JOURNAL_AUTHORITY_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
