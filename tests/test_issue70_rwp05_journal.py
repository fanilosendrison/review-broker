"""Failure outcome attribution, read-only reconciliation and pure-transition CAS races."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier,Event,local
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import artifact_identity,canonical_bytes
from review_broker.pre_model_active_decision_v3 import PreModelDecisionStateV3
from review_broker.pre_model_control_v3 import block_pre_model,refuse_permanently,transition_state
from review_broker.queue import AttemptState
from tests.issue70_rwp05_test_support import FailureScenario


class FailureJournalTests(unittest.TestCase):
    def scenario(self,**kwargs):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return FailureScenario(Path(temporary.name),**kwargs)

    def test_F17_unknown_and_error_responses_never_retry_or_claim_blocked(self):
        for flag in ('lose_update_acknowledgment','graphql_application_error','graphql_error_after_apply'):
            s=self.scenario();server=s.real.worker.transport
            s.archive.on_put=lambda:setattr(server,flag,True)
            result=s.run_packet()
            with self.subTest(flag=flag):
                self.assertEqual(result.status.value,'UNRESOLVED',result)
                self.assertIsNotNone(result.journal_outcome.pending)
                self.assertEqual(s.failure_cas_count(),1)
                before=(len(server.updates),len(server.proposal_calls))
                for _ in range(3):
                    follow=s.real.worker.journal.reconcile(result.journal_outcome.pending)
                    self.assertEqual(follow.status.value,'UNRESOLVED')
                s.producer.run(s.real.worker.context)
                self.assertEqual((len(server.updates),len(server.proposal_calls)),before)
                self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)

    def test_F17_interruption_before_after_application_preserves_pending_without_retry(self):
        for after in (False,True):
            s=self.scenario();server=s.real.worker.transport
            def interrupt():server.crash_event='PRE_MODEL_FAILURE';server.crash_after_apply=after
            s.archive.on_put=interrupt
            result=s.run_packet()
            with self.subTest(after=after):
                self.assertEqual(result.status.value,'UNRESOLVED')
                self.assertIsNotNone(result.journal_outcome.pending)
                self.assertEqual(s.failure_cas_count(),1)
                self.assertEqual(s.current().record.control.disposition,'BLOCKED' if after else 'RESERVED')
                before=len(server.updates)
                s.real.worker.journal.reconcile(result.journal_outcome.pending)
                self.assertEqual(len(server.updates),before)
                self.assertEqual(s.failure_cas_count(),1)

    def test_F18_attributed_mutation_delayed_or_stale_read_eventually_reconciles_read_only(self):
        for mode in ('unavailable','stale'):
            s=self.scenario();server=s.real.worker.transport
            def delayed():
                if mode=='unavailable':server.read_unavailable=1
                else:server.stale_reads[s.authority.snapshot.claim_ref]=(s.authority.snapshot.commit_sha,1)
            server.on_failure_applied=delayed
            result=s.run_packet()
            with self.subTest(mode=mode):
                self.assertEqual(result.status.value,'UNRESOLVED')
                self.assertIsNotNone(result.journal_outcome.pending.writer_evidence_id)
                before=(len(server.updates),len(server.proposal_calls))
                final=s.real.worker.journal.reconcile(result.journal_outcome.pending)
                self.assertEqual(final.status.value,'COMMITTED')
                self.assertEqual(final.snapshot.record.control.disposition,'BLOCKED')
                self.assertEqual((len(server.updates),len(server.proposal_calls)),before)

    def test_F18_recognized_expected_old_rejection_is_preserved_by_failure_orchestrator(self):
        s=self.scenario();server=s.real.worker.transport
        def move(event):
            if event!='PRE_MODEL_FAILURE':return
            a=s.authority.snapshot
            # Independently injected concurrent ref movement, not a new protocol
            # transition or a permission inferred from old ADMITTED contents.
            other=server.create_journal_commit(a.commit_sha,a.journal_bytes)
            server.attributed.add(other);server.refs[a.claim_ref]=other
        s.archive.on_put=lambda:setattr(server,'event_hook',move)
        result=s.run_packet()
        self.assertEqual((result.status.value,result.disposition),('REJECTED','RESERVED'),result)
        self.assertEqual(s.failure_cas_count(),1)
        self.assertTrue(result.journal_outcome is not None)
        before=(len(server.updates),len(server.proposal_calls));s.producer.run(s.real.worker.context)
        self.assertEqual((len(server.updates),len(server.proposal_calls)),before)

    def test_F18_identical_visible_blocked_without_writer_attribution_stays_unresolved(self):
        s=self.scenario();server=s.real.worker.transport
        s.archive.on_put=lambda:setattr(server,'lose_update_acknowledgment',True)
        result=s.run_packet()
        self.assertEqual(s.current().record.control.disposition,'BLOCKED')
        self.assertEqual(result.status.value,'UNRESOLVED')
        self.assertIsNone(result.journal_outcome.pending.writer_evidence_id)
        server.attributed.add(server.refs[s.authority.snapshot.claim_ref])
        before=len(server.updates)
        self.assertEqual(s.real.worker.journal.reconcile(result.journal_outcome.pending).status.value,'UNRESOLVED')
        self.assertEqual(len(server.updates),before)

    def test_F06_F23_interruption_after_choice_before_git_creation_never_restores_ticket(self):
        s=self.scenario();server=s.real.worker.transport
        baseline=[]
        def interrupt():
            baseline.append(len(server.commits));raise RuntimeError('fixture before Git creation')
        server.on_failure_commit=interrupt
        result=s.run_packet()
        self.assertEqual(result.status.value,'UNRESOLVED')
        self.assertEqual(len(server.commits),baseline[0])
        self.assertEqual(s.failure_cas_count(),0)
        self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
        before=len(server.proposal_calls);s.producer.run(s.real.worker.context)
        self.assertEqual(len(server.proposal_calls),before)

    def test_F21_blocked_decoder_preserves_v2_and_rejects_incoherent_history(self):
        from review_broker.journal_record_v3 import decode_journal_v2,encode_journal_v2
        s=self.scenario();s.run_packet();b=s.current();value=json.loads(b.journal_bytes)
        self.assertEqual(decode_journal_v2(b.journal_bytes).as_dict()['schema_version'],2)
        self.assertEqual(encode_journal_v2(decode_journal_v2(b.journal_bytes)),b.journal_bytes)
        mutators=[lambda v:v.update(schema_version=1),lambda v:v.pop('pre_model_control'),
            lambda v:v.update(invocation_count=1),lambda v:v.update(state='REQUESTED'),
            lambda v:v['pre_model_control'].update(generation=0),lambda v:v['pre_model_control'].update(worker=None),
            lambda v:v['pre_model_control'].update(disposition='RESERVED'),
            lambda v:v['pre_model_control'].update(failure_receipt_id='artifact:sha256:'+'f'*64),
            lambda v:v['history'].append(deepcopy(v['history'][-1])),
            lambda v:v['history'].append({'event':'REOPEN','evidence_ids':[]}),
            lambda v:v['history'][-1]['pre_model']['receipt'].pop('classification'),
            lambda v:v['history'][-1]['pre_model']['receipt'].update(reason_code='ARBITRARY'),
            lambda v:v['history'][-1]['pre_model']['receipt'].update(reference_id=None)]
        before=(len(s.real.worker.transport.updates),len(s.real.worker.transport.proposal_calls))
        for mutate in mutators:
            candidate=deepcopy(value);mutate(candidate)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):decode_journal_v2(canonical_bytes(candidate)+b'\n')
        with self.assertRaises(ValueError):decode_journal_v2(b.journal_bytes+b'\n')
        self.assertEqual((len(s.real.worker.transport.updates),len(s.real.worker.transport.proposal_calls)),before)

    def _component_a(self):
        # The actual producer reaches A and stops on an outside-catalog 500.
        # These tests qualify the journal CAS over validated proposals, separately
        # from active ticket/observation authorization tested in the continuation.
        s=self.scenario(status=500);s.run_packet()
        return s,s.current()

    def _receipt(self,a,*,different=False,permanent=False):
        c,r=a.record.control,a.record.attempt
        receipt=dict(schema_version=1,evidence_type='pre-model-preparation-failure',request_id=r.request_id,
            attempt_id=r.attempt_id,admission_evidence_id=r.admission['admission_evidence_id'],generation=1,
            reservation_id=c.reservation_id,workflow_run_id=c.worker.run_id,workflow_run_attempt=1,
            classification='PERMANENT' if permanent else 'UNKNOWN' if different else 'TRANSIENT',
            reason_code='SOURCE_DIGEST_MISMATCH' if permanent else 'SOURCE_ACCESS_AMBIGUOUS' if different else 'SOURCE_API_UNAVAILABLE',
            reference_id='contract' if permanent else 'requirement',
            observation_evidence_id=artifact_identity(b'second external premise' if different else b'first external premise'),
            observed_at='2026-11-06T07:00:00Z')
        return artifact_identity(canonical_bytes(receipt)+b'\n'),receipt

    def _race(self,s,a,mutations,first,*,committed=1):
        server=s.real.worker.transport;gate=Barrier(2,timeout=20);done=Event();actor=local()
        original=server.update_ref;payloads=[]
        def ordered(update):
            payloads.append(update);gate.wait()
            if actor.index!=first:self.assertTrue(done.wait(30))
            try:return original(update)
            finally:
                if actor.index==first:done.set()
        def run(index):
            actor.index=index
            return s.real.worker.journal._transition(a,mutations[index])
        with patch.object(server,'update_ref',ordered),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,(0,1)))
        self.assertEqual(len(payloads),2)
        self.assertTrue(all(p.before_oid==a.commit_sha and p.force is False for p in payloads))
        self.assertEqual(sum(r.status.value=='COMMITTED' for r in results),committed)
        self.assertEqual(results[first].status.value,'COMMITTED' if committed else 'UNRESOLVED')
        return results

    def test_F15_blocked_and_permanent_against_prepared_both_orders(self):
        for permanent in (False,True):
            for first in (0,1):
                s,a=self._component_a();c=a.record.control
                identity,receipt=self._receipt(a,permanent=permanent)
                fn=refuse_permanently if permanent else block_pre_model
                mutations=[lambda record:fn(record,identity,receipt,c.reservation_id,1,c.worker),
                    lambda record:transition_state(record,AttemptState.PREPARED,artifact_identity(b'verified packet premise'),c.reservation_id,1,c.worker)]
                with self.subTest(permanent=permanent,first=first):
                    results=self._race(s,a,mutations,first)
                    self.assertEqual(results[1-first].status.value,'REJECTED')
                    current=s.current()
                    self.assertEqual(current.record.attempt.state,AttemptState.ADMITTED if first==0 else AttemptState.PREPARED)
                    self.assertEqual(current.record.control.disposition,('REFUSED_PERMANENT' if permanent else 'BLOCKED') if first==0 else 'RESERVED')
                    self.assertEqual(sum(e.get('event')=='PRE_MODEL_FAILURE' for e in current.record.attempt.history),1 if first==0 else 0)

    def test_F16_identical_and_different_failure_proposals_one_attributed_winner(self):
        for identical in (False,True):
            for lost in (False,True):
                s,a=self._component_a();c=a.record.control;server=s.real.worker.transport
                server.identical_commits=identical;server.lose_update_acknowledgment=lost
                pairs=[self._receipt(a),self._receipt(a,different=not identical)]
                mutations=[(lambda record,pair=pair:block_pre_model(record,pair[0],pair[1],c.reservation_id,1,c.worker)) for pair in pairs]
                with self.subTest(identical=identical,lost=lost):
                    results=self._race(s,a,mutations,0,committed=0 if lost else 1)
                    self.assertEqual(results[1].status.value,'UNRESOLVED' if identical else 'REJECTED')
                    b=s.current();self.assertEqual(b.record.control.disposition,'BLOCKED')
                    self.assertEqual(sum(e.get('event')=='PRE_MODEL_FAILURE' for e in b.record.attempt.history),1)
                    before=len(server.proposal_calls)
                    if lost:self.assertEqual(s.real.worker.journal.reconcile(results[0].pending).status.value,'UNRESOLVED')
                    with self.assertRaises(RuntimeError):s.real.worker.journal._transition(b,mutations[0])
                    self.assertEqual(len(server.proposal_calls),before)
