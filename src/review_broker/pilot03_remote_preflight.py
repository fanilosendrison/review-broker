"""Fixed, non-inference remote bootstrap and preflight for RB-PILOT-03."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from .pilot_runtime_config import (
    PilotRuntimeConfig,
    RB03_RUNTIME,
    require_runtime_config,
)

BOOTSTRAP_ROOT = RB03_RUNTIME.bootstrap_root
REMOTE_WHEEL = RB03_RUNTIME.remote_wheel
REMOTE_VENV = RB03_RUNTIME.remote_venv
REMOTE_PYTHON = RB03_RUNTIME.remote_python
REMOTE_REVIEWCTL = RB03_RUNTIME.remote_reviewctl
REMOTE_PATH = "/home/codespace/nvm/current/bin:/usr/local/bin:/usr/bin:/bin"
CODEX_RUNTIME_ROOT = "/var/lib/review-broker/codex-0.164.0-linux-x64"

_PREPARE_SCRIPT = f'''import json,os,pathlib,stat
root=pathlib.Path("{BOOTSTRAP_ROOT}")
try:
 root.mkdir(mode=0o700)
 mode=stat.S_IMODE(root.lstat().st_mode)
 if root.is_symlink() or not root.is_dir() or mode != 0o700: raise OSError()
 print(json.dumps({{"status":"READY"}},separators=(",",":")))
except Exception:
 print(json.dumps({{"status":"REMOTE_BOOTSTRAP_UNAVAILABLE"}},separators=(",",":")))
'''

_VERIFY_INSTALLED = f'''import importlib.metadata,json,os,pathlib,subprocess,sys
status={{"remote_python_compatible":"NO","remote_wheel_sha256_match":"NO","remote_broker_installation_verified":"NO","remote_entrypoint_resolves":"NO","remote_dependencies_available":"NO","remote_codex_runtime_preflight":"FAIL","remote_non_inference_auth_status":"FAIL"}}
try:
 assert sys.version_info >= (3,11)
 status["remote_python_compatible"]="YES"
 assert importlib.metadata.version("review-broker")=="0.4.5"
 assert importlib.metadata.version("jsonschema")=="4.26.0"
 assert importlib.metadata.version("rfc8785")=="0.1.4"
 import jsonschema,rfc8785,review_broker.cli
 status["remote_dependencies_available"]="YES"
 distribution=importlib.metadata.distribution("review-broker")
 direct=json.loads(distribution.read_text("direct_url.json"))
 assert direct["archive_info"]["hash"]=="sha256="+os.environ["RB03_EXPECTED_WHEEL_SHA256"]
 assert direct["url"].endswith("/{Path(REMOTE_WHEEL).name}")
 root=pathlib.Path(sys.prefix).resolve()
 module=pathlib.Path(review_broker.cli.__file__).resolve()
 entry=pathlib.Path("{REMOTE_REVIEWCTL}").resolve()
 assert module.is_relative_to(root) and entry.is_relative_to(root) and entry.is_file()
 ep=next(value for value in importlib.metadata.entry_points(group="console_scripts") if value.name=="reviewctl")
 assert ep.value=="review_broker.cli:main"
 status["remote_broker_installation_verified"]="YES";status["remote_entrypoint_resolves"]="YES"
 from review_broker.codex import preflight_codex_runtime
 receipt=preflight_codex_runtime(pathlib.Path("{CODEX_RUNTIME_ROOT}"),environment={{"HOME":"/home/codespace","CODEX_HOME":"/home/codespace/.codex","PATH":"{REMOTE_PATH}","LANG":"C.UTF-8","TZ":"UTC"}})
 assert receipt["distribution"]=="@openai/codex" and receipt["distribution_version"]=="0.164.0" and receipt["cli_compatibility_verified"] is True
 status["remote_codex_runtime_preflight"]="PASS"
 auth=subprocess.run([receipt["execution_native"],"login","status"],env={{"HOME":"/home/codespace","CODEX_HOME":"/home/codespace/.codex","PATH":"{REMOTE_PATH}","LANG":"C.UTF-8","TZ":"UTC"}},capture_output=True,check=False,timeout=30)
 if auth.returncode==0: status["remote_non_inference_auth_status"]="PASS"
except Exception: pass
print(json.dumps(status,separators=(",",":")))
'''

_PREFLIGHT_SCRIPT = f'''import hashlib,json,os,pathlib,subprocess,sys
wheel=pathlib.Path("{REMOTE_WHEEL}");expected=sys.argv[1]
try:
 if sys.version_info < (3,11): raise RuntimeError("REMOTE_PYTHON_INCOMPATIBLE")
 if not wheel.is_file() or wheel.is_symlink(): raise RuntimeError("REMOTE_WHEEL_MISSING")
 digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
 if digest!=expected: raise RuntimeError("REMOTE_WHEEL_SHA256_MISMATCH")
 venv=pathlib.Path("{REMOTE_VENV}")
 if not venv.exists():
  subprocess.run([sys.executable,"-m","venv","--system-site-packages",str(venv)],check=True,capture_output=True,timeout=120)
 python=pathlib.Path("{REMOTE_PYTHON}")
 subprocess.run([str(python),"-m","pip","install","--no-index","--no-deps","--force-reinstall",str(wheel)],check=True,capture_output=True,timeout=120)
 if hashlib.sha256(wheel.read_bytes()).hexdigest()!=expected: raise RuntimeError("REMOTE_WHEEL_SHA256_MISMATCH")
 result=subprocess.run([str(python),"-P","-c",{_VERIFY_INSTALLED!r}],env={{"HOME":"/home/codespace","CODEX_HOME":"/home/codespace/.codex","PATH":"{REMOTE_PATH}","LANG":"C.UTF-8","TZ":"UTC","RB03_EXPECTED_WHEEL_SHA256":expected}},capture_output=True,text=True,check=False,timeout=120)
 if result.returncode!=0 or result.stderr: raise RuntimeError("REMOTE_PREFLIGHT_UNDETERMINED")
 value=json.loads(result.stdout);value["remote_wheel_sha256_match"]="YES";print(json.dumps(value,separators=(",",":")))
except RuntimeError as exc:
 print(json.dumps({{"failure":str(exc)}},separators=(",",":")))
except Exception:
 print(json.dumps({{"failure":"REMOTE_PREFLIGHT_UNDETERMINED"}},separators=(",",":")))
'''

_REQUIRED = {
    "remote_python_compatible": "YES",
    "remote_wheel_sha256_match": "YES",
    "remote_broker_installation_verified": "YES",
    "remote_entrypoint_resolves": "YES",
    "remote_dependencies_available": "YES",
    "remote_codex_runtime_preflight": "PASS",
    "remote_non_inference_auth_status": "PASS",
}
_FAILURES = frozenset({
    "REMOTE_REVIEWCTL_MISSING", "REMOTE_WHEEL_MISSING",
    "REMOTE_WHEEL_SHA256_MISMATCH", "REMOTE_PYTHON_INCOMPATIBLE",
    "REMOTE_DEPENDENCY_MISSING", "REMOTE_CODEX_RUNTIME_UNAVAILABLE",
    "REMOTE_PREFLIGHT_UNDETERMINED", "REMOTE_BOOTSTRAP_UNAVAILABLE",
})


class Pilot03PreflightError(RuntimeError):
    """A sanitary remote preflight gate failed before controller reservation."""


def run_remote_preflight(
    *, codespace: str, ssh_host_alias: str, ssh_config: Path,
    wheel_path: Path, wheel_sha256: str,
    runner: Callable[..., Any] = subprocess.run,
    runtime: PilotRuntimeConfig = RB03_RUNTIME,
) -> dict[str, str]:
    """Transfer and verify the exact local wheel without model inference."""
    runtime = require_runtime_config(runtime)
    prepare_script, preflight_script = _runtime_scripts(runtime)
    if (
        not re.fullmatch(r"[A-Za-z0-9-]+", codespace)
        or not Path(ssh_config).is_file() or not Path(wheel_path).is_file()
        or not re.fullmatch(r"[0-9a-f]{64}", wheel_sha256)
    ):
        raise Pilot03PreflightError("REMOTE_PREFLIGHT_UNDETERMINED")
    prepared = _run_ssh(runner, ssh_host_alias, ssh_config, prepare_script, [])
    if prepared != {"status": "READY"}:
        raise Pilot03PreflightError("REMOTE_BOOTSTRAP_UNAVAILABLE")
    copied = runner(
        ["gh", "codespace", "cp", "-c", codespace, str(wheel_path), f"remote:{runtime.remote_wheel}"],
        capture_output=True, check=False, timeout=120, shell=False,
    )
    if copied.returncode != 0:
        raise Pilot03PreflightError("REMOTE_WHEEL_MISSING")
    result = _run_ssh(runner, ssh_host_alias, ssh_config, preflight_script, [wheel_sha256])
    failure = result.get("failure") if isinstance(result, dict) else None
    if failure in _FAILURES:
        raise Pilot03PreflightError(failure)
    if result != _REQUIRED:
        missing = _classify_failed_result(result)
        raise Pilot03PreflightError(missing)
    return dict(result)


def _runtime_scripts(runtime: PilotRuntimeConfig) -> tuple[str, str]:
    if runtime is RB03_RUNTIME:
        return _PREPARE_SCRIPT, _PREFLIGHT_SCRIPT
    return (
        _PREPARE_SCRIPT.replace(BOOTSTRAP_ROOT, runtime.bootstrap_root),
        _PREFLIGHT_SCRIPT.replace(BOOTSTRAP_ROOT, runtime.bootstrap_root),
    )


def _run_ssh(runner, ssh_host_alias: str, ssh_config: Path, script: str, arguments: list[str]):
    result = runner(
        ["ssh", "-F", str(ssh_config), "-o", "BatchMode=yes", ssh_host_alias,
         "/usr/bin/env", "-i", f"PATH={REMOTE_PATH}", "python3", "-P", "-", *arguments],
        input=script, text=True, capture_output=True, check=False, timeout=180, shell=False,
    )
    if result.returncode != 0 or result.stderr or len(result.stdout) > 4096:
        raise Pilot03PreflightError("REMOTE_PREFLIGHT_UNDETERMINED")
    try:
        value = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise Pilot03PreflightError("REMOTE_PREFLIGHT_UNDETERMINED") from exc
    if not isinstance(value, dict):
        raise Pilot03PreflightError("REMOTE_PREFLIGHT_UNDETERMINED")
    return value


def _classify_failed_result(value: object) -> str:
    if not isinstance(value, dict):
        return "REMOTE_PREFLIGHT_UNDETERMINED"
    mapping = (
        ("remote_python_compatible", "REMOTE_PYTHON_INCOMPATIBLE"),
        ("remote_wheel_sha256_match", "REMOTE_WHEEL_SHA256_MISMATCH"),
        ("remote_dependencies_available", "REMOTE_DEPENDENCY_MISSING"),
        ("remote_broker_installation_verified", "REMOTE_REVIEWCTL_MISSING"),
        ("remote_entrypoint_resolves", "REMOTE_REVIEWCTL_MISSING"),
        ("remote_codex_runtime_preflight", "REMOTE_CODEX_RUNTIME_UNAVAILABLE"),
    )
    for field, failure in mapping:
        if value.get(field) != _REQUIRED[field]:
            return failure
    return "REMOTE_PREFLIGHT_UNDETERMINED"
