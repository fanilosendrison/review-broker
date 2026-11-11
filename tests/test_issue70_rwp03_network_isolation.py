"""Actual Linux kernel qualification; macOS functional tests do not qualify R5."""
import errno
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from tests.issue70_rwp03_linux_cold_isolation import minimal_environment

LAUNCHER = "tests.issue70_rwp03_linux_cold_isolation"


@unittest.skipUnless(sys.platform == "linux", "Linux-only qualification; macOS OS isolation remains NOT_QUALIFIED")
class LinuxColdIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rwp03-isolation-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.home = Path(cls.temporary.name)
        process = cls.execute(["-m", LAUNCHER, "probe"])
        if process.returncode:
            raise AssertionError(f"R5_LINUX_PROBE_FAILED:{process.returncode}:{process.stderr}")
        cls.receipt = json.loads(process.stdout)
        # Preserve the actual child receipt in CI output; no environment is dumped.
        sys.stdout.write(process.stdout)

    @classmethod
    def execute(cls, arguments, **kwargs):
        return subprocess.run([sys.executable, *arguments], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, env=minimal_environment(cls.home),
            close_fds=True, timeout=90, **kwargs)

    def test_01_seccomp_installation_and_kernel_state(self):
        self.assertEqual(self.receipt["mechanism"], "libseccomp.so.2/SCMP_ACT_ERRNO(EPERM)")
        self.assertIn(self.receipt["architecture"].lower(), ("x86_64", "amd64"))
        self.assertEqual(self.receipt["kernel"], {"NoNewPrivs": 1, "Seccomp": 2})
        # Independent required-name oracle; do not reuse the implementation tuple.
        self.assertEqual(self.receipt["denied_syscalls"], [
            "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
            "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg", "shutdown",
            "setsockopt", "getsockopt", "io_uring_setup", "io_uring_enter", "io_uring_register",
        ])

    def test_02_native_socket_denied(self):
        self.assertEqual(self.receipt["native_socket_errno"], errno.EPERM)

    def test_03_python_socket_denied(self):
        self.assertEqual(self.receipt["python_socket_errno"], errno.EPERM)

    def test_04_tcp_connect_ex_denied(self):
        self.assertEqual(self.receipt["tcp_connect_ex_errno"], errno.EPERM)

    def test_05_udp_sendto_denied(self):
        self.assertEqual(self.receipt["udp_sendto_errno"], errno.EPERM)

    def test_06_native_connect_denied(self):
        self.assertEqual(self.receipt["native_connect_errno"], errno.EPERM)

    def test_07_direct_child_inherits(self):
        child = self.receipt["child"]
        self.assertEqual(child["generation"], 1)
        self.assertEqual(child["kernel"], {"NoNewPrivs": 1, "Seccomp": 2})
        self.assertEqual(child["socket_errno"], errno.EPERM)

    def test_08_second_generation_after_exec_inherits(self):
        child = self.receipt["child"]["descendant"]
        self.assertEqual(child["generation"], 2)
        self.assertEqual(child["kernel"], {"NoNewPrivs": 1, "Seccomp": 2})
        self.assertEqual(child["socket_errno"], errno.EPERM)

    def test_09_complete_cold_reconstruction_under_filter(self):
        from review_broker.packet_retention_v3 import load_packet_evidence_v3
        from tests.issue70_rwp03_test_support import RealContinuationScenario
        with tempfile.TemporaryDirectory(dir=self.home) as temporary:
            scenario = RealContinuationScenario(Path(temporary))
            result = scenario.continuation.run(scenario.worker.context)
            self.assertEqual(result.status.value, "COMMITTED", result.reason)
            verification = scenario.verification()
            _, _, _, manifest = load_packet_evidence_v3(result.retained_root,
                scenario.worker.admission.journal_admission(), policy_verification=verification)
            self.assertEqual(scenario.cold(result.retained_root, verification.snapshot), manifest)
            self.assertEqual(manifest["technical_policy"]["qualification"],
                             "PREMODEL_POLICY_SOURCE_VERIFIED_ONLY")

    def test_10_missing_library_fails_closed_before_cold_import(self):
        # Failure-path injection only. All positive qualification uses real syscalls.
        code = '''
from unittest.mock import patch
from tests.issue70_rwp03_linux_cold_isolation import main
with patch('ctypes.CDLL',side_effect=OSError('deliberately unavailable library')):
    main(['cold'])
'''
        process = self.execute(["-c", code], pass_fds=())
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("R5_LIBSECCOMP_UNAVAILABLE", process.stderr)
        self.assertEqual(process.stdout, "")

    def test_11_no_inherited_network_descriptors(self):
        self.assertEqual(self.receipt["inherited_network_descriptors"], [])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as descriptor:
            process = self.execute(["-m", LAUNCHER, "cold"], pass_fds=(descriptor.fileno(),))
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("R5_INHERITED_NETWORK_DESCRIPTOR", process.stderr)
        self.assertEqual(process.stdout, "")

    def test_12_unsandboxed_linux_cold_invocation_rejected(self):
        process = self.execute(["-m", "tests.issue70_rwp03_test_support"], pass_fds=())
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("R5_UNSANDBOXED_COLD_INVOCATION", process.stderr)
        self.assertEqual(process.stdout, "")


if __name__ == "__main__":
    unittest.main()
