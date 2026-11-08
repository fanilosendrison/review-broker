"""Identity-bearing GitHub Git-data and immutable Contents response validation."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .github_contents import decode_github_contents_base64


def commit_sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{40}', value) is None:
        raise ValueError
    return value


def git_object_sha(value: object, repository: str, resource: str) -> str:
    """Validate an object identity and any supplied repository-scoped link.

    A response's optional URL cannot contradict its request context. This is
    GitHub endpoint validation, not independent reconstruction of remote Git.
    """
    if not isinstance(value, dict):
        raise ValueError
    sha = commit_sha(value['sha'])
    if 'url' in value and value['url'] != f'https://api.github.com/repos/{repository}/git/{resource}/{sha}':
        raise ValueError
    if resource == 'commits':
        if 'html_url' in value and value['html_url'] != f'https://github.com/{repository}/commit/{sha}':
            raise ValueError
        if 'tree' in value:
            git_object_sha(value['tree'], repository, 'trees')
        if 'parents' in value:
            if not isinstance(value['parents'], list):
                raise ValueError
            for parent in value['parents']:
                git_object_sha(parent, repository, 'commits')
    return sha


def ref_commit_sha(
    value: object, repository: str, ref: str, *, require_url: bool = True,
) -> str:
    if not isinstance(value, dict):
        raise ValueError
    if value['ref'] != ref or value['object']['type'] != 'commit':
        raise ValueError
    if (require_url or 'url' in value) and value.get('url') != f'https://api.github.com/repos/{repository}/git/{ref}':
        raise ValueError
    return git_object_sha(value['object'], repository, 'commits')


def contents_bytes(value: object, repository: str, state_path: str, sha: str) -> bytes:
    """Require the response itself to identify the requested immutable commit.

    Requesting ?ref=SHA is insufficient if returned metadata explicitly names
    another commit. Download links are inspected only for scope, never followed
    or retained in diagnostics; private raw URLs may contain opaque tokens.
    """
    if not isinstance(value, dict):
        raise ValueError
    api_url = f'https://api.github.com/repos/{repository}/contents/{state_path}?ref={sha}'
    html_url = f'https://github.com/{repository}/blob/{sha}/{state_path}'
    if (value['path'] != state_path or value['type'] != 'file' or value['url'] != api_url
            or value['encoding'] != 'base64' or not isinstance(value['content'], str)):
        raise ValueError
    raw = decode_github_contents_base64(value['content'])
    if 'size' in value and (type(value['size']) is not int or value['size'] != len(raw)):
        raise ValueError
    if 'name' in value and value['name'] != state_path.rsplit('/', 1)[-1]:
        raise ValueError
    if 'html_url' in value and value['html_url'] != html_url:
        raise ValueError
    blob = commit_sha(value['sha']) if 'sha' in value else None
    git_url = f'https://api.github.com/repos/{repository}/git/blobs/{blob}' if blob is not None else None
    if 'git_url' in value and (git_url is None or value['git_url'] != git_url):
        raise ValueError
    if '_links' in value:
        links = value['_links']
        if not isinstance(links, dict):
            raise ValueError
        expected = {'self': api_url, 'html': html_url, 'git': git_url}
        for key, target in expected.items():
            if key in links and (target is None or links[key] != target):
                raise ValueError
    if value.get('download_url') is not None:
        download = value['download_url']
        if not isinstance(download, str):
            raise ValueError
        parsed = urlsplit(download)
        if (parsed.scheme != 'https' or parsed.netloc != 'raw.githubusercontent.com'
                or parsed.path != f'/{repository}/{sha}/{state_path}' or parsed.fragment):
            raise ValueError
    return raw
