from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from review_broker.artifact_locator import build_evidence_artifact_locator, build_evidence_artifact_plan
from review_broker.artifact_resume import (
    ArtifactResumeError,
    PublicationRecoveryBinding,
    recover_validated_publication,
    resume_from_durable_artifact,
)
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, transition_record
from review_broker.validation import validate_evidence
from tests.test_evidence import EvidenceValidationTests


class FakeJournal:
    def __init__(self, record):
        self.record = record
        self.transitions = []

    def transition(self, request_id, target, evidence_ids):
        self.transitions.append((request_id, target, tuple(evidence_ids)))
        self.record = transition_record(self.record, target, evidence_ids)
        return self.record

    def get(self, request_id):
        return replace(self.record, state=AttemptState.REPORTED)


class CopyingStore:
    def __init__(self, source):
        self.source = source

    def download(self, locator, destination):
        shutil.copytree(self.source, destination)


class RejectingStore:
    def download(self, locator, destination):
        raise AssertionError("download forbidden before exact binding")


class ExactJournal:
    def __init__(self, record):
        self.record = record

    def get(self, request_id):
        return self.record


class ArtifactResumeTests(unittest.TestCase):
    def test_terminal_artifact_resumes_validation_without_model_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            evidence.mkdir()
            manifest = EvidenceValidationTests().fixture(evidence)
            resolved = {
                "schema_version": 1,
                "request_id": manifest["request_id"],
                "subject_id": manifest["subject_id"],
            }
            (evidence / "resolved-request.json").write_bytes(
                canonical_bytes(resolved) + b"\n"
            )
            plan = build_evidence_artifact_plan(
                evidence,
                broker_repository="sample/review-broker",
                artifact_name="terminal-123-1",
                workflow_run_id="123",
                workflow_run_attempt="1",
            )
            digest = "sha256:" + hashlib.sha256(b"archive").hexdigest()
            metadata = {
                "id": 987,
                "name": plan["artifact_name"],
                "digest": digest,
                "expired": False,
                "size_in_bytes": 7,
                "created_at": "2026-10-26T00:00:00+00:00",
                "expires_at": "2026-11-26T00:00:00+00:00",
                "workflow_run": {"id": 123},
            }
            locator = build_evidence_artifact_locator(
                plan, metadata, declared_digest=digest
            )
            record = AttemptRecord(
                request_id=manifest["request_id"],
                attempt_id="attempt:sha256:" + "3" * 64,
                state=AttemptState.TERMINAL_CAPTURED,
                invocation_count=1,
                evidence_locator_plan=plan,
                evidence_locator=locator,
            )
            journal = FakeJournal(record)
            result = {
                "request_id": manifest["request_id"],
                "attempt_id": record.attempt_id,
            }
            with mock.patch(
                "review_broker.artifact_resume.publish_validated_result",
                return_value=result,
            ) as publish:
                resumed = resume_from_durable_artifact(
                    "sample/review-broker",
                    record,
                    journal=journal,
                    store=CopyingStore(evidence),
                )
            publish.assert_called_once()
            self.assertEqual(journal.transitions[0][1], AttemptState.VALIDATED)
            self.assertEqual(resumed["state"], AttemptState.REPORTED.value)
            self.assertEqual(resumed["validation"]["evidence_status"], "VALID")

    def test_publication_recovery_rejects_mismatched_binding_before_download(self):
        request_id = "request:sha256:" + "1" * 64
        attempt_id = "attempt:sha256:" + "2" * 64
        locator = {
            "request_id": request_id,
            "attempt_id": attempt_id,
            "packet_id": "packet:sha256:" + "3" * 64,
            "artifact_id": 17,
            "artifact_digest": "sha256:" + "4" * 64,
        }
        record = AttemptRecord(
            request_id=request_id,
            attempt_id=attempt_id,
            state=AttemptState.VALIDATED,
            invocation_count=1,
            evidence_locator=locator,
        )
        binding = PublicationRecoveryBinding(
            issue_number=28,
            request_id=request_id,
            attempt_id=attempt_id,
            packet_id=locator["packet_id"],
            artifact_id=17,
            artifact_digest=locator["artifact_digest"],
            subject_repository="sample/subject",
            subject_pull_request=57,
            subject_head="a" * 40,
        )
        mutations = (
            replace(record, invocation_count=2),
            replace(record, state=AttemptState.TERMINAL_CAPTURED),
            replace(record, publication_intent={"unexpected": True}),
            replace(record, evidence_locator={**locator, "artifact_id": 18}),
        )
        for changed in mutations:
            with self.subTest(record=changed):
                with self.assertRaisesRegex(ArtifactResumeError, "BINDING_MISMATCH"):
                    recover_validated_publication(
                        "sample/review-broker",
                        binding,
                        journal=ExactJournal(changed),
                        store=RejectingStore(),
                    )

    def test_exact_validated_artifact_recomputes_same_validation_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / "evidence"
            evidence.mkdir()
            manifest = EvidenceValidationTests().fixture(evidence)
            request_id = manifest["request_id"]
            attempt_id = "attempt:sha256:" + "3" * 64
            resolved = {
                "schema_version": 1,
                "request_id": request_id,
                "subject_id": manifest["subject_id"],
                "subject": {
                    "repository": "sample/subject",
                    "pull_request": 57,
                    "head_commit": "a" * 40,
                },
            }
            (evidence / "resolved-request.json").write_bytes(canonical_bytes(resolved) + b"\n")
            metadata = json.loads(
                (evidence / "broker-metadata.json").read_text(encoding="utf-8")
            )
            metadata["issue_number"] = 28
            (evidence / "broker-metadata.json").write_bytes(canonical_bytes(metadata) + b"\n")
            validation = validate_evidence(evidence)
            validation_id = artifact_identity((evidence / "validation.json").read_bytes())
            (evidence / "validation.json").unlink()
            plan = build_evidence_artifact_plan(
                evidence,
                broker_repository="sample/review-broker",
                artifact_name="terminal-123-1",
                workflow_run_id="123",
                workflow_run_attempt="1",
            )
            digest = "sha256:" + hashlib.sha256(b"archive").hexdigest()
            locator = build_evidence_artifact_locator(plan, {
                "id": 987,
                "name": plan["artifact_name"],
                "digest": digest,
                "expired": False,
                "size_in_bytes": 7,
                "created_at": "2026-10-26T00:00:00+00:00",
                "expires_at": "2026-11-26T00:00:00+00:00",
                "workflow_run": {"id": 123},
            }, declared_digest=digest)
            record = AttemptRecord(
                request_id=request_id,
                attempt_id=attempt_id,
                state=AttemptState.VALIDATED,
                invocation_count=1,
                evidence_ids=(validation_id,),
                evidence_locator=locator,
            )
            binding = PublicationRecoveryBinding(
                issue_number=28,
                request_id=request_id,
                attempt_id=attempt_id,
                packet_id=manifest["packet_id"],
                artifact_id=987,
                artifact_digest=digest,
                subject_repository="sample/subject",
                subject_pull_request=57,
                subject_head="a" * 40,
            )
            journal = ExactJournal(record)
            with mock.patch(
                "review_broker.artifact_resume.publish_validated_result",
                return_value={"request_id": request_id, "attempt_id": attempt_id},
            ) as publish:
                resumed = recover_validated_publication(
                    "sample/review-broker",
                    binding,
                    journal=journal,
                    store=CopyingStore(evidence),
                )
            publish.assert_called_once()
            self.assertEqual(resumed["validation_id"], validation_id)
            self.assertEqual(resumed["validation"], validation)


if __name__ == "__main__":
    unittest.main()
