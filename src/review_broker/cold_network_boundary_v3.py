"""Shared qualified Linux cold-observer kernel boundary; no broker effects."""
import ctypes
import errno
import os
from pathlib import Path
import platform
import stat
import sys

SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg", "shutdown",
    "setsockopt", "getsockopt", "io_uring_setup", "io_uring_enter", "io_uring_register",
)
MECHANISM = "libseccomp.so.2/SCMP_ACT_ERRNO(EPERM)"
_FILTER_INSTALLED = False


def minimal_environment(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "TMPDIR": str(home), "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1"}


def kernel_status() -> dict[str, int]:
    rows = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    return {key: int(rows[key].strip()) for key in ("NoNewPrivs", "Seccomp")}


def require_kernel_status() -> dict[str, int]:
    status = kernel_status()
    if status != {"NoNewPrivs": 1, "Seccomp": 2}:
        raise RuntimeError(f"R5_KERNEL_STATE_INVALID:{status}")
    return status


def socket_descriptors() -> list[int]:
    result = []
    for name in os.listdir("/proc/self/fd"):
        try:
            descriptor = int(name)
            if stat.S_ISSOCK(os.fstat(descriptor).st_mode): result.append(descriptor)
        except OSError as error:
            if error.errno != errno.EBADF: raise
    return sorted(result)


def require_no_socket_descriptors() -> list[int]:
    descriptors = socket_descriptors()
    if descriptors: raise RuntimeError("R5_INHERITED_NETWORK_DESCRIPTOR")
    return descriptors


def require_supported_platform() -> None:
    if sys.platform != "linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError("R5_UNSUPPORTED_PLATFORM_OR_ABI")


def install_filter() -> None:
    global _FILTER_INSTALLED
    require_supported_platform()
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as error:
        raise RuntimeError("R5_LIBSECCOMP_UNAVAILABLE") from error
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_rule_add.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.restype = None
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context: raise RuntimeError("R5_SECCOMP_INIT_FAILED")
    try:
        for name in SYSCALLS:
            number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0: raise RuntimeError(f"R5_SYSCALL_UNRESOLVED:{name}")
            result = seccomp.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0)
            if result != 0: raise RuntimeError(f"R5_SECCOMP_RULE_FAILED:{name}:{result}")
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            raise OSError(ctypes.get_errno(), "R5_NO_NEW_PRIVS_FAILED")
        result = seccomp.seccomp_load(context)
        if result != 0: raise RuntimeError(f"R5_SECCOMP_LOAD_FAILED:{result}")
    finally:
        seccomp.seccomp_release(context)
    require_kernel_status()
    _FILTER_INSTALLED = True


def require_installed_filter() -> None:
    if not _FILTER_INSTALLED: raise RuntimeError("R5_UNSANDBOXED_COLD_INVOCATION")
    require_kernel_status()
    require_no_socket_descriptors()


