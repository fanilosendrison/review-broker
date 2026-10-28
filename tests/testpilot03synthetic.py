"""Offline remote-entrypoint tests for RB-PILOT-03 claim ordering."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.codex import InvocationError
from review_broker.pilot03_synthetic import PilotError, require_claim_available, run_synthetic_pilot_03


class Pilot03SyntheticTests(unittest.TestCase):
    def setup_paths(self, temporary):
        root = Path(temporary).resolve(); home = root / "home"; workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True); workspace.mkdir()
        return root, home, workspace, {"HOME": str(home), "CODEX_HOME": str(home / ".codex"), "PATH": "/usr/bin"}

    def test_claim_precedes_single_simulated_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _home, workspace, environment = self.setup_paths(temporary)
            run = root / "run"; claim = root / "claim.json"; observations = []
            def invoke(*_args, **_kwargs):
                observations.append(claim.exists())
                raise InvocationError("CODEX_APPLICATION_ERROR")
            with patch("review_broker.pilot_synthetic.preflight_codex_runtime", return_value={}), patch(
                "review_broker.pilot_synthetic.install_reviewer_profile"
            ), patch("review_broker.pilot_synthetic.invoke_once", side_effect=invoke) as invoked:
                result = run_synthetic_pilot_03(
                    broker_wheel_sha256="a" * 64, trusted_workspace=workspace,
                    codex_runtime_root=root / "runtime", environment=environment,
                    _run_directory=run, _claim_path=claim,
                )
            self.assertEqual(observations, [True]); self.assertEqual(invoked.call_count, 1)
            self.assertEqual(result["failure"], "CODEX_APPLICATION_ERROR")
            self.assertEqual(claim.stat().st_mode & 0o777, 0o600)

    def test_existing_or_corrupt_claim_refuses_without_invocation(self):
        for data in (b"{}", b"{"):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as temporary:
                root, _home, workspace, environment = self.setup_paths(temporary)
                claim = root / "claim.json"; claim.write_bytes(data); claim.chmod(0o600)
                with patch("review_broker.pilot_synthetic.invoke_once") as invoked:
                    with self.assertRaises(PilotError):
                        run_synthetic_pilot_03(
                            broker_wheel_sha256="a" * 64, trusted_workspace=workspace,
                            environment=environment, _run_directory=root / "run", _claim_path=claim,
                        )
                invoked.assert_not_called()

    def test_nonregular_claim_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claim"; path.mkdir()
            with self.assertRaisesRegex(PilotError, "CLAIM_UNAVAILABLE"):
                require_claim_available(path)
