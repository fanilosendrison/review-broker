"""Bounded remote observation and literal copying for RB-PILOT-03 artifacts."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from .pilot_private_retention import CodespaceLiteralCopier, PilotRetentionError, RemoteArtifact

_REMOTE_ROOT = "/tmp/review-broker-pilot-26-rb03"
ARTIFACT_PATHS = {
    "pilot-claim.json": "/tmp/review-broker-pilot-26-rb03.claim.json",
    "pilot-armed.json": f"{_REMOTE_ROOT}/pilot-armed.json",
    "pilot-summary.json": f"{_REMOTE_ROOT}/pilot-summary.json",
    "pilot-failure.json": f"{_REMOTE_ROOT}/pilot-failure.json",
    "codex-events.jsonl": f"{_REMOTE_ROOT}/evidence/codex-events.jsonl",
    "codex-stderr.txt": f"{_REMOTE_ROOT}/evidence/codex-stderr.txt",
    "codex-final.json": f"{_REMOTE_ROOT}/evidence/codex-final.json",
    "codex-exit-code.txt": f"{_REMOTE_ROOT}/evidence/codex-exit-code.txt",
}
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
        self, codespace: str, ssh_config: Path, *,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9-]+", codespace):
            raise ValueError("RB03_REMOTE_SOURCE_INVALID")
        self.codespace = codespace
        self.ssh_config = Path(ssh_config)
        self.runner = runner
        self._copier = CodespaceLiteralCopier(codespace, ARTIFACT_PATHS, runner=runner)

    def observe(self, relative_name: str) -> RemoteArtifact:
        path = self._path(relative_name)
        result = self.runner(
            ["ssh", "-F", str(self.ssh_config), "-o", "BatchMode=yes", self.codespace,
             "/usr/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin",
             "python3", "-P", "-", path],
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

    @staticmethod
    def _path(relative_name: str) -> str:
        try:
            return ARTIFACT_PATHS[relative_name]
        except (KeyError, TypeError) as exc:
            raise PilotRetentionError("PRIVATE_RETENTION_PATH_NOT_ALLOWED") from exc
