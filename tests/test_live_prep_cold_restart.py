"""Independent historical reconstruction and a real restarted ADMITTED interpreter."""
import base64
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timezone

from review_broker.cold_network_boundary_v3 import minimal_environment
from review_broker.cold_packet_observer_v3 import collect_api_corpus_v3,run_cold_observer_v3
from review_broker.github_policy_authority_v3 import GitHubProtectedPolicyAuthorityV3
from review_broker.github_prepared_artifact_v3 import GitHubPreparedArtifactV3
from review_broker.github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from review_broker.prepared_artifact_transport_v3 import PreparedMetadataReaderV3
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.prepared_packet_archive_v3 import extract_prepared_packet_v3
from review_broker.pre_model_dispatch_ack_v3 import acknowledgment_from_record
from review_broker.live_pre_model_worker_v3 import worker_observer_v3
from review_broker.github_actions_worker_authority_v3 import WorkerInputsV3
from review_broker.request_v3 import request_identity_v3
from tests.live_prep_artifact_provider_support import CompleteProviderService
from tests.live_prep_provider_support import controller_scenario
from tests.test_live_prep_complete_composition import worker_scenario


def private_json(path,value):
    path.write_text(json.dumps(value));path.chmod(0o600)


class ColdRestartTests(unittest.TestCase):
    def test_new_historical_reader_after_worker_and_both_subject_clones_disappear(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            controller=controller_scenario(root,service);service.controller_running=False
            result=worker_scenario(root,service,controller)
            self.assertTrue(result.cold_verified,result)
            original_packet=result.packet_id;original_receipt=result.remote_receipt_id
            identifier=request_identity_v3(service.request)
            inputs=WorkerInputsV3(identifier,controller.reservation_outcome.snapshot.record.control.reservation_id,1)
            del controller,result;gc.collect()
            for path in (root/'worker',root/'controller-source',service.origin):shutil.rmtree(path)
            counts=(len(service.acquisitions),len(service.mints),len(service.uploads),service.git.mutation_calls,len(service.source_calls))
            # A new observer obtains all authorities from GitHub-form observations,
            # not original Worker objects, source bytes, policies or live tickets.
            runtime=service.runtime('worker',vars(inputs));journal,dispatch=worker_observer_v3(runtime)
            p=journal.read(identifier);principal=dispatch.principal_id(acknowledgment_from_record(p.record))
            metadata=PreparedMetadataReaderV3(token='fixture-control',repository=runtime.expected.repository,
                executor=service.metadata,budget=runtime.api.metadata.budget)
            adapter=GitHubPreparedArtifactV3(metadata=metadata,
                worker_history=GitHubPreparedWorkerHistoryV3(metadata,runtime.expected,dispatch,principal),
                storage_executor=service.storage,budget=metadata.budget,clock=lambda:datetime.now(timezone.utc))
            history=PreparedJournalHistoryV3.read(journal,identifier,runtime.expected,dispatch,principal)
            storage=adapter.observe(history.admitted,history.verify)
            raw=adapter.download(storage,history.verify)
            destination=root/'external-observer';destination.mkdir(mode=0o700)
            packet=destination/'downloaded'
            extract_prepared_packet_v3(raw,packet,metadata.budget,history.verify)
            policy=GitHubProtectedPolicyAuthorityV3(api=runtime.api,journal=journal,expected=runtime.expected,
                dispatch_authority=dispatch)
            corpus=collect_api_corpus_v3(journal=journal,snapshot=p,expected=runtime.expected,
                policy=policy,dispatch=dispatch,packet_root=packet,prepared=True)
            observed=run_cold_observer_v3(corpus=corpus,packet_root=packet,private_base=destination,
                before_effect=history.verify,storage=storage)
            self.assertEqual(observed,{'packet_id':original_packet,'remote_receipt_id':original_receipt})
            self.assertEqual(counts,(len(service.acquisitions),len(service.mints),len(service.uploads),
                service.git.mutation_calls,len(service.source_calls)))
            with self.assertRaisesRegex(ValueError,'OBSERVER_CANNOT_SELECT_POLICY'):
                policy.select_policy(None,None,runtime.expected,before_effect=lambda:None)

    def test_restarted_ADMITTED_python_has_runtime_but_no_original_effect_permission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=CompleteProviderService(root)
            controller=controller_scenario(root,service);service.controller_running=False
            service.body_reference+='changed'
            first=worker_scenario(root,service,controller)
            self.assertEqual(first.state,'ADMITTED',first)
            identifier=request_identity_v3(service.request)
            inputs=WorkerInputsV3(identifier,controller.reservation_outcome.snapshot.record.control.reservation_id,1)
            external=root/'restart-server.json'
            private_json(external,{'request':service.request,'inputs':vars(inputs),'refs':service.git.refs,
                'trees':service.git.trees,'commits':service.git.commits,
                'blobs':{k:base64.b64encode(v).decode() for k,v in service.git.blobs.items()}})
            del controller,first;gc.collect();shutil.rmtree(root/'worker')
            fresh=root/'fresh-worker';fresh.mkdir(mode=0o700);home=root/'fresh-home';home.mkdir(mode=0o700)
            process=subprocess.run([sys.executable,'-m','tests.live_prep_restart_probe',str(external),str(fresh)],
                env=minimal_environment(home),stdin=subprocess.DEVNULL,capture_output=True,text=True,
                close_fds=True,pass_fds=(),timeout=90)
            self.assertEqual(process.returncode,0,process.stderr)
            observed=json.loads(process.stdout)
            self.assertEqual(observed['source_or_helper_effects'],0);self.assertEqual(observed['mutations'],0)
            self.assertEqual(observed['result']['status'],'REJECTED')
