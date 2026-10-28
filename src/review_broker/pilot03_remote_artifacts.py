"""Bounded remote observation and literal copying for RB-PILOT-03 artifacts."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from .pilot_private_retention import CodespaceLiteralCopier, PilotRetentionError, RemoteArtifact
from .pilot03_remote_preflight import REMOTE_PATH, REMOTE_PYTHON
from .pilot_runtime_config import PilotRuntimeConfig, RB03_RUNTIME, require_runtime_config

ARTIFACT_PATHS = RB03_RUNTIME.artifact_paths
_FIELDS = {"present", "regular", "symlink", "link_count", "byte_length", "sha256", "credential_screen"}
_OBSERVE_SCRIPT = r'''import hashlib,json,os,stat,sys
from review_broker.evidence import stream_contains_credential
path=sys.argv[1]
try: before=os.lstat(path)
except FileNotFoundError:
 print(json.dumps({"present":False,"regular":False,"symlink":False,"link_count":0,"byte_length":0,"sha256":None,"credential_screen":"UNDETERMINED"},separators=(",",":")));raise SystemExit
regular=stat.S_ISREG(before.st_mode); link=stat.S_ISLNK(before.st_mode)
out={"present":True,"regular":regular,"symlink":link,"link_count":before.st_nlink,"byte_length":before.st_size,"sha256":None,"credential_screen":"UNDETERMINED"}
if regular and not link:
 try:
  fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
  with os.fdopen(fd,"rb") as stream:
   digest=hashlib.sha256(); contaminated=False
   while True:
    block=stream.read(65536)
    if not block: break
    digest.update(block)
   stream.seek(0); contaminated=stream_contains_credential(stream)
   after=os.fstat(stream.fileno())
  current=os.lstat(path)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or (after.st_dev,after.st_ino)!=(current.st_dev,current.st_ino): raise OSError()
  out["sha256"]=digest.hexdigest();out["credential_screen"]="CONTAMINATED" if contaminated else "PASS_NO_MATCH"
 except Exception: out["regular"]=False;out["credential_screen"]="UNDETERMINED"
print(json.dumps(out,separators=(",",":")))
'''


class Pilot03RemoteArtifacts:
    """Expose only sanitary metadata and fixed literal RB-PILOT-03 copies."""

    def __init__(
        self, codespace: str, ssh_host_alias: str, ssh_config: Path, *,
        remote_python: str | None = None,
        runner: Callable[..., Any] = subprocess.run,
        runtime: PilotRuntimeConfig = RB03_RUNTIME,
    ) -> None:
        if (
            not re.fullmatch(r"[A-Za-z0-9-]+", codespace)
            or not re.fullmatch(r"[A-Za-z0-9._-]+", ssh_host_alias)
        ):
            raise ValueError("RB03_REMOTE_SOURCE_INVALID")
        self.codespace = codespace
        self.ssh_host_alias = ssh_host_alias
        self.ssh_config = Path(ssh_config)
        self.runtime = require_runtime_config(runtime)
        selected_python = self.runtime.remote_python if remote_python is None else remote_python
        if selected_python != self.runtime.remote_python:
            raise ValueError("RB03_REMOTE_PYTHON_INVALID")
        self.runner = runner
        self.remote_python = selected_python
        self.paths = self.runtime.artifact_paths
        self._copier = CodespaceLiteralCopier(codespace, self.paths, runner=runner)

    def observe(self, relative_name: str) -> RemoteArtifact:
        path = self._path(relative_name)
        result = self.runner(
            ["ssh", "-F", str(self.ssh_config), "-o", "BatchMode=yes", self.ssh_host_alias,
             "/usr/bin/env", "-i", f"PATH={REMOTE_PATH}",
             self.remote_python, "-P", "-", path],
            input=_OBSERVE_SCRIPT, text=True, capture_output=True, check=False,
            timeout=120, shell=False,
        )
        if result.returncode != 0 or result.stderr or len(result.stdout) > 2048:
            raise PilotRetentionError("RB03_REMOTE_OBSERVATION_UNDETERMINED")
        try:
            value = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise PilotRetentionError("RB03_REMOTE_OBSERVATION_INVALID") from exc
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise PilotRetentionError("RB03_REMOTE_OBSERVATION_INVALID")
        if (
            type(value["present"]) is not bool or type(value["regular"]) is not bool
            or type(value["symlink"]) is not bool or type(value["link_count"]) is not int
            or type(value["byte_length"]) is not int
            or value["credential_screen"] not in {"PASS_NO_MATCH", "CONTAMINATED", "UNDETERMINED"}
            or value["sha256"] is not None
            and not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
        ):
            raise PilotRetentionError("RB03_REMOTE_OBSERVATION_INVALID")
        return RemoteArtifact(**value)

    def copy_literal(self, relative_name: str, destination: Path) -> None:
        self._path(relative_name)
        self._copier.copy_literal(relative_name, destination)

    def _path(self, relative_name: str) -> str:
        try:
            return self.paths[relative_name]
        except (KeyError, TypeError) as exc:
            raise PilotRetentionError("PRIVATE_RETENTION_PATH_NOT_ALLOWED") from exc
