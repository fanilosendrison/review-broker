"""Read-only fault injection against REAL v1/v2 Review Broker modules.

Issue #51 / draft PR #55. These tests import the production journal,
reconciler, recovery, packet and request code, but replace network, GitHub
writes and Codespace operations with deterministic in-memory fixtures.

A green CI means the tested CURRENT behaviors are reproduced. It does
NOT mean that the unimplemented v3/packet-v2/result-v2 is qualified.

The tests marked expectedFailure are explicit UNIMPLEMENTED successor
obligations. They must NOT be silently converted to PASS or skipped.
"""
from __future__ import annotations

from dataclasses import replace
import json
import base64
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.admission import resolve_request
from review_broker.changes import ChangeScopeError, validate_change_scope
from review_broker.evidence import build_shutdown_observation
from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import attempt_identity, request_identity
from review_broker.packets import GitSourceReader, PacketError, SourceSpec
from review_broker.queue import (
    AttemptRecord, AttemptState, InMemoryJournal, StateTransitionError,
    record_shutdown_transition,
)
from review_broker.reconciliation import reconcile_repository
from review_broker.recovery import (
    PreparationRecoveryAction, decide_preparation_recovery,
    verify_rebuilt_packet,
)
from review_broker.request import (
    RequestContractError, build_issue_body, validate_request,
)


REQUEST_FIXTURE = Path(__file__).parent / "fixtures" / "sample-request.json"
BROKER = "fanilosendrison/review-broker"
SUBJECT = "fanilosendrison/proto-scope"
HEAD = "0" * 40
BASE = "1" * 40
MERGE_BASE = "2" * 40


class RealJournalAdapter:
    """Adapt real InMemoryJournal's attempt-keyed API to GitHubRefJournal API.

    The state machine and all evidence checks remain production code.
    No method changes the production transition rules.
    """

    def __init__(self):
        self.actual = InMemoryJournal()

    def claim(self, request_id, admission=None):
        return self.actual.claim(request_id, admission)

    def get(self, request_id):
        return self.actual.get(attempt_identity(request_id, 1))

    def transition(self, request_id, state, evidence_ids):
        return self.actual.transition(
            attempt_identity(request_id, 1), state, evidence_ids
        )

    def record_stopped(self, request_id, receipt):
        return self.actual.record_stopped(
            attempt_identity(request_id, 1), receipt
        )


class OfflineShutdownController:
    """Never starts or contacts a Codespace."""

    name = "qualification-fake-shutdown"

    def __init__(self, state="Shutdown"):
        self.observed = state
        self.stops = 0

    def state(self):
        return self.observed

    def stop(self):
        self.stops += 1
        self.observed = "Shutdown"


class ActualMechanismFaultTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
        self.req_id = request_identity(self.request)
        self.issue = {
            "number": 982,
            "body": build_issue_body(self.request),
            "user": {"login": "trusted"},
        }
        self.env = {
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": SUBJECT,
            "REVIEW_BROKER_DEFAULT_BRANCH": "dev",
            "REVIEW_BROKER_SECURITY_QUALIFIED": "true",
            "REVIEW_BROKER_SECURITY_EVIDENCE_ID": "synthetic-qualified",
        }

    def getter(self, endpoint):
        if "/issues?" in endpoint:
            return [self.issue]
        if "/git/matching-refs/" in endpoint:
            return []
        if endpoint == f"repos/{SUBJECT}/pulls/57":
            return {
                "head": {"sha": HEAD},
                "base": {"sha": BASE, "repo": {"id": 7}},
            }
        if "/compare/" in endpoint:
            return {"merge_base_commit": {"sha": MERGE_BASE}}
        raise AssertionError("UNEXPECTED_EXTERNAL_ACCESS:" + endpoint)

    def sweep(self, journal, dispatched, controller=None):
        return reconcile_repository(
            BROKER,
            "qualification-fake-shutdown",
            environment=self.env,
            get_json=self.getter,
            journal=journal,
            controller=controller or OfflineShutdownController(),
            dispatch=lambda *args: dispatched.append(args),
        )

    def claimed(self, state=AttemptState.REQUESTED):
        journal = RealJournalAdapter()
        record = journal.claim(self.req_id)
        if state in (AttemptState.ADMITTED, AttemptState.PREPARED, AttemptState.ARMED):
            journal.transition(self.req_id, AttemptState.ADMITTED, ["admission"])
        if state in (AttemptState.PREPARED, AttemptState.ARMED):
            journal.transition(self.req_id, AttemptState.PREPARED, ["packet"])
        if state is AttemptState.ARMED:
            journal.transition(self.req_id, AttemptState.ARMED, ["arm"])
            journal.actual.record_invocation(record.attempt_id)
        return journal

    def test_current_gap_admitted_claim_redispatched_each_sweep(self):
        """Observed F005 gap: existing reconciler has no permanent block."""
        j = self.claimed(AttemptState.ADMITTED)
        dispatched = []
        for _ in range(3):
            decisions = self.sweep(j, dispatched)
            self.assertEqual(decisions[0]["action"], "DISPATCH_PRE_MODEL")
        self.assertEqual(len(dispatched), 3)
        self.assertEqual(j.actual.attempt_count, 1)
        self.assertEqual(j.get(self.req_id).state, AttemptState.ADMITTED)

    @unittest.expectedFailure
    def test_future_contract_no_unbounded_redispatch_after_pre_model_failure(self):
        """DESIRED V3 only: present source has no durable blocked disposition."""
        j = self.claimed(AttemptState.ADMITTED)
        dispatched = []
        for _ in range(3):
            self.sweep(j, dispatched)
        self.assertLessEqual(len(dispatched), 1)

    def test_current_prepared_claim_requires_explicit_recovery(self):
        j = self.claimed(AttemptState.PREPARED)
        dispatched = []
        decision = self.sweep(j, dispatched)
        self.assertEqual(dispatched, [])
        self.assertEqual(decision[0]["action"], "AWAIT_EXPLICIT_PREPARED_RECOVERY")
        self.assertEqual(j.get(self.req_id).state, AttemptState.PREPARED)

    def test_armed_claim_is_not_redispatched_or_reinvoked(self):
        j = self.claimed(AttemptState.ARMED)
        dispatched = []
        observations = self.sweep(j, dispatched)
        self.assertEqual(dispatched, [])
        self.assertEqual(observations[0]["outcome"], "INDETERMINATE_AND_STOPPED")
        record = j.get(self.req_id)
        self.assertEqual(record.state, AttemptState.STOPPED)
        self.assertEqual(record.invocation_count, 1)
        with self.assertRaisesRegex(StateTransitionError, "INVOCATION_NOT_PERMITTED"):
            j.actual.record_invocation(record.attempt_id)

    def test_real_pre_model_stop_is_illegal_even_with_valid_shutdown(self):
        """Observed F005 gap: direct pre-model STOPPED is not implemented."""
        for state in (AttemptState.REQUESTED, AttemptState.ADMITTED):
            with self.subTest(state=state):
                record = self.claimed(state).get(self.req_id)
                receipt = build_shutdown_observation(
                    codespace_name="qualification-fake-shutdown",
                    request_id=record.request_id,
                    attempt_id=record.attempt_id,
                    observed_state="Shutdown",
                    context={"workflow_run_id": "synthetic", "workflow_run_attempt": "1"},
                )
                with self.assertRaisesRegex(StateTransitionError, "ILLEGAL_TRANSITION"):
                    record_shutdown_transition(record, receipt)

    @unittest.expectedFailure
    def test_future_contract_permanent_pre_model_stop_with_verified_receipt(self):
        """DESIRED V3 only, still requires a new typed refusal receipt."""
        record = self.claimed(AttemptState.ADMITTED).get(self.req_id)
        shutdown = build_shutdown_observation(
            codespace_name="qualification-fake-shutdown",
            request_id=record.request_id,
            attempt_id=record.attempt_id,
            observed_state="Shutdown",
            context={"workflow_run_id": "synthetic", "workflow_run_attempt": "1"},
        )
        result = record_shutdown_transition(record, shutdown)
        self.assertEqual(result.state, AttemptState.STOPPED)

    def test_real_pre_model_shutdown_must_not_be_forged(self):
        record = self.claimed().get(self.req_id)
        shutdown = build_shutdown_observation(
            codespace_name="qualification-fake-shutdown",
            request_id=record.request_id,
            attempt_id=record.attempt_id,
            observed_state="Shutdown",
            context={"workflow_run_id": "synthetic", "workflow_run_attempt": "1"},
        )
        fake = dict(shutdown, observed_state="Available")
        with self.assertRaisesRegex(StateTransitionError, "SHUTDOWN_OBSERVATION_INVALID"):
            record_shutdown_transition(record, fake)

    def test_real_prepared_packet_cannot_be_swapped_on_rebuild(self):
        record = self.claimed(AttemptState.PREPARED).get(self.req_id)
        self.assertEqual(
            decide_preparation_recovery(record, "admission"),
            PreparationRecoveryAction.REBUILD_PREPARED,
        )
        verify_rebuilt_packet(record, "packet")
        with self.assertRaisesRegex(ValueError, "PREPARED_PACKET_EVIDENCE_MISMATCH"):
            verify_rebuilt_packet(record, "different")

    def test_real_unarmed_admission_resolution_cannot_drift(self):
        record = self.claimed(AttemptState.ADMITTED).get(self.req_id)
        self.assertEqual(
            decide_preparation_recovery(record, "admission"),
            PreparationRecoveryAction.BUILD_FROM_ADMITTED,
        )
        with self.assertRaisesRegex(ValueError, "RESOLVED_REQUEST_EVIDENCE_MISMATCH"):
            decide_preparation_recovery(record, "different")

    def test_actual_git_ref_cas_conflict_fails_closed(self):
        journal = GitHubRefJournal("sample/broker")
        current = self.claimed(AttemptState.REQUESTED).get(self.req_id)
        journal._read = lambda _id: ("a" * 40, current)
        journal._state_commit = lambda _old, _new: "b" * 40
        journal._api = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "non-fast-forward"
        )
        with self.assertRaisesRegex(StateTransitionError, "STATE_COMPARE_AND_SWAP_FAILED"):
            journal.transition(self.req_id, AttemptState.ADMITTED, ["admission"])

    def test_actual_git_ref_ambiguous_claim_without_winner_fails_closed(self):
        journal = GitHubRefJournal("sample/broker")
        journal._read = lambda _id: None
        journal._ref_sha = lambda _ref: "a" * 40
        journal._state_commit = lambda _old, _record: "b" * 40
        journal._api = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "lost response"
        )
        with self.assertRaisesRegex(StateTransitionError, "ATOMIC_CLAIM_FAILED"):
            journal.claim(self.req_id)

    def test_current_gitref_reader_downgrades_unrecognized_future_journal(self):
        """Current parser accepts a future-shaped record and strips its fencing fields.

        This is an observed version-dispatch compatibility gap, not support for v3.
        """
        record = self.claimed(AttemptState.ADMITTED).get(self.req_id)
        future = record.as_dict()
        future["schema_version"] = 2
        future["pre_model_control"] = {
            "schema_version": 1,
            "generation": 1,
            "disposition": "REFUSED_PERMANENT",
            "reservation_id": "preparation-dispatch:sha256:" + "a" * 64,
            "authorization_id": self.req_id,
            "worker": None,
            "failure_receipt_id": "artifact:sha256:" + "b" * 64,
        }
        from review_broker.identity import canonical_bytes
        wire = base64.b64encode(canonical_bytes(future) + b"\n").decode("ascii")
        commit = "c" * 40

        def runner(command, **_kwargs):
            endpoint = command[4]
            if "/git/refs/heads/review-claims/" in endpoint:
                return subprocess.CompletedProcess(command, 0, json.dumps(
                    {"object": {"sha": commit}}
                ), "")
            if endpoint.endswith("?ref=" + commit):
                return subprocess.CompletedProcess(command, 0, json.dumps(
                    {"encoding": "base64", "content": wire}
                ), "")
            raise AssertionError("UNEXPECTED_EXTERNAL_ACCESS:" + endpoint)

        got = GitHubRefJournal("sample/broker", runner=runner).get(self.req_id)
        rewritten = got.as_dict()
        self.assertEqual(got.state, AttemptState.ADMITTED)
        self.assertEqual(rewritten["schema_version"], 1)
        self.assertNotIn("pre_model_control", rewritten)
        self.assertEqual(got.request_id, self.req_id)

    def test_actual_request_parser_rejects_future_v3_not_yet_supported(self):
        candidate = dict(self.request, schema_version=3)
        with self.assertRaisesRegex(RequestContractError, "unsupported request schema version"):
            validate_request(candidate)

    def test_actual_resolver_observes_repo_id_but_v1_request_does_not_bind_it(self):
        self.assertNotIn("repository_id", self.request["subject"])
        resolved = resolve_request(self.request, self.getter)
        self.assertEqual(resolved["subject"]["repository_id"], 7)
        self.assertNotIn("repository_id", resolved["request"]["subject"])
        self.assertNotIn("github_pr_id", resolved["subject"])

    def test_actual_subject_change_scope_rejects_reference_role_piggyback(self):
        changes = [{
            "status": "modified",
            "path": "source.md",
            "previous_path": None,
            "before_source_id": "S001",
            "after_source_id": "S002",
        }]
        sources = [
            {"source_id": "S001", "commit": BASE, "path": "source.md"},
            {"source_id": "S002", "commit": HEAD, "path": "source.md"},
            {"source_id": "S003", "commit": HEAD, "path": "context.md"},
        ]
        with self.assertRaisesRegex(ChangeScopeError, "CHANGE_SOURCE_COVERAGE_MISMATCH"):
            validate_change_scope(
                changes, sources, merge_base=BASE, head=HEAD
            )

    def test_actual_git_source_reader_binds_same_head_and_blob_bytes(self):
        with tempfile.TemporaryDirectory(prefix="rb-real-qualification-") as tmp:
            repo = Path(tmp) / "git-repository"
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            for key, val in (
                ("user.email", "fixture@example.invalid"),
                ("user.name", "Fixture"),
            ):
                subprocess.run(["git", "-C", str(repo), "config", key, val], check=True)
            file = repo / "context.md"
            file.write_bytes(b"original\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "B"], check=True)
            base = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            file.write_bytes(b"head-version\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "H"], check=True)
            head = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            reader = GitSourceReader(repo)
            old = reader.read(SourceSpec("sample/repo", base, "context.md"))
            new = reader.read(SourceSpec("sample/repo", head, "context.md"))
            self.assertEqual(old.original_bytes, b"original\n")
            self.assertEqual(new.original_bytes, b"head-version\n")
            self.assertNotEqual(old.git_blob_oid, new.git_blob_oid)
            self.assertEqual(reader.changed_paths(base, head), {"context.md"})
            with self.assertRaisesRegex(PacketError, "SOURCE_MISSING"):
                reader.read(SourceSpec("sample/repo", head, "absent.md"))


if __name__ == "__main__":
    unittest.main()
