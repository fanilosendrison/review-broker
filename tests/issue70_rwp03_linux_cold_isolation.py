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

from review_broker.cold_network_boundary_v3 import (
    SYSCALLS, MECHANISM, minimal_environment, kernel_status, require_kernel_status,
    socket_descriptors, require_no_socket_descriptors, require_supported_platform,
    install_filter, require_installed_filter,
)
PORT = 49231  # Independent numeric loopback probe; no listener is needed.


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
