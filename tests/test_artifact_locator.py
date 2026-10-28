from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from review_broker.artifact_locator import (
    ArtifactLocatorError,
    GitHubActionsArtifactStore,
    build_evidence_artifact_locator,
    build_evidence_artifact_plan,
)
from review_broker.identity import canonical_bytes


class ArtifactLocatorTests(unittest.TestCase):
    def evidence(self, root: Path) -> Path:
        evidence = root / "evidence"
        evidence.mkdir()
        request_id = "request:sha256:" + "1" * 64
        attempt_id = "attempt:sha256:" + "2" * 64
        subject_id = "subject:sha256:" + "3" * 64
        packet_id = "packet:sha256:" + "4" * 64
        values = {
            "resolved-request.json": {
                "request_id": request_id,
                "subject_id": subject_id,
            },
            "input-manifest.json": {
                "request_id": request_id,
                "subject_id": subject_id,
                "packet_id": packet_id,
            },
            "attempt.json": {"attempt_id": attempt_id},
            "terminal-capture.json": {
                "request_id": request_id,
                "attempt_id": attempt_id,
                "packet_id": packet_id,
            },
        }
        for name, value in values.items():
            (evidence / name).write_bytes(canonical_bytes(value) + b"\n")
        (evidence / "codex-events.jsonl").write_bytes(b'{"type":"turn.completed"}\n')
        return evidence

    def plan(self, root: Path):
        evidence = self.evidence(root)
        plan = build_evidence_artifact_plan(
            evidence,
            broker_repository="sample/review-broker",
            artifact_name="terminal-123-1",
            workflow_run_id="123",
            workflow_run_attempt="1",
        )
        return evidence, plan

    def archive(self, evidence: Path) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            for path in sorted(evidence.rglob("*")):
                if path.is_file():
                    bundle.writestr(path.relative_to(evidence).as_posix(), path.read_bytes())
        return output.getvalue()

    def metadata(self, plan, archive, *, expired=False):
        now = datetime.now(timezone.utc)
        return {
            "id": 987,
            "name": plan["artifact_name"],
            "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
            "expired": expired,
            "size_in_bytes": len(archive),
            "created_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "workflow_run": {"id": int(plan["workflow_run_id"])},
        }

    def test_locator_binds_run_attempt_subject_packet_and_exact_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence, plan = self.plan(Path(temporary))
            archive = self.archive(evidence)
            locator = build_evidence_artifact_locator(
                plan,
                self.metadata(plan, archive),
                declared_digest=hashlib.sha256(archive).hexdigest(),
            )
            self.assertEqual(locator["request_id"], plan["request_id"])
            self.assertEqual(locator["attempt_id"], plan["attempt_id"])
            self.assertEqual(locator["subject_id"], plan["subject_id"])
            self.assertEqual(locator["packet_id"], plan["packet_id"])
            self.assertEqual(locator["workflow_run_id"], "123")
            self.assertEqual(locator["workflow_run_attempt"], "1")
            self.assertEqual(set(locator["artifacts"]), set(plan["artifacts"]))

    def test_exact_archive_is_downloaded_and_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, plan = self.plan(root)
            archive = self.archive(evidence)
            metadata = self.metadata(plan, archive)
            locator = build_evidence_artifact_locator(
                plan, metadata, declared_digest=metadata["digest"]
            )

            def runner(command, **kwargs):
                endpoint = command[2]
                if endpoint.endswith("/zip"):
                    return subprocess.CompletedProcess(command, 0, archive, b"")
                return subprocess.CompletedProcess(command, 0, json.dumps(metadata), "")

            destination = root / "downloaded"
            GitHubActionsArtifactStore("sample/review-broker", runner=runner).download(
                locator, destination
            )
            self.assertEqual(
                (destination / "codex-events.jsonl").read_bytes(),
                (evidence / "codex-events.jsonl").read_bytes(),
            )

    def test_changed_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, plan = self.plan(root)
            archive = self.archive(evidence)
            metadata = self.metadata(plan, archive)
            locator = build_evidence_artifact_locator(
                plan, metadata, declared_digest=metadata["digest"]
            )

            def runner(command, **kwargs):
                if command[2].endswith("/zip"):
                    return subprocess.CompletedProcess(command, 0, archive + b"changed", b"")
                return subprocess.CompletedProcess(command, 0, json.dumps(metadata), "")

            with self.assertRaisesRegex(ArtifactLocatorError, "ARCHIVE_DIGEST_MISMATCH"):
                GitHubActionsArtifactStore(
                    "sample/review-broker", runner=runner
                ).download(locator, root / "downloaded")

    def test_incomplete_archive_is_rejected_after_archive_digest_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, plan = self.plan(root)
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as bundle:
                bundle.writestr("attempt.json", (evidence / "attempt.json").read_bytes())
            incomplete = output.getvalue()
            metadata = self.metadata(plan, incomplete)
            locator = build_evidence_artifact_locator(
                plan, metadata, declared_digest=metadata["digest"]
            )

            def runner(command, **kwargs):
                if command[2].endswith("/zip"):
                    return subprocess.CompletedProcess(command, 0, incomplete, b"")
                return subprocess.CompletedProcess(command, 0, json.dumps(metadata), "")

            with self.assertRaisesRegex(ArtifactLocatorError, "CONTENT_IDENTITY_MISMATCH"):
                GitHubActionsArtifactStore(
                    "sample/review-broker", runner=runner
                ).download(locator, root / "downloaded")

    def test_expired_or_mismatched_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence, plan = self.plan(Path(temporary))
            archive = self.archive(evidence)
            expired = self.metadata(plan, archive, expired=True)
            with self.assertRaisesRegex(ArtifactLocatorError, "METADATA_MISMATCH"):
                build_evidence_artifact_locator(
                    plan, expired, declared_digest=expired["digest"]
                )
            mismatched = self.metadata(plan, archive)
            mismatched["workflow_run"] = {"id": 999}
            with self.assertRaisesRegex(ArtifactLocatorError, "METADATA_MISMATCH"):
                build_evidence_artifact_locator(
                    plan, mismatched, declared_digest=mismatched["digest"]
                )

    def test_unavailable_or_ambiguous_plan_resolution_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, plan = self.plan(Path(temporary))

            def runner(command, **kwargs):
                return subprocess.CompletedProcess(
                    command, 0, json.dumps({"total_count": 0, "artifacts": []}), ""
                )

            with self.assertRaisesRegex(ArtifactLocatorError, "UNAVAILABLE_OR_AMBIGUOUS"):
                GitHubActionsArtifactStore(
                    "sample/review-broker", runner=runner
                ).resolve_plan(plan)


if __name__ == "__main__":
    unittest.main()
