"""Complete real candidate chain, three injected discoveries, four/empty references and cold PREPARED."""
from dataclasses import asdict
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import artifact_identity,canonical_bytes
from tests.issue68_test_support import IntegratedScenario
from tests.issue70_rwp03_linux_cold_isolation import minimal_environment
from tests.issue70_rwp05_test_support import FailureWorkerScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario
from tests.issue70_rwp05_evidence_support import private_write


class IntegratedStageOneTests(unittest.TestCase):
    def test_Stage1_PM01_PM23_true_common_controller_to_prepared_and_cold_both_reference_variants(self):
        original_seed=FailureWorkerScenario.seed
        for empty in (False,True):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);discoveries=[]
                def discover(worker):
                    first=original_seed(worker);discoveries.append(('issue_opened',first.status.value))
                    for source in ('reconciler','reconciler_repeat'):
                        observed=worker.controller.run(worker.admission);discoveries.append((source,observed.status.value))
                    return first
                with patch.object(FailureWorkerScenario,'seed',discover):s=RemoteFailureScenario(root,no_remote=empty)
                self.assertEqual(len(discoveries),3)
                self.assertEqual(len(s.real.worker.dispatch.calls),1)
                self.assertEqual(s.real.worker.transport.events.count('PRE_MODEL_DISPATCH_RESERVED'),1)
                self.assertEqual(s.real.worker.transport.events.count('PRE_MODEL_DISPATCH_ACKNOWLEDGED'),1)
                self.assertEqual(s.real.worker.transport.events.count('PRE_MODEL_WORKER_BOUND'),1)
                self.assertEqual(s.real.worker.transport.events.count('ADMITTED'),1)
                result=s.run_remote();self.assertEqual(result.status.value,'COMMITTED',result)
                self.assertEqual(s.current().record.attempt.state.value,'PREPARED')
                self.assertEqual(s.failure_cas_count(),0);self.assertEqual(s.archive.puts,[])
                self.assertEqual(len(s.service.uploads),1)
                observer=root/'cold-input';observer.mkdir(mode=0o700)
                w=s.real.worker;a=s.authority.snapshot;p=s.current()
                IntegratedScenario.save_transport(w,observer/'journal.json')
                origins=[dict(repository=x.repository,claim_ref=x.claim_ref,commit_sha=x.commit_sha,
                              parent_sha=x.parent_sha,journal_bytes_id=artifact_identity(x.journal_bytes)) for x in (a,p)]
                expected_manifest=(s.handoff.retained_root/'packet/input-manifest.json').read_bytes()
                expected_inventory=s.service.uploads[0][0].inventory_bytes
                expected_remote=result.remote_receipt.canonical_receipt_bytes
                original_id=s.handoff.packet_id
                for name,data in {
                    'server-origin.json':canonical_bytes(origins)+b'\n',
                    'server-mutation.json':canonical_bytes([asdict(u) for u in w.transport.updates])+b'\n',
                    'admission.json':canonical_bytes(w.admission.journal_admission())+b'\n',
                    'dispatch.json':canonical_bytes(w.dispatch_authority.archive)+b'\n',
                    'authenticated-storage.json':canonical_bytes(result.remote_receipt.value['storage'])+b'\n',
                    'independent-selection.json':s.real.archive.read_bytes(),
                    'downloaded.zip':result.archive_bytes,'request-id.txt':w.admission.request_id.encode(),
                }.items():private_write(observer/name,data)
                worker_root=s.worker_root
                del s,w,a,p,result;gc.collect();shutil.rmtree(worker_root)
                home=root/'home';home.mkdir(mode=0o700)
                process=subprocess.run([sys.executable,'-m','tests.issue70_rwp04_cold_probe',str(observer)],
                    stdin=subprocess.DEVNULL,capture_output=True,text=True,close_fds=True,pass_fds=(),
                    env=minimal_environment(home),timeout=90)
                self.assertEqual(process.returncode,0,process.stderr)
                observed=json.loads(process.stdout)
                self.assertEqual(canonical_bytes(observed['manifest'])+b'\n',expected_manifest)
                self.assertEqual(canonical_bytes(observed['inventory'])+b'\n',expected_inventory)
                self.assertEqual(canonical_bytes(observed['remote'])+b'\n',expected_remote)
                self.assertEqual(observed['manifest']['packet_id'],original_id)
                self.assertEqual([observed[k] for k in ('capture_calls','selections','uploads','journal_mutations')],[0,0,0,0])
                if empty:self.assertEqual(list((observer/'cold-packet/evidence/admitted-references').iterdir()),[])
