"""Authenticate a Codespace routing recipient; this context grants no execution authority."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Sequence

# Any is bounded untrusted GitHub JSON, validated before use as routing context.
@dataclass(frozen=True)
class Recipient:
    name: str
    codespace_id: int
    owner_login: str
    owner_id: int
    repository: str
    repository_id: int


def _name(value: object) -> str:
    if not isinstance(value,str) or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}',value) is None:
        raise ValueError('CODESPACE_SELECTION_INVALID')
    return value


def parse_api(raw: str) -> dict[str, Any]:
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('CODESPACE_API_AMBIGUOUS')
            result[key]=value
        return result
    if len(raw)>1_000_000:raise ValueError('CODESPACE_API_RESPONSE_TOO_LARGE')
    result=json.loads(raw,object_pairs_hook=pairs)
    if not isinstance(result,dict):raise ValueError('CODESPACE_API_RESPONSE_INVALID')
    return result


def validate_recipient(value: dict[str, Any], user: dict[str, Any], *, selection: str,
                       repository: str, repository_id: str) -> Recipient:
    try:
        name=_name(value['name'])
        if name!=_name(selection):raise ValueError
        ids=[value['id'],value['owner']['id'],value['repository']['id'],user['id']]
        if any(type(n)is not int or n<=0 for n in ids):raise ValueError
        if (not re.fullmatch(r'[1-9][0-9]*',repository_id)
            or value['repository']['id']!=int(repository_id)
            or value['repository']['full_name']!=repository
            or not isinstance(user['login'],str) or not user['login']
            or value['owner']['login']!=user['login'] or value['owner']['id']!=user['id']):
            raise ValueError
        return Recipient(name,value['id'],user['login'],user['id'],repository,int(repository_id))
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('CODESPACE_AUTHENTICATED_RECIPIENT_MISMATCH') from exc


def _api(endpoint: str) -> dict[str, Any]:
    result=subprocess.run(['gh','api',endpoint],check=True,capture_output=True,text=True,timeout=45)
    return parse_api(result.stdout)


def observe_recipient(*, selection: str, repository: str, repository_id: str) -> Recipient:
    name=_name(selection)
    return validate_recipient(_api('user/codespaces/'+name),_api('user'),
                              selection=name,repository=repository,repository_id=repository_id)


def capture_recipient(path: Path, **selection: str) -> Recipient:
    identity=observe_recipient(**selection)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        json.dump(asdict(identity),stream,sort_keys=True)
    return identity


def revalidate_recipient(path: Path, *, expected_id: str | None = None, **selection: str) -> Recipient:
    # The private controller file is context, not a signed grant or journal proof.
    original=parse_api(path.read_text(encoding='utf-8'))
    current=observe_recipient(**selection)
    if original!=asdict(current) or (expected_id is not None and str(current.codespace_id)!=expected_id):
        raise ValueError('CODESPACE_AUTHENTICATED_RECIPIENT_CHANGED')
    return current


def context_command(identity: Recipient, command: Sequence[str]) -> str:
    # OpenSSH uses a remote shell even when the local caller uses argv. Quote every token.
    return shlex.join(['env','-u','PYTHONPATH','CODESPACE_NAME='+_name(identity.name),*command])
