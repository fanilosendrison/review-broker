"""Rediscovery, copied results, future-operation fences and PREPARED barrier."""
from contextlib import ExitStack
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.pre_model_controller_v3 import PreModelControllerV3
from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
from review_broker.pre_model_failure_continuation_v3 import PreModelFailureContinuationV3
from review_broker.pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from review_broker.pre_model_failure_readback_v3 import HistoricalPreModelFailureV3
from tests.issue70_rwp02_test_support import TARGET
from tests.issue70_rwp04_test_support import ArtifactService
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario
from tests.issue70_rwp05_conflict_support import commit_foreign_permanent
from tests.journal_v3_test_support import TrustedPacketAuthority,PACKET_ID


class FailureObserverFenceTests(unittest.TestCase):
    def scenario(self,remote=False,**kwargs):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return (RemoteFailureScenario if remote else FailureScenario)(Path(temporary.name),**kwargs)

    def new_producer(self,s):
        return PreModelPacketContinuationV3(journal=s.real.worker.journal,current_worker_authority=s.real.authority,
            original_admission=s.real.worker.admission,capture_provider=s.real,reference_readers=s.real.reference_readers,
            policy_source_authority=s.real.source_authority,policy_selection_authority=s.real.selection_authority,
            packet_stages=s.real.stages,failure_evidence=s.evidence)

    def test_F22_blocked_and_permanent_rediscovery_or_new_worker_has_zero_new_effects(self):
        for permanent in (False,True):
            s=self.scenario(status=500 if permanent else 503);result=s.run_packet()
            if permanent:self.assertEqual(commit_foreign_permanent(s).status.value,'COMMITTED')
            original=s.current();w=s.real.worker;server=w.transport
            before=(len(server.proposal_calls),len(server.updates),len(w.dispatch.calls),s.real.capture_calls,len(s.archive.puts))
            with ExitStack() as stack:
                forbidden=[stack.enter_context(patch(target,side_effect=AssertionError(target))) for target in (
                    'review_broker.codex.invoke_once','review_broker.codespace.CodespaceController.start',
                    'review_broker.codespace.CodespaceController.stop','review_broker.codespace.CodespaceController.state')]
                controllers=[w.controller,PreModelControllerV3(w.journal,TARGET,w.dispatch,w.controller_authority,w.dispatch_authority)]
                for controller in controllers:
                    for _ in range(3):controller.run(w.admission)
                for context in (w.context,replace(w.context,inputs=replace(w.context.inputs,generation=2))):
                    self.assertNotEqual(w.worker().run(context).status.value,'COMMITTED')
                    producer=self.new_producer(s)
                    self.assertNotEqual(producer.run(context).status.value,'COMMITTED')
                    self.assertIsNone(producer._decision)
                b=s.current()
                for operation in ('recover','generation_2','stopped','armed'):
                    with self.assertRaises(RuntimeError):w.journal.unsupported(operation)
                with self.assertRaises(RuntimeError):w.journal.reserve_initial(b)
                with self.assertRaises(RuntimeError):w.journal.prepare(b,PACKET_ID,b.record.control.reservation_id,1,b.record.control.worker,TrustedPacketAuthority())
                if not permanent:
                    history=HistoricalPreModelFailureV3.read(w.journal,w.admission.request_id)
                    with self.assertRaises(RuntimeError):
                        w.journal.block_pre_model(history.admitted,history.blocked.record.control.failure_receipt_id,
                            history.receipt,history.admitted.record.control.reservation_id,1,
                            history.admitted.record.control.worker,history)
                for call in forbidden:call.assert_not_called()
            self.assertEqual(s.current(),original)
            self.assertEqual((len(server.proposal_calls),len(server.updates),len(w.dispatch.calls),s.real.capture_calls,len(s.archive.puts)),before)

    def test_F05_copied_failure_result_is_not_a_successful_remote_handoff(self):
        s=self.scenario();result=s.run_packet();w=s.real.worker
        from review_broker.github_prepared_artifact_v3 import PreparedArtifactUploaderV3,GitHubPreparedArtifactV3
        from review_broker.prepared_artifact_transport_v3 import PreparedMetadataReaderV3
        from review_broker.github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
        from tests.issue70_rwp04_test_support import BUDGET,NOW,PRINCIPAL
        service=ArtifactService(s.real)
        metadata=PreparedMetadataReaderV3(token='fixture',repository=w.expected.repository,executor=service.metadata,budget=BUDGET)
        adapter=GitHubPreparedArtifactV3(metadata=metadata,worker_history=GitHubPreparedWorkerHistoryV3(metadata,w.expected,w.dispatch_authority,PRINCIPAL),
            storage_executor=service.storage,budget=BUDGET,clock=lambda:NOW)
        remote=PreModelRemoteRetentionV3(producer=s.producer,retention_base=s.worker_root/'retained',
            verification=AuthorizedPolicyVerificationV3(w.journal,s.current(),w.expected,s.real.source_authority,s.real.selection_authority),
            uploader=PreparedArtifactUploaderV3(service),adapter=adapter,remote_verification_root=s.worker_root/'no-upload')
        self.assertNotEqual(remote.run(w.context,copy.deepcopy(result)).status.value,'COMMITTED')
        self.assertEqual(service.uploads,[])
        self.assertEqual(s.failure_cas_count(),1)

    def test_F11_prepared_entry_unknown_or_committed_never_falls_back_to_failure(self):
        for lost in (False,True):
            s=self.scenario(remote=True);server=s.real.worker.transport
            server.lose_update_acknowledgment=lost
            from review_broker.pre_model_failure_boundaries_v3 import PreModelFailureCollectorV3
            collectors=[];original=PreModelFailureCollectorV3.bind_artifact_adapter
            def capture(collector,adapter):
                collectors.append(collector);return original(collector,adapter)
            with patch.object(PreModelFailureCollectorV3,'bind_artifact_adapter',capture):result=s.run_remote()
            self.assertEqual(result.status.value,'UNRESOLVED' if lost else 'COMMITTED')
            self.assertEqual(s.current().record.attempt.state.value,'PREPARED')
            self.assertEqual(s.failure_cas_count(),0)
            self.assertEqual(s.archive.puts,[])
            self.assertEqual(server.events.count('PREPARED'),1)
            before=(len(server.proposal_calls),len(server.updates),len(s.service.uploads))
            s.run_remote()
            self.assertEqual(PreModelFailureContinuationV3(collectors[0]).run().status.value,'UNRESOLVED')
            if not lost:
                from review_broker.prepared_packet_readback_v3 import readback_prepared_packet_v3
                s.service.artifacts=[]
                observed=readback_prepared_packet_v3(journal=s.real.worker.journal,request_id=s.real.worker.admission.request_id,
                    adapter=s.adapter,source_authority=s.real.source_authority,selection_authority=s.real.selection_authority,
                    destination=s.root/'lost-prepared-observer')
                self.assertEqual((observed.journal_transition,observed.state,observed.remote_reconstruction),
                                 ('COMMITTED','PREPARED','UNAVAILABLE'))
            with self.assertRaises(ValueError):s.producer._decision.require_active(s.remote)
            self.assertEqual((len(server.proposal_calls),len(server.updates),len(s.service.uploads)),before)
