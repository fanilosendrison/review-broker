"""Evidence-distinct journal observations, without changing v1 wire identity."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Callable

from .github_contents import decode_github_contents_base64
from .github_journal_http import GitHubJournalResponse, JournalReadUnknown
from .identity import attempt_identity, canonical_bytes
from .queue import AttemptRecord, StateTransitionError


class JournalReadKind(str, Enum):
    PRESENT_VERIFIED = 'PRESENT_VERIFIED'
    ABSENT_AUTHENTICATED = 'ABSENT_AUTHENTICATED'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class JournalObservation:
    kind: JournalReadKind
    snapshot: tuple[str, AttemptRecord] | None = None
    reason: str = ''


def commit_sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{40}', value) is None:
        raise ValueError
    return value


def verified_absence(repository: str, base_branch: str, request: Callable[..., GitHubJournalResponse]) -> bool:
    """A ref 404 alone says nothing about repository or credential readability.

    REST metadata and the authenticated GraphQL viewer/repository must agree.
    A separate successful Git-data read proves effective Contents capability;
    viewerPermission by itself is only the actor's repository role.
    No evidence here proves that a historical ref was never deleted.
    """
    metadata = request('GET', f'repos/{repository}')
    if metadata.status != 200:
        return False
    owner, name = repository.split('/')
    query = ('query($owner:String!,$name:String!) { viewer { login id } '
             'repository(owner:$owner,name:$name) { nameWithOwner databaseId viewerPermission '
             'defaultBranchRef { name target { oid } } } }')
    identity = request('POST', 'graphql', {'query': query, 'variables': {'owner': owner, 'name': name}})
    if identity.status != 200 or set(identity.value) != {'data'}:
        return False
    meta = metadata.value
    data = identity.value['data']
    repo, viewer = data['repository'], data['viewer']
    branch = repo['defaultBranchRef']
    if (type(meta['id']) is not int or meta['id'] <= 0
            or meta['full_name'] != repository or repo['nameWithOwner'] != repository
            or type(repo['databaseId']) is not int or repo['databaseId'] != meta['id']
            or not isinstance(viewer['login'], str) or not viewer['login']
            or not isinstance(viewer['id'], str) or not viewer['id']
            or repo['viewerPermission'] not in {'READ', 'TRIAGE', 'WRITE', 'MAINTAIN', 'ADMIN'}
            or branch['name'] != base_branch):
        return False
    expected = commit_sha(branch['target']['oid'])
    base = request('GET', f'repos/{repository}/git/ref/heads/{base_branch}')
    return (base.status == 200 and base.value['object']['type'] == 'commit'
            and commit_sha(base.value['object']['sha']) == expected)


def observe_journal(
    repository: str, base_branch: str, claim_ref: str, request_id: str,
    state_path: str, request: Callable[..., GitHubJournalResponse],
) -> JournalObservation:
    reason = 'JOURNAL_REF_RESPONSE_INVALID'
    try:
        ref = request('GET', f'repos/{repository}/git/{claim_ref}')
        if ref.status == 404:
            if verified_absence(repository, base_branch, request):
                return JournalObservation(JournalReadKind.ABSENT_AUTHENTICATED)
            return JournalObservation(JournalReadKind.UNKNOWN, reason='JOURNAL_ABSENCE_UNVERIFIED')
        if ref.status != 200:
            return JournalObservation(JournalReadKind.UNKNOWN, reason='JOURNAL_REF_READ_UNKNOWN')
        value = ref.value
        if (value['ref'] != claim_ref or value['url'] != f'https://api.github.com/repos/{repository}/git/{claim_ref}'
                or value['object']['type'] != 'commit'):
            raise ValueError
        sha = commit_sha(value['object']['sha'])
        reason = 'JOURNAL_CONTENT_RESPONSE_INVALID'
        content = request('GET', f'repos/{repository}/contents/{state_path}?ref={sha}')
        value = content.value
        if content.status != 200 or value['encoding'] != 'base64' or not isinstance(value['content'], str):
            raise ValueError
        raw = decode_github_contents_base64(value['content'])
        decoded = json.loads(raw.decode('utf-8'))
        if not isinstance(decoded, dict) or raw != canonical_bytes(decoded) + b'\n':
            raise ValueError
        record = AttemptRecord.from_dict(decoded)
        if record.request_id != request_id or record.attempt_id != attempt_identity(request_id, 1):
            raise ValueError
        return JournalObservation(JournalReadKind.PRESENT_VERIFIED, (sha, record))
    except JournalReadUnknown as exc:
        return JournalObservation(JournalReadKind.UNKNOWN, reason=str(exc))
    except (KeyError, TypeError, ValueError, AttributeError, StateTransitionError):
        return JournalObservation(JournalReadKind.UNKNOWN, reason=reason)
