"""Read-only pilot identity isolation and physical Codespace overlap bounds.

Exercises actual pilot identity and authorization code, never actual pilot
transport or Codex. This does not qualify v3 worker/fencing or a resource
lease shared between manually invoked pilots and Actions workflows.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from review_broker.identity import attempt_identity
from review_broker.pilot03_authorization import (
    ExecutionAuthorization, ExecutionAuthorizationError,
)
from review_broker.pilot03_controller import (
    pilot03_identities, run_pilot03_controller,
)
from review_broker.pilot04_controller import pilot04_identities
from review_broker.pilot05_controller import pilot05_identities


class NoRemoteTransport:
    def __init__(self):
        self.prepares = 0
    def prepare(self):
        self.prepares += 1
        raise AssertionError("NO_REAL_TRANSPORT_MUST_RUN")


class PilotLogicalIsolationTests(unittest.TestCase):
    def test_p01_fixed_pilot_request_ids_are_distinct_and_reproducible(self):
        results=[fn() for fn in
                 (pilot03_identities,pilot04_identities,pilot05_identities)]
        self.assertEqual(len(set(x[0] for x in results)),3)
        for fn, (request,attempt) in zip(
                (pilot03_identities,pilot04_identities,pilot05_identities),results):
            with self.subTest(pilot=fn.__name__):
                self.assertEqual(fn(),(request,attempt))
                self.assertEqual(attempt,attempt_identity(request,1))
                self.assertTrue(request.startswith("request:sha256:"))

    def test_p02_mismatched_arbitrary_v3_request_refused_before_transport(self):
        expected_request,expected_attempt=pilot03_identities()
        with tempfile.TemporaryDirectory(prefix="rb-pilot-route-test-") as tmp:
            wheel=Path(tmp)/"dummy.whl"
            wheel.write_bytes(b"qualification-only-wheel")
            digest=sha256(wheel.read_bytes()).hexdigest()
            transport=NoRemoteTransport()
            foreign_request="request:sha256:"+"f"*64
            self.assertNotEqual(foreign_request,expected_request)
            authorization=ExecutionAuthorization(
                pilot_id="RB-PILOT-03",
                request_id=foreign_request,
                attempt_id=expected_attempt,
                review_broker_source_sha="a"*40,
                broker_wheel_sha256=digest,
                codespace_identity="review-broker-reviewer-4q4v769jr65hjww9",
            )
            with self.assertRaises(ExecutionAuthorizationError):
                run_pilot03_controller(
                    authorization=authorization,
                    source_sha="a"*40,
                    wheel_path=wheel,
                    codespace_identity="review-broker-reviewer-4q4v769jr65hjww9",
                    transport=transport,
                )
            self.assertEqual(transport.prepares,0)

    def test_p03_pilot_authorization_does_not_force_separate_physical_codespace(self):
        request,attempt=pilot03_identities()
        value={
            "schema_version":1,
            "pilot_id":"RB-PILOT-03",
            "request_id":request,
            "attempt_id":attempt,
            "review_broker_source_sha":"a"*40,
            "broker_wheel_sha256":"b"*64,
            "codespace_identity":"review-broker-reviewer-4q4v769jr65hjww9",
        }
        obj=ExecutionAuthorization.from_mapping(value)
        self.assertEqual(obj.codespace_identity,value["codespace_identity"])
        # This is the same literal as the independent control-qualification
        # workflow; main review's configured name remains unread/unverified.

    def test_p04_pilot_consent_is_not_a_v3_journal_side_effect_guard(self):
        source=(Path(__file__).resolve().parents[1]/
                "src/review_broker/pilot03_authorization.py").read_text()
        self.assertIn("authorization.require_matches",(
            Path(__file__).resolve().parents[1]/
            "src/review_broker/pilot03_controller.py").read_text())
        self.assertNotIn("pre_model_control",source)
        self.assertNotIn("PREPARED",source)
        # Pilot fixed logical request IDs are a useful disjoint namespace.
        # They do NOT prove exclusive ownership of a named Codespace.


if __name__=="__main__":
    unittest.main()
