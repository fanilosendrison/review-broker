"""Offline validation tests for controlled Codespaces SSH host aliases."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from review_broker.pilot03_ssh_config import Pilot03SshConfigError, validate_ssh_host_alias
from review_broker.pilot03_transport import Pilot03CodespaceTransport

CODESPACE = "expected-codespace"
ALIAS = "independent-host-alias"


def config_text(alias=ALIAS, codespace=CODESPACE, proxy_command=None):
    command = proxy_command or f"gh cs ssh -c {codespace} --stdio"
    return (
        f"Host {alias}\n"
        f"  ProxyCommand {command}\n"
        "  IdentityFile /tmp/synthetic-key\n"
    )


class Pilot03SshConfigTests(unittest.TestCase):
    def config(self, temporary, text=None):
        path = Path(temporary) / "ssh.conf"
        path.write_text(config_text() if text is None else text)
        path.chmod(0o600)
        return path

    def test_distinct_and_identical_literal_aliases_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.config(temporary)
            self.assertEqual(validate_ssh_host_alias(
                codespace_identity=CODESPACE, ssh_host_alias=ALIAS, ssh_config=path,
            ), ALIAS)
        with tempfile.TemporaryDirectory() as temporary:
            path = self.config(temporary, config_text(CODESPACE))
            self.assertEqual(validate_ssh_host_alias(
                codespace_identity=CODESPACE, ssh_host_alias=CODESPACE, ssh_config=path,
            ), CODESPACE)

    def test_all_four_exact_proxycommand_grammars_are_accepted(self):
        commands = (
            f"gh cs ssh -c {CODESPACE} --stdio",
            f"gh codespace ssh -c {CODESPACE} --stdio",
            f"gh cs ssh --codespace {CODESPACE} --stdio",
            f"gh codespace ssh --codespace {CODESPACE} --stdio",
            f"gh\tcs\tssh\t-c\t{CODESPACE}\t--stdio",
        )
        for command in commands:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                path = self.config(temporary, config_text(proxy_command=command))
                self.assertEqual(validate_ssh_host_alias(
                    codespace_identity=CODESPACE, ssh_host_alias=ALIAS, ssh_config=path,
                ), ALIAS)

    def test_shell_suffixes_and_extra_arguments_are_rejected(self):
        commands = (
            f"gh cs ssh -c {CODESPACE} --stdio ; echo extra",
            f"gh cs ssh -c {CODESPACE} --stdio && echo extra",
            f"gh cs ssh -c {CODESPACE} --stdio || echo extra",
            f"gh cs ssh -c {CODESPACE} --stdio | echo extra",
            f"gh cs ssh -c {CODESPACE} --stdio > output",
            f"gh cs ssh -c {CODESPACE} --stdio $(echo extra)",
            f"gh cs ssh -c {CODESPACE} --stdio `echo extra`",
            f"gh cs ssh -c {CODESPACE} --stdio --debug",
            f"gh cs ssh -c {CODESPACE} extra --stdio",
            f"gh cs ssh -c {CODESPACE} -c {CODESPACE} --stdio",
            f"gh cs ssh -c {CODESPACE} --stdio --stdio",
            "gh cs ssh -c another-codespace --stdio",
            f'gh cs ssh -c "{CODESPACE}" --stdio',
            f"gh cs ssh -c {CODESPACE} \\--stdio",
            f"env gh cs ssh -c {CODESPACE} --stdio",
            f"sh -c gh cs ssh -c {CODESPACE} --stdio",
        )
        for command in commands:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                path = self.config(temporary, config_text(proxy_command=command))
                with self.assertRaisesRegex(
                    Pilot03SshConfigError, "RB03_SSH_CODESPACE_BINDING_MISMATCH",
                ):
                    validate_ssh_host_alias(
                        codespace_identity=CODESPACE,
                        ssh_host_alias=ALIAS,
                        ssh_config=path,
                    )

    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH client unavailable")
    def test_openssh_effective_proxy_preserves_suffix_but_python_rejects_it(self):
        command = f"gh cs ssh -c {CODESPACE} --stdio ; echo extra"
        with tempfile.TemporaryDirectory() as temporary:
            path = self.config(temporary, config_text(proxy_command=command))
            result = subprocess.run(
                ["ssh", "-G", "-F", str(path), ALIAS],
                text=True, capture_output=True, check=False, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            effective = dict(
                line.split(" ", 1) for line in result.stdout.splitlines() if " " in line
            )
            self.assertEqual(effective["proxycommand"], command)
            with self.assertRaisesRegex(
                Pilot03SshConfigError, "RB03_SSH_CODESPACE_BINDING_MISMATCH",
            ):
                validate_ssh_host_alias(
                    codespace_identity=CODESPACE,
                    ssh_host_alias=ALIAS,
                    ssh_config=path,
                )

    def test_invalid_missing_ambiguous_and_wildcard_aliases_refuse(self):
        cases = {
            "empty": ("", config_text(), "RB03_SSH_HOST_ALIAS_INVALID"),
            "forbidden": ("bad alias", config_text(), "RB03_SSH_HOST_ALIAS_INVALID"),
            "undefined": ("other", config_text(), "RB03_SSH_HOST_ALIAS_UNAVAILABLE"),
            "ambiguous": (ALIAS, config_text() + config_text(), "RB03_SSH_HOST_ALIAS_UNAVAILABLE"),
            "wildcard": ("*", config_text("*"), "RB03_SSH_HOST_ALIAS_INVALID"),
            "multi-pattern": (ALIAS, config_text(f"{ALIAS} other"), "RB03_SSH_HOST_ALIAS_INVALID"),
        }
        for name, (alias, text, error) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                path = self.config(temporary, text)
                with self.assertRaisesRegex(Pilot03SshConfigError, error):
                    validate_ssh_host_alias(
                        codespace_identity=CODESPACE, ssh_host_alias=alias, ssh_config=path,
                    )

    def test_unavailable_config_and_codespace_binding_mismatch_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            with self.assertRaisesRegex(Pilot03SshConfigError, "RB03_SSH_HOST_ALIAS_UNAVAILABLE"):
                validate_ssh_host_alias(
                    codespace_identity=CODESPACE, ssh_host_alias=ALIAS, ssh_config=missing,
                )
            path = self.config(temporary, config_text(codespace="different-codespace"))
            with self.assertRaisesRegex(Pilot03SshConfigError, "RB03_SSH_CODESPACE_BINDING_MISMATCH"):
                validate_ssh_host_alias(
                    codespace_identity=CODESPACE, ssh_host_alias=ALIAS, ssh_config=path,
                )

    def test_constructor_refuses_before_lifecycle_or_remote_contact(self):
        lifecycle = Mock()
        with tempfile.TemporaryDirectory() as temporary:
            path = self.config(temporary, config_text(codespace="wrong"))
            with self.assertRaises(Pilot03SshConfigError):
                Pilot03CodespaceTransport(
                    CODESPACE, ALIAS, path, lifecycle=lifecycle, runner=Mock(),
                )
        lifecycle.start.assert_not_called()
        lifecycle.state.assert_not_called()
