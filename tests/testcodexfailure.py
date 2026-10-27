"""Offline tests for bounded Codex failure observations."""
from __future__ import annotations

import json
import unittest

from review_broker.codex import classify_failure
from review_broker.codexfailure import (
    build_pilot_failure_receipt,
    observe_codex_failure,
)
from review_broker.evidence import credential_material_detected


class CodexFailureObservationTests(unittest.TestCase):
    def test_structured_http_error_is_sanitized(self):
        nested = {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "code": "unsupported_value",
                "message": "raw provider detail must not be retained",
                "param": "model",
            },
            "status": 400,
        }
        events = [{
            "type": "turn.failed",
            "id": "turn-1",
            "error": {"message": "unexpected status 400: " + json.dumps(nested) + ", endpoint omitted"},
        }]
        observation = observe_codex_failure(
            returncode=1,
            event_bytes=(json.dumps(events[0]) + "\n").encode(),
            stderr_bytes=b"",
        )
        self.assertEqual(observation["classification"], "CODEX_PROVIDER_ERROR")
        self.assertEqual(observation["event_stream_status"], "PARSED")
        self.assertEqual(observation["exit_code"], 1)
        self.assertEqual(observation["signal"], "UNDETERMINED")
        self.assertEqual(observation["failure_events"], [{
            "event_index": 0,
            "event_type": "turn.failed",
            "event_id": "turn-1",
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

    def test_native_signal_timeout_and_transport_are_distinct(self):
        native = observe_codex_failure(returncode=-11, event_bytes=b"", stderr_bytes=b"")
        self.assertEqual(native["classification"], "CODEX_NATIVE_CRASH")
        self.assertEqual(native["signal"], 11)
        timeout = observe_codex_failure(
            returncode=None, event_bytes=b"", stderr_bytes=b"", transport="TIMEOUT",
        )
        self.assertEqual(timeout["classification"], "CODEX_TIMEOUT_INDETERMINATE")
        transport = observe_codex_failure(
            returncode=None, event_bytes=b"", stderr_bytes=b"", transport="OS_ERROR",
        )
        self.assertEqual(transport["classification"], "CODEX_TRANSPORT_FAILURE")

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
