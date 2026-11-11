"""RWP-01: real journal operations, simulated Git writes, injected dispatch only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from review_broker.github_journal_transport_v3 import (
    JournalOutcomeV3, OutcomeStatusV3,
)
from review_broker.github_journal_v3 import GitHubJournalV3Error
from review_broker.identity import canonical_bytes
from review_broker.journal_record_v3 import (
    WorkerIdentityV3, decode_journal_v2, preparation_dispatch_identity,
)
from review_broker.pre_model_controller_v3 import ControllerStatusV3
from review_broker.pre_model_dispatch_v3 import (
    InitialDispatchResultV3, InitialDispatchStatusV3,
)
from tests.issue70_rwp01_test_support import (
    ControllerScenario, ExactControllerAuthority, TARGET, alternate_origin_admission,
)
from tests.issue70_test_support import AuthenticatedScenario
from tests.journal_v3_test_support import (
    PACKET_ID, TrustedPacketAuthority, TrustedWorkerAuthority,
)

STATUS = ControllerStatusV3
EMPTY = []
INITIAL = [("REQUESTED", 0, "UNRESERVED", None)]
RESERVED = [("REQUESTED", 1, "RESERVED", None)]


class Issue70Rwp01ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.authenticated = AuthenticatedScenario(Path(cls.directory.name))
        cls.admission = cls.authenticated.admission

    def scenario(self):
        return ControllerScenario(self.admission)

    def measure(self, scenario, claims, cas, dispatch, final, result=None,
                claim_status=None, reservation_status=None):
        self.assertEqual(scenario.measurement(), {
            "claims_created": claims, "cas_attempted": cas,
            "dispatch_calls": dispatch, "final_journal": final,
        })
        if result is not None:
            self.assertEqual(None if result.claim_outcome is None else result.claim_outcome.status,
                             claim_status)
            self.assertEqual(None if result.reservation_outcome is None else result.reservation_outcome.status,
                             reservation_status)

    def test_RWP01_N01_exact_admission_reservation_then_dispatch(self):
        s = self.scenario()
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.DISPATCH_OBSERVED)
        self.measure(s, 1, 1, 1, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.COMMITTED)
        sent = s.dispatch.calls[0]
        snapshot = s.journal.read(self.admission.request_id)
        self.assertEqual(sent, result.dispatch_request)
        self.assertEqual((sent.broker_repository, sent.request_id, sent.attempt_id,
                          sent.claim_ref, sent.reservation_id, sent.generation),
                         (s.journal.repository, self.admission.request_id,
                          snapshot.record.attempt.attempt_id, snapshot.claim_ref,
                          preparation_dispatch_identity(self.admission.request_id,
                              snapshot.record.attempt.attempt_id, 1, self.admission.request_id), 1))
        self.assertEqual((sent.worker_workflow, sent.execution_ref, sent.executable_sha),
                         (TARGET.worker_workflow, TARGET.execution_ref, TARGET.executable_sha))
        self.assertEqual(decode_journal_v2(s.dispatch.journal_at_call[0].journal_bytes), snapshot.record)
        self.assertEqual(snapshot.parent_sha, s.transport.updates[0].before_oid)
        self.assertIsNotNone(result.reservation_outcome.snapshot.writer_evidence_id)
        self.assertIsNone(snapshot.record.control.worker)

    def test_RWP01_N02_duplicate_discovery_does_not_dispatch(self):
        s = self.scenario()
        s.controller.run(self.admission)
        for controller in (s.controller, s.new_controller()):
            self.assertEqual(controller.run(self.admission).status, STATUS.ALREADY_HANDLED)
        self.measure(s, 1, 1, 1, RESERVED)

    def test_RWP01_N03_two_controllers_have_one_attributed_cas_winner(self):
        s = self.scenario()
        s.initial_claim()
        s.transport.identical_commits = True
        s.transport.update_barrier = threading.Barrier(2, timeout=30)
        controllers = [s.controller, s.new_controller()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda c: c.run(self.admission), controllers))
        self.assertCountEqual([r.status for r in results],
                              [STATUS.DISPATCH_OBSERVED, STATUS.RESERVATION_UNRESOLVED])
        self.assertCountEqual([r.reservation_outcome.status for r in results],
                              [OutcomeStatusV3.COMMITTED, OutcomeStatusV3.UNRESOLVED])
        self.assertEqual(s.transport.updates[0], s.transport.updates[1])
        self.measure(s, 1, 2, 1, RESERVED)

    def test_RWP01_N04_crash_before_reservation_then_fresh_discovery(self):
        s = self.scenario()
        with patch.object(s.journal, "reserve_initial", side_effect=SystemExit("SIMULATED_CRASH")):
            with self.assertRaises(SystemExit):
                s.controller.run(self.admission)
        self.measure(s, 1, 0, 0, INITIAL)
        result = s.new_controller().run(self.admission)
        self.assertEqual(result.status, STATUS.DISPATCH_OBSERVED)
        self.measure(s, 1, 1, 1, RESERVED)

    def test_RWP01_N05_reserved_readback_is_observation_not_dispatch_right(self):
        s = self.scenario()
        initial = s.initial_claim()
        reserved = s.journal.reserve_initial(initial.snapshot)
        self.assertIs(reserved.status, OutcomeStatusV3.COMMITTED)
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.ALREADY_HANDLED)
        self.measure(s, 1, 1, 0, RESERVED, result)
        self.assertEqual(s.transport.create_calls, 1)
        # Existing later states are observation fixtures, not RWP-02 qualification.
        worker = WorkerIdentityV3(70002, 1)
        bound = s.journal.register_worker(reserved.snapshot,
            reserved.snapshot.record.control.reservation_id, 1, worker, TrustedWorkerAuthority(worker))
        admitted = s.journal.record_admission(bound.snapshot, self.admission.admission_evidence_id,
            bound.snapshot.record.control.reservation_id, 1, worker)
        self.assertEqual(s.new_controller().run(self.admission).status, STATUS.ALREADY_HANDLED)
        self.measure(s, 1, 3, 0, [("ADMITTED", 1, "RESERVED", worker)])
        s.journal.prepare(admitted.snapshot, PACKET_ID, admitted.snapshot.record.control.reservation_id,
                          1, worker, TrustedPacketAuthority())
        self.assertEqual(s.new_controller().run(self.admission).status, STATUS.ALREADY_HANDLED)
        self.measure(s, 1, 4, 0, [("PREPARED", 1, "RESERVED", worker)])
        self.assertEqual(s.transport.create_calls, 1)

    def test_RWP01_F01_unauthorized_requester_creates_nothing(self):
        s = self.scenario()
        s.mismatch_decision(authorized=False)
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
        self.measure(s, 0, 0, 0, EMPTY, result)

    def test_RWP01_F02_wrong_issue_or_changed_origin_creates_nothing(self):
        for admission in (replace(self.admission, broker_issue_id=1),
                          replace(self.admission, origin_body_bytes=b"modified")):
            with self.subTest(admission=admission.broker_issue_id):
                s = self.scenario()
                result = s.controller.run(admission)
                self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
                self.measure(s, 0, 0, 0, EMPTY, result)

    def test_RWP01_F03_incomplete_or_incoherent_history_creates_nothing(self):
        for field, value in (("complete", False), ("request_id", "request:sha256:" + "f" * 64)):
            s = self.scenario()
            history = json.loads(self.admission.history_provenance_bytes)
            history[field] = value
            bad = replace(self.admission, history_provenance_bytes=canonical_bytes(history))
            result = s.controller.run(bad)
            self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
            self.measure(s, 0, 0, 0, EMPTY, result)

    def test_RWP01_F04_wrong_subject_head_or_numeric_repository(self):
        for changes in ({"head_sha": "f" * 40}, {"repository_id": True}, {"repository_id": 1}):
            s = self.scenario()
            result = s.controller.run(replace(self.admission, **changes))
            self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
            self.measure(s, 0, 0, 0, EMPTY, result)

    def test_RWP01_F05_non_v3_request_is_refused(self):
        s = self.scenario()
        request = self.admission.request
        request["schema_version"] = 2
        result = s.controller.run(replace(self.admission, canonical_request_bytes=canonical_bytes(request)))
        self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
        self.measure(s, 0, 0, 0, EMPTY, result)

    def test_RWP01_F06_existing_claim_admission_conflict_is_refused(self):
        s = self.scenario()
        initial = s.initial_claim()
        raw = json.loads(initial.snapshot.journal_bytes)
        raw["admission"]["broker_issue_id"] = 1
        sha = s.transport.refs[initial.snapshot.claim_ref]
        s.transport.commits[sha] = replace(s.transport.commits[sha], journal_bytes=canonical_bytes(raw) + b"\n")
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.CLAIM_REJECTED)
        self.measure(s, 1, 0, 0, INITIAL, result)
        s = self.scenario()
        s.controller.run(self.admission)
        other = alternate_origin_admission(self.authenticated)
        self.assertEqual(other.request_id, self.admission.request_id)
        self.assertNotEqual(other.admission_evidence_id, self.admission.admission_evidence_id)
        s.controller.authority = ExactControllerAuthority(other)
        result = s.controller.run(other)
        self.assertEqual(result.status, STATUS.CLAIM_REJECTED)
        self.measure(s, 1, 1, 1, RESERVED, result)

    def test_RWP01_F07_unresolved_claim_creation_or_read_never_dispatches(self):
        for applies in (False, True):
            s = self.scenario()
            s.transport.creation_unknown = True
            s.transport.creation_applies = applies
            s.predecessor.trusted = False
            result = s.controller.run(self.admission)
            self.assertEqual(result.status, STATUS.CLAIM_UNRESOLVED)
            self.measure(s, int(applies), 0, 0, INITIAL if applies else EMPTY,
                         result, OutcomeStatusV3.UNRESOLVED)
            repeated = s.controller.run(self.admission)
            self.assertEqual(repeated.status, STATUS.CLAIM_UNRESOLVED)
            self.assertEqual(s.transport.create_calls, 1)
        s = self.scenario()
        s.transport.read_unavailable = 1
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.CLAIM_UNRESOLVED)
        self.assertEqual(s.controller.run(self.admission).status, STATUS.CLAIM_UNRESOLVED)
        self.measure(s, 0, 0, 0, EMPTY)
        s = self.scenario()
        claim = s.journal.claim
        def interrupted_create(*args):
            claim(*args)
            raise GitHubJournalV3Error("SIMULATED_POST_CREATE_INTERRUPTION")
        with patch.object(s.journal, "claim", side_effect=interrupted_create):
            result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.CLAIM_UNRESOLVED)
        self.measure(s, 1, 0, 0, INITIAL, result)
        self.assertEqual(s.controller.run(self.admission).status, STATUS.CLAIM_UNRESOLVED)
        self.measure(s, 1, 0, 0, INITIAL)

    def test_RWP01_F08_losing_cas_never_dispatches(self):
        s = self.scenario()
        initial = s.initial_claim().snapshot
        with patch.object(s.journal, "reserve_initial", wraps=s.journal.reserve_initial) as reserve:
            winner = s.journal.reserve_initial(initial)
            # Expose a genuine stale predecessor to a second reservation operation.
            with patch.object(s.journal, "read", return_value=initial):
                result = s.controller.run(self.admission)
            self.assertEqual(reserve.call_count, 2)
        self.assertIs(winner.status, OutcomeStatusV3.COMMITTED)
        self.assertEqual(result.status, STATUS.RESERVATION_REJECTED)
        self.measure(s, 1, 2, 0, RESERVED, result, reservation_status=OutcomeStatusV3.REJECTED)

    def test_RWP01_F09_graphql_applied_but_ambiguous_has_no_dispatch_right(self):
        for flag in ("graphql_error_after_apply", "lose_update_acknowledgment",
                     "ambiguous_expected_old_after_apply"):
            s = self.scenario()
            setattr(s.transport, flag, True)
            result = s.controller.run(self.admission)
            self.assertEqual(result.status, STATUS.RESERVATION_UNRESOLVED)
            self.measure(s, 1, 1, 0, RESERVED, result,
                         OutcomeStatusV3.COMMITTED, OutcomeStatusV3.UNRESOLVED)
            self.assertEqual(s.controller.run(self.admission).status, STATUS.RESERVATION_UNRESOLVED)
            s.new_controller().run(self.admission)
            self.measure(s, 1, 1, 0, RESERVED)
        s = self.scenario()
        update = s.transport.update_ref
        def unavailable_after_write(value):
            result = update(value)
            s.transport.read_unavailable = 1
            return result
        with patch.object(s.transport, "update_ref", side_effect=unavailable_after_write):
            result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.RESERVATION_UNRESOLVED)
        self.measure(s, 1, 1, 0, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.UNRESOLVED)
        s.new_controller().run(self.admission)
        self.measure(s, 1, 1, 0, RESERVED)

    def test_RWP01_F10_dispatch_ambiguity_or_error_has_no_retry(self):
        for error in (None, ConnectionError("SIMULATED_BEFORE_OR_DURING_TRANSPORT")):
            s = self.scenario()
            s.dispatch.result = InitialDispatchResultV3(InitialDispatchStatusV3.UNRESOLVED)
            s.dispatch.error = error
            result = s.controller.run(self.admission)
            self.assertEqual(result.status, STATUS.DISPATCH_UNRESOLVED)
            self.measure(s, 1, 1, 1, RESERVED, result,
                         OutcomeStatusV3.COMMITTED, OutcomeStatusV3.COMMITTED)
            self.assertEqual(s.controller.run(self.admission).status, STATUS.DISPATCH_UNRESOLVED)
            s.new_controller().run(self.admission)
            self.measure(s, 1, 1, 1, RESERVED)

    def test_RWP01_F11_acceptance_without_run_id_does_not_invent_worker(self):
        s = self.scenario()
        s.dispatch.result = InitialDispatchResultV3(InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID)
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.DISPATCH_UNRESOLVED)
        self.assertIsNone(result.dispatch_result.run_id)
        self.measure(s, 1, 1, 1, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.COMMITTED)

    def test_RWP01_F12_lost_response_and_reexecution_never_dispatch_again(self):
        s = self.scenario()
        s.dispatch.error = TimeoutError("SIMULATED_RESPONSE_LOSS_NOT_A_FAILURE_DEADLINE")
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.DISPATCH_UNRESOLVED)
        for controller in (s.controller, s.new_controller()):
            controller.run(self.admission)
        self.measure(s, 1, 1, 1, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.COMMITTED)
        current = s.journal.read(self.admission.request_id)
        worker = WorkerIdentityV3(70003, 1)
        s.journal.register_worker(current, current.record.control.reservation_id,
                                  1, worker, TrustedWorkerAuthority(worker))
        self.assertEqual(s.controller.run(self.admission).status, STATUS.DISPATCH_UNRESOLVED)
        self.assertEqual(s.new_controller().run(self.admission).status, STATUS.ALREADY_HANDLED)
        self.measure(s, 1, 2, 1, [("REQUESTED", 1, "RESERVED", worker)])

    def test_RWP01_F13_absent_nonboolean_or_mismatched_controller_authority(self):
        for changes in ({"authorized": None}, {"authorized": 1},
                        {"broker_repository_node_id": "OTHER"},
                        {"journal_admission_bytes": b"{}"},
                        {"target": replace(TARGET, executable_sha="d" * 40)}):
            s = self.scenario()
            s.mismatch_decision(**changes)
            result = s.controller.run(self.admission)
            self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
            self.measure(s, 0, 0, 0, EMPTY, result)
        s = self.scenario()
        s.controller.authority = None
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.ADMISSION_DENIED)
        self.measure(s, 0, 0, 0, EMPTY, result)
        s = self.scenario()
        authorize = s.authority.authorize
        def reconfigure(**context):
            decision = authorize(**context)
            s.controller.target = replace(TARGET, executable_sha="d" * 40)
            return decision
        s.authority.authorize = reconfigure
        result = s.controller.run(self.admission)
        self.assertEqual(result.dispatch_request.executable_sha, TARGET.executable_sha)
        self.measure(s, 1, 1, 1, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.COMMITTED)

    def test_RWP01_F14_historical_namespace_or_unauthorized_writer_is_rejected(self):
        s = self.scenario()
        with patch.object(s.journal, "claim_ref", return_value="refs/heads/review-claims/legacy"):
            result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.CLAIM_REJECTED)
        self.measure(s, 0, 0, 0, EMPTY, result)
        s = self.scenario()
        initial = s.initial_claim().snapshot
        raw = json.loads(initial.journal_bytes)
        raw["schema_version"] = 1
        s.transport.commits[initial.commit_sha] = replace(
            s.transport.commits[initial.commit_sha], journal_bytes=canonical_bytes(raw) + b"\n")
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.CLAIM_REJECTED)
        self.measure(s, 1, 0, 0, [("INVALID_JOURNAL", 1, None, None)], result)
        s = self.scenario()
        s.journal.mutation_authority.trusted = False
        result = s.controller.run(self.admission)
        self.assertEqual(result.status, STATUS.RESERVATION_UNRESOLVED)
        self.measure(s, 1, 1, 0, RESERVED, result,
                     OutcomeStatusV3.COMMITTED, OutcomeStatusV3.UNRESOLVED)

    def test_RWP01_F15_no_dispatch_before_attributed_committed_reservation(self):
        for status in (OutcomeStatusV3.REJECTED, OutcomeStatusV3.UNRESOLVED,
                       OutcomeStatusV3.COMMITTED):
            s = self.scenario()
            # COMMITTED without a snapshot/evidence is deliberately invalid.
            with patch.object(s.journal, "reserve_initial", return_value=JournalOutcomeV3(status)):
                result = s.controller.run(self.admission)
            self.assertNotIn(result.status, (STATUS.DISPATCH_OBSERVED, STATUS.DISPATCH_UNRESOLVED))
            self.measure(s, 1, 0, 0, INITIAL, result, OutcomeStatusV3.COMMITTED, status)


if __name__ == "__main__":
    unittest.main()
