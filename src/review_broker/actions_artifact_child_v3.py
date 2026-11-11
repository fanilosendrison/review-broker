"""One pinned official Artifact child, synchronously owned by the original Worker."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
from threading import Lock
from .pre_model_observation_diagnostics_v3 import measured_phase_v3
import time
from typing import Callable, Mapping

from .github_prepared_artifact_v3 import (
    PreparedUploadPlanV3, PreparedUploadResultV3, UploadStatusV3,
)

UPLOAD_ACTION_COMMIT = "cf430e030ddbb5b0abf93d22962f4752f3646cd9"
UPLOAD_ACTION_DIST_BLOB = "7b3f92ae681d6eeca5f5e5e4cf892ad0dfb254ea"
# These are consumed by the pinned @actions/artifact client, not source/Git APIs.
_ARTIFACT_ENV = frozenset({"ACTIONS_RUNTIME_TOKEN", "ACTIONS_RESULTS_URL",
    "ACTIONS_RUNTIME_URL", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
    "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL"})
_NAME = re.compile(r"(?:rb-v3-prepared-[0-9a-f]{64}-[1-9][0-9]*-1|"
                   r"rb-v3-failure-observation-[0-9a-f]{64})\Z")


def verify_upload_helper_v3(root: Path) -> Path:
    """Verify Git identity AND actual executable bytes, without executing the helper."""
    root = Path(root)
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("ARTIFACT_TRUST_ROOT_INVALID")
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError("ARTIFACT_TRUST_ROOT_NOT_PRIVATE")
    environment={key:os.environ[key] for key in ('PATH','HOME','LANG','TMPDIR') if key in os.environ}
    environment.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
        GIT_NO_LAZY_FETCH='1',GIT_NO_REPLACE_OBJECTS='1',GIT_TERMINAL_PROMPT='0')
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
        env=environment, capture_output=True, check=True, timeout=10).stdout.strip().decode("ascii")
    if head != UPLOAD_ACTION_COMMIT:
        raise ValueError("ARTIFACT_HELPER_HEAD_MISMATCH")
    target = root / "dist/upload/index.js"
    if any(p.is_symlink() for p in (root / "dist", target.parent, target)):
        raise ValueError("ARTIFACT_HELPER_SYMLINK")
    entry = subprocess.run(["git", "-C", str(root), "ls-tree", "HEAD", "--",
        "dist/upload/index.js"], env=environment, capture_output=True, check=True, timeout=10).stdout
    if entry != (f"100644 blob {UPLOAD_ACTION_DIST_BLOB}\tdist/upload/index.js\n".encode()):
        raise ValueError("ARTIFACT_HELPER_TREE_MISMATCH")
    if not stat.S_ISREG(target.stat().st_mode):
        raise ValueError("ARTIFACT_HELPER_NOT_REGULAR")
    raw = target.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != UPLOAD_ACTION_DIST_BLOB:
        raise ValueError("ARTIFACT_HELPER_BYTES_MISMATCH")
    return target


def artifact_child_environment_v3(source: Mapping[str, str], file: Path,
                                  private_root: Path) -> dict[str, str]:
    """No ambient PATH, Node options, source credential, Actions file commands or proxies."""
    result = {key: source[key] for key in _ARTIFACT_ENV if key in source}
    for required in ("ACTIONS_RUNTIME_TOKEN", "ACTIONS_RESULTS_URL"):
        if not result.get(required):
            raise ValueError("ARTIFACT_RUNTIME_UNAVAILABLE")
    result.update({"HOME": str(private_root), "TMPDIR": str(private_root),
        "LANG": "C.UTF-8", "INPUT_PATH": str(file), "INPUT_ARCHIVE": "false",
        "INPUT_OVERWRITE": "false", "INPUT_RETENTION-DAYS": "30",
        "INPUT_IF-NO-FILES-FOUND": "error", "INPUT_INCLUDE-HIDDEN-FILES": "false",
        "INPUT_COMPRESSION-LEVEL": "0", "INPUT_NAME": file.name})
    return result


def run_artifact_child_v3(argv: list[str], environment: Mapping[str, str],
                          log: Path, *, timeout: float, max_log_bytes: int, on_started=None) -> int:
    """Drain output to a private bounded file; timeout/output overflow terminates the child."""
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    process = None
    try:
        with os.fdopen(descriptor, "wb", buffering=0) as output:
            process = subprocess.Popen(argv, env=dict(environment), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True,
                start_new_session=True)
            if on_started is not None:on_started(process.pid)
            assert process.stdout is not None
            deadline, written = time.monotonic() + timeout, 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("ARTIFACT_CHILD_TIMEOUT")
                    if not selector.select(remaining):
                        raise TimeoutError("ARTIFACT_CHILD_TIMEOUT")
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        selector.unregister(process.stdout)
                        break
                    remaining_bytes = max_log_bytes - written
                    output.write(chunk[:remaining_bytes])
                    written += len(chunk)
                    if written > max_log_bytes:
                        raise ValueError("ARTIFACT_CHILD_OUTPUT_BUDGET")
                return process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except BaseException:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()


class GitHubActionsArtifactChildV3:
    """At most one spawn per instance, including errors; no broker retry or cleanup.

    Provider-internal retries belong to the single pinned child. Its ACK is not
    remote-byte evidence. An authority failure after the effect propagates, so no
    following effect can be authorized by this result. Orphans are retained.
    """
    def __init__(self, *, trusted_root: Path, node: Path, private_base: Path,
                 environment: Mapping[str, str], max_bytes: int,
                 runner: Callable = run_artifact_child_v3,
                 verifier: Callable = verify_upload_helper_v3,
                 timeout: float = 300, max_log_bytes: int = 65536, on_started=None):
        if (not Path(node).is_absolute() or type(max_bytes) is not int or max_bytes < 1
                or timeout <= 0 or type(max_log_bytes) is not int or max_log_bytes < 1):
            raise ValueError("ARTIFACT_CHILD_CONFIGURATION_INVALID")
        self.root, self.node, self.base = Path(trusted_root), Path(node), Path(private_base)
        self.environment = dict(environment)
        self.max_bytes, self.runner, self.verifier = max_bytes, runner, verifier
        self.timeout, self.max_log_bytes = timeout, max_log_bytes
        self.on_started = on_started
        self._lock, self._attempted = Lock(), False

    def upload_bytes_once(self, name: str, raw: bytes, *, before_effect) -> PreparedUploadResultV3:
        with self._lock:
            if self._attempted:
                raise ValueError("ARTIFACT_CHILD_ALREADY_ATTEMPTED")
            self._attempted = True
        # Only these established LOCAL plan errors are deterministic refusals.
        if (type(name) is not str or _NAME.fullmatch(name) is None
                or type(raw) is not bytes or not 0 < len(raw) <= self.max_bytes):
            return PreparedUploadResultV3(UploadStatusV3.REFUSED)
        before_effect()
        executable = self.verifier(self.root)
        before_effect()
        if (self.base.is_symlink() or not self.base.is_dir()
                or stat.S_IMODE(self.base.stat().st_mode) != 0o700):
            raise ValueError("ARTIFACT_PRIVATE_BASE_INVALID")
        directory = Path(tempfile.mkdtemp(prefix="artifact-child-", dir=self.base))
        target = directory / name
        before_effect()
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
        environment = artifact_child_environment_v3(self.environment, target, directory)
        before_effect()  # Immediately before the single opaque provider launch.
        try:
            notification = {} if self.on_started is None else {"on_started": self.on_started}
            code = self.runner([str(self.node), str(executable)], environment,
                directory / "child-output.log", timeout=self.timeout,
                max_log_bytes=self.max_log_bytes, **notification)
            result = UploadStatusV3.ACK if type(code) is int and code == 0 else UploadStatusV3.UNKNOWN
        except Exception:
            result = UploadStatusV3.UNKNOWN
        before_effect()  # No ACK (or UNKNOWN) overrides moved authority.
        return PreparedUploadResultV3(result)

    @measured_phase_v3('ARTIFACT_UPLOAD')
    def upload_once(self, plan: PreparedUploadPlanV3, archive: bytes, *, before_effect):
        if type(plan) is not PreparedUploadPlanV3 or plan.retention_days != 30:
            raise ValueError("ARTIFACT_PREPARED_PLAN_INVALID")
        return self.upload_bytes_once(plan.artifact_name, archive, before_effect=before_effect)
