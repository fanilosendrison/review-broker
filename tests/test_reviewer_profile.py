from pathlib import Path
import os
from unittest import mock
import tempfile
import unittest

from review_broker.reviewer_profile import (
    ReviewerProfileError,
    install_reviewer_profile,
    profile_bytes,
    profile_name,
    verify_reviewer_profile,
)


class ReviewerProfileTests(unittest.TestCase):
    def roots(self, root: Path) -> tuple[Path, Path, Path]:
        root = root.resolve()
        home = root / "home"
        workspace = root / "workspace"
        packet = root / "packet"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        packet.mkdir()
        return home, workspace, packet

    def test_profile_does_not_grant_root_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            text = profile_bytes(home, workspace, packet).decode("utf-8")
            self.assertNotIn('"/" = "read"', text)
            self.assertIn('":minimal" = "read"', text)
            self.assertIn(f'"{packet}" = "read"', text)

    def test_profile_denies_runtime_home_and_trusted_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            text = profile_bytes(home, workspace, packet).decode("utf-8")
            self.assertIn(f'default_permissions = "{profile_name(packet)}"', text)
            self.assertIn(f'"{home}" = "deny"', text)
            self.assertIn(f'"{workspace}" = "deny"', text)
            self.assertIn("enabled = false", text)
            self.assertIn('inherit = "none"', text)
            self.assertIn('allow_login_shell = false', text)

    def test_packet_cannot_overlap_privileged_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            for unsafe in (home, home / ".codex", workspace, workspace.parent):
                with self.subTest(unsafe=unsafe):
                    with self.assertRaisesRegex(ReviewerProfileError, "OVERLAP"):
                        profile_bytes(home, workspace, unsafe)

    def test_install_and_verify_exact_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            path = install_reviewer_profile(home, workspace, packet)
            self.assertEqual(path, home / ".codex" / f"{profile_name(packet)}.config.toml")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            verify_reviewer_profile(home, workspace, packet)

    def test_distinct_actions_attempts_keep_immutable_profiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home, workspace, _ = self.roots(root)
            first = root / "runs" / "123" / "1" / "evidence"
            second = root / "runs" / "124" / "1" / "evidence"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            first_path = install_reviewer_profile(home, workspace, first)
            before = first_path.read_bytes()
            second_path = install_reviewer_profile(home, workspace, second)
            self.assertNotEqual(first_path, second_path)
            self.assertEqual(first_path.read_bytes(), before)
            verify_reviewer_profile(home, workspace, first)
            verify_reviewer_profile(home, workspace, second)

    def test_partial_and_conflicting_profile_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            profile = home / ".codex" / f"{profile_name(packet)}.config.toml"
            for content in (b"", b"untrusted = true\n"):
                profile.write_bytes(content)
                profile.chmod(0o600)
                with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_MISMATCH"):
                    install_reviewer_profile(home, workspace, packet)
                self.assertEqual(profile.read_bytes(), content)

    def test_ownership_mode_and_link_attacks_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            profile = install_reviewer_profile(home, workspace, packet)
            profile.chmod(0o644)
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_MODE_INVALID"):
                verify_reviewer_profile(home, workspace, packet)
            profile.chmod(0o600)
            with mock.patch("review_broker.reviewer_profile.os.getuid", return_value=-1):
                with self.assertRaisesRegex(ReviewerProfileError, "CODEX_HOME_UNTRUSTED|PROFILE_OWNER_INVALID"):
                    verify_reviewer_profile(home, workspace, packet)
            alias = Path(temporary) / "alias"
            os.link(profile, alias)
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_TYPE_INVALID"):
                verify_reviewer_profile(home, workspace, packet)
            alias.unlink()
            profile.unlink()
            profile.symlink_to(home / ".codex" / "auth.json")
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_SYMLINK"):
                install_reviewer_profile(home, workspace, packet)
            profile.unlink()
            self.assertFalse(profile.exists())

    def test_untrusted_codex_home_cannot_deploy(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            (home / ".codex").chmod(0o777)
            with self.assertRaisesRegex(ReviewerProfileError, "CODEX_HOME_UNTRUSTED"):
                install_reviewer_profile(home, workspace, packet)

    def test_base_user_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            (home / ".codex" / "config.toml").write_text("model = 'other'\n")
            with self.assertRaisesRegex(ReviewerProfileError, "BASE_USER_CONFIG_PRESENT"):
                install_reviewer_profile(home, workspace, packet)

    def test_changed_profile_is_rejected_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            path = home / ".codex" / f"{profile_name(packet)}.config.toml"
            path.write_text("untrusted = true\n")
            path.chmod(0o600)
            before = path.read_bytes()
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_MISMATCH"):
                install_reviewer_profile(home, workspace, packet)
            self.assertEqual(path.read_bytes(), before)

    def test_symlinked_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            target = Path(temporary) / "target"
            target.write_bytes(profile_bytes(home, workspace, packet))
            profile = home / ".codex" / f"{profile_name(packet)}.config.toml"
            profile.symlink_to(target)
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_SYMLINK"):
                verify_reviewer_profile(home, workspace, packet)

    def test_profile_contains_no_credential_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace, packet = self.roots(Path(temporary))
            rendered = profile_bytes(home, workspace, packet)
            for forbidden in (b"access_token", b"refresh_token", b"auth.json", b"Bearer "):
                self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
