import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.reviewer_profile import install_reviewer_profile
from review_broker.security_probe import SecurityProbeError, run_reviewer_isolation_probe


PASSING_OBSERVATION = {
    "packet_canary_readable": True,
    "auth_parent_canary_readable": False,
    "auth_file_os_access_readable": False,
    "trusted_workspace_readable": False,
    "packet_directory_writable": False,
    "unauthorized_network_connect": False,
    "sensitive_environment_visible": False,
    "process_canary_visible": False,
    "visible_proc_pid_count": 2,
    "parent_process_environment_os_access_readable": True,
}


class SecurityProbeTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        root = root.resolve()
        home = root / "home"
        workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        (workspace / "README.md").write_text("trusted")
        (home / ".codex" / "auth.json").write_text("non-secret-fixture")
        install_reviewer_profile(home, workspace)
        return home, workspace

    def test_passing_observation_produces_bounded_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.fixture(Path(temporary))

            def runner(command, **kwargs):
                self.assertIn("review-broker", command)
                self.assertEqual(
                    kwargs["env"]["REVIEW_BROKER_PROCESS_CANARY"],
                    "non-secret-process-canary",
                )
                return subprocess.CompletedProcess(
                    command, 0, stdout=json.dumps(PASSING_OBSERVATION) + "\n", stderr=""
                )

            receipt = run_reviewer_isolation_probe(
                home,
                workspace,
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
            home, workspace = self.fixture(Path(temporary))
            observation = dict(PASSING_OBSERVATION, auth_parent_canary_readable=True)

            def runner(command, **kwargs):
                return subprocess.CompletedProcess(
                    command, 0, stdout=json.dumps(observation) + "\n", stderr=""
                )

            with self.assertRaisesRegex(
                SecurityProbeError, "auth_parent_canary_readable"
            ):
                run_reviewer_isolation_probe(
                    home,
                    workspace,
                    runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )

    def test_probe_transport_failure_is_not_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.fixture(Path(temporary))

            def runner(command, **kwargs):
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

            with self.assertRaisesRegex(
                SecurityProbeError, "SANDBOX_PROBE_EXECUTION_FAILED"
            ):
                run_reviewer_isolation_probe(
                    home,
                    workspace,
                    runner=runner,
                    environment={"HOME": str(home), "PATH": "/usr/bin"},
                )


if __name__ == "__main__":
    unittest.main()
