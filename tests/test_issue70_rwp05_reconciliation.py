"""R1: thrown post-CAS reads preserve the exact enriched pending operation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.pre_model_active_decision_v3 import PreModelDecisionStateV3
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_git_support import install_concrete_failure_writer


class FailureReconciliationExceptionTests(unittest.TestCase):
    def scenario(self,*,lost=False,edge='ref'):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        s=FailureScenario(Path(temporary.name));s.read_fault=True;s.failed_http_reads=[]
        def install():
            s.real.worker.transport.lose_update_acknowledgment=lost
            api,transport=install_concrete_failure_writer(s);s.api,s.http=api,transport
            original=transport._executor
            def after_cas(update,result):
                # The independent simulated ref service, not the HTTP success,
                # determines actual head even when the CAS acknowledgment was lost.
                api.refs[update.name]=s.real.worker.transport.refs[update.name]
                api.concrete_readback=True
            api.after_cas=after_cas
            def execute(request):
                if getattr(api,'concrete_readback',False) and s.read_fault and request.get_method()=='GET':
                    if '/git/ref/' in request.full_url:
                        if edge=='matching':
                            api._record(request);return HttpResponseV3(404,b'{}',{})
                        if edge=='ref':
                            api._record(request);s.failed_http_reads.append(request.full_url);raise OSError('fixture ref unavailable')
                    if edge=='matching' and '/git/matching-refs/' in request.full_url:
                        api._record(request);s.failed_http_reads.append(request.full_url);raise OSError('fixture matching ref unavailable')
                return original(request)
            transport._executor=execute
        s.archive.on_put=install
        return s

    def assert_pending_and_finish(self,s,result,*,lost=False):
        self.assertEqual(result.status.value,'UNRESOLVED',result)
        self.assertIsNotNone(result.journal_outcome,result)
        pending=result.journal_outcome.pending;self.assertIsNotNone(pending)
        a=s.authority.snapshot;server=s.real.worker.transport
        self.assertEqual((pending.repository,pending.claim_ref,pending.predecessor_sha,pending.intended_sha),
                         (a.repository,a.claim_ref,a.commit_sha,server.refs[a.claim_ref]))
        self.assertEqual((pending.request_id,pending.admission,pending.mutation_kind),
                         (a.record.attempt.request_id,a.record.attempt.admission,'UPDATE_REFS'))
        self.assertEqual(pending.writer_evidence_id is None,lost)
        self.assertFalse(pending.expected_old_rejected)
        self.assertIsNone(pending.rejection_evidence_id)
        self.assertEqual(s.api.mutation_calls,4)  # blob/tree/commit plus exactly one CAS.
        self.assertEqual(s.failure_cas_count(),1)
        self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
        with self.assertRaises(ValueError):s.producer._decision.require_active(s.producer)
        before=(len(server.updates),len(server.proposal_calls),s.api.mutation_calls,len(s.archive.puts))
        s.read_fault=False
        if lost:server.attributed.add(pending.intended_sha)  # Equal authenticated B is not this operation's ACK.
        for _ in range(3):
            follow=s.real.worker.journal.reconcile(pending)
            self.assertEqual(follow.status.value,'UNRESOLVED' if lost else 'COMMITTED')
            if lost:self.assertEqual(follow.pending,pending)
            else:self.assertEqual(follow.snapshot.record.control.disposition,'BLOCKED')
        s.producer.run(s.real.worker.context)
        self.assertEqual((len(server.updates),len(server.proposal_calls),s.api.mutation_calls,len(s.archive.puts)),before)

    def test_R1_F17_F18_real_ref_and_matching_http_exceptions_known_and_lost_ack(self):
        for edge in ('ref','matching'):
            for lost in (False,True):
                s=self.scenario(lost=lost,edge=edge);result=s.run_packet()
                with self.subTest(edge=edge,lost=lost):
                    self.assertTrue(s.failed_http_reads)
                    self.assert_pending_and_finish(s,result,lost=lost)

    def test_R1_F18_recognized_rejection_evidence_survives_thrown_readback(self):
        s=self.scenario();install=s.archive.on_put;server=s.real.worker.transport
        def raced():
            install();a=s.authority.snapshot
            def move(event):
                if event!='PRE_MODEL_FAILURE':return
                other=server.create_journal_commit(a.commit_sha,a.journal_bytes)
                server.attributed.add(other);server.refs[a.claim_ref]=other
                from tests.github_transport_live_v3_support import PARENT_TREE
                s.api.commits[other]=(PARENT_TREE,[a.commit_sha])
            server.event_hook=move
        s.archive.on_put=raced;result=s.run_packet()
        self.assertEqual(result.status.value,'UNRESOLVED');self.assertIsNotNone(result.journal_outcome)
        pending=result.journal_outcome.pending;self.assertIsNotNone(pending)
        self.assertTrue(pending.expected_old_rejected);self.assertTrue(pending.application_errors)
        from tests.journal_v3_test_support import REJECTION_EVIDENCE_ID
        self.assertEqual(pending.rejection_evidence_id,REJECTION_EVIDENCE_ID)
        self.assertIsNone(pending.writer_evidence_id)
        self.assertEqual((pending.predecessor_sha,pending.intended_sha),(s.authority.snapshot.commit_sha,s.api.next_commit))
        self.assertTrue(s.failed_http_reads);self.assertEqual(s.api.mutation_calls,4)
        self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
        before=(len(server.updates),len(server.proposal_calls),s.api.mutation_calls)
        s.read_fault=False
        self.assertEqual(s.real.worker.journal.reconcile(pending).status.value,'REJECTED')
        self.assertEqual((len(server.updates),len(server.proposal_calls),s.api.mutation_calls),before)

    def test_R1_F17_origin_verification_read_exception_preserves_pending(self):
        s=self.scenario(edge='none');authority=s.real.worker.journal.predecessor_authority;original=authority.evidence_id
        def unavailable(**kwargs):
            if hasattr(s,'api') and getattr(s.api,'concrete_readback',False) and s.read_fault:
                raise OSError('fixture origin service unavailable')
            return original(**kwargs)
        with patch.object(authority,'evidence_id',unavailable):result=s.run_packet()
        self.assert_pending_and_finish(s,result)

    def test_R1_F17_reconciliation_authority_exception_keeps_already_recognized_writer(self):
        s=self.scenario(edge='none');authority=s.real.worker.journal.mutation_authority;original=authority.permits;calls=[]
        def unavailable(update,evidence):
            if hasattr(s,'api') and getattr(s.api,'concrete_readback',False):
                calls.append((update,evidence))
                if len(calls)==2:raise OSError('fixture mutation authority read unavailable')
            return original(update,evidence)
        with patch.object(authority,'permits',unavailable):result=s.run_packet()
        self.assertGreaterEqual(len(calls),2)
        self.assert_pending_and_finish(s,result)
