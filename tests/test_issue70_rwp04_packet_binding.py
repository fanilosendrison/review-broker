"""Coherent retained-packet substitution cannot replace the genuine RWP-03 handoff."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest

from review_broker.changes import build_change_basis
from review_broker.identity import canonical_bytes, packet_identity
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.packet_v2 import _packet_basis, subject_capture_evidence_id_v2
from review_broker.packet_v2_renderer import render_packet_v2_prompt
from review_broker.physical import decode_physical_lines
from tests.issue70_rwp04_test_support import RemoteScenario


class OriginalPacketBindingTests(unittest.TestCase):
    def test_R3_coherent_changed_diff_with_genuine_handoff_has_zero_uploads_or_cas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            r = RemoteScenario(root)
            retained = r.handoff.retained_root
            original_packet_id = r.handoff.packet_id
            admission, capture, profile, manifest = load_packet_evidence_v3(
                retained, r.verification.snapshot.record.attempt.admission,
                policy_verification=r.verification)
            original_policy = dict(manifest["technical_policy"])
            changed_diff = capture.diff.replace(b"+after\n", b"+other\n")
            self.assertNotEqual(changed_diff, capture.diff)
            changed_capture = replace(capture, diff=changed_diff)
            changed_capture = replace(changed_capture, evidence_id=subject_capture_evidence_id_v2(changed_capture))
            manifest["subject"]["subject_capture_evidence_id"] = changed_capture.evidence_id
            changed_basis, _ = build_change_basis(manifest["change_scope"]["changes"], manifest["subject_sources"],
                merge_base=capture.merge_base_sha, head=capture.head_sha, diff=changed_diff)
            manifest["change_scope"].update(changed_basis)
            # These production functions construct the coherent attack, not the
            # independent acceptance oracle (the genuine original handoff and
            # separately measured service/CAS counters below).
            manifest["packet_id"] = packet_identity(_packet_basis(manifest))
            subject_lines = {entry["source_id"]: capture.records[index].lines
                             for index, entry in enumerate(manifest["subject_sources"])}
            reference_lines = {entry["source_id"]: decode_physical_lines(
                (retained/"packet"/entry["snapshot"]).read_bytes())[1]
                for entry in manifest["reference_sources"]}
            prompt = render_packet_v2_prompt(manifest, subject_lines=subject_lines,
                                             reference_lines=reference_lines, diff=changed_diff)
            manifest.update(prompt_sha256=hashlib.sha256(prompt).hexdigest(), prompt_byte_length=len(prompt))
            (retained/"packet/changes.patch").write_bytes(changed_diff)
            (retained/"packet/input.txt").write_bytes(prompt)
            (retained/"packet/input-manifest.json").write_bytes(canonical_bytes(manifest)+b"\n")
            # Positive attack-validity control: all independent authorities remain
            # recognized and the real cold loader/full verifier accept this new,
            # internally coherent packet. No verifier is replaced by a fake.
            _, _, _, loaded = load_packet_evidence_v3(retained, admission.journal_admission(),
                                                       policy_verification=r.verification)
            self.assertEqual(loaded["packet_id"], manifest["packet_id"])
            self.assertNotEqual(loaded["packet_id"], original_packet_id)
            self.assertEqual(loaded["technical_policy"], original_policy)
            result = r.run()  # Actual original producer and its genuine handoff.
            with self.subTest(decision=True): self.assertEqual(result.status.value, "REJECTED", result.reason)
            self.assertEqual(len(r.service.uploads), 0)
            self.assertEqual(r.s.worker.transport.events.count("PREPARED"), 0)
            self.assertEqual(r.s.worker.journal.read(admission.request_id).record.attempt.state.value, "ADMITTED")
            self.assertEqual(r.handoff.packet_id, original_packet_id)
