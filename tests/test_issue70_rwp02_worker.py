"""RWP-02: real journal/CAS/identity mechanisms, synthetic external trust only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from review_broker.github_journal_transport_v3 import OutcomeStatusV3
from review_broker.github_journal_v3 import GitHubJournalV3Error
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import decode_journal_v2, encode_journal_v2
from review_broker.pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3, acknowledgment_from_record
from tests.issue70_rwp01_test_support import ControllerScenario
from tests.issue70_rwp02_test_support import (
    RUN_ID, WorkerScenario,
)
from tests.issue70_test_support import AuthenticatedScenario
from tests.journal_v3_test_support import TrustedWorkerAuthority

COMMITTED, REJECTED, UNRESOLVED = OutcomeStatusV3


class Rwp02ConstructionTests(unittest.TestCase):
    def test_dispatch_ack_contract_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('review_broker.pre_model_dispatch_ack_v3'))

    def test_authenticated_worker_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('review_broker.pre_model_worker_v3'))


class Issue70Rwp02WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.admission = AuthenticatedScenario(Path(cls.directory.name)).admission
        cls.records = []

    @classmethod
    def tearDownClass(cls):
        path = Path('artifacts/rwp02/scenario-measurements.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_bytes(cls.records) + b'\n')

    def setUp(self):
        self.network = patch('socket.socket.connect', side_effect=AssertionError('LIVE_NETWORK_FORBIDDEN'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.sources = []
        for name in ('review_broker.packets.GitSourceReader.read',
                     'review_broker.github_git_file_v3.GitHubGitFileReaderV3.observe'):
            guard = patch(name, side_effect=AssertionError('SOURCE_ACQUISITION_FORBIDDEN'))
            self.sources.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        self.assertEqual(sum(source.call_count for source in self.sources), 0)

    def scenario(self, seed=True):
        s = WorkerScenario(self.admission)
        if seed:
            self.assertEqual(s.seed().acknowledgment_outcome.status, COMMITTED)
        return s

    def record(self, s, result, ack=1, worker=0, operation_index=None):
        s.source_acquisitions = sum(source.call_count for source in self.sources)
        m = s.measure(result)
        self.assertEqual((m['dispatches'], m['ack_attempts'], m['worker_attempts']), (1, ack, worker))
        self.assertEqual((m['source_acquisitions'], m['real_github_effects']), (0, 0))
        self.assertEqual(m['journal']['state'], 'REQUESTED')
        self.assertEqual(m['journal']['invocation_count'], 0)
        self.records.append(dict(case=self._testMethodName, operation_index=operation_index, **m))
        return m

    def deny(self, s, **counts):
        result = s.run()
        self.assertNotEqual(result.status, COMMITTED)
        self.record(s, result, **counts)
        return result

    def context_change(self, s, *, runtime=None, inputs=None, **values):
        s.context = replace(s.context, runtime=runtime or s.context.runtime,
                            inputs=inputs or s.context.inputs, **values)
        s.boundary.context = s.context  # Simulate authentic observation of the wrong execution.

    def forge_ack(self, s, **changes):
        snapshot = s.journal.read(self.admission.request_id)
        value = json.loads(snapshot.journal_bytes)
        event = value['history'][-1]
        event['pre_model']['receipt'].update(changes)
        basis = dict(event=event['event'], request_id=value['request_id'],
                     attempt_id=value['attempt_id'], generation=1, prior_history_count=2,
                     receipt=event['pre_model']['receipt'])
        evidence = artifact_identity(canonical_bytes(basis) + b'\n')
        value['evidence_ids'][-1] = evidence
        event['evidence_ids'] = [evidence]
        s.transport.commits[snapshot.commit_sha] = replace(
            s.transport.commits[snapshot.commit_sha], journal_bytes=canonical_bytes(value)+b'\n')

    def test_RWP02_N01_nominal(self):
        s = self.scenario(); result = s.run()
        self.assertEqual(result.status, COMMITTED)
        m = self.record(s, result, worker=1)
        self.assertEqual(m['committed_mutations'], 4)
        self.assertEqual(m['journal']['pre_model_control']['worker'], dict(run_id=RUN_ID, run_attempt=1))
        snapshot = result.journal_outcome.snapshot
        ack = acknowledgment_from_record(snapshot.record)
        self.assertNotEqual(ack.evidence_id, snapshot.record.attempt.history[2]['evidence_ids'][0])
        self.assertEqual(ack.evidence_id, artifact_identity(canonical_bytes(ack.as_dict())+b'\n'))

    def test_RWP02_N02_cold_receipt_reconstruction(self):
        s = self.scenario(); before = s.journal.read(self.admission.request_id)
        command = ('import sys; from review_broker.journal_record_v3 import decode_journal_v2; '
                   'from review_broker.pre_model_dispatch_ack_v3 import acknowledgment_from_record; '
                   'print(acknowledgment_from_record(decode_journal_v2(sys.stdin.buffer.read())).evidence_id)')
        fresh = subprocess.check_output([sys.executable, '-c', command], input=before.journal_bytes).decode().strip()
        self.assertEqual(fresh, acknowledgment_from_record(before.record).evidence_id)
        s.dispatch_authority = s.dispatch_authority.cold()
        result = s.run(); self.assertEqual(result.status, COMMITTED)
        self.record(s, result, worker=1)

    def test_RWP02_N03_worker_starts_before_ack(self):
        s = self.scenario(False); observed = []
        def before_ack():
            observed.append(s.run())
            self.record(s, observed[0], ack=0)
        s.dispatch.on_dispatch = before_ack
        s.seed()
        self.assertEqual(observed[0].reason, 'NO_CONFIRMED_ACK_AUTHORITY')
        self.record(s, observed[0])
        self.assertEqual(s.api.calls, [])

    def race(self, identical=False):
        s = self.scenario(); s.transport.identical_commits = identical
        s.transport.update_barrier = threading.Barrier(2, timeout=20)
        workers = [s.worker(), s.worker()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda w: w.run(s.context), workers))
        self.assertEqual(sum(r.status is COMMITTED for r in results), 1)
        self.assertEqual(len(s.transport.applied), 3)
        for index, result in enumerate(results):
            self.record(s, result, worker=2, operation_index=index)
        return s, results

    def test_RWP02_N04_two_identical_workers(self):
        self.race()

    def test_RWP02_N05_discovery_after_binding_is_observer(self):
        s = self.scenario(); self.assertEqual(s.run().status, COMMITTED)
        result = s.run(); self.assertEqual(result.reason, 'EXISTING_WORKER_OBSERVER_ONLY')
        self.record(s, result, worker=1)

    def test_RWP02_N06_historical_synthetic_identity(self):
        legacy = ControllerScenario(self.admission); legacy.controller.run(self.admission)
        old = legacy.journal.read(self.admission.request_id)
        self.assertEqual(encode_journal_v2(decode_journal_v2(old.journal_bytes)), old.journal_bytes)
        basis = dict(event='PRE_MODEL_DISPATCH_RESERVED', request_id=self.admission.request_id,
                     attempt_id=old.record.attempt.attempt_id, generation=1, prior_history_count=1)
        digest = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(',', ':')).encode()+b'\n').hexdigest()
        self.assertEqual(old.record.attempt.history[-1]['evidence_ids'], ['artifact:sha256:'+digest])
        self.assertIsNone(acknowledgment_from_record(old.record))
        s = self.scenario(); result = s.run()
        self.assertEqual(result.status, COMMITTED)
        self.record(s, result, worker=1)

    def test_RWP02_F01_other_run(self):
        s = self.scenario(); self.context_change(s, runtime=replace(s.context.runtime, run_id=RUN_ID+1))
        self.deny(s)

    def test_RWP02_F02_rerun(self):
        s = self.scenario(); self.context_change(s, runtime=replace(s.context.runtime, run_attempt=2))
        s.api.run['run_attempt'] = 2; self.deny(s)

    def test_RWP02_F03_other_request(self):
        s = self.scenario(); self.context_change(s, inputs=replace(s.context.inputs, request_id='request:sha256:'+'f'*64))
        self.deny(s)

    def test_RWP02_F04_other_reservation(self):
        s = self.scenario(); self.context_change(s, inputs=replace(s.context.inputs, reservation_id='preparation-dispatch:sha256:'+'f'*64))
        self.deny(s)

    def test_RWP02_F05_other_generation(self):
        for generation in (0, 2, True, '1'):
            s = self.scenario(); self.context_change(s, inputs=replace(s.context.inputs, generation=generation))
            self.deny(s)

    def test_RWP02_F06_repository_numeric_identity(self):
        s = self.scenario(); s.api.run['repository']['id'] += 1; self.deny(s)

    def test_RWP02_F07_workflow_identity(self):
        for field, value in [('workflow_id', 78), ('path', '.github/workflows/other.yml'), ('name', 'other')]:
            s = self.scenario(); s.api.run[field] = value; self.deny(s)

    def test_RWP02_F08_observed_executable_sha(self):
        s = self.scenario(); s.api.run['head_sha'] = 'd'*40; self.deny(s)

    def test_RWP02_F09_observed_execution_ref(self):
        for value in ('other-branch', None):
            s = self.scenario(); s.api.run['head_branch'] = value; self.deny(s)

    def test_RWP02_F10_jobs_and_pagination(self):
        for variant in ('absent', 'duplicate', 'incomplete', 'wrong-attempt', 'wrong-id'):
            s = self.scenario()
            if variant == 'absent': s.api.jobs, s.api.total = [], 0
            if variant == 'duplicate': s.api.jobs += [dict(s.api.jobs[0], id=502)]; s.api.total = 2
            if variant == 'incomplete': s.api.total = 2
            if variant == 'wrong-attempt': s.api.jobs[0]['run_attempt'] = 2
            if variant == 'wrong-id': self.context_change(s, job_id=502)
            self.deny(s)

    def test_RWP02_F11_unauthenticated_context(self):
        s = self.scenario(); s.boundary.trusted = False; self.deny(s)
        self.assertEqual(s.api.calls, [])

    def test_RWP02_F12_dispatch_principal_not_requester(self):
        for actor in ('actor', 'triggering_actor'):
            s = self.scenario(); s.api.run[actor]['id'] = self.admission.requester_id
            self.deny(s)

    def test_RWP02_F13_204_or_missing_run(self):
        for status, run in [(204, RUN_ID), (200, None)]:
            s = self.scenario(False); s.dispatch.status, s.dispatch.run_id = status, run
            s.seed(); self.deny(s, ack=0)

    def test_RWP02_F14_ambiguous_dispatch_no_redispatch(self):
        s = self.scenario(False); s.dispatch.ambiguous = True
        s.seed(); s.controller.run(self.admission); self.deny(s, ack=0)
        self.assertEqual(len(s.dispatch.calls), 1)

    def test_RWP02_F15_ack_cas_unresolved(self):
        s = self.scenario(False)
        s.transport.event_hook = lambda event: setattr(s.transport, 'lose_update_acknowledgment', True) if event.endswith('ACKNOWLEDGED') else None
        result = s.seed(); self.assertEqual(result.acknowledgment_outcome.status, UNRESOLVED)
        self.deny(s)
        s.controller.run(self.admission); self.assertEqual(s.transport.events.count('PRE_MODEL_DISPATCH_ACKNOWLEDGED'), 1)

    def test_RWP02_F16_forged_or_unrecognized_ack(self):
        s = self.scenario(); self.forge_ack(s, workflow_run_id=RUN_ID+1); self.deny(s)
        s = self.scenario(); s.dispatch_authority.recognized = False; self.deny(s)
        s = self.scenario(); issued = s.dispatch.calls[-1]
        reservation = s.controller_result.reservation_outcome.snapshot
        for fields in ({'request': replace(issued)}, {'response': replace(s.dispatch.response)},
                       {'transport': object()}, {'controller_authority': object()}):
            args = dict(request=issued, response=s.dispatch.response, transport=s.dispatch,
                        controller_authority=s.controller_authority, reservation=reservation)
            args.update(fields)
            self.assertIsNone(s.dispatch_authority.observe(**args))

    def test_RWP02_F17_duplicate_replaced_replayed_ack(self):
        s = self.scenario(); snapshot = s.journal.read(self.admission.request_id)
        receipt = acknowledgment_from_record(snapshot.record)
        for changes in ({'schema_version': 2}, {'generation': True}, {'workflow_run_id': True},
                        {'run_attempt': 1}, {'broker_repository_id': 0}):
            with self.assertRaises(ValueError):
                DispatchAcknowledgmentV3.from_dict(dict(receipt.as_dict(), **changes))
        with self.assertRaises(GitHubJournalV3Error):
            s.journal.acknowledge_dispatch(snapshot, receipt, s.dispatch_authority)
        for changes in ({'executable_sha': 'd'*40}, {'dispatch_response_evidence_id': 'artifact:sha256:'+'f'*64}):
            fresh = self.scenario(); self.forge_ack(fresh, **changes); self.deny(fresh)
        value = json.loads(snapshot.journal_bytes); value['history'].append(value['history'][-1])
        with self.assertRaises(ValueError): decode_journal_v2(canonical_bytes(value)+b'\n')
        self.record(s, s.run(), worker=1)

    def test_RWP02_F18_stale_snapshot(self):
        s = self.scenario(); stale = s.journal.read(self.admission.request_id)
        self.assertEqual(s.run().status, COMMITTED)
        with patch.object(s.journal, 'read', return_value=stale): result = s.run()
        self.assertNotEqual(result.status, COMMITTED); self.record(s, result, worker=2)

    def test_RWP02_F19_identical_target_cas_attribution(self):
        s, results = self.race(True)
        self.assertCountEqual([r.status for r in results], [COMMITTED, UNRESOLVED])
        self.assertEqual(s.transport.updates[-1].after_oid, s.transport.updates[-2].after_oid)

    def test_RWP02_F20_interruptions_no_automatic_retry(self):
        for event, after in [('PRE_MODEL_DISPATCH_ACKNOWLEDGED', False),
                             ('PRE_MODEL_DISPATCH_ACKNOWLEDGED', True), ('PRE_MODEL_WORKER_BOUND', True)]:
            s = self.scenario(False); s.transport.crash_event, s.transport.crash_after_apply = event, after
            s.seed(); worker = s.worker(); result = worker.run(s.context)
            count = len(s.transport.events); worker.run(s.context); s.controller.run(self.admission)
            self.assertEqual(len(s.transport.events), count)
            self.assertNotEqual(result.status, COMMITTED)
            self.record(s, result, worker=int(event.endswith('BOUND')))

    def test_RWP02_F21_no_source_acquisition_before_or_after_binding(self):
        s = self.scenario()
        with patch('review_broker.packets.GitSourceReader.read', side_effect=AssertionError('SOURCE_FORBIDDEN')) as source:
            result = s.run(); self.assertEqual(result.status, COMMITTED); source.assert_not_called()
        self.record(s, result, worker=1)

    def test_RWP02_F22_environment_fields_are_not_authority(self):
        s = self.scenario(); self.context_change(s, boundary_id='environment-only')
        self.deny(s)

    def test_RWP02_F23_local_hash_not_signed_attestation(self):
        s = self.scenario(); ack = acknowledgment_from_record(s.journal.read(self.admission.request_id).record)
        clone = DispatchAcknowledgmentV3.from_dict(json.loads(canonical_bytes(ack.as_dict())))
        self.assertEqual(clone.evidence_id, ack.evidence_id)
        s.dispatch_authority.archive.clear(); self.deny(s)

    def test_RWP02_F24_synthetic_worker_authority_cannot_bind_ack(self):
        legacy = self.scenario(False); legacy.controller.acknowledgment_authority = None
        legacy.seed(); self.deny(legacy, ack=0)
        s = self.scenario(); snapshot = s.journal.read(self.admission.request_id)
        from review_broker.journal_record_v3 import WorkerIdentityV3
        worker = WorkerIdentityV3(RUN_ID, 1)
        with self.assertRaises(GitHubJournalV3Error):
            s.journal.register_worker(snapshot, s.context.inputs.reservation_id, 1,
                                      worker, TrustedWorkerAuthority(worker))
        self.record(s, s.run(), worker=1)
