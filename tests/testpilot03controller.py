"""Offline controller tests for R03 truth, recovery, replay, and Shutdown."""
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
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
WHEEL_BYTES = b"wheel"
WHEEL_DIGEST = hashlib.sha256(WHEEL_BYTES).hexdigest()
ARMED = "2026-10-28T00:00:00+00:00"


def encoded(value):
    return canonical_bytes(value) + b"\n"


def receipt_values(request, attempt, outcome="FAIL"):
    claim = {"schema_version": 1, "pilot_id": "RB-PILOT-03", "request_id": request,
             "attempt_id": attempt, "packet_id": PACKET, "status": "ARMED", "armed_utc": ARMED}
    armed = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
             "request_id": request, "attempt_id": attempt, "packet_id": PACKET,
             "broker_wheel_sha256": WHEEL_DIGEST, "acknowledged_residual_risk": True,
             "armed_utc": ARMED}
    summary = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
               "pilot_id": "RB-PILOT-03", "request_id": request, "attempt_id": attempt,
               "packet_id": PACKET, "broker_wheel_sha256": WHEEL_DIGEST,
               "model_requested": "gpt-5.6-sol", "effort_requested": "xhigh",
               "pilot_functional": outcome, "pilot_execution": "COMPLETED" if outcome == "PASS" else "FAILED",
               "credential_screen": "PASS_NO_MATCH", "pilot_security_qualified": False,
               "production_security_qualified": False, "github_publication": "NONE",
               "reviewer_authority": "NONE"}
    values = {"pilot-claim.json": encoded(claim), "pilot-armed.json": encoded(armed),
              "codex-events.jsonl": b'{"type":"turn.failed"}\n',
              "codex-stderr.txt": b"safe failure\n", "codex-final.json": b"",
              "codex-exit-code.txt": b"0\n" if outcome == "PASS" else b"1\n"}
    if outcome == "PASS":
        summary.update({"schema_and_citations": "PASS", "verdict": "NO_GO"})
    else:
        summary["failure"] = "CODEX_APPLICATION_ERROR"
        failure = build_pilot_failure_receipt(
            request_id=request, attempt_id=attempt, packet_id=PACKET,
            classification=summary["failure"], failure_observation=None,
            credential_screen="PASS_NO_MATCH", artifacts={},
        )
        failure.update({"pilot_id": "RB-PILOT-03", "broker_wheel_sha256": WHEEL_DIGEST,
                        "model_requested": "gpt-5.6-sol", "effort_requested": "xhigh",
                        "pilot_security_qualified": False, "production_security_qualified": False})
        failure_bytes = encoded(failure)
        summary["failure_receipt_sha256"] = hashlib.sha256(failure_bytes).hexdigest()
        values["pilot-failure.json"] = failure_bytes
    values["pilot-summary.json"] = encoded(summary)
    return values


class Source:
    def __init__(self, values, *, copy_failure=False):
        self.values = dict(values); self.copy_failure = copy_failure
        self.observations = 0; self.copies = 0

    def observe(self, name):
        self.observations += 1
        data = self.values.get(name)
        if data is None:
            return RemoteArtifact(False)
        return RemoteArtifact(True, True, False, 1, len(data), hashlib.sha256(data).hexdigest(), "PASS_NO_MATCH")

    def copy_literal(self, name, destination):
        self.copies += 1
        if self.copy_failure:
            raise OSError("synthetic copy failure")
        destination.write_bytes(self.values[name]); destination.chmod(0o600)


class Transport:
    def __init__(self, source, *, result=1, emit_error=None, shutdown_observed=True, preflight_error=None):
        self.artifact_source = source; self.result = result; self.emit_error = emit_error
        self.observed = shutdown_observed; self.preflight_error = preflight_error
        self.emissions = 0; self.stops = 0; self.preflights = 0

    def prepare(self): pass
    def preflight(self, **_kwargs):
        self.preflights += 1
        if self.preflight_error: raise self.preflight_error
    def emit_once(self, **_kwargs):
        self.emissions += 1
        if self.emit_error: raise self.emit_error
        return self.result
    def shutdown(self): self.stops += 1
    def shutdown_observed(self): return self.observed


class Pilot03ControllerTests(unittest.TestCase):
    def setUp(self):
        self.request, self.attempt = pilot03_identities()
        self.authorization = ExecutionAuthorization(
            "RB-PILOT-03", self.request, self.attempt, SOURCE, WHEEL_DIGEST, "space",
        )

    def run_controller(self, temporary, transport, name="case"):
        root = Path(temporary); wheel = root / f"{name}.whl"; wheel.write_bytes(WHEEL_BYTES)
        report = run_pilot03_controller(
            authorization=self.authorization, source_sha=SOURCE, wheel_path=wheel,
            codespace_identity="space", transport=transport, _state_root=root / f"state-{name}",
        )
        with patch("review_broker.cli.load_execution_authorization", return_value=self.authorization), patch(
            "review_broker.cli.Pilot03CodespaceTransport", return_value=transport,
        ), patch("review_broker.cli.run_pilot03_controller", return_value=report), contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(["pilot-synthetic-03-controller", "--execution-authorization", "/fixture",
                              "--source-sha", SOURCE, "--broker-wheel", str(wheel),
                              "--codespace", "space", "--ssh-config", "/fixture",
                              "--ssh-host-alias", "independent-host-alias"])
        return report, exit_code

    def test_cli_denies_absent_authorization_before_transport(self):
        arguments = ["pilot-synthetic-03-controller", "--source-sha", SOURCE,
                     "--broker-wheel", "/missing.whl", "--codespace", "space",
                     "--ssh-config", "/missing.conf",
                     "--ssh-host-alias", "independent-host-alias"]
        with patch("review_broker.cli.Pilot03CodespaceTransport") as transport:
            self.assertEqual(main(arguments), 1)
        transport.assert_not_called()

    def test_authorization_mismatch_refuses_before_transport(self):
        with self.assertRaisesRegex(ExecutionAuthorizationError, "DENIED"):
            load_execution_authorization(None)
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "wheel.whl"; wheel.write_bytes(b"other")
            transport = Transport(Source({}))
            with self.assertRaisesRegex(ExecutionAuthorizationError, "MISMATCH"):
                run_pilot03_controller(authorization=self.authorization, source_sha=SOURCE,
                    wheel_path=wheel, codespace_identity="space", transport=transport,
                    _state_root=Path(temporary) / "state")
            self.assertEqual(transport.emissions, 0)

    def test_r03_01_exit_zero_never_bypasses_receipt_or_shutdown_gates(self):
        def missing(values): values.pop("pilot-summary.json")
        def malformed(values): values["pilot-summary.json"] = b"{"
        def wrong_packet(values):
            import json
            summary = json.loads(values["pilot-summary.json"])
            summary["packet_id"] = "packet:sha256:" + "9" * 64
            values["pilot-summary.json"] = encoded(summary)
        cases = {
            "none": ({}, False, True),
            "summary-absent": (missing, False, True),
            "summary-malformed": (malformed, False, True),
            "packet-incoherent": (wrong_packet, False, True),
            "copy-failed": (None, True, True),
            "shutdown-unobserved": (None, False, False),
        }
        for name, (mutation, copy_failure, shutdown) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                values = {} if name == "none" else receipt_values(self.request, self.attempt, "PASS")
                if callable(mutation): mutation(values)
                transport = Transport(Source(values, copy_failure=copy_failure), result=0, shutdown_observed=shutdown)
                report, exit_code = self.run_controller(temporary, transport, name)
                self.assertNotEqual(report["pilot_acceptance"], "PASS")
                self.assertNotEqual(exit_code, 0)
                if name != "shutdown-unobserved":
                    self.assertNotEqual(report["pilot_functional"], "PASS")

    def test_positive_success_and_codex_failure_remain_truthful(self):
        for outcome, result, expected_acceptance in (("PASS", 0, "PASS"), ("FAIL", 1, "FAIL")):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                source = Source(receipt_values(self.request, self.attempt, outcome))
                transport = Transport(source, result=result)
                report, exit_code = self.run_controller(temporary, transport, outcome)
                self.assertEqual(report["pilot_functional"], outcome)
                self.assertEqual(report["sanitized_receipt_retention"], "PASS")
                self.assertEqual(report["raw_diagnostic_retention"], "PASS")
                self.assertEqual(report["pilot_acceptance"], expected_acceptance)
                self.assertEqual(exit_code, 0 if outcome == "PASS" else 1)

    def test_r03_03_transport_exceptions_retain_once_without_retry(self):
        errors = (
            subprocess.TimeoutExpired(["ssh"], 1), OSError("SSH_LOST"),
            RuntimeError("INDETERMINATE_TRANSPORT"),
        )
        for index, error in enumerate(errors):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temporary:
                source = Source(receipt_values(self.request, self.attempt, "FAIL"))
                transport = Transport(source, emit_error=error)
                report, exit_code = self.run_controller(temporary, transport, f"error-{index}")
                self.assertEqual(report["pilot_execution"], "INDETERMINATE")
                self.assertEqual(report["sanitized_receipt_retention"], "PASS")
                self.assertEqual(report["raw_diagnostic_retention"], "PASS")
                self.assertGreater(source.observations, 0)
                self.assertEqual((transport.emissions, transport.stops), (1, 1))
                self.assertEqual(report["automatic_retries"], 0)
                self.assertNotEqual(exit_code, 0)

    def test_preflight_failure_does_not_arm_or_emit_and_still_shuts_down(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transport = Transport(Source({}), preflight_error=RuntimeError("REMOTE_REVIEWCTL_MISSING"))
            report, exit_code = self.run_controller(temporary, transport, "preflight")
            self.assertFalse(report["controller_claim_armed"])
            self.assertEqual(report["remote_command_emissions"], 0)
            self.assertEqual((transport.emissions, transport.stops), (0, 1))
            self.assertEqual(report["codespace_shutdown"], "OBSERVED")
            self.assertNotEqual(exit_code, 0)

    def test_replay_refusal_remains_before_second_emission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL_BYTES)
            first = Transport(Source(receipt_values(self.request, self.attempt)), result=1)
            run_pilot03_controller(authorization=self.authorization, source_sha=SOURCE,
                wheel_path=wheel, codespace_identity="space", transport=first, _state_root=root / "state")
            second = Transport(Source(receipt_values(self.request, self.attempt)), result=1)
            report = run_pilot03_controller(authorization=self.authorization, source_sha=SOURCE,
                wheel_path=wheel, codespace_identity="space", transport=second, _state_root=root / "state")
            self.assertEqual(second.emissions, 0)
            self.assertIn("CONTROLLER_ATTEMPT_ALREADY_ARMED", report["controller_error"])
            self.assertEqual(second.stops, 1)
