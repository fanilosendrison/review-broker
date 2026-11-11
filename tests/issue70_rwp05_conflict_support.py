"""Existing permanent-refusal actor premise for independent race/fence tests."""
from review_broker.identity import artifact_identity,canonical_bytes


def commit_foreign_permanent(scenario):
    a=scenario.current();attempt,control=a.record.attempt,a.record.control
    receipt=dict(schema_version=1,evidence_type='pre-model-preparation-failure',request_id=attempt.request_id,
        attempt_id=attempt.attempt_id,admission_evidence_id=attempt.admission['admission_evidence_id'],
        generation=1,reservation_id=control.reservation_id,workflow_run_id=control.worker.run_id,
        workflow_run_attempt=1,classification='PERMANENT',reason_code='SOURCE_DIGEST_MISMATCH',
        reference_id='contract',observation_evidence_id=artifact_identity(b'external immutable-digest premise'),
        observed_at='2026-11-06T07:00:00Z')
    expected=canonical_bytes(receipt)
    class ExistingPermanentAuthority:
        def permits(self,value):return canonical_bytes(value)==expected
    return scenario.real.worker.journal.refuse_permanently(a,artifact_identity(expected+b'\n'),receipt,
        control.reservation_id,1,control.worker,ExistingPermanentAuthority())
