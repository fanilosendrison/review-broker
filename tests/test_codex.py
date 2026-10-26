import hashlib
import json
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
from review_broker.reviewer_profile import install_reviewer_profile, profile_name
from review_broker.packets import SourceRecord, build_packet


class CodexAdapterTests(unittest.TestCase):
    def test_command_is_pinned_and_read_only(self):
        command = build_command(Path("/schema.json"), Path("/final.json"), CodexPolicy(), "review-broker-test")
        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--ephemeral", command)
        self.assertNotIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertNotIn("--sandbox", command)
        self.assertIn("--strict-config", command)
        self.assertEqual(command[command.index("--profile") + 1], "review-broker-test")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-sol")
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertEqual(command[-1], "-")
        self.assertEqual(command.count("features.shell_tool=false"), 1)
        self.assertNotIn("features.shell_tool=true", command)
        self.assertNotIn("--enable", command)
        self.assertEqual(
            [command[index + 1] for index, arg in enumerate(command[:-1]) if arg == "-c"],
            ['features.shell_tool=false', 'model_reasoning_effort="xhigh"'],
        )
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertNotIn("OPENAI_API_KEY", command)
        self.assertNotIn("--api-key", command)
        self.assertEqual(command[command.index("--output-schema") + 1], "/schema.json")
        self.assertEqual(command[command.index("--output-last-message") + 1], "/final.json")

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
        command = build_command(Path("schema"), Path("final"), CodexPolicy(), "review-broker-test")
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
            packet = Path(temporary).resolve() / "packet"
            packet.mkdir()
            source = b"non-secret fixture\n"
            oid = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
            record = SourceRecord.from_bytes("sample/repo", "a" * 40, "fixture.md", oid, source)
            manifest = build_packet([record], request_id="request:sha256:" + "1" * 64,
                subject_id="subject:sha256:" + "2" * 64, mission_instruction="Review.",
                profile={"id": "code", "version": 1}, output_directory=packet)
            schema = packet / "response.schema.json"
            schema.write_text("{}")

            calls = []

            def runner(command, **kwargs):
                calls.append(list(command))
                self.assertFalse(kwargs["shell"])
                self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
                kwargs["stdout"].write(b'{"type":"turn.started"}\n')
                kwargs["stderr"].write(b"model unavailable")
                return subprocess.CompletedProcess(command, 1)

            home = packet.parent / "home"
            workspace = packet.parent / "workspace"
            (home / ".codex").mkdir(parents=True)
            workspace.mkdir()
            install_reviewer_profile(home, workspace, packet)
            environment = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}

            with self.assertRaisesRegex(InvocationError, "MODEL_UNAVAILABLE"):
                invoke_once(
                    packet,
                    schema,
                    "attempt:sha256:" + "a" * 64,
                    expected_packet_id=manifest["packet_id"],
                    broker_wheel_sha256="b" * 64,
                    trusted_workspace=workspace,
                    runner=runner,
                    environment=environment,
                )
            attempt = json.loads((packet / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(attempt["broker_wheel_sha256"], "b" * 64)
            self.assertEqual(calls, [attempt["argv"]])
            self.assertEqual(attempt["argv"].count("features.shell_tool=false"), 1)
            self.assertEqual(attempt["argv"][attempt["argv"].index("--profile") + 1],
                             profile_name(packet))
            self.assertEqual(attempt["permission_profile"], profile_name(packet))
            self.assertEqual(attempt["permission_profile_sha256"],
                             hashlib.sha256((home / ".codex" / (profile_name(packet) + ".config.toml")).read_bytes()).hexdigest())
            for name in (
                "attempt.json", "input-manifest.json", "prompt.sha256",
                "codex-events.jsonl", "codex-stderr.txt", "codex-exit-code.txt",
                "input-before.sha256", "input-after.sha256",
            ):
                self.assertTrue((packet / name).is_file(), name)
            with self.assertRaisesRegex(InvocationError, "ALREADY_ATTEMPTED"):
                invoke_once(
                    packet,
                    schema,
                    "attempt:sha256:" + "a" * 64,
                    expected_packet_id=manifest["packet_id"],
                    broker_wheel_sha256="b" * 64,
                    trusted_workspace=workspace,
                    runner=runner,
                    environment=environment,
                )
            self.assertEqual(calls, [attempt["argv"]])

    def test_model_transport_requires_prepared_packet_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            packet, home, workspace = (root / name for name in ("packet", "home", "workspace"))
            packet.mkdir()
            workspace.mkdir()
            (home / ".codex").mkdir(parents=True)
            source = b"safe\n"
            oid = hashlib.sha1(b"blob 5\0" + source).hexdigest()
            build_packet([SourceRecord.from_bytes("sample/repo", "a" * 40,
                "safe.md", oid, source)], request_id="request:sha256:" + "1" * 64,
                subject_id="subject:sha256:" + "2" * 64,
                mission_instruction="Review.", profile={"id": "code", "version": 1},
                output_directory=packet)
            schema = packet / "schema.json"
            schema.write_text("{}")
            install_reviewer_profile(home, workspace, packet)
            def forbidden_runner(*args, **kwargs):
                self.fail("model-capable transport was reached")
            with self.assertRaisesRegex(InvocationError, "PACKET_ID_MISMATCH"):
                invoke_once(packet, schema, "attempt", expected_packet_id="packet:sha256:" + "0" * 64,
                            broker_wheel_sha256="b" * 64, trusted_workspace=workspace,
                            environment={"HOME": str(home), "PATH": os.environ.get("PATH", "")},
                            runner=forbidden_runner)
            self.assertFalse((packet / "attempt.json").exists())

    def test_model_packet_rejects_hardlink_alias_before_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            packet = root / "packet"
            packet.mkdir()
            outside = root / "controlled-nonsecret.txt"
            outside.write_text("non-secret-canary")
            (packet / "input.txt").write_text("prompt")
            (packet / "input-manifest.json").write_text('{"sources":[]}')
            os.link(outside, packet / "broker-metadata.json")
            schema = packet / "schema.json"
            schema.write_text("{}")
            with self.assertRaisesRegex(InvocationError, "PACKET_TREE_UNTRUSTED"):
                invoke_once(packet, schema, "attempt", broker_wheel_sha256="b" * 64,
                            expected_packet_id="packet:sha256:" + "3" * 64,
                            trusted_workspace=root)
            self.assertFalse((packet / "attempt.json").exists())

    def test_missing_security_profile_is_rejected_before_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            packet = root / "packet"
            home = root / "home"
            workspace = root / "workspace"
            packet.mkdir()
            (home / ".codex").mkdir(parents=True)
            workspace.mkdir()
            (packet / "input.txt").write_bytes(b"prompt")
            (packet / "input-manifest.json").write_text('{"sources":[]}')
            schema = packet / "schema.json"
            schema.write_text("{}")
            environment = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}
            with self.assertRaisesRegex(InvocationError, "SECURITY_PROFILE_INVALID"):
                invoke_once(
                    packet,
                    schema,
                    "attempt",
                    expected_packet_id="packet:sha256:" + "3" * 64,
                    broker_wheel_sha256="b" * 64,
                    trusted_workspace=workspace,
                    environment=environment,
                )
            self.assertFalse((packet / "attempt.json").exists())

    def test_unarmed_invocation_is_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary)
            (packet / "input.txt").write_bytes(b"prompt")
            (packet / "input-manifest.json").write_text("{}")
            schema = packet / "schema.json"
            schema.write_text("{}")
            with self.assertRaisesRegex(InvocationError, "NOT_ARMED"):
                invoke_once(
                    packet,
                    schema,
                    "attempt",
                    expected_packet_id="packet:sha256:" + "3" * 64,
                    broker_wheel_sha256="b" * 64,
                    trusted_workspace=packet,
                    armed=False,
                )


if __name__ == "__main__":
    unittest.main()
