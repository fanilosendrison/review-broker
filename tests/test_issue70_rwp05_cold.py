"""Actual separate-interpreter failure reconstruction after deleting the entire Worker root."""
from dataclasses import asdict
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from review_broker.identity import artifact_identity,canonical_bytes
from tests.issue68_test_support import IntegratedScenario
from tests.issue70_rwp03_linux_cold_isolation import minimal_environment
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario
from tests.issue70_rwp05_evidence_support import private_write


def export_external_server(s,observer):
    observer.mkdir(mode=0o700)
    server=s.real.worker.transport
    a=s.authority.snapshot
    IntegratedScenario.save_transport(s.real.worker,observer/'journal.json')
    origins=[]
    for sha in server.attributed:
        x=server.commits[sha]
        origins.append(dict(repository=a.repository,claim_ref=a.claim_ref,commit_sha=sha,
            parent_sha=x.parent_sha,journal_bytes_id=artifact_identity(x.journal_bytes)))
    private_write(observer/'server-origin.json',canonical_bytes(origins)+b'\n')
    private_write(observer/'server-mutation.json',canonical_bytes([asdict(x) for x in server.updates])+b'\n')
    private_write(observer/'admission.json',canonical_bytes(a.record.attempt.admission)+b'\n')
    private_write(observer/'request-id.txt',a.record.attempt.request_id.encode())


class FailureColdTests(unittest.TestCase):
    def child(self,observer,external,root):
        home=root/'child-home'
        if not home.exists():home.mkdir(mode=0o700)
        process=subprocess.run([sys.executable,'-m','tests.issue70_rwp05_cold_probe',str(observer),str(external)],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,close_fds=True,pass_fds=(),
            env=minimal_environment(home),timeout=90)
        self.assertEqual(process.returncode,0,process.stderr)
        data=json.loads(process.stdout)
        self.assertTrue(data['forbidden_counts'])
        self.assertTrue(all(count==0 for count in data['forbidden_counts'].values()))
        return data['result']

    def test_F19_transient_and_unknown_same_original_ids_time_after_worker_disappearance(self):
        for remote in (False,True):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                s=RemoteFailureScenario(root) if remote else FailureScenario(root)
                if remote:
                    s.service.lost_upload_response=True;s.service.metadata_failure=503
                    result=s.run_remote()
                else:result=s.run_packet()
                self.assertEqual((result.status.value,result.disposition),('COMMITTED','BLOCKED'))
                observer=root/'external-server';export_external_server(s,observer)
                expected_receipt=result.failure_receipt_id;expected_observation=result.observation_evidence_id
                expected=s.current().record.attempt.history[-1]['pre_model']['receipt']
                worker_root,external=s.worker_root,s.external
                del s,result;gc.collect();shutil.rmtree(worker_root)
                self.assertFalse(worker_root.exists())
                observed=self.child(observer,external,root)
                self.assertEqual((observed['status'],observed['state'],observed['disposition'],observed['failure_observation']),
                                 ('COMMITTED','ADMITTED','BLOCKED','VERIFIED'))
                self.assertEqual(observed['receipt_id'],expected_receipt)
                self.assertEqual(observed['observation_id'],expected_observation)
                self.assertEqual(observed['observed_at'],expected['observed_at'])
                self.assertEqual(observed['classification'],expected['classification'])
                self.assertEqual(observed['reason_code'],expected['reason_code'])

    def test_F20_F21_lost_rejected_cause_and_untrusted_history_do_not_mutate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);s=FailureScenario(root);result=s.run_packet()
            self.assertEqual(result.status.value,'COMMITTED')
            observer=root/'server';export_external_server(s,observer)
            external=s.external;worker_root=s.worker_root;observation_id=result.observation_evidence_id
            receipt_id=result.failure_receipt_id;b_sha=s.current().commit_sha
            del s,result;gc.collect();shutil.rmtree(worker_root)
            for mode,expected in [('missing-object','UNAVAILABLE'),('corrupt-object','REJECTED'),('withdrawn-origin','REJECTED')]:
                case=root/mode;shutil.copytree(external,case)
                if mode=='missing-object':(case/'observation-objects'/observation_id.rsplit(':',1)[-1]).unlink()
                elif mode=='corrupt-object':(case/'observation-objects'/observation_id.rsplit(':',1)[-1]).write_bytes(b'corrupt')
                else:(case/'trusted-origin'/observation_id.rsplit(':',1)[-1]).unlink()
                with self.subTest(mode=mode):
                    observed=self.child(observer,case,root)
                    self.assertEqual((observed['status'],observed['disposition'],observed['failure_observation']),
                                     ('COMMITTED','BLOCKED',expected))
                    self.assertEqual(observed['receipt_id'],receipt_id)
            for mode in ('wrong-parent','withdrawn-writer','coherent-falsification'):
                case=root/mode;shutil.copytree(observer,case)
                if mode=='wrong-parent':
                    path=case/'journal.json';value=json.loads(path.read_bytes())
                    value['commits'][b_sha]['parent_sha']='f'*40;path.write_bytes(canonical_bytes(value)+b'\n')
                elif mode=='withdrawn-writer':
                    path=case/'server-origin.json';value=json.loads(path.read_bytes())
                    path.write_bytes(canonical_bytes([v for v in value if v['commit_sha']!=b_sha])+b'\n')
                else:
                    from review_broker.pre_model_failure_observation_v3 import FailureObservationV3
                    from tests.issue68_test_support import restore_transport
                    from review_broker.journal_record_v3 import decode_journal_v2
                    transport=restore_transport(case/'journal.json')
                    value=json.loads(transport.commits[b_sha].journal_bytes)
                    original_receipt=value['history'][-1]['pre_model']['receipt']
                    forged_observation=json.loads((external/'observation-objects'/observation_id.rsplit(':',1)[-1]).read_bytes())
                    forged_observation['observed_at']='2026-11-06T07:00:01Z'
                    forged_observation_id=FailureObservationV3.from_value(forged_observation).evidence_id
                    original_receipt.update(observation_evidence_id=forged_observation_id,observed_at=forged_observation['observed_at'])
                    new_receipt_id=artifact_identity(canonical_bytes(original_receipt)+b'\n')
                    value['pre_model_control']['failure_receipt_id']=new_receipt_id
                    value['history'][-1]['evidence_ids']=[new_receipt_id]
                    value['evidence_ids'][-1]=new_receipt_id
                    raw=canonical_bytes(value)+b'\n';decode_journal_v2(raw)  # Positive coherent-wire control.
                    forged_sha=transport.create_journal_commit(transport.commits[b_sha].parent_sha,raw)
                    transport.refs[next(iter(transport.refs))]=forged_sha
                    holder=type('UntrustedSnapshotInput',(),{'transport':transport})()
                    IntegratedScenario.save_transport(holder,case/'journal.json')
                with self.subTest(mode=mode):
                    observed=self.child(case,external,root)
                    self.assertEqual((observed['status'],observed['disposition']),('UNRESOLVED','UNCONFIRMED'))
