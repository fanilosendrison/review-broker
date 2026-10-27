"""Offline adversarial tests for private synthetic-pilot retention."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from review_broker.identity import canonical_bytes
from review_broker.pilot_controller_state import arm_controller_attempt, request_reservation_digest
from review_broker.pilot_private_retention import (
    CodespaceLiteralCopier,
    DIAGNOSTIC_LIMITS,
    PilotRetentionError,
    RemoteArtifact,
    retain_private_pilot_artifacts,
    retention_then_shutdown,
)

REQUEST = "request:sha256:" + "1" * 64
ATTEMPT = "attempt:sha256:" + "2" * 64
SOURCE = "3" * 40
PILOT = "RB-PILOT-EXAMPLE"


class FakeSource:
    def __init__(self, values: dict[str, bytes]):
        self.values = dict(values)
        self.overrides: dict[str, RemoteArtifact] = {}
        self.copy_failures: set[str] = set()
        self.copies: list[str] = []

    def observe(self, name: str) -> RemoteArtifact:
        if name in self.overrides:
            return self.overrides[name]
        if name not in self.values:
            return RemoteArtifact(False)
        data = self.values[name]
        return RemoteArtifact(
            True, True, False, 1, len(data), hashlib.sha256(data).hexdigest(),
            "PASS_NO_MATCH",
        )

    def copy_literal(self, name: str, destination: Path) -> None:
        self.copies.append(name)
        if name in self.copy_failures:
            raise OSError("synthetic transfer failure")
        destination.write_bytes(self.values[name]); destination.chmod(0o600)


def fixture_values(*, screen: str = "PASS_NO_MATCH") -> dict[str, bytes]:
    summary = {
        "request_id": REQUEST, "attempt_id": ATTEMPT,
        "packet_id": "packet:sha256:" + "4" * 64,
        "credential_screen": screen,
    }
    return {
        "pilot-claim.json": canonical_bytes({"request_id": REQUEST, "attempt_id": ATTEMPT}) + b"\n",
        "pilot-armed.json": canonical_bytes({"request_id": REQUEST, "attempt_id": ATTEMPT}) + b"\n",
        "pilot-summary.json": canonical_bytes(summary) + b"\n",
        "pilot-failure.json": canonical_bytes({"request_id": REQUEST, "attempt_id": ATTEMPT}) + b"\n",
        "codex-events.jsonl": b'{"type":"turn.failed"}\n',
        "codex-stderr.txt": b"synthetic diagnostic\n",
        "codex-final.json": b"",
        "codex-exit-code.txt": b"1\n",
    }


class PrivateRetentionTests(unittest.TestCase):
    def prepare(self, temporary: str) -> Path:
        root = Path(temporary) / "pilots"
        arm_controller_attempt(
            pilot_id=PILOT, request_id=REQUEST, attempt_id=ATTEMPT,
            source_sha=SOURCE, _state_root=root,
            _created_utc="2026-10-28T00:00:00+00:00",
        )
        return root

    def retain(self, root: Path, source: FakeSource):
        return retain_private_pilot_artifacts(
            pilot_id=PILOT, request_id=REQUEST, attempt_id=ATTEMPT,
            source_sha=SOURCE, source=source, _state_root=root,
            _retained_at="2026-10-28T00:01:00+00:00",
        )

    def test_complete_private_retention_survives_remote_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); source = FakeSource(fixture_values())
            manifest = self.retain(root, source)
            self.assertEqual(manifest["sanitized_receipt_retention"], "PASS")
            self.assertEqual(manifest["raw_diagnostic_retention"], "PASS")
            attempt = root / request_reservation_digest(REQUEST)
            self.assertEqual(stat.S_IMODE(attempt.stat().st_mode), 0o700)
            for directory in (attempt / "receipts", attempt / "diagnostics"):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
                for path in directory.iterdir():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            identities = {
                entry["relative_name"]: entry["sha256"]
                for entry in manifest["artifact_entries"] if entry["retained_local"]
            }
            source.values.clear()  # Simulated remote /tmp loss after Shutdown.
            for name, digest in identities.items():
                directory = "receipts" if name.startswith("pilot-") else "diagnostics"
                self.assertEqual(
                    hashlib.sha256((attempt / directory / name).read_bytes()).hexdigest(), digest,
                )

    def test_absent_optional_failure_receipt_preserves_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); values = fixture_values(); values.pop("pilot-failure.json")
            manifest = self.retain(root, FakeSource(values))
            entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == "pilot-failure.json")
            self.assertEqual(entry["retention_status"], "ABSENT")
            self.assertEqual(manifest["sanitized_receipt_retention"], "PASS")

    def test_summary_screen_blocks_all_raw_diagnostics(self):
        for screen in ("UNDETERMINED", "CONTAMINATED_QUARANTINED"):
            with self.subTest(screen=screen), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary); source = FakeSource(fixture_values(screen=screen))
                manifest = self.retain(root, source)
                self.assertEqual(manifest["raw_diagnostic_retention"], "SKIPPED_QUARANTINED")
                self.assertFalse(any(name in source.copies for name in DIAGNOSTIC_LIMITS))

    def test_remote_and_local_credential_detection_refuse_raw_copy(self):
        for screen, expected in (
            ("CONTAMINATED", "REFUSED_CONTAMINATED"),
            ("UNDETERMINED", "REFUSED_SCREEN_UNDETERMINED"),
        ):
            with self.subTest(screen=screen), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary); source = FakeSource(fixture_values())
                name = "codex-stderr.txt"; observed = source.observe(name)
                source.overrides[name] = RemoteArtifact(
                    True, True, False, 1, observed.byte_length, observed.sha256, screen,
                )
                manifest = self.retain(root, source)
                entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == name)
                self.assertEqual(entry["retention_status"], expected)
                self.assertNotIn(name, source.copies)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); values = fixture_values()
            values["codex-stderr.txt"] = b"Authorization: Bearer synthetic-secret-material"
            source = FakeSource(values)
            manifest = self.retain(root, source)
            entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == "codex-stderr.txt")
            self.assertEqual(entry["retention_status"], "REFUSED_CONTAMINATED")
            self.assertFalse((root / request_reservation_digest(REQUEST) / "diagnostics/codex-stderr.txt").exists())

    def test_oversize_alias_hardlink_hash_and_transfer_failures_are_distinct(self):
        cases = {
            "oversize": ("REFUSED_OVERSIZED", RemoteArtifact(True, True, False, 1, 65, "a" * 64, "PASS_NO_MATCH")),
            "symlink": ("LOCAL_VALIDATION_FAILED", RemoteArtifact(True, False, True, 1, 2, "a" * 64, "PASS_NO_MATCH")),
            "hardlink": ("LOCAL_VALIDATION_FAILED", RemoteArtifact(True, True, False, 2, 2, "a" * 64, "PASS_NO_MATCH")),
            "hash": ("HASH_MISMATCH", RemoteArtifact(True, True, False, 1, 2, "a" * 64, "PASS_NO_MATCH")),
        }
        for case, (expected, observation) in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary); source = FakeSource(fixture_values())
                source.overrides["codex-exit-code.txt"] = observation
                manifest = self.retain(root, source)
                entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == "codex-exit-code.txt")
                self.assertEqual(entry["retention_status"], expected)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); source = FakeSource(fixture_values())
            source.copy_failures.add("codex-final.json")
            manifest = self.retain(root, source)
            entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == "codex-final.json")
            self.assertEqual(entry["retention_status"], "TRANSFER_FAILED")

    def test_existing_different_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); attempt = root / request_reservation_digest(REQUEST)
            diagnostics = attempt / "diagnostics"; diagnostics.mkdir(mode=0o700)
            occupied = diagnostics / "codex-events.jsonl"; occupied.write_bytes(b"different"); occupied.chmod(0o600)
            manifest = self.retain(root, FakeSource(fixture_values()))
            entry = next(x for x in manifest["artifact_entries"] if x["relative_name"] == "codex-events.jsonl")
            self.assertEqual(entry["retention_status"], "LOCAL_VALIDATION_FAILED")
            self.assertEqual(occupied.read_bytes(), b"different")

    def test_shutdown_boundary_runs_for_success_partial_and_failure(self):
        for result in ("success", "partial", "failure"):
            with self.subTest(result=result):
                shutdown = Mock()
                def retain():
                    if result == "failure": raise PilotRetentionError("synthetic")
                    return {"raw_diagnostic_retention": "PASS" if result == "success" else "PARTIAL"}
                if result == "failure":
                    with self.assertRaises(PilotRetentionError): retention_then_shutdown(retain, shutdown)
                else:
                    retention_then_shutdown(retain, shutdown)
                shutdown.assert_called_once_with()

    def test_manifest_and_fsync_failures_do_not_skip_shutdown(self):
        shutdown = Mock()
        with self.assertRaises(OSError):
            retention_then_shutdown(lambda: (_ for _ in ()).throw(OSError("manifest")), shutdown)
        shutdown.assert_called_once_with()
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary); shutdown = Mock()
            with patch(
                "review_broker.pilot_private_retention._fsync_directory",
                side_effect=OSError("synthetic fsync"),
            ), self.assertRaises(OSError):
                retention_then_shutdown(
                    lambda: self.retain(root, FakeSource(fixture_values())), shutdown,
                )
            shutdown.assert_called_once_with()

    def test_literal_codespace_copy_has_fixed_argv_without_expand(self):
        runner = Mock(return_value=type("Result", (), {"returncode": 0})())
        copier = CodespaceLiteralCopier(
            "review-broker-example", {"codex-final.json": "/fixed/evidence/codex-final.json"},
            runner=runner,
        )
        copier.copy_literal("codex-final.json", Path("/private/controller/final.json"))
        command = runner.call_args.args[0]
        self.assertEqual(command[:5], ["gh", "codespace", "cp", "-c", "review-broker-example"])
        self.assertNotIn("--expand", command)
        self.assertNotIn("-r", command)
        self.assertFalse(runner.call_args.kwargs["shell"])


if __name__ == "__main__":
    unittest.main()
