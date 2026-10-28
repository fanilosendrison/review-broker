"""Offline controller integration tests for claim, retention, replay, and Shutdown."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.cli import main
from review_broker.codexfailure import build_pilot_failure_receipt
from review_broker.identity import canonical_bytes
from review_broker.pilot03_authorization import ExecutionAuthorization, ExecutionAuthorizationError, load_execution_authorization
from review_broker.pilot03_controller import pilot03_identities, run_pilot03_controller
from review_broker.pilot_private_retention import RemoteArtifact

SOURCE = "6" * 40
PACKET = "packet:sha256:" + "7" * 64
WHEEL_DIGEST = hashlib.sha256(b"wheel").hexdigest()
ARMED = "2026-10-28T00:00:00+00:00"


def encoded(value):
    return canonical_bytes(value) + b"\n"


class Source:
    def __init__(self, request, attempt):
        claim = {"schema_version": 1, "pilot_id": "RB-PILOT-03", "request_id": request,
                 "attempt_id": attempt, "packet_id": PACKET, "status": "ARMED", "armed_utc": ARMED}
        armed = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
                 "request_id": request, "attempt_id": attempt, "packet_id": PACKET,
                 "broker_wheel_sha256": WHEEL_DIGEST, "acknowledged_residual_risk": True,
                 "armed_utc": ARMED}
        failure = build_pilot_failure_receipt(
            request_id=request, attempt_id=attempt, packet_id=PACKET,
            classification="CODEX_APPLICATION_ERROR", failure_observation=None,
            credential_screen="PASS_NO_MATCH", artifacts={},
        )
        failure.update({"pilot_id": "RB-PILOT-03", "broker_wheel_sha256": WHEEL_DIGEST,
                        "model_requested": "gpt-5.6-sol", "effort_requested": "xhigh",
                        "pilot_security_qualified": False, "production_security_qualified": False})
        failure_bytes = encoded(failure)
        summary = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
                   "pilot_id": "RB-PILOT-03", "request_id": request, "attempt_id": attempt,
                   "packet_id": PACKET, "broker_wheel_sha256": WHEEL_DIGEST,
                   "model_requested": "gpt-5.6-sol", "effort_requested": "xhigh",
                   "pilot_functional": "FAIL", "pilot_execution": "FAILED",
                   "credential_screen": "PASS_NO_MATCH", "failure": "CODEX_APPLICATION_ERROR",
                   "failure_receipt_sha256": hashlib.sha256(failure_bytes).hexdigest(),
                   "pilot_security_qualified": False, "production_security_qualified": False,
                   "github_publication": "NONE", "reviewer_authority": "NONE"}
        self.values = {"pilot-claim.json": encoded(claim), "pilot-armed.json": encoded(armed),
                       "pilot-summary.json": encoded(summary), "pilot-failure.json": failure_bytes,
                       "codex-events.jsonl": b'{"type":"turn.failed"}\n',
                       "codex-stderr.txt": b"safe failure\n", "codex-final.json": b"",
                       "codex-exit-code.txt": b"1\n"}

    def observe(self, name):
        data = self.values.get(name)
        if data is None:
            return RemoteArtifact(False)
        return RemoteArtifact(True, True, False, 1, len(data), hashlib.sha256(data).hexdigest(), "PASS_NO_MATCH")

    def copy_literal(self, name, destination):
        destination.write_bytes(self.values[name]); destination.chmod(0o600)


class Transport:
    def __init__(self, request, attempt):
        self.artifact_source = Source(request, attempt)
        self.emissions = 0; self.stops = 0
    def prepare(self): pass
    def preflight(self, **_kwargs): pass
    def emit_once(self, **_kwargs): self.emissions += 1; return 1
    def shutdown(self): self.stops += 1
    def shutdown_observed(self): return True


class Pilot03ControllerTests(unittest.TestCase):
    def test_cli_denies_absent_authorization_before_transport(self):
        arguments = ["pilot-synthetic-03-controller", "--source-sha", SOURCE,
                     "--broker-wheel", "/missing.whl", "--codespace", "space",
                     "--ssh-config", "/missing.conf"]
        with patch("review_broker.cli.Pilot03CodespaceTransport") as transport:
            self.assertEqual(main(arguments), 1)
        transport.assert_not_called()

    def test_authorization_absent_and_mismatch_refuse_before_transport(self):
        with self.assertRaisesRegex(ExecutionAuthorizationError, "DENIED"):
            load_execution_authorization(None)
        request, attempt = pilot03_identities()
        authorization = ExecutionAuthorization("RB-PILOT-03", request, attempt, SOURCE, WHEEL_DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "wheel.whl"; wheel.write_bytes(b"other")
            transport = Transport(request, attempt)
            with self.assertRaisesRegex(ExecutionAuthorizationError, "MISMATCH"):
                run_pilot03_controller(authorization=authorization, source_sha=SOURCE,
                    wheel_path=wheel, codespace_identity="space", transport=transport,
                    _state_root=Path(temporary) / "state")
            self.assertEqual(transport.emissions, 0)

    def test_prepare_failure_still_crosses_shutdown_boundary(self):
        request, attempt = pilot03_identities()
        authorization = ExecutionAuthorization("RB-PILOT-03", request, attempt, SOURCE, WHEEL_DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(b"wheel")
            transport = Transport(request, attempt)
            transport.prepare = lambda: (_ for _ in ()).throw(RuntimeError("PREPARE_FAILED"))
            report = run_pilot03_controller(authorization=authorization, source_sha=SOURCE,
                wheel_path=wheel, codespace_identity="space", transport=transport,
                _state_root=root / "state")
            self.assertEqual(report["remote_command_emissions"], 0)
            self.assertEqual(report["codespace_shutdown"], "OBSERVED")
            self.assertEqual(transport.stops, 1)

    def test_valid_failure_retains_diagnostics_once_and_observes_shutdown(self):
        request, attempt = pilot03_identities()
        authorization = ExecutionAuthorization("RB-PILOT-03", request, attempt, SOURCE, WHEEL_DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(b"wheel")
            transport = Transport(request, attempt)
            report = run_pilot03_controller(authorization=authorization, source_sha=SOURCE,
                wheel_path=wheel, codespace_identity="space", transport=transport,
                _state_root=root / "state")
            self.assertEqual(report["pilot_functional"], "FAIL")
            self.assertEqual(report["sanitized_receipt_retention"], "PASS")
            self.assertEqual(report["raw_diagnostic_retention"], "PASS")
            self.assertEqual(report["codespace_shutdown"], "OBSERVED")
            self.assertEqual((transport.emissions, report["automatic_retries"]), (1, 0))
            replay = Transport(request, attempt)
            second = run_pilot03_controller(authorization=authorization, source_sha=SOURCE,
                wheel_path=wheel, codespace_identity="space", transport=replay,
                _state_root=root / "state")
            self.assertEqual(replay.emissions, 0)
            self.assertIn("CONTROLLER_ATTEMPT_ALREADY_ARMED", second["controller_error"])
            self.assertEqual(replay.stops, 1)
