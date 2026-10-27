"""Offline tests for bounded Codex failure observations."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from review_broker.codex import classify_failure
from review_broker.codexfailure import (
    build_pilot_failure_receipt,
    failure_artifact_manifest,
    observe_codex_failure,
    observe_codex_failure_files,
)
from review_broker.evidence import (
    EvidenceCaptureError,
    credential_material_detected,
    scan_for_credentials,
)


class CodexFailureObservationTests(unittest.TestCase):
    def test_structured_http_error_is_sanitized(self):
        event = {
            "type": "turn.failed",
            "id": "turn-1",
            "error": {
                "type": "invalid_request_error",
                "code": "unsupported_value",
                "message": "raw provider detail must not be retained",
                "param": "model",
            },
            "status": 400,
        }
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(event) + "\n").encode(),
            stderr_bytes=b"",
        )
        self.assertEqual(observation["classification"], "CODEX_PROVIDER_ERROR")
        self.assertEqual(observation["event_stream_status"], "PARSED")
        self.assertEqual(observation["exit_code"], 1)
        self.assertEqual(observation["signal"], "UNDETERMINED")
        self.assertEqual(observation["failure_events"], [{
            "event_index": 0,
            "event_type": "turn.failed",
            "event_id": "UNDETERMINED",
            "category": "invalid_request_error",
            "code": "unsupported_value",
            "http_status": 400,
            "parameter": "model",
        }])
        encoded = json.dumps(observation)
        self.assertNotIn("raw provider detail", encoded)

    def test_application_error_without_http_status_is_distinct(self):
        event = {
            "type": "error",
            "error": {"type": "runtime_error", "code": "worker_failed"},
        }
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(event) + "\n").encode(),
            stderr_bytes=b"",
        )
        self.assertEqual(observation["classification"], "CODEX_APPLICATION_ERROR")
        self.assertEqual(observation["failure_events"][0]["http_status"], "UNDETERMINED")
        self.assertEqual(observation["failure_events"][0]["parameter"], "UNDETERMINED")

    def test_malformed_jsonl_and_bare_exit_are_unclassified(self):
        malformed = observe_codex_failure(
            returncode=1, event_bytes=b'{"type":"error"\n', stderr_bytes=b"",
        )
        self.assertEqual(malformed["classification"], "CODEX_NONZERO_EXIT_UNCLASSIFIED")
        self.assertEqual(malformed["event_stream_status"], "MALFORMED")
        self.assertEqual(malformed["failure_events"], [])

        bare = observe_codex_failure(returncode=1, event_bytes=b"", stderr_bytes=b"")
        self.assertEqual(bare["classification"], "CODEX_NONZERO_EXIT_UNCLASSIFIED")
        self.assertEqual(bare["event_stream_status"], "EMPTY")
        self.assertEqual(classify_failure("process terminated unexpectedly"),
                         "CODEX_FAILURE_UNCLASSIFIED")

    def test_structured_fields_are_type_and_length_bounded(self):
        event = {
            "type": "error",
            "status": "400",
            "error": {"type": "x" * 129, "code": 7, "param": ["model"]},
        }
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(event) + "\n").encode(),
            stderr_bytes=b"",
        )
        structured = observation["failure_events"][0]
        self.assertEqual(structured["category"], "UNDETERMINED")
        self.assertEqual(structured["code"], "UNDETERMINED")
        self.assertEqual(structured["http_status"], "UNDETERMINED")
        self.assertEqual(structured["parameter"], "UNDETERMINED")

    def test_signal_timeout_and_transport_are_distinct(self):
        for returncode, signal in ((-15, 15), (-9, 9), (-11, 11)):
            with self.subTest(returncode=returncode):
                terminated = observe_codex_failure(
                    returncode=returncode, event_bytes=b"", stderr_bytes=b"",
                )
                self.assertEqual(terminated["classification"],
                                 "CODEX_SIGNAL_TERMINATION")
                self.assertEqual(terminated["process_outcome"],
                                 "SIGNAL_TERMINATION")
                self.assertEqual(terminated["exit_code"], "UNDETERMINED")
                self.assertEqual(terminated["signal"], signal)
        bare = observe_codex_failure(returncode=1, event_bytes=b"", stderr_bytes=b"")
        self.assertEqual(bare["classification"], "CODEX_NONZERO_EXIT_UNCLASSIFIED")
        timeout = observe_codex_failure(
            returncode=None, event_bytes=b"", stderr_bytes=b"", transport="TIMEOUT",
        )
        self.assertEqual(timeout["classification"], "CODEX_TIMEOUT_INDETERMINATE")
        transport = observe_codex_failure(
            returncode=None, event_bytes=b"", stderr_bytes=b"", transport="OS_ERROR",
        )
        self.assertEqual(transport["classification"], "CODEX_TRANSPORT_FAILURE")

    def test_free_text_never_establishes_failure_cause(self):
        cases = (
            ({"type": "turn.started", "message": "quota"},
             "CODEX_NONZERO_EXIT_UNCLASSIFIED"),
            ({"type": "turn.failed", "error": {"message": "OAuth expired"}},
             "CODEX_APPLICATION_ERROR"),
            ({"type": "error", "message": "model not supported"},
             "CODEX_APPLICATION_ERROR"),
        )
        for event, expected in cases:
            with self.subTest(event=event):
                observed = observe_codex_failure(
                    returncode=1,
                    event_bytes=(json.dumps(event) + "\n").encode(),
                    stderr_bytes=b"quota model unavailable OAuth expired",
                )
                self.assertEqual(observed["classification"], expected)

        malformed = observe_codex_failure(
            returncode=1,
            event_bytes=b'{"type":"error","message":"quota"}\n{"type":',
            stderr_bytes=b"quota",
        )
        self.assertEqual(malformed["event_stream_status"], "MALFORMED")
        self.assertEqual(malformed["classification"],
                         "CODEX_NONZERO_EXIT_UNCLASSIFIED")

    def test_embedded_json_and_untyped_fields_are_not_promoted(self):
        message = (
            'texte libre {"status":418,"error":'
            '{"type":"fabricated_error"}} suite'
        )
        embedded = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps({
                "type": "turn.failed", "error": {"message": message},
            }) + "\n").encode(),
            stderr_bytes=b"",
        )
        self.assertEqual(embedded["classification"], "CODEX_APPLICATION_ERROR")
        self.assertEqual(embedded["failure_events"][0]["http_status"],
                         "UNDETERMINED")
        self.assertEqual(embedded["failure_events"][0]["category"],
                         "UNDETERMINED")

        wrong_types = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps({
                "type": "error", "status": "400",
                "error": {"type": 7, "code": ["bad"], "param": {}},
            }) + "\n").encode(),
            stderr_bytes=b"",
        )
        self.assertEqual(wrong_types["classification"], "CODEX_APPLICATION_ERROR")
        self.assertTrue(all(
            wrong_types["failure_events"][0][key] == "UNDETERMINED"
            for key in ("category", "code", "http_status", "parameter")
        ))

    def test_truncated_and_contradictory_events_remain_neutral(self):
        truncated = observe_codex_failure(
            returncode=1, event_bytes=b'{"type":"turn.failed"', stderr_bytes=b"",
        )
        self.assertEqual(truncated["event_stream_status"], "MALFORMED")
        self.assertEqual(truncated["classification"],
                         "CODEX_NONZERO_EXIT_UNCLASSIFIED")
        contradictory = observe_codex_failure(
            returncode=1,
            event_bytes=(
                b'{"type":"error","status":400}\n'
                b'{"type":"turn.failed","status":503}\n'
            ),
            stderr_bytes=b"",
        )
        self.assertEqual(contradictory["event_stream_status"], "CONTRADICTORY")
        self.assertEqual(contradictory["classification"],
                         "CODEX_NONZERO_EXIT_UNCLASSIFIED")
        self.assertEqual(contradictory["failure_events"], [])

    def test_file_observation_and_hashing_have_fixed_memory_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "codex-events.jsonl"
            stderr = root / "codex-stderr.txt"
            stderr.write_bytes(b"")
            for size_mib in (8, 32):
                with events.open("wb") as stream:
                    stream.truncate(size_mib * 1024 * 1024)
                tracemalloc.start()
                observed = observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                self.assertEqual(observed["event_stream_status"], "LIMIT_EXCEEDED")
                self.assertEqual(observed["classification"],
                                 "CODEX_NONZERO_EXIT_UNCLASSIFIED")
                self.assertLess(peak, 2 * 1024 * 1024)

            with stderr.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            events.write_bytes(b"")
            tracemalloc.start()
            observed = observe_codex_failure_files(
                returncode=1, events_path=events, stderr_path=stderr,
            )
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(observed["classification"],
                             "CODEX_NONZERO_EXIT_UNCLASSIFIED")
            self.assertLess(peak, 2 * 1024 * 1024)

            with events.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            tracemalloc.start()
            manifest = failure_artifact_manifest(root)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            expected = hashlib.sha256()
            zero_block = b"\0" * 65_536
            for _ in range(32 * 16):
                expected.update(zero_block)
            self.assertEqual(manifest["codex-events.jsonl"]["sha256"],
                             expected.hexdigest())
            self.assertEqual(manifest["codex-events.jsonl"]["byte_length"],
                             32 * 1024 * 1024)
            self.assertLess(peak, 2 * 1024 * 1024)

    def test_file_observation_rejects_limits_aliases_and_nonregular_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stderr = root / "codex-stderr.txt"
            stderr.write_bytes(b"")
            events = root / "codex-events.jsonl"
            events.write_bytes(b"x" * 65_537)
            self.assertEqual(observe_codex_failure_files(
                returncode=1, events_path=events, stderr_path=stderr,
            )["event_stream_status"], "LIMIT_EXCEEDED")

            events.unlink()
            self.assertEqual(observe_codex_failure_files(
                returncode=1, events_path=events, stderr_path=stderr,
            )["event_stream_status"], "UNAVAILABLE")
            self.assertFalse(failure_artifact_manifest(root)[
                "codex-events.jsonl"]["present"])
            target = root / "target"
            target.write_text('{"type":"error","status":400}\n')
            events.symlink_to(target)
            self.assertEqual(observe_codex_failure_files(
                returncode=1, events_path=events, stderr_path=stderr,
            )["event_stream_status"], "UNAVAILABLE")
            self.assertFalse(failure_artifact_manifest(root)[
                "codex-events.jsonl"]["present"])
            events.unlink()
            if hasattr(os, "mkfifo"):
                os.mkfifo(events)
                self.assertEqual(observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )["event_stream_status"], "UNAVAILABLE")
                self.assertFalse(failure_artifact_manifest(root)[
                    "codex-events.jsonl"]["present"])
                events.unlink()
            events.write_text('{"type":"error","status":400}\n')
            entry = failure_artifact_manifest(root)["codex-events.jsonl"]
            self.assertTrue(entry["present"])
            self.assertEqual(entry["sha256"], hashlib.sha256(
                events.read_bytes()
            ).hexdigest())
            with patch(
                "review_broker.codexfailure.observed_regular_file",
                side_effect=OSError("synthetic read error"),
            ):
                self.assertEqual(observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )["event_stream_status"], "UNAVAILABLE")
            with patch(
                "review_broker.codexfailure._hash_regular_file",
                side_effect=OSError("synthetic read error"),
            ):
                self.assertFalse(failure_artifact_manifest(root)[
                    "codex-events.jsonl"]["present"])

    def test_path_swap_to_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "codex-events.jsonl"
            stderr = root / "codex-stderr.txt"
            target = root / "target"
            events.write_text('{"type":"error","status":400}\n')
            target.write_text('{"type":"error","status":503}\n')
            stderr.write_bytes(b"")
            real_open = os.open

            def swap_before_open(path, flags):
                events.unlink()
                events.symlink_to(target)
                return real_open(path, flags)

            with patch("review_broker.fileobservation.os.open",
                       side_effect=swap_before_open):
                observed = observe_codex_failure_files(
                    returncode=1, events_path=events, stderr_path=stderr,
                )
            self.assertEqual(observed["event_stream_status"], "UNAVAILABLE")
            self.assertEqual(observed["classification"],
                             "CODEX_NONZERO_EXIT_UNCLASSIFIED")

    def test_credential_screen_streams_complete_files_across_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            large = root / "large.bin"
            with large.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            tracemalloc.start()
            self.assertEqual(scan_for_credentials(root), [])
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertLess(peak, 2 * 1024 * 1024)

            token = b"Bearer SYNTHETIC00000000000000000000"
            with large.open("r+b") as stream:
                stream.seek(65_530)
                stream.write(token)
            self.assertEqual(scan_for_credentials(root), ["large.bin"])
            with patch(
                "review_broker.evidence.observed_regular_file",
                side_effect=EvidenceCaptureError("synthetic read error"),
            ):
                with self.assertRaisesRegex(
                    EvidenceCaptureError, "CREDENTIAL_SCREENING_UNDETERMINED",
                ):
                    scan_for_credentials(root)

    def test_receipt_rejects_unstructured_observation_mapping(self):
        receipt = build_pilot_failure_receipt(
            request_id="request:sha256:" + "1" * 64,
            attempt_id="attempt:sha256:" + "2" * 64,
            packet_id="packet:sha256:" + "3" * 64,
            classification="CODEX_FAILURE_UNCLASSIFIED",
            failure_observation={"message": "ordinary raw provider detail"},
            credential_screen="PASS_NO_MATCH",
            artifacts={},
        )
        self.assertEqual(receipt["failure_observation"], "UNDETERMINED")
        self.assertNotIn("ordinary raw provider detail", json.dumps(receipt))

    def test_credential_shaped_fields_are_not_copied(self):
        event = {
            "type": "error",
            "id": "Bearer SYNTHETIC00000000000000000000",
            "error": {
                "type": "invalid_request_error",
                "code": "sk-SYNTHETIC00000000000000000000",
                "param": "authorization",
            },
            "status": 401,
        }
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(event) + "\n").encode(),
            stderr_bytes=b"",
        )
        sanitized = observation["failure_events"][0]
        self.assertEqual(sanitized["event_id"], "UNDETERMINED")
        self.assertEqual(sanitized["code"], "UNDETERMINED")
        self.assertFalse(credential_material_detected(observation))


if __name__ == "__main__":
    unittest.main()
