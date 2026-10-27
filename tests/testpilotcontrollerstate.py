"""Adversarial tests for persistent synthetic-pilot controller claims."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from review_broker.pilot_controller_state import (
    ControllerClaimError,
    arm_controller_attempt,
    read_controller_claim,
    request_reservation_digest,
)

REQUEST = "request:sha256:" + "1" * 64
ATTEMPT = "attempt:sha256:" + "2" * 64
SOURCE = "3" * 40


class ControllerClaimTests(unittest.TestCase):
    def arm(self, root: Path, *, request: str = REQUEST, attempt: str = ATTEMPT):
        return arm_controller_attempt(
            pilot_id="RB-PILOT-EXAMPLE", request_id=request,
            attempt_id=attempt, source_sha=SOURCE, _state_root=root,
            _created_utc="2026-10-28T00:00:00+00:00",
        )

    def test_first_arm_is_private_canonical_and_durable_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"
            value = self.arm(root)
            claim = root / request_reservation_digest(REQUEST) / "controller-claim.json"
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(claim.stat().st_mode), 0o600)
            self.assertEqual(json.loads(claim.read_text()), value)
            self.assertEqual(read_controller_claim(REQUEST, _state_root=root), value)
            # Remote /tmp disappearance cannot affect the persistent controller root.
            remote = Path(temporary) / "remote-tmp"
            remote.mkdir(); remote.rmdir()
            with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_ATTEMPT_ALREADY_ARMED"):
                self.arm(root)

    def test_same_request_refuses_same_or_different_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"; self.arm(root)
            for attempt in (ATTEMPT, "attempt:sha256:" + "4" * 64):
                with self.subTest(attempt=attempt), self.assertRaisesRegex(
                    ControllerClaimError, "CONTROLLER_ATTEMPT_ALREADY_ARMED",
                ):
                    self.arm(root, attempt=attempt)

    def test_distinct_request_gets_distinct_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"; self.arm(root)
            other = "request:sha256:" + "5" * 64
            self.arm(root, request=other, attempt="attempt:sha256:" + "6" * 64)
            self.assertNotEqual(request_reservation_digest(REQUEST), request_reservation_digest(other))

    def test_invalid_identity_is_rejected_without_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"
            with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_ATTEMPT_IDENTITY_INVALID"):
                self.arm(root, request="invalid")
            self.assertFalse(root.exists())

    def test_malformed_truncated_alias_nonregular_and_mode_are_unavailable(self):
        cases = ("truncated", "malformed", "symlink", "directory", "mode")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "pilots"; root.mkdir(mode=0o700)
                reservation = root / request_reservation_digest(REQUEST)
                reservation.mkdir(mode=0o700); claim = reservation / "controller-claim.json"
                if case == "truncated": claim.write_bytes(b"")
                elif case == "malformed": claim.write_text("{")
                elif case == "symlink": claim.symlink_to(Path(temporary) / "outside")
                elif case == "directory": claim.mkdir()
                else: claim.write_text("{}")
                if claim.is_file() and not claim.is_symlink(): claim.chmod(0o644 if case == "mode" else 0o600)
                with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_CLAIM_UNAVAILABLE"):
                    self.arm(root)

    def test_untrusted_root_alias_and_mode_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); real = base / "real"; real.mkdir(mode=0o700)
            alias = base / "alias"; alias.symlink_to(real)
            with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_STATE_ROOT_UNTRUSTED"):
                self.arm(alias)
            weak = base / "weak"; weak.mkdir(mode=0o755)
            with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_STATE_ROOT_UNTRUSTED"):
                self.arm(weak)

    def test_write_and_fsync_failures_never_report_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"
            with patch("review_broker.pilot_controller_state.os.open", side_effect=OSError("synthetic")):
                with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_CLAIM_WRITE_FAILED"):
                    self.arm(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"
            with patch("review_broker.pilot_controller_state.os.fsync", side_effect=OSError("synthetic")):
                with self.assertRaisesRegex(ControllerClaimError, "CONTROLLER_CLAIM_WRITE_FAILED"):
                    self.arm(root)

    def test_concurrent_arm_has_one_success_and_one_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilots"; barrier = threading.Barrier(2)
            outcomes: list[str] = []
            def worker():
                barrier.wait()
                try: self.arm(root)
                except ControllerClaimError as exc: outcomes.append(str(exc))
                else: outcomes.append("SUCCESS")
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertEqual(outcomes.count("SUCCESS"), 1)
            self.assertEqual(len(outcomes), 2)
            self.assertIn(outcomes[0] if outcomes[0] != "SUCCESS" else outcomes[1], {
                "CONTROLLER_ATTEMPT_ALREADY_ARMED", "CONTROLLER_CLAIM_UNAVAILABLE",
            })


if __name__ == "__main__":
    unittest.main()
