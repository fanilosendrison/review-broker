"""Operator evidence hygiene: inert fixtures, no live credential or network access."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qualification-evidence.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("qualification_evidence_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvidenceHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.inert = "synthetic-test-value-not-a-real-credential"

    def test_nested_sensitive_fields_rejected_without_value_in_diagnostic(self):
        for key in ("temp_clone_token", "AUTHORIZATION", "myPassword", "private_key",
                    "app-secret", "Cookie", "credential", "privateKey"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as caught:
                    self.tool.check_json({"outer": [{key: self.inert}]})
                self.assertNotIn(self.inert, str(caught.exception))

    def test_empty_fields_and_exact_nonsecret_counter_allowlist(self):
        self.tool.check_json({"token": "", "secret": None, "cookie": [],
                              "SOURCE_APP_TOKEN_MINTS": 0, "token_mint_count": 2})
        for value in (self.inert, True, -1, {"token": self.inert}):
            with self.assertRaises(ValueError):
                self.tool.check_json({"token_mint_count": value})
        with self.assertRaises(ValueError):
            self.tool.check_json(dict(other_token_mint_count=0))

    def test_projection_drops_unneeded_fields_before_inspection(self):
        value = {"id": 5, "full_name": "owner/repo", "temp_clone_token": self.inert}
        self.assertEqual(self.tool.project_json(value, "{id,full_name}"),
                         {"id": 5, "full_name": "owner/repo"})
        with self.assertRaises(ValueError):
            self.tool.project_json(value, "{temp_clone_token}")
        with self.assertRaises(ValueError):
            self.tool.project_json(value, ".")

    def test_projection_nested_arrays_and_explicit_filter_required(self):
        value = {"nodes": [{"name": "a", "target": {"oid": "b"}, "secret": self.inert}]}
        expected = {"nodes": [{"name": "a", "target": {"oid": "b"}}]}
        self.assertEqual(self.tool.project_json(value,
                         "{nodes:[.nodes[]|{name,target:{oid:.target.oid}}]}"), expected)
        for selector in ("", ".", ".[]", "not a jq expression"):
            with self.assertRaises(ValueError):
                self.tool.project_json(value, selector)

    def test_text_and_nested_serialized_fields_are_checked(self):
        unsafe = json.dumps({"temp_clone_token": self.inert})
        for text in (unsafe, "prefix " + unsafe, json.dumps({"output": unsafe}),
                     "Authorization: Bearer " + self.inert,
                     "authorization: Basic " + self.inert,
                     "Proxy-Authorization: token " + self.inert):
            with self.subTest(text_kind=text[:10]):
                with self.assertRaises(ValueError):
                    self.tool.check_text(text)
        for value in (1, False, [self.inert], {"value": self.inert}):
            with self.assertRaises(ValueError):
                self.tool.check_text("log-prefix " + json.dumps({"secret": value}))
        with self.assertRaises(ValueError):
            self.tool.check_text(json.dumps(json.dumps({"secret": self.inert})))
        self.tool.check_text("Ran 15 tests\nOK\nSOURCE_APP_TOKEN_MINTS=0\n")
        self.tool.check_text(json.dumps({"temp_clone_token": "[REDACTED]"}))

    def test_project_cli_never_writes_unsafe_or_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            value = {"id": 9, "temp_clone_token": self.inert}
            command = [sys.executable, str(SCRIPT), "project", "--filter", '{id}',
                       "--output", str(output)]
            result = subprocess.run(command, input=json.dumps(value), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), {"id": 9})
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            before = output.read_bytes()
            result = subprocess.run(command, input=json.dumps(value), text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            output.unlink()
            command[command.index('{id}')] = '{temp_clone_token}'
            result = subprocess.run(command, input=json.dumps(value), text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertNotIn(self.inert, result.stdout + result.stderr)

    def test_operator_source_and_tests_are_safe_reviewer_input(self):
        # Unsafe test objects are constructed only in memory, never logged as data.
        self.tool.check_text(SCRIPT.read_text())
        self.tool.check_text(Path(__file__).read_text())

    def test_scan_cli_rejects_unstructured_authorization_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.txt"
            path.write_text("Authorization: Bearer " + self.inert)
            result = subprocess.run([sys.executable, str(SCRIPT), "scan", str(path)],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(self.inert, result.stdout + result.stderr)
            path.write_text("SOFTWARE_CORRECTNESS_REVIEW=GO\n")
            result = subprocess.run([sys.executable, str(SCRIPT), "scan", str(path)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
