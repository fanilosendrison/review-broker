"""Fresh current-Worker authority using the actual RWP-02 journal scenario."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest

from review_broker.github_actions_identity_v3 import (
    GitHubActionsIdentityReaderV3, GitHubActionsIdentityV3Error,
)
from review_broker.github_journal_transport_v3 import GraphQLRefUpdateV3
from review_broker.journal_record_v3 import encode_journal_v2
from review_broker.pre_model_control_v3 import transition_state
from review_broker.pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptState
from tests.issue70_rwp02_test_support import (
    BOUNDARY, PRINCIPAL,
)
from tests.packet_v2_test_support import admitted
from tests.issue70_rwp03_test_support import (
    ContinuationWorkerScenario, FixturePolicySourceAuthority, FixturePolicySelectionAuthority,
)


class CurrentWorkerTests(unittest.TestCase):
    def setUp(self):
        self.scenario = ContinuationWorkerScenario(admitted())
        self.scenario.seed()
        result = self.scenario.run()
        self.assertEqual(result.status.value, "COMMITTED")
        self.snapshot = result.journal_outcome.snapshot
        s = self.scenario
        self.authority = CurrentBoundWorkerAuthorityV3(
            journal=s.journal, actions_reader=GitHubActionsIdentityReaderV3(
                "synthetic-token", s.expected.repository, s.expected.repository_id,
                executor=s.api, clock=lambda: datetime(2026, 11, 3, tzinfo=timezone.utc)),
            expected=s.expected, execution_boundary=s.boundary,
            execution_boundary_id=BOUNDARY, dispatch_authority=s.dispatch_authority,
            dispatch_principal_id=PRINCIPAL,
        )

    def continuation(self, capture=None):
        probe = CaptureBoundaryProbe() if capture is None else capture
        component = PreModelPacketContinuationV3(
            journal=self.scenario.journal, current_worker_authority=self.authority,
            original_admission=self.scenario.admission, capture_provider=probe,
            reference_readers=lambda guard: {},
            policy_source_authority=FixturePolicySourceAuthority(),
            policy_selection_authority=FixturePolicySelectionAuthority(),
            packet_stages=ForbiddenPacketStages(),
        )
        return component, probe

    def check(self, context=None, snapshot=None, state=AttemptState.REQUESTED):
        return self.authority.require_current(
            self.scenario.context if context is None else context,
            self.snapshot if snapshot is None else snapshot, state)

    def test_current_worker_reauthenticates_run_and_job_on_every_call(self):
        before = len(self.scenario.api.calls)
        self.assertEqual(self.check(), self.snapshot.record.control.worker)
        middle = len(self.scenario.api.calls)
        self.check()
        self.assertGreater(middle, before)
        self.assertGreater(len(self.scenario.api.calls), middle)
        # ACK reservation commit is not the direct parent of this later snapshot.
        ack = self.scenario.dispatch_authority.archive
        self.assertTrue(ack)

    def test_current_worker_reauthenticates_after_attributed_admission(self):
        s = self.scenario
        worker = self.check()
        successor = transition_state(
            self.snapshot.record, AttemptState.ADMITTED,
            s.admission.admission_evidence_id, s.context.inputs.reservation_id, 1, worker)
        outcome = s.journal.record_admission(
            self.snapshot, s.admission.admission_evidence_id,
            s.context.inputs.reservation_id, 1, worker)
        self.assertEqual(outcome.status.value, "COMMITTED")
        self.assertIsNone(outcome.pending)
        after = outcome.snapshot
        self.assertEqual(after.parent_sha, self.snapshot.commit_sha)
        self.assertEqual(after.journal_bytes, encode_journal_v2(successor))
        self.assertTrue(s.journal.mutation_authority.permits(GraphQLRefUpdateV3(
            self.snapshot.repository_node_id, self.snapshot.claim_ref,
            self.snapshot.commit_sha, after.commit_sha, False), after.writer_evidence_id))
        self.assertEqual(s.journal.read(s.admission.request_id), after)
        self.assertEqual(self.check(snapshot=after, state=AttemptState.ADMITTED), worker)
        with self.assertRaises(ValueError):
            self.check()  # Cached bound-Worker snapshot is no longer current.
        s.api.run["triggering_actor"]["id"] += 1
        with self.assertRaises(ValueError):
            self.check(snapshot=after, state=AttemptState.ADMITTED)

    def test_F24_unrecognized_dispatch_ack(self):
        self.scenario.dispatch_authority.recognized = False
        with self.assertRaises(ValueError):
            self.check()

    def test_F26_unauthenticated_context(self):
        self.scenario.boundary.trusted = False
        with self.assertRaises(ValueError):
            self.check()

    def test_F26_wrong_current_job(self):
        self.scenario.api.jobs[0]["id"] += 1
        with self.assertRaises(ValueError):
            self.check()

    def test_F26_rerun(self):
        self.scenario.api.run["run_attempt"] = 2
        with self.assertRaises(GitHubActionsIdentityV3Error):
            self.check()

    def test_F26_other_actor(self):
        self.scenario.api.run["actor"]["id"] += 1
        with self.assertRaises(ValueError):
            self.check()

    def test_F27_stale_snapshot(self):
        with self.assertRaises(ValueError):
            self.check(snapshot=replace(self.snapshot, commit_sha="9" * 40))

    def test_F27_wrong_boundary_state(self):
        with self.assertRaises(ValueError):
            self.check(state=AttemptState.PREPARED)

    def test_N05_continuation_attributes_admitted_before_capture_handoff(self):
        component, probe = self.continuation()
        result = component.run(self.scenario.context)
        self.assertEqual(result.journal_outcome.status.value, "COMMITTED")
        self.assertIsNone(result.journal_outcome.pending)
        self.assertEqual(probe.calls, 1)
        self.assertIsNone(result.packet_id)  # Probe stops; no false packet completion.
        self.assertEqual(self.scenario.transport.events.count("ADMITTED"), 1)
        self.assertEqual(component.run(self.scenario.context).reason, "OBSERVER_ONLY_NO_RETRY")
        self.assertEqual(probe.calls, 1)

    def test_F24_missing_ack_prevents_continuation(self):
        self.corrupt_journal(lambda raw: raw["history"].__setitem__(slice(None), [
            e for e in raw["history"] if e.get("event") != "PRE_MODEL_DISPATCH_ACKNOWLEDGED"]))
        self.assert_no_capture()

    def test_F25_missing_duplicate_or_mismatched_binding(self):
        original = self.scenario.transport.commits[self.snapshot.commit_sha]
        for mode in ("missing", "duplicate", "mismatched"):
            self.scenario.transport.commits[self.snapshot.commit_sha] = original
            def corrupt(raw):
                bindings = [e for e in raw["history"] if e.get("event") == "PRE_MODEL_WORKER_BOUND"]
                if mode == "missing":
                    raw["history"].remove(bindings[0])
                elif mode == "duplicate":
                    raw["history"].append(bindings[0])
                else:
                    bindings[0]["pre_model"]["receipt"]["worker"]["run_id"] += 1
            self.corrupt_journal(corrupt)
            with self.subTest(mode=mode):
                self.assert_no_capture()

    def test_F26_authenticated_manual_or_rerun_context_prevents_continuation(self):
        s = self.scenario
        original = s.context
        for changes in ({"event_name": "pull_request", "worker_dispatch": False},
                        {"run_attempt": 2}, {"job_key": "other"}):
            with self.subTest(changes=changes):
                s.context = replace(original, runtime=replace(original.runtime, **changes))
                s.boundary.context = s.context
                self.assert_no_capture()
        s.context = original
        s.boundary.context = original

    def test_F27_wrong_generation_or_current_worker(self):
        original = self.scenario.transport.commits[self.snapshot.commit_sha]
        for field, value in (("generation", 2), ("worker", {"run_id": 9, "run_attempt": 1})):
            self.scenario.transport.commits[self.snapshot.commit_sha] = original
            self.corrupt_journal(lambda raw: raw["pre_model_control"].__setitem__(field, value))
            with self.subTest(field=field):
                self.assert_no_capture()

    def test_F28_rejected_admitted_cas_has_zero_capture(self):
        s = self.scenario
        def compete(event):
            if event == "ADMITTED":
                alternate = s.transport.create_journal_commit(
                    self.snapshot.commit_sha, self.snapshot.journal_bytes)
                s.transport.refs[self.snapshot.claim_ref] = alternate
                s.transport.attributed.add(alternate)
        s.transport.event_hook = compete
        result = self.assert_no_capture()
        self.assertEqual(result.status.value, "REJECTED")
        self.assertEqual(result.journal_outcome.status.value, "REJECTED")

    def test_F29_unresolved_applied_admitted_is_not_inferred_or_retried(self):
        s = self.scenario
        s.transport.lose_update_acknowledgment = True
        component, probe = self.continuation()
        result = component.run(s.context)
        self.assertEqual(result.status.value, "UNRESOLVED")
        self.assertEqual(probe.calls, 0)
        self.assertEqual(s.journal.read(s.admission.request_id).record.attempt.state,
                         AttemptState.ADMITTED)
        self.assertEqual(component.run(s.context).reason, "OBSERVER_ONLY_NO_RETRY")
        self.assertEqual(s.transport.events.count("ADMITTED"), 1)
        restarted, fresh_probe = self.continuation()
        self.assertNotEqual(restarted.run(s.context).status.value, "COMMITTED")
        self.assertEqual(fresh_probe.calls, 0)

    def test_N08_F30_identical_target_competition_has_one_attributed_handoff(self):
        s = self.scenario
        s.transport.identical_commits = True
        s.transport.update_barrier = Barrier(2, timeout=10)
        components = [self.continuation() for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda item: item[0].run(s.context), components))
        self.assertEqual(sum(probe.calls for _, probe in components), 1)
        self.assertEqual(sum(r.journal_outcome is not None
                             and r.journal_outcome.status.value == "COMMITTED" for r in results), 1)
        self.assertEqual(sum(r.journal_outcome is not None
                             and r.journal_outcome.status.value == "UNRESOLVED" for r in results), 1)
        self.assertTrue(all(r.packet_id is None for r in results))

    def test_interruption_before_and_after_admitted_never_retries(self):
        for after in (False, True):
            with self.subTest(after=after):
                self.setUp()
                s = self.scenario
                s.transport.crash_event = "ADMITTED"
                s.transport.crash_after_apply = after
                component, probe = self.continuation()
                result = component.run(s.context)
                self.assertEqual(result.status.value, "UNRESOLVED")
                self.assertEqual(probe.calls, 0)
                self.assertIsNone(result.packet_id)
                self.assertEqual(component.run(s.context).reason, "OBSERVER_ONLY_NO_RETRY")
                self.assertEqual(s.transport.events.count("ADMITTED"), 1)

    def test_authority_loss_after_admission_prevents_capture(self):
        s = self.scenario
        def revoke(event):
            if event == "ADMITTED":
                s.boundary.trusted = False
        s.transport.event_hook = revoke
        self.assert_no_capture()

    def assert_no_capture(self):
        component, probe = self.continuation()
        result = component.run(self.scenario.context)
        self.assertNotEqual(result.status.value, "COMMITTED")
        self.assertEqual(probe.calls, 0)
        self.assertIsNone(result.packet_id)
        self.assertEqual(component.run(self.scenario.context).reason, "OBSERVER_ONLY_NO_RETRY")
        return result

    def corrupt_journal(self, mutation):
        transport = self.scenario.transport
        original = transport.commits[self.snapshot.commit_sha]
        raw = json.loads(original.journal_bytes)
        mutation(raw)
        transport.commits[self.snapshot.commit_sha] = replace(
            original, journal_bytes=canonical_bytes(raw) + b"\n")


class CaptureBoundaryProbe:
    """Tests only the Phase-B handoff; never pretends to verify a packet."""
    def __init__(self):
        self.calls = 0

    def capture(self, admission, before_effect):
        before_effect()
        self.calls += 1
        raise RuntimeError("PHASE_B_CAPTURE_HANDOFF_OBSERVED")


class ForbiddenPacketStages:
    def __getattr__(self, name):
        raise AssertionError(f"packet stage reached before capture: {name}")


class AuthorizedInternalBoundaryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from tests.issue70_rwp03_test_support import RealContinuationScenario
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.s = RealContinuationScenario(self.root)

    def refused(self):
        result = self.s.continuation.run(self.s.worker.context)
        self.assertNotEqual(result.status.value, "COMMITTED")
        self.assertIsNone(result.packet_id)
        self.assertFalse((self.root/"candidate").exists())
        self.assertFalse((self.root/"retained").exists())

    def test_R3_coherent_issue_body_replacement(self):
        self.s.inputs.issue_readers["requirement"]._executor.body = "coherent changed body"
        self.refused()

    def test_R3_coherent_issue_comment_replacement(self):
        self.s.inputs.issue_readers["decision"]._executor.body = "coherent changed comment"
        self.refused()

    def test_R3_second_materialization_changes_previously_accepted_reference(self):
        api = self.s.inputs.issue_readers["requirement"]._executor
        reads = []
        def execute(request):
            response = api(request)
            if request.full_url.endswith("/issues/43"):
                reads.append(request.full_url)
                api.body = "coherent replacement after first accepted observation"
            return response
        self.s.inputs.issue_readers["requirement"]._executor = execute
        self.refused()
        self.assertEqual(len(reads), 2)
        self.assertTrue(self.s.archive.exists())  # First reference pass reached selection.

    def test_R3_observation_time_alone_is_not_content_drift(self):
        for reader in self.s.inputs.issue_readers.values():
            reader._clock = lambda: datetime(2026, 1, 3, tzinfo=timezone.utc)
        result = self.s.continuation.run(self.s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)

    def test_R4_git_internal_read_stops_on_journal_movement(self):
        from unittest.mock import patch
        from review_broker.packets import GitSourceReader
        calls = []
        original = GitSourceReader._git
        def execute(reader, *args, **kwargs):
            result = original(reader, *args, **kwargs)
            calls.append(args)
            snapshot = self.s.worker.journal.read(self.s.worker.admission.request_id)
            transport = self.s.worker.transport
            sha = transport.create_journal_commit(snapshot.commit_sha, snapshot.journal_bytes)
            transport.attributed.add(sha)
            transport.refs[snapshot.claim_ref] = sha
            return result
        with patch.object(GitSourceReader, "_git", execute):
            self.refused()
        self.assertEqual(len(calls), 1)

    def test_R4_reference_internal_http_stops_on_authority_loss(self):
        api = self.s.inputs.issue_readers["requirement"]._executor
        calls = []
        def execute(request):
            calls.append(request.full_url)
            response = api(request)
            self.s.worker.boundary.trusted = False
            return response
        self.s.inputs.issue_readers["requirement"]._executor = execute
        self.refused()
        self.assertEqual(len(calls), 1)

    def test_R4_policy_source_internal_reads_use_current_guard(self):
        from tests.issue70_rwp03_test_support import POLICY_BYTES, SOURCE
        archive = self.root/"independent-source.bin"
        archive.write_bytes(POLICY_BYTES)
        reads = []
        def read_policy(expectation, *, before_effect):
            before_effect()
            data = archive.read_bytes()
            reads.append(data)
            self.s.worker.boundary.trusted = False
            before_effect()
            reads.append(archive.read_bytes())
            return data, SOURCE
        self.s.source_authority.read_policy = read_policy
        self.refused()
        self.assertEqual(reads, [POLICY_BYTES])

    def test_R4_selection_internal_archive_reads_stop_after_revocation(self):
        from unittest.mock import patch
        from pathlib import Path
        reads, original = [], Path.read_bytes
        def read(path):
            data = original(path)
            if path == self.s.archive:
                reads.append(data)
                self.s.worker.boundary.trusted = False
            return data
        with patch.object(Path, "read_bytes", read):
            self.refused()
        self.assertEqual(len(reads), 1)


if __name__ == "__main__":
    unittest.main()
