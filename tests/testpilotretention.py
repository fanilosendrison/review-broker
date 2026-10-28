"""Offline adversarial tests for private synthetic-pilot retention."""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from review_broker.codexfailure import build_pilot_failure_receipt
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
PACKET = "packet:sha256:" + "4" * 64
SOURCE = "3" * 40
WHEEL = "5" * 64
PILOT = "RB-PILOT-EXAMPLE"
ARMED_UTC = "2026-10-28T00:00:00+00:00"

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
        destination.write_bytes(self.values[name])
        destination.chmod(0o600)

def _encoded(value: dict) -> bytes:
    return canonical_bytes(value) + b"\n"

def valid_receipts(*, outcome: str = "FAIL", screen: str = "PASS_NO_MATCH") -> dict[str, bytes]:
    remote_claim = {
        "schema_version": 1,
        "pilot_id": PILOT,
        "request_id": REQUEST,
        "attempt_id": ATTEMPT,
        "packet_id": PACKET,
        "status": "ARMED",
        "armed_utc": ARMED_UTC,
    }
    armed = {
        "schema_version": 1,
        "scope": "SYNTHETIC_NONPRODUCTION_ONLY",
        "issue": 26,
        "request_id": REQUEST,
        "attempt_id": ATTEMPT,
        "packet_id": PACKET,
        "broker_wheel_sha256": WHEEL,
        "acknowledged_residual_risk": True,
        "armed_utc": ARMED_UTC,
    }
    summary = {
        "schema_version": 1,
        "scope": "SYNTHETIC_NONPRODUCTION_ONLY",
        "issue": 26,
        "pilot_id": PILOT,
        "request_id": REQUEST,
        "attempt_id": ATTEMPT,
        "packet_id": PACKET,
        "broker_wheel_sha256": WHEEL,
        "model_requested": "gpt-5.6-sol",
        "effort_requested": "xhigh",
        "pilot_functional": outcome,
        "pilot_execution": "COMPLETED" if outcome == "PASS" else "FAILED",
        "credential_screen": screen,
        "pilot_security_qualified": False,
        "production_security_qualified": False,
        "github_publication": "NONE",
        "reviewer_authority": "NONE",
    }
    values = {
        "pilot-claim.json": _encoded(remote_claim),
        "pilot-armed.json": _encoded(armed),
        "codex-events.jsonl": b'{"type":"turn.failed"}\n',
        "codex-stderr.txt": b"synthetic diagnostic\n",
        "codex-final.json": b"",
        "codex-exit-code.txt": b"1\n",
    }
    if outcome == "PASS":
        summary.update({"schema_and_citations": "PASS", "verdict": "NO_GO"})
    else:
        summary["failure"] = "CODEX_APPLICATION_ERROR"
        failure = build_pilot_failure_receipt(
            request_id=REQUEST,
            attempt_id=ATTEMPT,
            packet_id=PACKET,
            classification=summary["failure"],
            failure_observation=None,
            credential_screen=screen,
            artifacts={},
        )
        failure.update({
            "pilot_id": PILOT,
            "broker_wheel_sha256": WHEEL,
            "model_requested": "gpt-5.6-sol",
            "effort_requested": "xhigh",
            "pilot_security_qualified": False,
            "production_security_qualified": False,
        })
        failure_bytes = _encoded(failure)
        summary["failure_receipt_sha256"] = hashlib.sha256(failure_bytes).hexdigest()
        values["pilot-failure.json"] = failure_bytes
    values["pilot-summary.json"] = _encoded(summary)
    return values

def mutate_json(values: dict[str, bytes], name: str, mutation, *replacement) -> None:
    import json
    value = json.loads(values[name])
    if replacement:
        value[mutation] = replacement[0]
    else:
        mutation(value)
    values[name] = _encoded(value)

class PrivateRetentionTests(unittest.TestCase):
    def prepare(self, temporary: str) -> Path:
        root = Path(temporary).resolve() / "pilots"
        arm_controller_attempt(
            pilot_id=PILOT,
            request_id=REQUEST,
            attempt_id=ATTEMPT,
            source_sha=SOURCE,
            _state_root=root,
            _created_utc=ARMED_UTC,
        )
        return root

    def retain(self, root: Path, source: FakeSource):
        return retain_private_pilot_artifacts(
            pilot_id=PILOT,
            request_id=REQUEST,
            attempt_id=ATTEMPT,
            source_sha=SOURCE,
            source=source,
            _state_root=root,
            _retained_at="2026-10-28T00:01:00+00:00",
        )

    def assert_no_raw_copy(self, source: FakeSource) -> None:
        self.assertFalse(set(source.copies) & set(DIAGNOSTIC_LIMITS))

    def test_valid_success_and_failure_receipts_are_accepted(self):
        for outcome in ("PASS", "FAIL"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                source = FakeSource(valid_receipts(outcome=outcome))
                manifest = self.retain(root, source)
                self.assertEqual(manifest["sanitized_receipt_retention"], "PASS")
                self.assertEqual(manifest["raw_diagnostic_retention"], "PASS")
                self.assertEqual(manifest["receipt_set_validation"], "RECEIPT_SET_VALID")
                self.assertTrue(set(DIAGNOSTIC_LIMITS) <= set(source.copies))

    def test_complete_private_retention_survives_remote_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            source = FakeSource(valid_receipts())
            manifest = self.retain(root, source)
            attempt = root / request_reservation_digest(REQUEST)
            self.assertEqual(stat.S_IMODE(attempt.stat().st_mode), 0o700)
            for directory in (attempt / "receipts", attempt / "diagnostics"):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
                for path in directory.iterdir():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            retained = [entry for entry in manifest["artifact_entries"] if entry["retained_local"]]
            source.values.clear()
            for entry in retained:
                directory = "receipts" if entry["relative_name"].startswith("pilot-") else "diagnostics"
                path = attempt / directory / entry["relative_name"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])

    def test_original_summary_counterexamples_never_copy_raw(self):
        cases = {
            "minimal": lambda values: values.__setitem__(
                "pilot-summary.json",
                _encoded({
                    "request_id": REQUEST,
                    "attempt_id": ATTEMPT,
                    "credential_screen": "PASS_NO_MATCH",
                }),
            ),
            "wrong-packet": lambda values: mutate_json(
                values, "pilot-summary.json",
                lambda summary: summary.__setitem__("packet_id", "packet:sha256:" + "9" * 64),
            ),
            "quarantine-contradiction": lambda values: mutate_json(
                values, "pilot-summary.json",
                lambda summary: summary.__setitem__("failure", "PILOT_QUARANTINE_FAILED"),
            ),
            "missing": lambda values: values.pop("pilot-summary.json"),
            "malformed": lambda values: values.__setitem__("pilot-summary.json", b"{"),
        }
        for name, mutation in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                values = valid_receipts()
                mutation(values)
                source = FakeSource(values)
                manifest = self.retain(root, source)
                self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
                self.assertEqual(manifest["receipt_set_validation"], "RECEIPT_SET_INVALID")
                self.assert_no_raw_copy(source)

    def test_incoherent_receipt_sets_never_report_pass_or_copy_raw(self):
        cases = {
            "claim-request": ("pilot-claim.json", lambda value: value.__setitem__("request_id", "request:sha256:" + "8" * 64)),
            "armed-attempt": ("pilot-armed.json", lambda value: value.__setitem__("attempt_id", "attempt:sha256:" + "8" * 64)),
            "claim-empty": ("pilot-claim.json", None),
            "armed-empty": ("pilot-armed.json", None),
            "failure-incoherent": ("pilot-failure.json", lambda value: value.__setitem__("classification", "OTHER_FAILURE")),
            "failure-digest": ("pilot-summary.json", lambda value: value.__setitem__("failure_receipt_sha256", "9" * 64)),
        }
        for name, (receipt, mutation) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                values = valid_receipts()
                if mutation is None:
                    values[receipt] = b""
                else:
                    mutate_json(values, receipt, mutation)
                source = FakeSource(values)
                manifest = self.retain(root, source)
                self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
                self.assert_no_raw_copy(source)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            values = valid_receipts()
            values.pop("pilot-failure.json")
            source = FakeSource(values)
            manifest = self.retain(root, source)
            self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
            self.assert_no_raw_copy(source)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            values = valid_receipts(outcome="PASS")
            values["pilot-failure.json"] = valid_receipts()["pilot-failure.json"]
            source = FakeSource(values)
            manifest = self.retain(root, source)
            self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
            self.assert_no_raw_copy(source)

    def test_stale_valid_local_receipts_do_not_hide_current_transfer_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            values = valid_receipts()
            attempt = root / request_reservation_digest(REQUEST)
            receipts = attempt / "receipts"
            receipts.mkdir(mode=0o700)
            for name in ("pilot-claim.json", "pilot-armed.json", "pilot-summary.json", "pilot-failure.json"):
                path = receipts / name
                path.write_bytes(values[name])
                path.chmod(0o600)
            source = FakeSource(values)
            source.copy_failures.update(("pilot-claim.json", "pilot-armed.json", "pilot-summary.json", "pilot-failure.json"))
            manifest = self.retain(root, source)
            self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
            self.assert_no_raw_copy(source)

    def test_summary_screen_blocks_all_raw_diagnostics(self):
        for screen in ("UNDETERMINED", "CONTAMINATED_QUARANTINED"):
            with self.subTest(screen=screen), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                source = FakeSource(valid_receipts(screen=screen))
                manifest = self.retain(root, source)
                self.assertEqual(manifest["raw_diagnostic_retention"], "SKIPPED_QUARANTINED")
                self.assert_no_raw_copy(source)

    def test_remote_and_local_credential_detection_refuse_raw_copy(self):
        for screen, expected in (("CONTAMINATED", "REFUSED_CONTAMINATED"), ("UNDETERMINED", "REFUSED_SCREEN_UNDETERMINED")):
            with self.subTest(screen=screen), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                source = FakeSource(valid_receipts())
                observed = source.observe("codex-stderr.txt")
                source.overrides["codex-stderr.txt"] = RemoteArtifact(
                    True, True, False, 1, observed.byte_length, observed.sha256, screen,
                )
                manifest = self.retain(root, source)
                entry = next(item for item in manifest["artifact_entries"] if item["relative_name"] == "codex-stderr.txt")
                self.assertEqual(entry["retention_status"], expected)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            values = valid_receipts()
            values["codex-stderr.txt"] = b"Authorization: Bearer synthetic-secret-material"
            manifest = self.retain(root, FakeSource(values))
            attempt = root / request_reservation_digest(REQUEST)
            self.assertFalse((attempt / "diagnostics/codex-stderr.txt").exists())
            entry = next(item for item in manifest["artifact_entries"] if item["relative_name"] == "codex-stderr.txt")
            self.assertEqual(entry["retention_status"], "REFUSED_CONTAMINATED")

    def test_oversize_alias_hardlink_hash_and_transfer_failures_are_distinct(self):
        cases = {
            "oversize": ("REFUSED_OVERSIZED", RemoteArtifact(True, True, False, 1, 65, "a" * 64, "PASS_NO_MATCH")),
            "symlink": ("LOCAL_VALIDATION_FAILED", RemoteArtifact(True, False, True, 1, 2, "a" * 64, "PASS_NO_MATCH")),
            "hardlink": ("LOCAL_VALIDATION_FAILED", RemoteArtifact(True, True, False, 2, 2, "a" * 64, "PASS_NO_MATCH")),
            "hash": ("HASH_MISMATCH", RemoteArtifact(True, True, False, 1, 2, "a" * 64, "PASS_NO_MATCH")),
        }
        for name, (expected, observation) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self.prepare(temporary)
                source = FakeSource(valid_receipts())
                source.overrides["codex-exit-code.txt"] = observation
                manifest = self.retain(root, source)
                entry = next(item for item in manifest["artifact_entries"] if item["relative_name"] == "codex-exit-code.txt")
                self.assertEqual(entry["retention_status"], expected)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            source = FakeSource(valid_receipts())
            source.copy_failures.add("codex-final.json")
            manifest = self.retain(root, source)
            entry = next(item for item in manifest["artifact_entries"] if item["relative_name"] == "codex-final.json")
            self.assertEqual(entry["retention_status"], "TRANSFER_FAILED")

    def test_existing_different_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            attempt = root / request_reservation_digest(REQUEST)
            diagnostics = attempt / "diagnostics"
            diagnostics.mkdir(mode=0o700)
            occupied = diagnostics / "codex-events.jsonl"
            occupied.write_bytes(b"different")
            occupied.chmod(0o600)
            manifest = self.retain(root, FakeSource(valid_receipts()))
            entry = next(item for item in manifest["artifact_entries"] if item["relative_name"] == "codex-events.jsonl")
            self.assertEqual(entry["retention_status"], "LOCAL_VALIDATION_FAILED")
            self.assertEqual(occupied.read_bytes(), b"different")

    def test_shutdown_boundary_runs_for_success_partial_and_failure(self):
        for result in ("success", "partial", "failure"):
            with self.subTest(result=result):
                shutdown = Mock()
                def retain():
                    if result == "failure":
                        raise PilotRetentionError("synthetic")
                    return {"raw_diagnostic_retention": "PASS" if result == "success" else "PARTIAL"}
                if result == "failure":
                    with self.assertRaises(PilotRetentionError):
                        retention_then_shutdown(retain, shutdown)
                else:
                    retention_then_shutdown(retain, shutdown)
                shutdown.assert_called_once_with()

    def test_manifest_and_fsync_failures_do_not_skip_shutdown(self):
        shutdown = Mock()
        with self.assertRaises(OSError):
            retention_then_shutdown(lambda: (_ for _ in ()).throw(OSError("manifest")), shutdown)
        shutdown.assert_called_once_with()
        with tempfile.TemporaryDirectory() as temporary:
            root = self.prepare(temporary)
            shutdown = Mock()
            with patch("review_broker.pilot_private_retention._fsync_directory", side_effect=OSError("synthetic")), self.assertRaises(OSError):
                retention_then_shutdown(lambda: self.retain(root, FakeSource(valid_receipts())), shutdown)
            shutdown.assert_called_once_with()

    def test_literal_codespace_copy_has_fixed_argv_without_expand(self):
        runner = Mock(return_value=type("Result", (), {"returncode": 0})())
        copier = CodespaceLiteralCopier(
            "review-broker-example",
            {"codex-final.json": "/fixed/evidence/codex-final.json"},
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
