from dataclasses import replace
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from review_broker.artifact_locator import build_evidence_artifact_locator, build_evidence_artifact_plan
from review_broker.artifact_resume import resume_from_durable_artifact
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, transition_record
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


if __name__ == "__main__":
    unittest.main()
