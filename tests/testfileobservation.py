"""Adversarial tests for coherent bounded regular-file observations."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

import review_broker.codexfailure as codexfailure
import review_broker.evidence as evidence
import review_broker.fileobservation as fileobservation
from review_broker.evidence import EvidenceCaptureError
from review_broker.fileobservation import FileObservationError


_EVENT_400 = b'{"type":"error","status":400}\n'
_EVENT_503 = b'{"type":"error","status":503}\n'
_CLEAN = b"clean synthetic output".ljust(44, b".")
_CONTAMINATED = b"Bearer SYNTHETIC00000000000000000000".ljust(44, b".")


@contextmanager
def _mutate_after_consumer(real_observer, mutation, path):
    """Schedule a real mutation after consumption but before final validation."""
    with real_observer(path) as stream:
        yield stream
        mutation(path)


def _rewrite_same_inode(path: Path, replacement: bytes) -> None:
    before = path.stat()
    with path.open("r+b") as stream:
        stream.write(replacement)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    after = path.stat()
    if before.st_ino != after.st_ino or before.st_size != after.st_size:
        raise AssertionError("fixture did not preserve inode and size")


def _identity_with_coarse_timestamps(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        0,
        0,
    )


class FileObservationAdversarialTests(unittest.TestCase):
    def test_path_rebind_rejects_event_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "evidence"
            root.mkdir()
            events = root / "codex-events.jsonl"
            stderr = root / "codex-stderr.txt"
            replacement = base / "replacement"
            retained = base / "retained"
            events.write_bytes(_EVENT_400)
            stderr.write_bytes(b"")
            replacement.write_bytes(_EVENT_503)

            def rebind(path):
                path.rename(retained)
                replacement.rename(path)

            real = fileobservation.observed_regular_file
            observer = lambda path: _mutate_after_consumer(real, rebind, path)
            with patch.object(codexfailure, "observed_regular_file", observer):
                observed = codexfailure.observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )
            self.assertEqual(json.loads(events.read_bytes())["status"], 503)
            self.assertEqual(observed["event_stream_status"], "UNAVAILABLE")
            self.assertEqual(observed["failure_events"], [])

    def test_path_rebind_rejects_manifest_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "evidence"
            root.mkdir()
            artifact = root / "codex-events.jsonl"
            replacement = base / "replacement"
            retained = base / "retained"
            artifact.write_bytes(b"old-data")
            replacement.write_bytes(b"new-data")

            def rebind(path):
                path.rename(retained)
                replacement.rename(path)

            real = fileobservation.observed_regular_file
            observer = lambda path: _mutate_after_consumer(real, rebind, path)
            with patch.object(codexfailure, "observed_regular_file", observer):
                entry = codexfailure.failure_artifact_manifest(root)[artifact.name]
            self.assertEqual(artifact.read_bytes(), b"new-data")
            self.assertFalse(entry["present"])
            self.assertEqual(entry["sha256"], "UNDETERMINED")

    def test_path_rebind_makes_credential_screen_indeterminate(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "evidence"
            root.mkdir()
            artifact = root / "codex-final.json"
            replacement = base / "replacement"
            retained = base / "retained"
            artifact.write_bytes(_CLEAN)
            replacement.write_bytes(_CONTAMINATED)

            def rebind(path):
                path.rename(retained)
                replacement.rename(path)

            real = fileobservation.observed_regular_file
            observer = lambda path: _mutate_after_consumer(real, rebind, path)
            with patch.object(evidence, "observed_regular_file", observer):
                with self.assertRaisesRegex(
                    EvidenceCaptureError, "CREDENTIAL_SCREENING_UNDETERMINED",
                ):
                    evidence.scan_for_credentials(root)
            self.assertIn(b"Bearer ", artifact.read_bytes())

    def test_same_size_rewrite_rejects_event_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "codex-events.jsonl"
            stderr = root / "codex-stderr.txt"
            events.write_bytes(_EVENT_400)
            stderr.write_bytes(b"")
            real = fileobservation.observed_regular_file
            mutation = lambda path: _rewrite_same_inode(path, _EVENT_503)
            observer = lambda path: _mutate_after_consumer(real, mutation, path)
            with patch.object(fileobservation, "_identity",
                              _identity_with_coarse_timestamps), patch.object(
                codexfailure, "observed_regular_file", observer,
            ):
                observed = codexfailure.observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )
            self.assertEqual(json.loads(events.read_bytes())["status"], 503)
            self.assertEqual(observed["event_stream_status"], "UNAVAILABLE")
            self.assertEqual(observed["failure_events"], [])

    def test_same_size_rewrite_rejects_manifest_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "codex-events.jsonl"
            artifact.write_bytes(b"old-data")
            real = fileobservation.observed_regular_file
            mutation = lambda path: _rewrite_same_inode(path, b"new-data")
            observer = lambda path: _mutate_after_consumer(real, mutation, path)
            with patch.object(fileobservation, "_identity",
                              _identity_with_coarse_timestamps), patch.object(
                codexfailure, "observed_regular_file", observer,
            ):
                entry = codexfailure.failure_artifact_manifest(root)[artifact.name]
            self.assertEqual(artifact.read_bytes(), b"new-data")
            self.assertFalse(entry["present"])
            self.assertEqual(entry["sha256"], "UNDETERMINED")

    def test_same_size_rewrite_makes_credential_screen_indeterminate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "codex-final.json"
            artifact.write_bytes(_CLEAN)
            real = fileobservation.observed_regular_file
            mutation = lambda path: _rewrite_same_inode(path, _CONTAMINATED)
            observer = lambda path: _mutate_after_consumer(real, mutation, path)
            with patch.object(fileobservation, "_identity",
                              _identity_with_coarse_timestamps), patch.object(
                evidence, "observed_regular_file", observer,
            ):
                with self.assertRaisesRegex(
                    EvidenceCaptureError, "CREDENTIAL_SCREENING_UNDETERMINED",
                ):
                    evidence.scan_for_credentials(root)
            self.assertIn(b"Bearer ", artifact.read_bytes())

    def test_bounded_read_rejects_rebind_and_same_size_rewrite(self):
        for replacement, rebind in ((b"new-data", True), (b"new-data", False)):
            with self.subTest(rebind=rebind), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                artifact = base / "artifact"
                artifact.write_bytes(b"old-data")
                retained = base / "retained"
                candidate = base / "replacement"
                candidate.write_bytes(replacement)

                def mutation(path):
                    if rebind:
                        path.rename(retained)
                        candidate.rename(path)
                    else:
                        _rewrite_same_inode(path, replacement)

                real = fileobservation.observed_regular_file
                observer = lambda path: _mutate_after_consumer(real, mutation, path)
                with patch.object(fileobservation, "_identity",
                                  _identity_with_coarse_timestamps), patch.object(
                    fileobservation, "observed_regular_file", observer,
                ):
                    with self.assertRaises(FileObservationError):
                        fileobservation.read_regular_file_bounded(artifact, 8)

    def test_final_path_absence_and_symlink_are_rejected(self):
        for replacement in ("absent", "symlink"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                artifact = base / "artifact"
                retained = base / "retained"
                target = base / "target"
                artifact.write_bytes(b"stable")
                target.write_bytes(b"replacement")

                def mutate(path):
                    path.rename(retained)
                    if replacement == "symlink":
                        path.symlink_to(target)

                real = fileobservation.observed_regular_file
                observer = lambda path: _mutate_after_consumer(real, mutate, path)
                with patch.object(fileobservation, "observed_regular_file", observer):
                    with self.assertRaises(FileObservationError):
                        fileobservation.read_regular_file_bounded(artifact, 6)

    def test_incomplete_first_pass_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            artifact.write_bytes(b"complete")
            with self.assertRaisesRegex(
                FileObservationError, "OBSERVED_FILE_READ_INCOMPLETE",
            ):
                with fileobservation.observed_regular_file(artifact) as stream:
                    self.assertEqual(stream.read(1), b"c")

    def test_stable_positive_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "codex-events.jsonl"
            stderr = root / "codex-stderr.txt"
            clean = root / "clean"
            events.write_bytes(_EVENT_400)
            stderr.write_bytes(b"")
            clean.write_bytes(b"ordinary output")
            observed = codexfailure.observe_codex_failure_files(
                returncode=1, events_path=events, stderr_path=stderr,
            )
            self.assertEqual(observed["failure_events"][0]["http_status"], 400)
            entry = codexfailure.failure_artifact_manifest(root)[events.name]
            self.assertEqual(entry["sha256"], hashlib.sha256(_EVENT_400).hexdigest())
            self.assertEqual(evidence.scan_for_credentials(root), [])

            clean.write_bytes(_CONTAMINATED)
            self.assertEqual(evidence.scan_for_credentials(root), ["clean"])
            clean.write_bytes(b"")
            self.assertEqual(fileobservation.read_regular_file_bounded(clean, 0), b"")
            clean.write_bytes(b"12345678")
            self.assertEqual(
                fileobservation.read_regular_file_bounded(clean, 8), b"12345678",
            )

    def test_credential_match_still_consumes_to_eof(self):
        stream = io.BytesIO(_CONTAMINATED + b"tail" * 20_000)
        self.assertTrue(evidence._stream_contains_credential(stream))
        self.assertEqual(stream.tell(), len(stream.getvalue()))

    def test_large_stable_observations_keep_fixed_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "codex-final.json"
            with artifact.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)

            tracemalloc.start()
            entry = codexfailure.failure_artifact_manifest(root)[artifact.name]
            _, manifest_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertTrue(entry["present"])
            self.assertEqual(entry["byte_length"], 32 * 1024 * 1024)
            self.assertLess(manifest_peak, 2 * 1024 * 1024)

            tracemalloc.start()
            self.assertEqual(evidence.scan_for_credentials(root), [])
            _, screen_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertLess(screen_peak, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
