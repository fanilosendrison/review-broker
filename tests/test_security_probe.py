import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from review_broker.reviewer_profile import install_reviewer_profile, profile_name
from review_broker.security_probe import SecurityProbeError, run_reviewer_isolation_probe


PASSING_OBSERVATION = {
    "packet_canary_readable": True,
    "auth_parent_canary_readable": False,
    "trusted_workspace_readable": False,
    "packet_directory_writable": False,
    "unauthorized_network_connect": False,
    "sensitive_environment_visible": False,
    "process_canary_visible": False,
    "outside_packet_canary_readable": False,
    "symlink_to_auth_parent_canary_readable": False,
    "hardlink_to_auth_parent_canary_readable": False,
    "hardlink_created": True,
    "visible_proc_pid_count": 2,
    "parent_process_environment_os_access_readable": True,
}


class SecurityProbeTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        root = root.resolve()
        home = root / "home"
        workspace = root / "workspace"
        packet = root / "packet"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        packet.mkdir()
        (workspace / "README.md").write_text("trusted")
        (home / ".codex" / "auth.json").write_text("non-secret-fixture")
        install_reviewer_profile(home, workspace, packet)
        return home, workspace, packet

    def test_passing_observation_produces_bounded_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))

            def runner(command, **kwargs):
                self.assertEqual(command[0], "/trusted/codex")
                self.assertIn(profile_name(packet), command)
                self.assertEqual(command[-2], str(Path(sys.executable).resolve()))
                self.assertEqual(
                    kwargs["env"]["REVIEW_BROKER_PROCESS_CANARY"],
                    "non-secret-process-canary",
                )
                return subprocess.CompletedProcess(
                    command, 0, stdout=json.dumps(PASSING_OBSERVATION) + "\n", stderr=""
                )

            receipt = run_reviewer_isolation_probe(
                home, workspace, packet, Path("/trusted/codex"),
                runner=runner,
                environment={"HOME": str(home), "PATH": "/usr/bin"},
            )
            self.assertTrue(receipt["qualified"])
            self.assertEqual(receipt["mismatches"], [])
            self.assertFalse(
                (home / ".codex" / "review-broker-auth-parent-canary.txt").exists()
            )

    def test_readable_auth_canary_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))
            observation = dict(PASSING_OBSERVATION, auth_parent_canary_readable=True)

            def runner(command, **kwargs):
                return subprocess.CompletedProcess(
                    command, 0, stdout=json.dumps(observation) + "\n", stderr=""
                )

            with self.assertRaisesRegex(
                SecurityProbeError, "auth_parent_canary_readable"
            ):
                run_reviewer_isolation_probe(
                    home, workspace, packet, Path("/trusted/codex"),
                    runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )

    def test_outside_packet_access_blocks_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))
            observed = dict(PASSING_OBSERVATION, outside_packet_canary_readable=True)
            def runner(command, **kwargs):
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps(observed), stderr="")
            with self.assertRaisesRegex(SecurityProbeError, "outside_packet_canary_readable"):
                run_reviewer_isolation_probe(
                    home, workspace, packet, Path("/trusted/codex"), runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )

    def test_unconstructed_hardlink_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))
            observed = dict(PASSING_OBSERVATION, hardlink_created=False)
            def runner(command, **kwargs):
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps(observed), stderr="")
            with self.assertRaisesRegex(SecurityProbeError, "hardlink_created"):
                run_reviewer_isolation_probe(
                    home, workspace, packet, Path("/trusted/codex"), runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )

    def test_real_runner_receives_resolved_interpreter_without_path_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, workspace, packet = self.fixture(root)
            shim = root / "sandbox-shim"
            shim.write_text(
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                "child = sys.argv[-2]\n"
                "if not os.path.isabs(child) or not os.access(child, os.X_OK):\n"
                "    raise SystemExit(127)\n"
                f"print(json.dumps({PASSING_OBSERVATION!r}))\n",
                encoding="utf-8",
            )
            shim.chmod(0o700)

            receipt = run_reviewer_isolation_probe(
                home,
                workspace,
                packet,
                shim,
                environment={"HOME": str(home), "PATH": ""},
            )
            self.assertTrue(receipt["qualified"])

    def test_missing_interpreter_fails_before_sandbox_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))
            runner = mock.Mock()
            with mock.patch("review_broker.security_probe.sys.executable", "/missing/python"):
                with self.assertRaisesRegex(
                    SecurityProbeError, "PROBE_PYTHON_EXECUTABLE_INVALID"
                ):
                    run_reviewer_isolation_probe(
                        home,
                        workspace,
                        packet,
                        Path("/trusted/codex"),
                        runner=runner,
                        environment={"HOME": str(home), "PATH": ""},
                    )
            runner.assert_not_called()

    def test_probe_transport_failure_is_not_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.fixture(Path(temporary))

            def runner(command, **kwargs):
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

            with self.assertRaisesRegex(
                SecurityProbeError, "SANDBOX_PROBE_EXECUTION_FAILED"
            ):
                run_reviewer_isolation_probe(
                    home, workspace, packet, Path("/trusted/codex"),
                    runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )


if __name__ == "__main__":
    unittest.main()
