"""Offline qualification for isolated Terra RB-PILOT-04 preparation."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from review_broker.cli import main
from review_broker.codex import InvocationError, build_command
from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.pilot03_authorization import ExecutionAuthorization
from review_broker.pilot03_controller import pilot03_identities
from review_broker.pilot03_transport import Pilot03CodespaceTransport
from review_broker.pilot04_controller import pilot04_identities, run_pilot04_controller
from review_broker.pilot04_synthetic import PILOT_POLICY, PilotError, run_synthetic_pilot_04
from review_broker.pilot_runtime_config import PilotRuntimeConfig, RB04_RUNTIME, require_runtime_config
from review_broker.pilot_synthetic import pilot_fixture, pilot_fixture_02
from review_broker.pilot_private_retention import RemoteArtifact

SOURCE = "8" * 40
WHEEL = b"rb04-wheel"
DIGEST = hashlib.sha256(WHEEL).hexdigest()
PACKET = "packet:sha256:" + "9" * 64
ARMED = "2026-10-28T00:00:00+00:00"


def encoded(value):
    return canonical_bytes(value) + b"\n"


def rb04_receipts(request, attempt, *, outcome="FAIL"):
    claim = {"schema_version": 1, "pilot_id": "RB-PILOT-04", "request_id": request,
             "attempt_id": attempt, "packet_id": PACKET, "status": "ARMED", "armed_utc": ARMED}
    armed = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
             "request_id": request, "attempt_id": attempt, "packet_id": PACKET,
             "broker_wheel_sha256": DIGEST, "acknowledged_residual_risk": True,
             "armed_utc": ARMED}
    summary = {"schema_version": 1, "scope": "SYNTHETIC_NONPRODUCTION_ONLY", "issue": 26,
               "pilot_id": "RB-PILOT-04", "request_id": request, "attempt_id": attempt,
               "packet_id": PACKET, "broker_wheel_sha256": DIGEST,
               "model_requested": "gpt-5.6-terra", "effort_requested": "medium",
               "pilot_functional": outcome,
               "pilot_execution": "COMPLETED" if outcome == "PASS" else "FAILED",
               "credential_screen": "PASS_NO_MATCH", "pilot_security_qualified": False,
               "production_security_qualified": False, "github_publication": "NONE",
               "reviewer_authority": "NONE"}
    values = {"pilot-claim.json": encoded(claim), "pilot-armed.json": encoded(armed),
              "pilot-summary.json": encoded(summary), "codex-events.jsonl": b"{}\n",
              "codex-stderr.txt": b"", "codex-final.json": b"{}",
              "codex-exit-code.txt": b"0\n" if outcome == "PASS" else b"1\n"}
    if outcome == "PASS":
        summary.update({"schema_and_citations": "PASS", "verdict": "NO_GO"})
        values["pilot-summary.json"] = encoded(summary)
    else:
        summary["failure"] = "CODEX_APPLICATION_ERROR"
        values["pilot-summary.json"] = encoded(summary)
    return values


class Source:
    def __init__(self, values, *, screen="PASS_NO_MATCH"): self.values = values; self.screen = screen
    def observe(self, name):
        data = self.values.get(name)
        if data is None: return RemoteArtifact(False)
        return RemoteArtifact(True, True, False, 1, len(data), hashlib.sha256(data).hexdigest(), self.screen)
    def copy_literal(self, name, destination):
        destination.write_bytes(self.values[name]); destination.chmod(0o600)


class Transport:
    def __init__(self, source, *, preflight_error=None, result=1, emit_error=None, observed=True):
        self.artifact_source = source; self.preflight_error = preflight_error; self.result = result
        self.emit_error = emit_error; self.observed = observed
        self.prepares = 0; self.emissions = 0; self.stops = 0
    def prepare(self): self.prepares += 1
    def preflight(self, **_kwargs):
        if self.preflight_error: raise self.preflight_error
    def emit_once(self, **_kwargs):
        self.emissions += 1
        if self.emit_error: raise self.emit_error
        return self.result
    def shutdown(self): self.stops += 1
    def shutdown_observed(self): return self.observed


class Runner:
    def __init__(self, results): self.results = list(results); self.calls = []
    def __call__(self, command, **kwargs): self.calls.append((command, kwargs)); return self.results.pop(0)


class Lifecycle:
    def start(self): pass
    def state(self): return "Available"
    def stop(self): pass


class Pilot04Tests(unittest.TestCase):
    def test_identity_is_deterministic_and_isolated_from_all_historical_pilots(self):
        request, attempt = pilot04_identities()
        self.assertEqual((request, attempt), pilot04_identities())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            historical = {
                pilot_fixture(root / "one")["request_id"],
                pilot_fixture_02(root / "two")["request_id"],
                pilot03_identities()[0],
            }
        self.assertNotIn(request, historical)
        self.assertEqual(attempt, attempt_identity(request, 1))

    def test_explicit_terra_policy_reaches_invocation_and_evidence(self):
        self.assertEqual((PILOT_POLICY.model, PILOT_POLICY.reasoning_effort),
                         ("gpt-5.6-terra", "medium"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); home = root / "home"; workspace = root / "workspace"
            (home / ".codex").mkdir(parents=True); workspace.mkdir(); claim = root / "claim"
            observed = []
            def invoke(*_args, **kwargs):
                observed.append((claim.exists(), kwargs["policy"], kwargs["armed"]))
                raise InvocationError("CODEX_APPLICATION_ERROR")
            env = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"), "PATH": "/usr/bin"}
            with patch("review_broker.pilot_synthetic.preflight_codex_runtime", return_value={}), patch(
                "review_broker.pilot_synthetic.install_reviewer_profile"
            ), patch("review_broker.pilot_synthetic.invoke_once", side_effect=invoke):
                result = run_synthetic_pilot_04(
                    broker_wheel_sha256="a" * 64, trusted_workspace=workspace,
                    codex_runtime_root=root / "runtime", environment=env,
                    _run_directory=root / "run", _claim_path=claim,
                )
            self.assertEqual(observed, [(True, PILOT_POLICY, True)])
            self.assertEqual((result["model_requested"], result["effort_requested"]),
                             ("gpt-5.6-terra", "medium"))
            failure = json.loads((root / "run/pilot-failure.json").read_text())
            self.assertEqual((failure["model_requested"], failure["effort_requested"]),
                             ("gpt-5.6-terra", "medium"))

    def test_runtime_configuration_is_closed_not_caller_constructible(self):
        copied = PilotRuntimeConfig(**RB04_RUNTIME.__dict__)
        with self.assertRaisesRegex(ValueError, "CONFIG_UNSUPPORTED"):
            require_runtime_config(copied)

    def test_actual_argv_preserves_security_schema_and_exact_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = build_command(
                Path("/protected/codex"), root / "schema.json", root / "final.json",
                PILOT_POLICY, "credential-isolated-read-only",
            )
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-terra")
        self.assertIn('model_reasoning_effort="medium"', command)
        for value in ("--json", "--ephemeral", "--strict-config", "--ignore-rules",
                      "--skip-git-repo-check", "--output-schema", "--output-last-message"):
            self.assertIn(value, command)
        self.assertIn("features.shell_tool=false", command)
        self.assertEqual(command[command.index("--profile") + 1],
                         "credential-isolated-read-only")

    def test_transport_uses_isolated_paths_and_exact_remote_entrypoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); config = root / "ssh.conf"
            config.write_text("Host alias\n  ProxyCommand gh cs ssh -c space --stdio\n")
            config.chmod(0o600); wheel = root / "review_broker-0.4.5-py3-none-any.whl"; wheel.write_bytes(WHEEL)
            ready = subprocess.CompletedProcess([], 0, '{"status":"READY"}', "")
            copied = subprocess.CompletedProcess([], 0, "", "")
            passed = {"remote_python_compatible":"YES","remote_wheel_sha256_match":"YES",
                      "remote_broker_installation_verified":"YES","remote_entrypoint_resolves":"YES",
                      "remote_dependencies_available":"YES","remote_codex_runtime_preflight":"PASS",
                      "remote_non_inference_auth_status":"PASS"}
            runner = Runner([ready, copied, subprocess.CompletedProcess([], 0, json.dumps(passed), ""),
                             subprocess.CompletedProcess([], 1, "", "")])
            transport = Pilot03CodespaceTransport(
                "space", "alias", config, runner=runner, lifecycle=Lifecycle(), runtime=RB04_RUNTIME,
            )
            transport.preflight(source_sha=SOURCE, wheel_path=wheel, wheel_sha256=DIGEST)
            self.assertIn("rb04-bootstrap", runner.calls[1][0][-1])
            transport.emit_once(wheel_sha256=DIGEST)
            command, options = runner.calls[-1]
            self.assertIn(RB04_RUNTIME.remote_python, command)
            self.assertIn('"pilot-synthetic-04"', options["input"])
            self.assertNotIn('"pilot-synthetic-03"', options["input"])
            with self.assertRaisesRegex(RuntimeError, "ALREADY_EMITTED"):
                transport.emit_once(wheel_sha256=DIGEST)

    def test_missing_cli_authorization_refuses_before_transport_construction(self):
        arguments = [
            "pilot-synthetic-04-controller", "--source-sha", SOURCE,
            "--broker-wheel", "/missing.whl", "--codespace", "space",
            "--ssh-config", "/missing.conf", "--ssh-host-alias", "alias",
        ]
        with patch("review_broker.cli.Pilot03CodespaceTransport") as transport, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(arguments), 1)
        transport.assert_not_called()

    def test_authorization_is_attempt_bound_and_preflight_precedes_claim(self):
        request, attempt = pilot04_identities()
        authorization = ExecutionAuthorization("RB-PILOT-04", request, attempt, SOURCE, DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            refused = Transport(Source({}), preflight_error=RuntimeError("REMOTE_PREFLIGHT_UNDETERMINED"))
            report = run_pilot04_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=refused, _state_root=root / "state-refused",
            )
            self.assertFalse(report["controller_claim_armed"]); self.assertEqual(refused.emissions, 0)
            wrong = ExecutionAuthorization("RB-PILOT-03", *pilot03_identities(), SOURCE, DIGEST, "space")
            never = Transport(Source({}))
            with self.assertRaisesRegex(ValueError, "MISMATCH"):
                run_pilot04_controller(
                    authorization=wrong, source_sha=SOURCE, wheel_path=wheel,
                    codespace_identity="space", transport=never, _state_root=root / "state-wrong",
                )
            self.assertEqual((never.prepares, never.emissions), (0, 0))

    def test_success_requires_coherent_receipts_shutdown_and_single_emission(self):
        request, attempt = pilot04_identities()
        authorization = ExecutionAuthorization("RB-PILOT-04", request, attempt, SOURCE, DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            transport = Transport(Source(rb04_receipts(request, attempt, outcome="PASS")), result=0)
            report = run_pilot04_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=transport, _state_root=root / "state",
            )
            self.assertEqual((transport.emissions, transport.stops), (1, 1))
            self.assertEqual(report["pilot_acceptance"], "PASS")
            second = Transport(Source(rb04_receipts(request, attempt)), result=1)
            replay = run_pilot04_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=second, _state_root=root / "state",
            )
            self.assertEqual(second.emissions, 0)
            self.assertIn("CONTROLLER_ATTEMPT_ALREADY_ARMED", replay["controller_error"])

    def test_transport_error_has_no_retry_and_shutdown_is_still_required(self):
        request, attempt = pilot04_identities(); authorization = ExecutionAuthorization(
            "RB-PILOT-04", request, attempt, SOURCE, DIGEST, "space",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            transport = Transport(Source(rb04_receipts(request, attempt)),
                                  emit_error=subprocess.TimeoutExpired(["ssh"], 1), observed=False)
            report = run_pilot04_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=transport, _state_root=root / "state",
            )
            self.assertEqual((transport.emissions, transport.stops), (1, 1))
            self.assertEqual(report["automatic_retries"], 0)
            self.assertEqual(report["pilot_execution"], "INDETERMINATE")
            self.assertNotEqual(report["pilot_acceptance"], "PASS")
            self.assertEqual(report["codespace_shutdown"], "UNDETERMINED")

    def test_nonzero_or_missing_evidence_never_passes(self):
        request, attempt = pilot04_identities(); authorization = ExecutionAuthorization(
            "RB-PILOT-04", request, attempt, SOURCE, DIGEST, "space",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            transport = Transport(Source({}), result=1)
            report = run_pilot04_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=transport, _state_root=root / "state",
            )
            self.assertNotEqual(report["pilot_acceptance"], "PASS")
            self.assertNotEqual(report["pilot_functional"], "PASS")
            self.assertEqual(report["automatic_retries"], 0)
