"""Newly decodable failed ADMITTED control must not reopen older preparation helpers."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.packet_v2 import build_packet_v2_candidate
from review_broker.packet_retention_v3 import persist_packet_evidence_v3,packet_retention_locator_v3
from review_broker.packet_preparation_authority_v3 import prepare_packet_receipt_v3,RetainedPacketAuthorityV3
from review_broker.packet_v2_technical_policy import AuthorizedPolicySnapshotV3
from review_broker.pre_model_policy_selection_v3 import PolicySelectionReceiptV3
from review_broker.packets import GitSourceReader
from tests.packet_v2_test_support import profile
from tests.issue70_rwp03_test_support import POLICY_BYTES,SOURCE
from tests.issue70_rwp05_test_support import FailureScenario


class FailedPreparationFenceTests(unittest.TestCase):
    def test_F22_failed_control_is_rejected_before_authorized_git_or_legacy_packet_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);s=FailureScenario(root);positive=[]
            base=root/'legacy-open-retention'
            # Independent component positive controls use the actual current A,
            # never a fake read presenting a historical snapshot as current head.
            def open_controls():
                s.reference_status=200
                a=s.authority.snapshot;inputs=s.real.inputs
                bundle=AuthorizedPolicySnapshotV3(POLICY_BYTES,SOURCE,PolicySelectionReceiptV3.from_bytes(s.real.archive.read_bytes()))
                build_packet_v2_candidate(inputs.admission,inputs.capture,bundle,root/'open-authorized',inputs.issue_readers,
                                           policy_verification=s.real.verification())
                manifest=persist_packet_evidence_v3(inputs.admission,inputs.capture,profile(),base,a,s.real.worker.journal,inputs.issue_readers)
                positive.append((manifest,bundle))
                s.reference_status=503
            s.archive.on_put=open_controls
            result=s.run_packet();self.assertEqual(result.status.value,'COMMITTED')
            self.assertEqual(len(positive),1)
            b=s.current();self.assertEqual(b.record.control.disposition,'BLOCKED')
            s.reference_status=200  # No unrelated read error can mask this fence.
            inputs=s.real.inputs;manifest,bundle=positive[0]
            reads=[];original=GitSourceReader._git
            def observed_git(reader,*args,**kwargs):
                reads.append(args);return original(reader,*args,**kwargs)
            with patch.object(GitSourceReader,'_git',observed_git):
                with self.subTest(api='authorized-build'),self.assertRaises(ValueError):
                    build_packet_v2_candidate(inputs.admission,inputs.capture,bundle,root/'forbidden-authorized',inputs.issue_readers,
                                               policy_verification=s.real.verification())
            with self.subTest(api='authorized-build-reads'):self.assertEqual(reads,[])
            with self.subTest(api='legacy-persist'),self.assertRaises(ValueError):
                persist_packet_evidence_v3(inputs.admission,inputs.capture,profile(),root/'forbidden-legacy',b,s.real.worker.journal,inputs.issue_readers)
            with self.subTest(api='legacy-persist-path'):self.assertFalse((root/'forbidden-legacy').exists())
            with self.subTest(api='legacy-receipt'),self.assertRaises(ValueError):
                prepare_packet_receipt_v3(base,b,manifest['technical_policy']['technical_policy_id'],
                    manifest['subject']['subject_capture_evidence_id'],manifest['packet_id'])
            authority=RetainedPacketAuthorityV3(base,manifest['technical_policy']['technical_policy_id'],
                manifest['subject']['subject_capture_evidence_id'],manifest['packet_id'])
            receipt_path=packet_retention_locator_v3(base,b.claim_ref)/'evidence/preparation-receipt.json'
            with self.subTest(api='legacy-receipt-path'):self.assertFalse(receipt_path.exists())
            from review_broker.identity import artifact_identity
            receipt_id=artifact_identity(receipt_path.read_bytes()) if receipt_path.exists() else artifact_identity(b'not-retained')
            disk_reads=[];original_read=Path.read_bytes
            def observed_read(path):
                disk_reads.append(path);return original_read(path)
            with patch.object(Path,'read_bytes',observed_read):
                allowed=authority.permits(snapshot=b,packet_evidence_id=receipt_id,reservation_id=b.record.control.reservation_id,
                                          generation=1,worker=b.record.control.worker)
            with self.subTest(api='legacy-authority'):self.assertIs(allowed,False)
            with self.subTest(api='legacy-authority-reads'):self.assertEqual(disk_reads,[])
            self.assertEqual(s.current(),b)
            self.assertEqual(s.failure_cas_count(),1)
            self.assertEqual(s.real.worker.transport.events.count('PREPARED'),0)
