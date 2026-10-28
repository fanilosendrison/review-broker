import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.codex import InvocationError, invoke_once
from review_broker.codex_runtime_identity import (
    CodexRuntimeIdentityError,
    VerifiedCodexRuntime,
    load_codex_release_trust,
    verify_codex_release_archive,
    verify_codex_runtime,
)
from review_broker.packets import SourceRecord, build_packet
from review_broker.reviewer_profile import install_reviewer_profile


def verified_runtime(root: Path) -> VerifiedCodexRuntime:
    return VerifiedCodexRuntime(
        executable=root / "protected" / "bin" / "codex",
        launcher_selected=root / "bin" / "codex",
        launcher_resolved=root / "package" / "bin" / "codex.js",
        launcher_sha256="1" * 64,
        installed_native=root / "package" / "native" / "codex",
        native_sha256="2" * 64,
        protected_runtime_root=root / "protected",
        distribution="@openai/codex",
        distribution_version="0.164.0",
        platform_alias="@openai/codex-linux-x64",
        platform_version="0.164.0-linux-x64",
        root_dist_integrity="sha512-root-fixture",
        platform_dist_integrity="sha512-platform-fixture",
    )


class CodexRuntimeIdentityBaselineTests(unittest.TestCase):
    def _prepared_attempt(self, root: Path) -> tuple[Path, Path, Path, Path, str]:
        packet = root / "packet"
        home = root / "home"
        workspace = root / "workspace"
        packet.mkdir()
        workspace.mkdir()
        (home / ".codex").mkdir(parents=True)
        source = b"controlled non-secret fixture\n"
        oid = hashlib.sha1(
            b"blob " + str(len(source)).encode() + b"\0" + source
        ).hexdigest()
        manifest = build_packet(
            [SourceRecord.from_bytes("sample/repo", "a" * 40, "fixture.md", oid, source)],
            request_id="request:sha256:" + "1" * 64,
            subject_id="subject:sha256:" + "2" * 64,
            mission_instruction="Review.",
            profile={"id": "code", "version": 1},
            output_directory=packet,
        )
        schema = packet / "response.schema.json"
        schema.write_text("{}", encoding="utf-8")
        install_reviewer_profile(home, workspace, packet)
        return packet, home, workspace, schema, manifest["packet_id"]

    def _invoke_with_path(self, root: Path, path: Path) -> tuple[bool, Path]:
        packet, home, workspace, schema, packet_id = self._prepared_attempt(root)
        called = False

        def forbidden_runner(command, **kwargs):
            nonlocal called
            called = True
            return subprocess.CompletedProcess(command, 1)

        with self.assertRaisesRegex(InvocationError, "CODEX_RUNTIME_IDENTITY"):
            invoke_once(
                packet,
                schema,
                "attempt:sha256:" + "a" * 64,
                expected_packet_id=packet_id,
                broker_wheel_sha256="b" * 64,
                trusted_workspace=workspace,
                codex_runtime_root=root / "protected",
                runner=forbidden_runner,
                environment={"HOME": str(home), "PATH": str(path)},
            )
        return called, packet

    def test_unverified_runtime_variants_are_rejected_before_transport(self):
        scenarios = (
            "path-substitution",
            "version-spoof",
            "modified-launcher",
            "modified-native",
            "missing-native",
            "unexpected-symlink-target",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                binary_directory = root / "bin"
                installation = root / "installation"
                binary_directory.mkdir()
                installation.mkdir()
                launcher = installation / "codex.js"
                launcher.write_bytes(
                    b"official-launcher-fixture\n"
                    if scenario not in {"version-spoof", "modified-launcher"}
                    else b"modified launcher claiming codex-cli 0.164.0\n"
                )
                native = installation / "codex"
                if scenario != "missing-native":
                    native.write_bytes(
                        b"official-native-fixture\n"
                        if scenario != "modified-native"
                        else b"modified-native-fixture\n"
                    )
                selected = binary_directory / "codex"
                if scenario == "unexpected-symlink-target":
                    outside = root / "outside-launcher"
                    outside.write_bytes(b"unexpected target\n")
                    selected.symlink_to(outside)
                elif scenario in {"modified-launcher", "modified-native", "missing-native"}:
                    selected.symlink_to(launcher)
                else:
                    selected.write_bytes(launcher.read_bytes())
                    selected.chmod(0o700)

                called, packet = self._invoke_with_path(root, binary_directory)
                self.assertFalse(called)
                self.assertFalse((packet / "attempt.json").exists())

    def test_attempt_evidence_requires_verified_executable_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            binary_directory = root / "bin"
            binary_directory.mkdir()
            fake = binary_directory / "codex"
            fake.write_bytes(b"controlled substitution\n")
            fake.chmod(0o700)
            packet, home, workspace, schema, packet_id = self._prepared_attempt(root)

            def runner(command, **kwargs):
                kwargs["stderr"].write(b"controlled failure")
                return subprocess.CompletedProcess(command, 1)

            with self.assertRaises(InvocationError):
                invoke_once(
                    packet,
                    schema,
                    "attempt:sha256:" + "a" * 64,
                    expected_packet_id=packet_id,
                    broker_wheel_sha256="b" * 64,
                    trusted_workspace=workspace,
                    codex_runtime_root=root / "protected",
                    runner=runner,
                    runtime_verifier=lambda child, runtime_root: verified_runtime(root),
                    environment={"HOME": str(home), "PATH": str(binary_directory)},
                )
            attempt = json.loads((packet / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(
                attempt["runtime_identity_verification"],
                "VERIFIED_OFFICIAL_NPM_ARTIFACT",
            )
            self.assertRegex(attempt["codex_launcher_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(attempt["codex_native_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(os.path.isabs(attempt["argv"][0]))


class CodexRuntimeIdentityVerifierTests(unittest.TestCase):
    def _fixture(self, root: Path):
        package = root / "npm" / "@openai" / "codex"
        launcher = package / "bin" / "codex.js"
        platform_root = package / "node_modules" / "@openai" / "codex-linux-x64"
        target_root = platform_root / "vendor" / "x86_64-unknown-linux-musl"
        native = target_root / "bin" / "codex"
        selected_directory = root / "path"
        protected_anchor = root / "protected-anchor"
        protected = protected_anchor / "codex-0.164.0-linux-x64"
        for directory in (
            launcher.parent, native.parent, selected_directory,
            protected / "bin",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        launcher_bytes = b"official launcher fixture\n"
        native_bytes = b"official native fixture\n"
        root_manifest = self._json_bytes({
            "name": "@openai/codex",
            "version": "0.164.0",
            "bin": {"codex": "bin/codex.js"},
            "optionalDependencies": {
                "@openai/codex-linux-x64": "npm:@openai/codex@0.164.0-linux-x64"
            },
        })
        platform_manifest = self._json_bytes({
            "name": "@openai/codex",
            "version": "0.164.0-linux-x64",
            "os": ["linux"],
            "cpu": ["x64"],
        })
        target_manifest = self._json_bytes({
            "layoutVersion": 1,
            "version": "0.164.0",
            "target": "x86_64-unknown-linux-musl",
            "entrypoint": "bin/codex",
        })
        launcher.write_bytes(launcher_bytes)
        launcher.chmod(0o755)
        native.write_bytes(native_bytes)
        native.chmod(0o755)
        (package / "package.json").write_bytes(root_manifest)
        (platform_root / "package.json").write_bytes(platform_manifest)
        (target_root / "codex-package.json").write_bytes(target_manifest)
        (protected / "bin" / "codex").write_bytes(native_bytes)
        (protected / "bin" / "codex").chmod(0o555)
        (protected / "codex-package.json").write_bytes(target_manifest)
        (selected_directory / "codex").symlink_to(launcher)
        for path in (protected / "codex-package.json",):
            path.chmod(0o444)
        for directory in (protected / "bin", protected, protected_anchor):
            directory.chmod(0o555)
        trust = {
            "schema_version": 1,
            "distribution": {
                "name": "@openai/codex",
                "version": "0.164.0",
                "registry_metadata_url": "https://registry.invalid/root",
                "tarball_url": "https://registry.invalid/root.tgz",
                "dist_integrity": "sha512-" + base64.b64encode(b"r" * 64).decode(),
                "archive_sha256": "0" * 64,
                "package_json_sha256": self._sha256(root_manifest),
                "launcher_entry": "bin/codex.js",
                "launcher_sha256": self._sha256(launcher_bytes),
            },
            "platforms": {
                "linux-x86_64": {
                    "system": "Linux",
                    "machine": "x86_64",
                    "npm_alias": "@openai/codex-linux-x64",
                    "npm_spec": "npm:@openai/codex@0.164.0-linux-x64",
                    "published_name": "@openai/codex",
                    "published_version": "0.164.0-linux-x64",
                    "registry_metadata_url": "https://registry.invalid/platform",
                    "tarball_url": "https://registry.invalid/platform.tgz",
                    "dist_integrity": "sha512-" + base64.b64encode(b"p" * 64).decode(),
                    "archive_sha256": "3" * 64,
                    "package_json_sha256": self._sha256(platform_manifest),
                    "package_relative_path": "node_modules/@openai/codex-linux-x64",
                    "target": "x86_64-unknown-linux-musl",
                    "target_manifest_entry": "vendor/x86_64-unknown-linux-musl/codex-package.json",
                    "target_manifest_sha256": self._sha256(target_manifest),
                    "native_entry": "vendor/x86_64-unknown-linux-musl/bin/codex",
                    "native_sha256": self._sha256(native_bytes),
                    "protected_runtime_directory": "codex-0.164.0-linux-x64",
                }
            },
        }
        return {
            "trust": trust,
            "environment": {"PATH": str(selected_directory)},
            "package": package,
            "launcher": launcher,
            "platform_root": platform_root,
            "native": native,
            "protected": protected,
            "anchor": protected_anchor,
            "native_bytes": native_bytes,
        }

    def _verify(self, fixture, **overrides):
        arguments = {
            "_trust": fixture["trust"],
            "_system": "Linux",
            "_machine": "x86_64",
            "_expected_owner_uid": os.getuid(),
            "_protection_anchor": fixture["anchor"],
        }
        arguments.update(overrides)
        return verify_codex_runtime(
            fixture["environment"], fixture["protected"], **arguments
        )

    def test_exact_release_and_protected_native_are_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(Path(temporary).resolve())
            runtime = self._verify(fixture)
            self.assertEqual(runtime.native_sha256, self._sha256(fixture["native_bytes"]))
            self.assertEqual(runtime.executable, fixture["protected"] / "bin" / "codex")
            self.assertEqual(
                runtime.evidence()["runtime_identity_verification"],
                "VERIFIED_OFFICIAL_NPM_ARTIFACT",
            )
            self.assertFalse(runtime.evidence()["node_interpreter_used"])

    def test_substitutions_and_missing_runtime_fail_closed(self):
        scenarios = (
            "ambiguous-path", "version-spoof", "launcher-change", "native-change",
            "missing-launcher", "missing-platform", "platform-symlink", "mutable-protected",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                fixture = self._fixture(Path(temporary).resolve())
                if scenario == "ambiguous-path":
                    other = Path(temporary) / "other"
                    other.mkdir()
                    candidate = other / "codex"
                    candidate.write_bytes(b"substitute")
                    candidate.chmod(0o755)
                    fixture["environment"]["PATH"] = os.pathsep.join(
                        (str(other), fixture["environment"]["PATH"])
                    )
                elif scenario == "version-spoof":
                    manifest = fixture["package"] / "package.json"
                    manifest.write_bytes(manifest.read_bytes().replace(b"0.164.0", b"0.164.1", 1))
                elif scenario == "launcher-change":
                    fixture["launcher"].write_bytes(b"modified launcher claiming 0.164.0")
                elif scenario == "native-change":
                    fixture["native"].write_bytes(b"modified native")
                elif scenario == "missing-launcher":
                    fixture["launcher"].unlink()
                elif scenario == "missing-platform":
                    (fixture["platform_root"] / "package.json").unlink()
                elif scenario == "platform-symlink":
                    original = fixture["platform_root"]
                    moved = original.with_name("outside-platform")
                    original.rename(moved)
                    original.symlink_to(moved, target_is_directory=True)
                elif scenario == "mutable-protected":
                    fixture["protected"].chmod(0o777)
                with self.assertRaises(CodexRuntimeIdentityError):
                    self._verify(fixture)

    def test_unsupported_architecture_and_archive_integrity_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = self._fixture(root)
            with self.assertRaisesRegex(CodexRuntimeIdentityError, "PLATFORM_UNSUPPORTED"):
                self._verify(fixture, _machine="aarch64")
            archive = root / "release.tgz"
            archive.write_bytes(b"official archive fixture")
            integrity = "sha512-" + base64.b64encode(
                hashlib.sha512(b"different archive").digest()
            ).decode()
            with self.assertRaisesRegex(CodexRuntimeIdentityError, "INTEGRITY_MISMATCH"):
                verify_codex_release_archive(archive, integrity)

    def test_source_replacement_after_verification_cannot_select_execution_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(Path(temporary).resolve())
            runtime = self._verify(fixture)
            fixture["native"].write_bytes(b"replacement after verification")
            self.assertEqual(runtime.executable.read_bytes(), fixture["native_bytes"])
            self.assertNotEqual(runtime.executable, fixture["native"])

    def test_published_trust_record_has_exact_supported_release(self):
        trust = load_codex_release_trust()
        self.assertEqual(trust["distribution"]["version"], "0.164.0")
        platform_value = trust["platforms"]["linux-x86_64"]
        self.assertEqual(platform_value["published_version"], "0.164.0-linux-x64")
        self.assertEqual(platform_value["npm_alias"], "@openai/codex-linux-x64")

    def test_workflow_preflights_identity_before_durable_arm(self):
        workflow = (
            Path(__file__).parents[1] / ".github" / "workflows" / "review-request.yml"
        ).read_text(encoding="utf-8")
        preflight = workflow.index("internal-preflight-codex-runtime")
        arm = workflow.index("Durably arm exactly one invocation")
        invoke = workflow.index("internal-invoke")
        self.assertLess(preflight, arm)
        self.assertLess(arm, invoke)
        self.assertIn("--codex-runtime-root \"$CODEX_RUNTIME_ROOT\"", workflow)
        self.assertIn("REVIEW_BROKER_SECURITY_QUALIFIED", workflow)

    @staticmethod
    def _json_bytes(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    @staticmethod
    def _sha256(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    unittest.main()
