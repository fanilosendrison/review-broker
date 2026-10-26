from pathlib import Path
import tempfile
import unittest

from review_broker.reviewer_profile import (
    PROFILE_NAME,
    ReviewerProfileError,
    install_reviewer_profile,
    profile_bytes,
    verify_reviewer_profile,
)


class ReviewerProfileTests(unittest.TestCase):
    def roots(self, root: Path) -> tuple[Path, Path]:
        root = root.resolve()
        home = root / "home"
        workspace = root / "workspace"
        (home / ".codex").mkdir(parents=True)
        workspace.mkdir()
        return home, workspace

    def test_profile_denies_runtime_home_and_trusted_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            text = profile_bytes(home, workspace).decode("utf-8")
            self.assertIn('default_permissions = "review-broker"', text)
            self.assertIn(f'"{home}" = "deny"', text)
            self.assertIn(f'"{workspace}" = "deny"', text)
            self.assertIn('"/" = "read"', text)
            self.assertIn("enabled = false", text)
            self.assertIn('inherit = "none"', text)
            self.assertIn('allow_login_shell = false', text)

    def test_install_and_verify_exact_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            path = install_reviewer_profile(home, workspace)
            self.assertEqual(path, home / ".codex" / f"{PROFILE_NAME}.config.toml")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            verify_reviewer_profile(home, workspace)

    def test_base_user_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            (home / ".codex" / "config.toml").write_text("model = 'other'\n")
            with self.assertRaisesRegex(ReviewerProfileError, "BASE_USER_CONFIG_PRESENT"):
                install_reviewer_profile(home, workspace)

    def test_changed_profile_is_rejected_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            path = home / ".codex" / f"{PROFILE_NAME}.config.toml"
            path.write_text("untrusted = true\n")
            before = path.read_bytes()
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_MISMATCH"):
                install_reviewer_profile(home, workspace)
            self.assertEqual(path.read_bytes(), before)

    def test_symlinked_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            target = Path(temporary) / "target"
            target.write_bytes(profile_bytes(home, workspace))
            profile = home / ".codex" / f"{PROFILE_NAME}.config.toml"
            profile.symlink_to(target)
            with self.assertRaisesRegex(ReviewerProfileError, "PROFILE_SYMLINK"):
                verify_reviewer_profile(home, workspace)

    def test_profile_contains_no_credential_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, workspace = self.roots(Path(temporary))
            rendered = profile_bytes(home, workspace)
            for forbidden in (b"access_token", b"refresh_token", b"auth.json", b"Bearer "):
                self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
