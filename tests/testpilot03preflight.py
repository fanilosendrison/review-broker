"""Offline adversarial tests for the RB-PILOT-03 remote bootstrap preflight."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.pilot03_remote_preflight import (
    REMOTE_PYTHON, REMOTE_REVIEWCTL, REMOTE_WHEEL,
    _PREFLIGHT_SCRIPT, _PREPARE_SCRIPT, _runtime_scripts,
    Pilot03PreflightError, run_remote_preflight,
)
from review_broker.pilot_runtime_config import (
    PilotRuntimeConfig, RB03_RUNTIME, RB04_RUNTIME, RB05_RUNTIME,
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


def nested_verification_script(preflight):
    for node in ast.walk(ast.parse(preflight)):
        if not isinstance(node, ast.Call) or not node.args or not isinstance(node.args[0], ast.List):
            continue
        values = node.args[0].elts
        for index, value in enumerate(values[:-1]):
            if isinstance(value, ast.Constant) and value.value == "-c":
                nested = values[index + 1]
                if isinstance(nested, ast.Constant) and isinstance(nested.value, str):
                    return nested.value
    raise AssertionError("nested verification script missing")


def nested_identities(preflight):
    tree = ast.parse(nested_verification_script(preflight))
    version = suffix = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Call):
            function = node.left.func
            if (
                isinstance(function, ast.Attribute) and function.attr == "version"
                and node.left.args and ast.literal_eval(node.left.args[0]) == "review-broker"
            ):
                version = ast.literal_eval(node.comparators[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "endswith":
                suffix = ast.literal_eval(node.args[0])
    return version, suffix


class Pilot03PreflightTests(unittest.TestCase):
    def paths(self, temporary):
        root = Path(temporary); config = root / "ssh.conf"
        config.write_text(
            "Host independent-host-alias\n"
            "  ProxyCommand gh cs ssh -c space --stdio\n"
            "  IdentityFile /tmp/synthetic-key\n"
        )
        config.chmod(0o600)
        wheel = root / "review_broker-0.4.5-py3-none-any.whl"; wheel.write_bytes(b"wheel")
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

    def test_runtime_scripts_bind_exact_version_wheel_and_bootstrap(self):
        rb03 = _runtime_scripts(RB03_RUNTIME)
        self.assertEqual(rb03, (_PREPARE_SCRIPT, _PREFLIGHT_SCRIPT))
        rb04 = _runtime_scripts(RB04_RUNTIME)
        self.assertEqual(rb04, (
            _PREPARE_SCRIPT.replace(RB03_RUNTIME.bootstrap_root, RB04_RUNTIME.bootstrap_root),
            _PREFLIGHT_SCRIPT.replace(
                RB03_RUNTIME.bootstrap_root, RB04_RUNTIME.bootstrap_root,
            ),
        ))
        prepare, preflight = _runtime_scripts(RB05_RUNTIME)
        self.assertIn(RB05_RUNTIME.bootstrap_root, prepare)
        for value in (RB05_RUNTIME.remote_wheel, RB05_RUNTIME.remote_venv,
                      RB05_RUNTIME.remote_python, RB05_RUNTIME.remote_reviewctl):
            self.assertIn(value, preflight)
        self.assertIn('version("review-broker")=="0.4.8"', preflight)
        self.assertNotIn(RB03_RUNTIME.remote_wheel, preflight)
        self.assertNotIn('version("review-broker")=="0.4.5"', preflight)

    def test_nested_verification_uses_each_runtime_version_and_wheel_basename(self):
        for runtime in (RB03_RUNTIME, RB04_RUNTIME, RB05_RUNTIME):
            with self.subTest(pilot=runtime.pilot_id):
                prepare, preflight = _runtime_scripts(runtime)
                version, suffix = nested_identities(preflight)
                self.assertEqual(version, runtime.package_version)
                self.assertEqual(suffix, "/" + Path(runtime.remote_wheel).name)
                self.assertIn(runtime.remote_wheel, preflight)
                self.assertIn(runtime.bootstrap_root, prepare)
        self.assertEqual(_runtime_scripts(RB03_RUNTIME), (_PREPARE_SCRIPT, _PREFLIGHT_SCRIPT))
        self.assertEqual(
            _runtime_scripts(RB04_RUNTIME)[1],
            _PREFLIGHT_SCRIPT.replace(RB03_RUNTIME.bootstrap_root, RB04_RUNTIME.bootstrap_root),
        )

    def test_baseline_rb05_generator_reproduces_basename_mismatch(self):
        baseline = PilotRuntimeConfig(
            pilot_id="RB-PILOT-05", cli_command="pilot-synthetic-05",
            remote_root="/tmp/review-broker-pilot-26-rb05",
            bootstrap_root="/tmp/review-broker-pilot-26-rb05-bootstrap",
            package_version="0.4.7",
        )
        script = _PREFLIGHT_SCRIPT.replace(REMOTE_WHEEL, baseline.remote_wheel)
        script = script.replace(RB03_RUNTIME.bootstrap_root, baseline.bootstrap_root)
        script = script.replace(
            'version("review-broker")=="0.4.5"',
            'version("review-broker")=="0.4.7"',
        )
        version, suffix = nested_identities(script)
        self.assertEqual(version, baseline.package_version)
        self.assertEqual(suffix, "/review_broker-0.4.5-py3-none-any.whl")
        self.assertNotEqual(suffix, "/" + Path(baseline.remote_wheel).name)

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
