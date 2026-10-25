import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.codex import (
    CodexPolicy,
    InvocationError,
    build_command,
    classify_failure,
    ensure_cli_compatibility,
    invoke_once,
    sanitized_environment,
)


class CodexAdapterTests(unittest.TestCase):
    def test_command_is_pinned_and_read_only(self):
        command = build_command(Path("/schema.json"), Path("/final.json"), CodexPolicy())
        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-sol")
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertEqual(command[-1], "-")

    def test_api_and_github_credentials_are_removed(self):
        source = {
            "PATH": os.environ.get("PATH", ""),
            "OPENAI_API_KEY": "forbidden",
            "CODEX_API_KEY": "forbidden",
            "OPENAI_BASE_URL": "forbidden",
            "GH_TOKEN": "forbidden",
            "GITHUB_TOKEN": "forbidden",
            "CODEX_HOME": "/qualified/auth/home",
        }
        cleaned, removed = sanitized_environment(source)
        self.assertEqual(cleaned["CODEX_HOME"], "/qualified/auth/home")
        self.assertTrue({"OPENAI_API_KEY", "CODEX_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"} <= set(removed))
        self.assertNotIn("OPENAI_API_KEY", cleaned)

    def test_installed_help_must_support_every_qualified_flag(self):
        command = build_command(Path("schema"), Path("final"), CodexPolicy())
        help_text = " ".join(x for x in command if x.startswith("--"))
        ensure_cli_compatibility(help_text)
        with self.assertRaisesRegex(InvocationError, "UNSUPPORTED_FLAG"):
            ensure_cli_compatibility(help_text.replace("--ignore-rules", ""))

    def test_failure_classification_is_explicit(self):
        cases = {
            "model gpt-5.6-sol is not available": "MODEL_UNAVAILABLE",
            "login required; authentication expired": "OAUTH_EXPIRED",
            "usage limit reached quota exceeded": "QUOTA_EXHAUSTED",
            "process terminated unexpectedly": "CODEX_CRASH",
        }
        for message, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify_failure(message), expected)

    def test_one_shot_failure_preserves_evidence_and_forbids_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary)
            (packet / "input.txt").write_bytes(b"prompt")
            (packet / "input-manifest.json").write_text('{"packet_id":"packet:sha256:x"}')
            schema = packet / "response.schema.json"
            schema.write_text("{}")

            def runner(command, **kwargs):
                kwargs["stdout"].write(b'{"type":"turn.started"}\n')
                kwargs["stderr"].write(b"model unavailable")
                return subprocess.CompletedProcess(command, 1)

            with self.assertRaisesRegex(InvocationError, "MODEL_UNAVAILABLE"):
                invoke_once(packet, schema, "attempt:sha256:" + "a" * 64, runner=runner)
            for name in (
                "attempt.json", "input-manifest.json", "prompt.sha256",
                "codex-events.jsonl", "codex-stderr.txt", "codex-exit-code.txt",
                "input-before.sha256", "input-after.sha256",
            ):
                self.assertTrue((packet / name).is_file(), name)
            with self.assertRaisesRegex(InvocationError, "ALREADY_ATTEMPTED"):
                invoke_once(packet, schema, "attempt:sha256:" + "a" * 64, runner=runner)

    def test_unarmed_invocation_is_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary)
            (packet / "input.txt").write_bytes(b"prompt")
            (packet / "input-manifest.json").write_text("{}")
            schema = packet / "schema.json"
            schema.write_text("{}")
            with self.assertRaisesRegex(InvocationError, "NOT_ARMED"):
                invoke_once(packet, schema, "attempt", armed=False)


if __name__ == "__main__":
    unittest.main()
