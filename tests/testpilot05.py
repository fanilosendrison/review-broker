"""Offline qualification for isolated Sol/xhigh RB-PILOT-05 preparation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.cli import main
from review_broker.codex import build_command
from review_broker.identity import attempt_identity
from review_broker.packets import verify_packet
from review_broker.pilot03_authorization import ExecutionAuthorization
from review_broker.pilot03_controller import pilot03_identities
from review_broker.pilot04_controller import pilot04_identities
from review_broker.pilot05_controller import pilot05_identities, run_pilot05_controller
from review_broker.pilot05_synthetic import PILOT_POLICY, PilotError, run_synthetic_pilot_05
from review_broker.pilot_runtime_config import PilotRuntimeConfig, RB05_RUNTIME, require_runtime_config
from review_broker.pilot_synthetic import pilot_fixture, pilot_fixture_02
from tests.testpilot04 import DIGEST, SOURCE, WHEEL, Source, Transport, rb04_receipts


def rb05_receipts(request, attempt, *, outcome="FAIL"):
    values = rb04_receipts(request, attempt, outcome=outcome)
    replacements = ((b"RB-PILOT-04", b"RB-PILOT-05"),
                    (b"gpt-5.6-terra", b"gpt-5.6-sol"),
                    (b'"medium"', b'"xhigh"'))
    for name, data in list(values.items()):
        for old, new in replacements:
            data = data.replace(old, new)
        values[name] = data
    return values


def completed_output(evidence, *_args, **kwargs):
    manifest = verify_packet(evidence)
    response = {
        "schema_version": 1,
        "request_id": manifest["request_id"],
        "subject_id": manifest["subject_id"],
        "packet_id": manifest["packet_id"],
        "verdict": "NO_GO",
        "sources_examined": ["S001"],
        "findings": [{
            "id": "F001",
            "category": "contradiction",
            "claim": "The age-18 boundary contradicts the documented behavior.",
            "consequence": "An applicant aged 18 is incorrectly rejected.",
            "evidence": [{
                "source_id": "S001", "line": 3, "quote": "return age > 18",
            }],
        }],
        "remaining_uncertainties": [],
    }
    message = json.dumps(response)
    events = [
        {"type": "thread.started", "thread_id": "synthetic"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
        {"type": "turn.completed"},
    ]
    (evidence / "codex-final.json").write_text(message)
    (evidence / "codex-events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
    )
    (evidence / "codex-exit-code.txt").write_text("0\n")
    assert kwargs["policy"] == PILOT_POLICY


class Pilot05Tests(unittest.TestCase):
    def test_identity_is_deterministic_and_isolated_from_all_historical_pilots(self):
        request, attempt = pilot05_identities()
        self.assertEqual((request, attempt), pilot05_identities())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            historical = {
                pilot_fixture(root / "one")["request_id"],
                pilot_fixture_02(root / "two")["request_id"],
                pilot03_identities()[0], pilot04_identities()[0],
            }
        self.assertNotIn(request, historical)
        self.assertEqual(attempt, attempt_identity(request, 1))

    def test_sol_xhigh_wire_schema_and_functional_oracle(self):
        self.assertEqual((PILOT_POLICY.model, PILOT_POLICY.reasoning_effort),
                         ("gpt-5.6-sol", "xhigh"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); home = root / "home"; workspace = root / "workspace"
            (home / ".codex").mkdir(parents=True); workspace.mkdir(); observed = []
            def invoke(*args, **kwargs):
                observed.append((args[1].name, kwargs["policy"], kwargs["armed"]))
                completed_output(*args, **kwargs)
            environment = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"), "PATH": "/usr/bin"}
            with patch("review_broker.pilot_synthetic.preflight_codex_runtime", return_value={}), patch(
                "review_broker.pilot_synthetic.install_reviewer_profile"
            ), patch("review_broker.pilot_synthetic.invoke_once", side_effect=invoke):
                result = run_synthetic_pilot_05(
                    broker_wheel_sha256="a" * 64, trusted_workspace=workspace,
                    codex_runtime_root=root / "runtime", environment=environment,
                    _run_directory=root / "run", _claim_path=root / "claim",
                )
            self.assertEqual(observed, [(
                "reviewer-findings-v1.codex-wire.schema.json", PILOT_POLICY, True,
            )])
            self.assertEqual(result["pilot_functional"], "PASS")
            self.assertEqual(result["schema_and_citations"], "PASS")
            self.assertEqual(result["verdict"], "NO_GO")

    def test_actual_command_preserves_sol_xhigh_security_flags(self):
        command = build_command(
            Path("/protected/codex"), Path("/wire.json"), Path("/final.json"),
            PILOT_POLICY, "credential-isolated-read-only",
        )
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-sol")
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertEqual(command[command.index("--output-schema") + 1], "/wire.json")
        self.assertIn("features.shell_tool=false", command)

    def test_runtime_configuration_is_exact_and_closed(self):
        self.assertEqual(RB05_RUNTIME.remote_root, "/tmp/review-broker-pilot-26-rb05")
        self.assertEqual(RB05_RUNTIME.remote_wheel,
                         "/tmp/review-broker-pilot-26-rb05-bootstrap/review_broker-0.4.7-py3-none-any.whl")
        self.assertIs(require_runtime_config(RB05_RUNTIME), RB05_RUNTIME)
        with self.assertRaisesRegex(ValueError, "CONFIG_UNSUPPORTED"):
            require_runtime_config(PilotRuntimeConfig(**RB05_RUNTIME.__dict__))

    def test_missing_cli_authorization_refuses_before_transport(self):
        arguments = [
            "pilot-synthetic-05-controller", "--source-sha", SOURCE,
            "--broker-wheel", "/missing.whl", "--codespace", "space",
            "--ssh-config", "/missing.conf", "--ssh-host-alias", "alias",
        ]
        with patch("review_broker.cli.Pilot03CodespaceTransport") as transport, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(arguments), 1)
        transport.assert_not_called()

    def test_authorization_and_preflight_refuse_before_claim_or_emission(self):
        request, attempt = pilot05_identities()
        authorization = ExecutionAuthorization("RB-PILOT-05", request, attempt, SOURCE, DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            refused = Transport(Source({}), preflight_error=RuntimeError("REMOTE_PREFLIGHT_UNDETERMINED"))
            report = run_pilot05_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=refused, _state_root=root / "refused",
            )
            self.assertFalse(report["controller_claim_armed"]); self.assertEqual(refused.emissions, 0)
            for pilot_id, identities in (("RB-PILOT-03", pilot03_identities()),
                                         ("RB-PILOT-04", pilot04_identities())):
                wrong = ExecutionAuthorization(pilot_id, *identities, SOURCE, DIGEST, "space")
                never = Transport(Source({}))
                with self.assertRaisesRegex(ValueError, "MISMATCH"):
                    run_pilot05_controller(
                        authorization=wrong, source_sha=SOURCE, wheel_path=wheel,
                        codespace_identity="space", transport=never, _state_root=root / pilot_id,
                    )
                self.assertEqual((never.prepares, never.emissions), (0, 0))

    def test_acceptance_requires_receipts_retention_shutdown_and_one_emission(self):
        request, attempt = pilot05_identities()
        authorization = ExecutionAuthorization("RB-PILOT-05", request, attempt, SOURCE, DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            transport = Transport(Source(rb05_receipts(request, attempt, outcome="PASS")), result=0)
            report = run_pilot05_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=transport, _state_root=root / "state",
            )
            self.assertEqual((transport.emissions, transport.stops), (1, 1))
            self.assertEqual(report["pilot_acceptance"], "PASS")
            replay = Transport(Source(rb05_receipts(request, attempt)), result=1)
            second = run_pilot05_controller(
                authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                codespace_identity="space", transport=replay, _state_root=root / "state",
            )
            self.assertEqual(replay.emissions, 0)
            self.assertIn("ALREADY_ARMED", second["controller_error"])

    def test_invalid_evidence_or_contamination_never_passes(self):
        request, attempt = pilot05_identities()
        authorization = ExecutionAuthorization("RB-PILOT-05", request, attempt, SOURCE, DIGEST, "space")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheel = root / "wheel.whl"; wheel.write_bytes(WHEEL)
            for index, source in enumerate((Source({}), Source(
                rb05_receipts(request, attempt, outcome="PASS"), screen="CONTAMINATED",
            ))):
                transport = Transport(source, result=1 if index == 0 else 0)
                report = run_pilot05_controller(
                    authorization=authorization, source_sha=SOURCE, wheel_path=wheel,
                    codespace_identity="space", transport=transport,
                    _state_root=root / f"state-{index}",
                )
                self.assertNotEqual(report["pilot_acceptance"], "PASS")
                if index == 0:
                    self.assertNotEqual(report["pilot_functional"], "PASS")
                self.assertEqual(report["automatic_retries"], 0)

    def test_remote_claim_replay_refuses_without_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); claim = root / "claim"; claim.write_text("{}\n"); claim.chmod(0o600)
            with self.assertRaisesRegex(PilotError, "ALREADY_CONSUMED"):
                run_synthetic_pilot_05(
                    broker_wheel_sha256="a" * 64, _run_directory=root / "run", _claim_path=claim,
                )


if __name__ == "__main__":
    unittest.main()
