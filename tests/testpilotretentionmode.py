"""Adversarial tests for staged private-retention mode normalization."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from review_broker.pilot_controller_state import request_reservation_digest
from review_broker.pilot_private_retention import (
    PilotRetentionError,
    _normalize_staged_file,
)
from review_broker.pilot_synthetic import PILOT_MISSION, PILOT_SOURCE
from tests.testpilotretention import (
    REQUEST,
    FakeSource,
    PrivateRetentionTests,
    valid_receipts,
)


class ModePreservingSource(FakeSource):
    def __init__(self, values, mode=0o644):
        super().__init__(values)
        self.mode = mode

    def copy_literal(self, name, destination):
        self.copies.append(name)
        destination.write_bytes(self.values[name])
        destination.chmod(self.mode)


class StagedModeNormalizationTests(unittest.TestCase):
    prepare = PrivateRetentionTests.prepare
    retain = PrivateRetentionTests.retain

    def test_mode_0644_transfer_is_normalized_and_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            source = ModePreservingSource(valid_receipts(outcome="PASS"))
            original = {name: hashlib.sha256(data).hexdigest()
                        for name, data in source.values.items()}
            manifest = self.retain(root, source)
            self.assertEqual(manifest["raw_diagnostic_retention"], "PASS")
            attempt = root / request_reservation_digest(REQUEST)
            for entry in manifest["artifact_entries"]:
                if not entry["retained_local"]:
                    continue
                directory = "receipts" if entry["relative_name"].startswith("pilot-") else "diagnostics"
                retained = attempt / directory / entry["relative_name"]
                self.assertEqual(stat.S_IMODE(retained.stat().st_mode), 0o600)
                self.assertEqual(hashlib.sha256(retained.read_bytes()).hexdigest(),
                                 original[entry["relative_name"]])

    def test_hash_mismatch_still_fails_after_mode_normalization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            source = ModePreservingSource(valid_receipts(outcome="PASS"))
            observed = source.observe("codex-final.json")
            source.overrides["codex-final.json"] = type(observed)(
                True, True, False, 1, observed.byte_length, "a" * 64, "PASS_NO_MATCH",
            )
            manifest = self.retain(root, source)
            entry = next(item for item in manifest["artifact_entries"]
                         if item["relative_name"] == "codex-final.json")
            self.assertEqual(entry["retention_status"], "HASH_MISMATCH")

    def test_mode_0600_normalization_preserves_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary) / "staging"; staging.mkdir(mode=0o700)
            path = staging / "codex-final.json"; data = b'{"safe":true}'
            path.write_bytes(data); path.chmod(0o600)
            _normalize_staged_file(path, staging)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_symlink_is_refused_without_following_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); staging = root / "staging"; staging.mkdir(mode=0o700)
            target = root / "target"; target.write_bytes(b"safe"); target.chmod(0o644)
            path = staging / "codex-final.json"; path.symlink_to(target)
            with self.assertRaises(OSError):
                _normalize_staged_file(path, staging)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_hardlink_is_refused_without_mode_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); staging = root / "staging"; staging.mkdir(mode=0o700)
            path = staging / "codex-final.json"; path.write_bytes(b"safe"); path.chmod(0o644)
            os.link(path, root / "alias")
            with self.assertRaises(PilotRetentionError):
                _normalize_staged_file(path, staging)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_nonregular_files_are_refused(self):
        for kind in ("directory", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                staging = Path(temporary) / "staging"; staging.mkdir(mode=0o700)
                path = staging / "codex-final.json"
                path.mkdir() if kind == "directory" else os.mkfifo(path)
                with self.assertRaises(PilotRetentionError):
                    _normalize_staged_file(path, staging)

    def test_incorrect_owner_and_identity_change_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary) / "staging"; staging.mkdir(mode=0o700)
            path = staging / "codex-final.json"; path.write_bytes(b"safe")
            descriptor = os.open(path, os.O_RDONLY)
            try:
                opened = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            class Changed:
                def __init__(self, value, *, uid=None, ino=None):
                    for name in ("st_mode", "st_nlink", "st_uid", "st_dev", "st_ino"):
                        setattr(self, name, getattr(value, name))
                    if uid is not None: self.st_uid = uid
                    if ino is not None: self.st_ino = ino
            with patch("review_broker.pilot_private_retention.os.fstat",
                       return_value=Changed(opened, uid=os.getuid() + 1)), self.assertRaises(PilotRetentionError):
                _normalize_staged_file(path, staging)
            calls = [opened, Changed(opened, ino=opened.st_ino + 1)]
            with patch("review_broker.pilot_private_retention.os.fstat", side_effect=calls), self.assertRaises(PilotRetentionError):
                _normalize_staged_file(path, staging)

    def test_fchmod_and_metadata_sync_fail_closed(self):
        for function in ("fchmod", "fsync"):
            with self.subTest(function=function), tempfile.TemporaryDirectory() as temporary:
                staging = Path(temporary) / "staging"; staging.mkdir(mode=0o700)
                path = staging / "codex-final.json"; path.write_bytes(b"safe")
                with patch(f"review_broker.pilot_private_retention.os.{function}",
                           side_effect=OSError("synthetic")), self.assertRaises(OSError):
                    _normalize_staged_file(path, staging)

    def test_historical_rb05_fixture_bytes_remain_unchanged(self):
        self.assertEqual(hashlib.sha256(PILOT_SOURCE).hexdigest(),
                         "08db9bbffa1af0a1df9f147b5f3405e363361113c00934c44777916bf4c8b379")
        self.assertEqual(hashlib.sha256(PILOT_MISSION.encode()).hexdigest(),
                         "820c7f92cec3e64f4f141256b16dd84f08666b1953afdea1c6c8c2bc400e1376")


if __name__ == "__main__":
    unittest.main()
