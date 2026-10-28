"""Offline adversarial tests for the RB-PILOT-03 remote bootstrap preflight."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.pilot03_remote_preflight import (
    REMOTE_PYTHON, REMOTE_REVIEWCTL, REMOTE_WHEEL,
    Pilot03PreflightError, run_remote_preflight,
)
from review_broker.pilot03_transport import Pilot03CodespaceTransport

PASS = {
    "remote_python_compatible": "YES",
    "remote_wheel_sha256_match": "YES",
    "remote_broker_installation_verified": "YES",
    "remote_entrypoint_resolves": "YES",
    "remote_dependencies_available": "YES",
    "remote_codex_runtime_preflight": "PASS",
    "remote_non_inference_auth_status": "PASS",
}


class Runner:
    def __init__(self, results):
        self.results = list(results); self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return self.results.pop(0)


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class Lifecycle:
    def start(self): pass
    def state(self): return "Available"
    def stop(self): pass


class Pilot03PreflightTests(unittest.TestCase):
    def paths(self, temporary):
        root = Path(temporary); config = root / "ssh.conf"
        config.write_text(
            "Host independent-host-alias\n"
            "  ProxyCommand gh cs ssh -c space --stdio\n"
            "  IdentityFile /tmp/synthetic-key\n"
        )
        config.chmod(0o600)
        wheel = root / "review_broker-0.4.3-py3-none-any.whl"; wheel.write_bytes(b"wheel")
        return config, wheel, hashlib.sha256(b"wheel").hexdigest()

    def runner(self, final, copy_return=0):
        return Runner([
            completed(stdout=json.dumps({"status": "READY"})),
            completed(returncode=copy_return),
            completed(stdout=json.dumps(final)),
        ])

    def test_complete_preflight_transfers_exact_wheel_and_uses_sanitary_scripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, wheel, digest = self.paths(temporary); runner = self.runner(PASS)
            receipt = run_remote_preflight(
                codespace="space", ssh_host_alias="independent-host-alias",
                ssh_config=config, wheel_path=wheel, wheel_sha256=digest, runner=runner,
            )
            self.assertEqual(receipt, PASS)
            copy_command, copy_options = runner.calls[1]
            self.assertEqual(copy_command, ["gh", "codespace", "cp", "-c", "space",
                                            str(wheel), f"remote:{REMOTE_WHEEL}"])
            self.assertFalse(copy_options["shell"])
            for command, options in (runner.calls[0], runner.calls[2]):
                self.assertEqual(command[0], "ssh")
                self.assertEqual(command[5], "independent-host-alias")
                self.assertNotIn("bash", command)
                self.assertFalse(options["shell"])
                self.assertIn("input", options)
            preflight_script = runner.calls[2][1]["input"]
            self.assertIn("--no-index", preflight_script)
            self.assertIn("--no-deps", preflight_script)
            self.assertIn('preflight_codex_runtime', preflight_script)
            self.assertIn('version(\"jsonschema\")==\"4.26.0\"', preflight_script)

    def test_required_remote_failures_refuse(self):
        cases = {
            "REMOTE_REVIEWCTL_MISSING": {**PASS, "remote_entrypoint_resolves": "NO"},
            "REMOTE_WHEEL_SHA256_MISMATCH": {**PASS, "remote_wheel_sha256_match": "NO"},
            "REMOTE_PYTHON_INCOMPATIBLE": {**PASS, "remote_python_compatible": "NO"},
            "REMOTE_DEPENDENCY_MISSING": {**PASS, "remote_dependencies_available": "NO"},
            "REMOTE_CODEX_RUNTIME_UNAVAILABLE": {**PASS, "remote_codex_runtime_preflight": "FAIL"},
            "REMOTE_PREFLIGHT_UNDETERMINED": {**PASS, "remote_non_inference_auth_status": "FAIL"},
        }
        for expected, value in cases.items():
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                config, wheel, digest = self.paths(temporary)
                with self.assertRaisesRegex(Pilot03PreflightError, expected):
                    run_remote_preflight(
                        codespace="space", ssh_host_alias="independent-host-alias",
                        ssh_config=config, wheel_path=wheel, wheel_sha256=digest,
                        runner=self.runner(value),
                    )

    def test_missing_remote_wheel_transfer_and_malformed_result_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, wheel, digest = self.paths(temporary)
            runner = Runner([completed(stdout=json.dumps({"status": "READY"})), completed(1)])
            with self.assertRaisesRegex(Pilot03PreflightError, "REMOTE_WHEEL_MISSING"):
                run_remote_preflight(
                    codespace="space", ssh_host_alias="independent-host-alias",
                    ssh_config=config, wheel_path=wheel, wheel_sha256=digest, runner=runner,
                )
        with tempfile.TemporaryDirectory() as temporary:
            config, wheel, digest = self.paths(temporary)
            runner = Runner([completed(stdout=json.dumps({"status": "READY"})), completed(), completed(stdout="{")])
            with self.assertRaisesRegex(Pilot03PreflightError, "REMOTE_PREFLIGHT_UNDETERMINED"):
                run_remote_preflight(
                    codespace="space", ssh_host_alias="independent-host-alias",
                    ssh_config=config, wheel_path=wheel, wheel_sha256=digest, runner=runner,
                )

    def test_transport_uses_prepared_python_for_emission_and_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, wheel, digest = self.paths(temporary)
            runner = self.runner(PASS)
            transport = Pilot03CodespaceTransport(
                "space", "independent-host-alias", config,
                runner=runner, lifecycle=Lifecycle(),
            )
            transport.preflight(source_sha="a" * 40, wheel_path=wheel, wheel_sha256=digest)
            runner.results.append(completed(returncode=1))
            self.assertEqual(transport.emit_once(wheel_sha256=digest), 1)
            emission = runner.calls[-1][0]
            self.assertEqual(emission[5], "independent-host-alias")
            self.assertIn(REMOTE_PYTHON, emission)
            self.assertNotIn("python3", emission)
            self.assertIn(REMOTE_REVIEWCTL, runner.calls[-1][1]["input"])
            self.assertEqual(transport.artifact_source.remote_python, REMOTE_PYTHON)
