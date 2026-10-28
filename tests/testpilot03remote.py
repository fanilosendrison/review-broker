"""Adversarial offline tests for the bounded RB-PILOT-03 remote adapter."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.pilot03_remote_artifacts import ARTIFACT_PATHS, Pilot03RemoteArtifacts
from review_broker.pilot_private_retention import PilotRetentionError


class Runner:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return self.value


class Pilot03RemoteTests(unittest.TestCase):
    def adapter(self, value):
        temporary = tempfile.NamedTemporaryFile()
        self.addCleanup(temporary.close)
        runner = Runner(value)
        return Pilot03RemoteArtifacts("expected-space", Path(temporary.name), runner=runner), runner

    def test_sanitary_observation_uses_stdin_and_no_shell(self):
        data = b"safe"
        value = {
            "present": True, "regular": True, "symlink": False, "link_count": 1,
            "byte_length": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "credential_screen": "PASS_NO_MATCH",
        }
        adapter, runner = self.adapter(subprocess.CompletedProcess([], 0, json.dumps(value), ""))
        self.assertEqual(adapter.observe("codex-final.json").sha256, value["sha256"])
        command, kwargs = runner.calls[0]
        self.assertEqual(command[0], "ssh")
        self.assertNotIn("bash", command)
        self.assertFalse(kwargs["shell"])
        self.assertIn("input", kwargs)
        self.assertNotIn(data.decode(), json.dumps(value))

    def test_absent_and_adversarial_metadata(self):
        absent = {"present": False, "regular": False, "symlink": False, "link_count": 0,
                  "byte_length": 0, "sha256": None, "credential_screen": "UNDETERMINED"}
        adapter, _ = self.adapter(subprocess.CompletedProcess([], 0, json.dumps(absent), ""))
        self.assertFalse(adapter.observe("pilot-summary.json").present)
        for output in ("{", json.dumps({**absent, "raw": "secret"})):
            adapter, _ = self.adapter(subprocess.CompletedProcess([], 0, output, ""))
            with self.assertRaises(PilotRetentionError):
                adapter.observe("pilot-summary.json")

    def test_unknown_paths_and_raw_remote_output_are_refused(self):
        adapter, _ = self.adapter(subprocess.CompletedProcess([], 0, "x" * 3000, ""))
        with self.assertRaises(PilotRetentionError):
            adapter.observe("../credential")
        with self.assertRaises(PilotRetentionError):
            adapter.observe("codex-events.jsonl")
        self.assertEqual(set(ARTIFACT_PATHS), {
            "pilot-claim.json", "pilot-armed.json", "pilot-summary.json", "pilot-failure.json",
            "codex-events.jsonl", "codex-stderr.txt", "codex-final.json", "codex-exit-code.txt",
        })
