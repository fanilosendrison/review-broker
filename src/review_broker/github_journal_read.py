"""Evidence-distinct journal observations, without changing v1 wire identity."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Callable

from .github_journal_identity import commit_sha, contents_bytes, ref_commit_sha, repository_id
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
    meta = metadata.value
    expected_id = repository_id(meta, repository)
    owner, name = repository.split('/')
    query = ('query($owner:String!,$name:String!) { viewer { login id } '
             'repository(owner:$owner,name:$name) { nameWithOwner databaseId viewerPermission '
             'defaultBranchRef { name target { oid } } } }')
    identity = request('POST', 'graphql', {'query': query, 'variables': {'owner': owner, 'name': name}})
    if identity.status != 200 or set(identity.value) != {'data'}:
        return False
    data = identity.value['data']
    repo, viewer = data['repository'], data['viewer']
    branch = repo['defaultBranchRef']
    if ('default_branch' in meta and meta['default_branch'] != base_branch
            or 'permissions' in meta and (
                not isinstance(meta['permissions'], dict) or meta['permissions'].get('pull') is not True)):
        return False
    if (repo['nameWithOwner'] != repository
            or type(repo['databaseId']) is not int or repo['databaseId'] != expected_id
            or not isinstance(viewer['login'], str) or not viewer['login']
            or not isinstance(viewer['id'], str) or not viewer['id']
            or repo['viewerPermission'] not in {'READ', 'TRIAGE', 'WRITE', 'MAINTAIN', 'ADMIN'}
            or branch['name'] != base_branch):
        return False
    expected = commit_sha(branch['target']['oid'])
    base = request('GET', f'repos/{repository}/git/ref/heads/{base_branch}')
    return (base.status == 200
            and ref_commit_sha(base.value, repository, f'refs/heads/{base_branch}') == expected)


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
        sha = ref_commit_sha(ref.value, repository, claim_ref)
        reason = 'JOURNAL_CONTENT_RESPONSE_INVALID'
        content = request('GET', f'repos/{repository}/contents/{state_path}?ref={sha}')
        if content.status != 200:
            raise ValueError
        raw = contents_bytes(content.value, repository, state_path, sha)
        decoded = json.loads(raw.decode('utf-8'))
        if not isinstance(decoded, dict) or raw != canonical_bytes(decoded) + b'\n':
            raise ValueError
        record = AttemptRecord.from_dict(decoded)
        if record.request_id != request_id or record.attempt_id != attempt_identity(request_id, 1):
            raise ValueError
        return JournalObservation(JournalReadKind.PRESENT_VERIFIED, (sha, record))
    except JournalReadUnknown as exc:
        return JournalObservation(JournalReadKind.UNKNOWN, reason=str(exc))
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError, StateTransitionError):
        return JournalObservation(JournalReadKind.UNKNOWN, reason=reason)
