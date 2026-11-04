"""Linux-only seccomp boundary for the RWP-03 cold verification subprocess."""
import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import stat
import subprocess
import sys

SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg", "shutdown",
    "setsockopt", "getsockopt", "io_uring_setup", "io_uring_enter", "io_uring_register",
)
MECHANISM = "libseccomp.so.2/SCMP_ACT_ERRNO(EPERM)"
PORT = 49231  # Numeric loopback only; no listener or external endpoint is needed.
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


def require_eperm(operation) -> int:
    try:
        operation()
    except OSError as error:
        if error.errno == errno.EPERM: return error.errno
        raise RuntimeError(f"R5_WRONG_DENIAL:{error.errno}") from error
    raise RuntimeError("R5_NETWORK_OPERATION_SUCCEEDED")


# Independent descendant oracle: kernel state and real syscalls, not parent flags.
DESCENDANT_CODE = '''
import errno,json,pathlib,socket,subprocess,sys
rows=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines())
state={key:int(rows[key].strip()) for key in ('NoNewPrivs','Seccomp')}
assert state=={'NoNewPrivs':1,'Seccomp':2},state
try:
    socket.socket(socket.AF_INET,socket.SOCK_STREAM)
except OSError as error:
    assert error.errno==errno.EPERM,error.errno
else:
    raise RuntimeError('R5_DESCENDANT_SOCKET_ALLOWED')
result={'kernel':state,'socket_errno':errno.EPERM,'generation':int(sys.argv[1])}
if result['generation']==1:
    process=subprocess.run([sys.executable,'-c',sys.argv[2],'2',sys.argv[2]],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,close_fds=True,
        pass_fds=(),check=True,timeout=30)
    result['descendant']=json.loads(process.stdout)
sys.stdout.write(json.dumps(result,sort_keys=True,separators=(',',':')))
'''


def probe() -> dict:
    inherited = require_no_socket_descriptors()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp, socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM) as udp:
        install_filter()
        libc = ctypes.CDLL(None, use_errno=True)
        libc.socket.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        libc.socket.restype = ctypes.c_int
        libc.connect.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        libc.connect.restype = ctypes.c_int
        ctypes.set_errno(0)
        descriptor = libc.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        native_socket_errno = ctypes.get_errno()
        if descriptor != -1:
            os.close(descriptor)
            raise RuntimeError("R5_NATIVE_SOCKET_ALLOWED")
        if native_socket_errno != errno.EPERM: raise RuntimeError("R5_NATIVE_SOCKET_WRONG_ERRNO")
        python_errno = require_eperm(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        connect_ex_errno = tcp.connect_ex(("127.0.0.1", PORT))
        if connect_ex_errno != errno.EPERM: raise RuntimeError(f"R5_CONNECT_EX:{connect_ex_errno}")
        udp_errno = require_eperm(lambda: udp.sendto(b"rwp03-isolation-probe", ("127.0.0.1", PORT)))
        class SockaddrIn(ctypes.Structure):
            _fields_ = [("family", ctypes.c_ushort), ("port", ctypes.c_ushort),
                        ("address", ctypes.c_ubyte * 4), ("padding", ctypes.c_ubyte * 8)]
        address = SockaddrIn(socket.AF_INET, socket.htons(PORT), (ctypes.c_ubyte * 4)(127, 0, 0, 1))
        ctypes.set_errno(0)
        result = libc.connect(tcp.fileno(), ctypes.byref(address), ctypes.sizeof(address))
        native_connect_errno = ctypes.get_errno()
        if result != -1 or native_connect_errno != errno.EPERM:
            raise RuntimeError(f"R5_NATIVE_CONNECT_NOT_DENIED:{result}:{native_connect_errno}")
        child = subprocess.run([sys.executable, "-c", DESCENDANT_CODE, "1", DESCENDANT_CODE],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, close_fds=True,
            pass_fds=(), check=True, timeout=60)
        output = {"mechanism": MECHANISM, "architecture": platform.machine(),
                  "kernel": require_kernel_status(), "denied_syscalls": list(SYSCALLS),
                  "native_socket_errno": native_socket_errno, "python_socket_errno": python_errno,
                  "tcp_connect_ex_errno": connect_ex_errno, "udp_sendto_errno": udp_errno,
                  "native_connect_errno": native_connect_errno, "child": json.loads(child.stdout),
                  "inherited_network_descriptors": inherited}
    require_no_socket_descriptors()
    return output


def main(arguments=None) -> None:
    require_supported_platform()
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if not arguments or arguments[0] not in ("probe", "cold"):
        raise RuntimeError("R5_EXPECTED_PROBE_OR_COLD")
    if arguments[0] == "probe":
        if len(arguments) != 1: raise RuntimeError("R5_UNEXPECTED_PROBE_ARGUMENTS")
        sys.stdout.write(json.dumps(probe(), sort_keys=True, separators=(",", ":")) + "\n")
    else:
        require_no_socket_descriptors()
        install_filter()
        require_installed_filter()
        sys.argv = ["tests.issue70_rwp03_test_support", *arguments[1:]]
        runpy.run_module("tests.issue70_rwp03_test_support", run_name="__main__")


if __name__ == "__main__":
    # Keep the installation marker in the canonical module used by cold_probe.
    from tests.issue70_rwp03_linux_cold_isolation import main as canonical_main
    canonical_main()
