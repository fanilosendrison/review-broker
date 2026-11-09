"""Construct one immutable Git proposal; never create or update a claim ref."""
from __future__ import annotations

import base64
import json
import secrets
import subprocess
from typing import Any, Callable

from .github_journal_http import JournalReadUnknown
from .github_contents import decode_github_contents_base64
from .git_blob_identity import blob_identity
from .github_journal_identity import (
    GitObjectFacts, blob_sizes, git_object_context, git_object_sha, object_roles, verify_tree_paths,
)
from .identity import canonical_bytes
from .queue import AttemptRecord

# Any is the existing untrusted/validated GitHub JSON payload representation.
Api = Callable[..., subprocess.CompletedProcess[str]]


def _verify_tree_bindings(
    value: dict[str, Any], payload: dict[str, Any],
) -> None:
    if 'tree' not in value:
        return
    returned = {entry['path']: entry for entry in value['tree']}
    described = {path: entry['type'] for path, entry in returned.items()}
    described.update({entry['path']: entry['type'] for entry in payload['tree']})
    verify_tree_paths(described)
    roots = {path.split('/', 1)[0] for path in returned}
    for expected in payload['tree']:
        if expected['path'].split('/', 1)[0] not in roots:
            raise ValueError
        observed = returned.get(expected['path'])
        if observed is None:
            components = expected['path'].split('/')
            ancestors = ['/'.join(components[:end]) for end in range(1, len(components))]
            if not any(path in returned and returned[path]['type'] == 'tree' for path in ancestors):
                raise ValueError
            continue  # An explicit compatible ancestor may represent the subtree.
        if any(observed[key] != expected[key] for key in ('mode', 'type', 'sha')):
            raise ValueError


def _create_object(
    api: Api, repository: str, resource: str, payload: dict[str, Any],
    *, known: GitObjectFacts,
) -> GitObjectFacts:
    try:
        roles = object_roles([], known.roles)
        sizes = blob_sizes([], known.sizes)
        expected_blob = None
        raw = b''
        if resource == 'blobs':
            if payload['encoding'] != 'base64' or not isinstance(payload['content'], str):
                raise ValueError
            raw = decode_github_contents_base64(payload['content'])
            expected_blob = blob_identity(raw)
            roles = object_roles([(expected_blob, 'blob')], roles)
            sizes = blob_sizes([(expected_blob, len(raw))], sizes)
        elif resource == 'trees':
            roles = object_roles([(entry['sha'], entry['type']) for entry in payload['tree']], roles)
        elif resource == 'commits':
            roles = object_roles([(payload['tree'], 'tree'), *[(p, 'commit') for p in payload['parents']]], roles)
        result = api('POST', f'repos/{repository}/git/{resource}', payload)
        value = json.loads(result.stdout)
        facts = git_object_context(value, repository, resource,
            known_roles=roles, known_sizes=sizes, known_links=known.links,
            known_bindings=known.bindings)
        sha = facts.sha
        if resource == 'blobs':
            if sha != expected_blob:
                raise ValueError
            if 'content' in value or 'encoding' in value:
                if (value['encoding'] != 'base64' or not isinstance(value['content'], str)
                        or decode_github_contents_base64(value['content']) != raw):
                    raise ValueError
        if resource == 'trees':
            _verify_tree_bindings(value, payload)
            # Submitted paths and returned flat/nested paths describe the same tree.
            facts = git_object_context({'sha': sha, 'tree': payload['tree']}, repository, 'trees',
                known_roles=facts.roles, known_sizes=facts.sizes, known_links=facts.links,
                known_bindings=facts.bindings)
        if resource == 'commits':
            facts = git_object_context({'sha': sha, 'tree': {'sha': payload['tree']},
                'parents': [{'sha': p} for p in payload['parents']]}, repository, 'commits',
                known_roles=facts.roles, known_sizes=facts.sizes, known_links=facts.links,
                known_bindings=facts.bindings)
            if 'message' in value and value['message'] not in (payload['message'], payload['message'] + '\n'):
                raise ValueError
            if 'tree' in value and git_object_sha(value['tree'], repository, 'trees') != payload['tree']:
                raise ValueError
            if 'parents' in value:
                parents = [git_object_sha(p, repository, 'commits') for p in value['parents']]
                if parents != payload['parents']:
                    raise ValueError
        return facts
    except (KeyError, TypeError, ValueError, RecursionError):
        raise JournalReadUnknown('JOURNAL_OBJECT_RESPONSE_UNKNOWN') from None


def state_commit(
    api: Api, repository: str, state_path: str, parent_sha: str, record: AttemptRecord,
) -> str:
    result = api('GET', f'repos/{repository}/git/commits/{parent_sha}')
    try:
        parent = json.loads(result.stdout)
        facts = git_object_context(parent, repository, 'commits')
        if facts.sha != parent_sha:
            raise ValueError
        parent_tree = git_object_sha(parent['tree'], repository, 'trees')
    except (KeyError, TypeError, ValueError, RecursionError):
        raise JournalReadUnknown('JOURNAL_PARENT_TREE_UNKNOWN') from None
    raw = canonical_bytes(record.as_dict()) + b'\n'
    encoded = base64.b64encode(raw).decode('ascii')
    facts = _create_object(api, repository, 'blobs', {'content': encoded, 'encoding': 'base64'}, known=facts)
    facts = _create_object(api, repository, 'trees', {
        'base_tree': parent_tree,
        'tree': [{'path': state_path, 'mode': '100644', 'type': 'blob', 'sha': facts.sha}],
    }, known=facts)
    facts = _create_object(api, repository, 'commits', {
        'message': f'state: {record.state.value} {record.attempt_id}\n\ntransaction: {secrets.token_hex(32)}',
        'tree': facts.sha, 'parents': [parent_sha],
    }, known=facts)
    return facts.sha
