"""Offline child-boundary witnesses. No official helper or credential is exercised."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_broker.actions_artifact_child_v3 import (
    GitHubActionsArtifactChildV3, UPLOAD_ACTION_COMMIT, UPLOAD_ACTION_DIST_BLOB,
    run_artifact_child_v3, verify_upload_helper_v3,
)
from review_broker.github_prepared_artifact_v3 import PreparedUploadPlanV3, UploadStatusV3

NAME = "rb-v3-prepared-" + "a" * 64 + "-123-1"
ENV = {"ACTIONS_RUNTIME_TOKEN": "fake-runtime-only", "ACTIONS_RESULTS_URL": "https://fixture.invalid",
    "GITHUB_TOKEN": "fake-control", "REVIEW_BROKER_SOURCE_TOKEN": "fake-source",
    "REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY": "fake-private-key", "GH_TOKEN": "fake-gh",
    "REVIEW_BROKER_V3_LIVE_PREP_SHA": "fake-owner", "NODE_OPTIONS": "untrusted-loader",
    "GITHUB_OUTPUT": "/untrusted/output", "PATH": "/untrusted/bin"}


class ArtifactChildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        os.chmod(self.root, 0o700)
        self.calls = []

    def child(self, runner=None, verifier=lambda root: root / "dist/upload/index.js"):
        def execute(argv, env, log, **options):
            target = Path(env["INPUT_PATH"])
            self.calls.append((argv, env, target.read_bytes(), options))
            self.assertEqual(target.name, env["INPUT_NAME"])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
            return 0 if runner is None else runner(argv, env, log, **options)
        return GitHubActionsArtifactChildV3(trusted_root=self.root, node=Path("/trusted/node24"),
            private_base=self.root, environment=ENV, max_bytes=100000, runner=execute, verifier=verifier)

    def test_A02_A08_A17_A18_direct_bytes_exact_name_and_credential_allowlist(self):
        for name, raw in ((NAME, b"PK\x03\x04exact-zip\x00"),
                ("rb-v3-failure-observation-" + "b" * 64, b'{"schema_version":1}\n')):
            self.child().upload_bytes_once(name, raw, before_effect=lambda: None)
            argv, env, observed, _ = self.calls[-1]
            self.assertEqual(argv, ["/trusted/node24", str(self.root / "dist/upload/index.js")])
            self.assertEqual(observed, raw)
            self.assertEqual(env["INPUT_ARCHIVE"], "false")
            self.assertEqual(env["INPUT_OVERWRITE"], "false")
            self.assertEqual(env["INPUT_RETENTION-DAYS"], "30")
            self.assertEqual(env["ACTIONS_RUNTIME_TOKEN"], "fake-runtime-only")
            self.assertEqual(set(env) & set(ENV), {"ACTIONS_RUNTIME_TOKEN", "ACTIONS_RESULTS_URL"})
            self.assertEqual(Path(env["INPUT_PATH"]).name, name)

    def test_A09_A10_A14_one_call_ack_is_not_rest_authority(self):
        child = self.child()
        plan = PreparedUploadPlanV3(NAME, b"inventory", object())
        result = child.upload_once(plan, b"exact-bytes", before_effect=lambda: None)
        self.assertEqual(result.status, UploadStatusV3.ACK)
        self.assertFalse(hasattr(result, "artifact_id"))
        with self.assertRaisesRegex(ValueError, "ALREADY_ATTEMPTED"):
            child.upload_once(plan, b"exact-bytes", before_effect=lambda: None)
        self.assertEqual(len(self.calls), 1)

    def test_A11_A13_every_post_launch_error_is_unknown_and_never_respawned(self):
        def timeout(*args, **kwargs): raise TimeoutError("opaque retries exhausted")
        def exception(*args, **kwargs): raise OSError("opaque child error")
        for outcome in (lambda *a, **k: 1, lambda *a, **k: -15, timeout, exception):
            with self.subTest(outcome=outcome):
                child = self.child(outcome)
                before = len(self.calls)
                self.assertEqual(child.upload_bytes_once(NAME, b"raw", before_effect=lambda: None).status,
                    UploadStatusV3.UNKNOWN)
                with self.assertRaises(ValueError):
                    child.upload_bytes_once(NAME, b"raw", before_effect=lambda: None)
                self.assertEqual(len(self.calls) - before, 1)

    def test_A15_A16_movement_after_child_orphan_never_returns_permission(self):
        allowed = True
        def guard():
            if not allowed: raise ValueError("moved")
        def move(*args, **kwargs):
            nonlocal allowed
            allowed = False
            return 0
        child = self.child(move)
        with self.assertRaisesRegex(ValueError, "moved"):
            child.upload_bytes_once(NAME, b"orphan", before_effect=guard)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(list(self.root.glob("artifact-child-*/" + NAME))[0].read_bytes(), b"orphan")
        with self.assertRaisesRegex(ValueError, "ALREADY_ATTEMPTED"):
            child.upload_bytes_once(NAME, b"raw", before_effect=guard)

    def test_deterministic_local_refusal_has_zero_spawns(self):
        for name, raw in (("bad/name", b"raw"), (NAME + ".zip", b"raw"), (NAME, b"")):
            self.assertEqual(self.child().upload_bytes_once(name, raw, before_effect=lambda: None).status,
                UploadStatusV3.REFUSED)
        self.assertEqual(self.calls, [])

    def test_A01_exact_git_head_tree_and_actual_blob_are_all_checked(self):
        self.assertEqual(UPLOAD_ACTION_COMMIT, "cf430e030ddbb5b0abf93d22962f4752f3646cd9")
        self.assertEqual(UPLOAD_ACTION_DIST_BLOB, "7b3f92ae681d6eeca5f5e5e4cf892ad0dfb254ea")
        target = self.root / "dist/upload/index.js"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"substituted")
        good = [subprocess.CompletedProcess([], 0, (UPLOAD_ACTION_COMMIT + "\n").encode()),
            subprocess.CompletedProcess([], 0,
                ("100644 blob " + UPLOAD_ACTION_DIST_BLOB + "\tdist/upload/index.js\n").encode())]
        with patch("review_broker.actions_artifact_child_v3.subprocess.run", side_effect=good):
            with self.assertRaisesRegex(ValueError, "BYTES_MISMATCH"):
                verify_upload_helper_v3(self.root)
        with patch("review_broker.actions_artifact_child_v3.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, b"wrong-head\n")):
            with self.assertRaisesRegex(ValueError, "HEAD_MISMATCH"):
                verify_upload_helper_v3(self.root)

    def test_real_runner_bounds_private_output_and_timeout_without_official_helper(self):
        log = self.root / "output"
        code = run_artifact_child_v3([sys.executable, "-c", "import sys;sys.stdout.write('bounded')"],
            {}, log, timeout=5, max_log_bytes=100)
        self.assertEqual(code, 0)
        self.assertEqual(log.read_bytes(), b"bounded")
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)
        with self.assertRaisesRegex(ValueError, "OUTPUT_BUDGET"):
            run_artifact_child_v3([sys.executable, "-c", "import sys;sys.stdout.write('x'*10000)"],
                {}, self.root / "overflow", timeout=5, max_log_bytes=37)
        self.assertEqual((self.root / "overflow").stat().st_size, 37)
        with self.assertRaises(TimeoutError):
            run_artifact_child_v3([sys.executable, "-c", "import time;time.sleep(5)"],
                {}, self.root / "timeout", timeout=0.05, max_log_bytes=100)
