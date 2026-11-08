"""Identity-bearing GitHub Git-data and immutable Contents response validation."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from graphlib import TopologicalSorter
from urllib.parse import urlsplit

from .github_contents import decode_github_contents_base64
from .git_blob_identity import blob_identity, sha1_oid as commit_sha


_GIT_RESOURCES = {'blob': 'blobs', 'tree': 'trees', 'commit': 'commits'}
_GIT_KINDS = {resource: kind for kind, resource in _GIT_RESOURCES.items()}


def _add_object_role(roles: dict[str, str], sha: str, kind: str) -> None:
    commit_sha(sha)
    if kind not in _GIT_RESOURCES or (sha in roles and roles[sha] != kind):
        raise ValueError
    roles[sha] = kind


def object_roles(
    assertions: Iterable[tuple[str, str]], known: Mapping[str, str] | None = None,
) -> dict[str, str]:
    roles: dict[str, str] = {}
    for sha, kind in (known or {}).items():
        _add_object_role(roles, sha, kind)
    for sha, kind in assertions:
        _add_object_role(roles, sha, kind)
    return roles


def _add_blob_size(sizes: dict[str, int], sha: str, size: int) -> None:
    commit_sha(sha)
    if type(size) is not int or size < 0 or (sha in sizes and sizes[sha] != size):
        raise ValueError
    sizes[sha] = size


def blob_sizes(
    assertions: Iterable[tuple[str, int]], known: Mapping[str, int] | None = None,
) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for sha, size in (known or {}).items():
        _add_blob_size(sizes, sha, size)
    for sha, size in assertions:
        _add_blob_size(sizes, sha, size)
    return sizes


def object_links(
    assertions: Iterable[tuple[str, str]], known: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, frozenset[str]]:
    """Check only already-supplied ancestor links; never fetch a remote graph."""
    links: dict[str, set[str]] = {}
    for source, targets in (known or {}).items():
        links[commit_sha(source)] = {commit_sha(target) for target in targets}
    for source, target in assertions:
        links.setdefault(commit_sha(source), set()).add(commit_sha(target))
    TopologicalSorter(links).prepare()  # CycleError is a ValueError; DAG sharing is valid.
    return {source: frozenset(targets) for source, targets in links.items()}


def verify_tree_paths(paths: Mapping[str, str]) -> None:
    _tree_path_ancestors(paths)


def _tree_path_ancestors(paths: Mapping[str, str]) -> list[tuple[str, str]]:
    ancestors = []
    for path in paths:
        components = path.split('/')
        if any(part in {'', '.', '..'} or '\x00' in part for part in components):
            raise ValueError
        for end in range(1, len(components)):
            prefix = '/'.join(components[:end])
            ancestor = paths.get(prefix)
            if ancestor is not None:
                if ancestor != 'tree':
                    raise ValueError
                ancestors.append((prefix, path))
    return ancestors


def git_object_sha(
    value: object, repository: str, resource: str, *, known_roles: Mapping[str, str] | None = None,
    known_sizes: Mapping[str, int] | None = None,
    known_links: Mapping[str, frozenset[str]] | None = None,
) -> str:
    """Validate one response's roles, sizes, scope and supplied ancestry links."""
    return git_object_identity(value, repository, resource, known_roles=known_roles,
        known_sizes=known_sizes, known_links=known_links)[0]


def git_object_identity(
    value: object, repository: str, resource: str, *, known_roles: Mapping[str, str] | None = None,
    known_sizes: Mapping[str, int] | None = None,
    known_links: Mapping[str, frozenset[str]] | None = None,
) -> tuple[str, dict[str, str], dict[str, int]]:
    """Preserve the established identity/role/size projection for read callers."""
    sha, roles, sizes, _ = git_object_facts(value, repository, resource,
        known_roles=known_roles, known_sizes=known_sizes, known_links=known_links)
    return sha, roles, sizes


def git_object_facts(
    value: object, repository: str, resource: str, *, known_roles: Mapping[str, str] | None = None,
    known_sizes: Mapping[str, int] | None = None,
    known_links: Mapping[str, frozenset[str]] | None = None,
) -> tuple[str, dict[str, str], dict[str, int], dict[str, frozenset[str]]]:
    roles = object_roles([], known_roles)
    sizes = blob_sizes([], known_sizes)
    links: list[tuple[str, str]] = []
    sha = _git_object_sha(value, repository, resource, roles, sizes, links)
    return sha, roles, sizes, object_links(links, known_links)


def _git_object_sha(
    value: object, repository: str, resource: str, roles: dict[str, str], sizes: dict[str, int],
    links: list[tuple[str, str]],
) -> str:
    if not isinstance(value, dict):
        raise ValueError
    sha = commit_sha(value['sha'])
    _add_object_role(roles, sha, _GIT_KINDS[resource])
    if resource == 'blobs' and 'size' in value:
        _add_blob_size(sizes, sha, value['size'])
    if 'url' in value and value['url'] != f'https://api.github.com/repos/{repository}/git/{resource}/{sha}':
        raise ValueError
    if resource == 'trees':
        if 'truncated' in value and value['truncated'] is not False:
            raise ValueError
        if 'tree' in value:
            if not isinstance(value['tree'], list):
                raise ValueError
            paths = {}
            identities = {}
            modes = {'blob': {'100644', '100755', '120000'}, 'tree': {'040000'}, 'commit': {'160000'}}
            for entry in value['tree']:
                if (not isinstance(entry, dict) or not isinstance(entry['path'], str)
                        or not entry['path'] or entry['path'] in paths):
                    raise ValueError
                paths[entry['path']] = entry['type']
                if 'size' in entry and (type(entry['size']) is not int or entry['size'] < 0):
                    raise ValueError
                if entry['mode'] not in modes[entry['type']]:
                    raise ValueError
                identities[entry['path']] = _git_object_sha(entry, repository, _GIT_RESOURCES[entry['type']], roles, sizes, links)
                links.append((sha, identities[entry['path']]))
            for ancestor, path in _tree_path_ancestors(paths):
                links.append((identities[ancestor], identities[path]))
    if resource == 'commits':
        if 'html_url' in value and value['html_url'] != f'https://github.com/{repository}/commit/{sha}':
            raise ValueError
        if 'tree' in value:
            links.append((sha, _git_object_sha(value['tree'], repository, 'trees', roles, sizes, links)))
        if 'parents' in value:
            if not isinstance(value['parents'], list):
                raise ValueError
            for parent in value['parents']:
                links.append((sha, _git_object_sha(parent, repository, 'commits', roles, sizes, links)))
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


def verify_ref_update_ack(value: object, repository: str, ref: str, sha: str) -> None:
    # V1 permits an empty JSON ACK when exact unique-proposal readback follows.
    # Supplied identity, unlike absent redundant metadata, must never disagree.
    if isinstance(value, dict) and not value:
        return
    if ref_commit_sha(value, repository, ref, require_url=False) != commit_sha(sha):
        raise ValueError


def repository_id(value: object, repository: str) -> int:
    if not isinstance(value, dict) or value['full_name'] != repository:
        raise ValueError
    identity = value['id']
    if type(identity) is not int or identity <= 0:
        raise ValueError
    owner, name = repository.split('/')
    api_url = f'https://api.github.com/repos/{repository}'
    expected = {
        'name': name, 'url': api_url, 'html_url': f'https://github.com/{repository}',
        'clone_url': f'https://github.com/{repository}.git',
        'ssh_url': f'git@github.com:{repository}.git', 'git_url': f'git://github.com/{repository}.git',
        'svn_url': f'https://github.com/{repository}',
        'git_refs_url': api_url + '/git/refs{/sha}',
        'git_commits_url': api_url + '/git/commits{/sha}',
        'blobs_url': api_url + '/git/blobs{/sha}', 'trees_url': api_url + '/git/trees{/sha}',
        'contents_url': api_url + '/contents/{+path}',
    }
    for key, target in expected.items():
        if key in value and value[key] != target:
            raise ValueError
    if 'owner' in value:
        metadata = value['owner']
        if not isinstance(metadata, dict) or metadata['login'] != owner:
            raise ValueError
        for key, target in {'url': f'https://api.github.com/users/{owner}',
                            'html_url': f'https://github.com/{owner}'}.items():
            if key in metadata and metadata[key] != target:
                raise ValueError
    return identity


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
    if blob is not None:
        if blob_identity(raw) != blob:
            raise ValueError
        object_roles([(sha, 'commit'), (blob, 'blob')])
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
