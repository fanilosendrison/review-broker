"""Coherent fault construction, never a replacement loader/verifier or acceptance oracle."""
from dataclasses import replace
import hashlib

from review_broker.changes import build_change_basis
from review_broker.identity import canonical_bytes,packet_identity
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.packet_v2 import _packet_basis,subject_capture_evidence_id_v2,verify_packet_v2_candidate
from review_broker.packet_v2_renderer import render_packet_v2_prompt
from review_broker.physical import decode_physical_lines
from review_broker.pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from review_broker.identity import artifact_identity


def mutate_coherently(root, verification, *, keep_asserted_packet_id=False):
    admission,capture,_,manifest=load_packet_evidence_v3(root,verification.snapshot.record.attempt.admission,
                                                        policy_verification=verification)
    original_manifest=canonical_bytes(manifest)+b'\n';original_id=manifest['packet_id']
    diff=capture.diff.replace(b'+after\n',b'+other\n');assert diff!=capture.diff
    changed=replace(capture,diff=diff)
    manifest['subject']['subject_capture_evidence_id']=subject_capture_evidence_id_v2(changed)
    basis,_=build_change_basis(manifest['change_scope']['changes'],manifest['subject_sources'],
                              merge_base=capture.merge_base_sha,head=capture.head_sha,diff=diff)
    manifest['change_scope'].update(basis)
    calculated=packet_identity(_packet_basis(manifest));assert calculated!=original_id
    manifest['packet_id']=original_id if keep_asserted_packet_id else calculated
    subject_lines={e['source_id']:capture.records[i].lines for i,e in enumerate(manifest['subject_sources'])}
    reference_lines={e['source_id']:decode_physical_lines((root/'packet'/e['snapshot']).read_bytes())[1]
                     for e in manifest['reference_sources']}
    prompt=render_packet_v2_prompt(manifest,subject_lines=subject_lines,reference_lines=reference_lines,diff=diff)
    manifest.update(prompt_sha256=hashlib.sha256(prompt).hexdigest(),prompt_byte_length=len(prompt))
    (root/'packet/changes.patch').write_bytes(diff)
    (root/'packet/input.txt').write_bytes(prompt)
    (root/'packet/input-manifest.json').write_bytes(canonical_bytes(manifest)+b'\n')
    return original_manifest,canonical_bytes(manifest)+b'\n',original_id,calculated


def register_reconstruction_fault(scenario, root, *, check):
    original,observed,original_id,calculated=mutate_coherently(root,scenario.verification,
                                                             keep_asserted_packet_id=check=='PACKET_ID')
    if check=='PACKET_ID':
        source=verify_packet_v2_candidate
        subject_matches=lambda subject:subject==scenario.remote_root/'packet'
        expected_id,observed_id=original_id,calculated
        operation='VERIFY_REMOTE_PACKET'
    else:
        source=PreModelRemoteRetentionV3.run
        subject_matches=lambda subject:subject[0]==scenario.remote_root and canonical_bytes(subject[1])+b'\n'==original and canonical_bytes(subject[2])+b'\n'==observed
        expected_id,observed_id=artifact_identity(original),artifact_identity(observed)
        operation='VERIFY_REMOTE_MANIFEST'
    scenario.authority.verification_records.append(dict(phase='REMOTE_RECONSTRUCTION',operation=operation,
        source=source,subject_matches=subject_matches,reference_id=None,artifact_id='991',
        target='/repos/'+scenario.real.worker.expected.repository+'/actions/artifacts/991/zip',
        fact=dict(kind='VERIFICATION_FAILED',check=check,expected_id=expected_id,observed_id=observed_id,
                  expected_size=None,observed_size=None)))
    scenario.service._unconfirmed()
