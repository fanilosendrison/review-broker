"""Reconcile explicit immutable tree/path bindings, including sparse descriptions."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .git_blob_identity import sha1_oid

TreeEntry = tuple[str, str, str]  # mode, kind, child object identity
TreePath = tuple[str, str]  # containing tree identity, exact relative Git path
_TREE_MODES = {'blob': {'100644', '100755', '120000'}, 'tree': {'040000'}, 'commit': {'160000'}}


def verify_tree_paths(paths: Mapping[str, str]) -> None:
    for path in paths:
        components = path.split('/')
        if any(part in {'', '.', '..'} or '\x00' in part for part in components):
            raise ValueError
        for end in range(1, len(components)):
            ancestor = paths.get('/'.join(components[:end]))
            if ancestor is not None and ancestor != 'tree':
                raise ValueError


def tree_bindings(
    assertions: Iterable[tuple[TreePath, TreeEntry]],
    known: Mapping[TreePath, TreeEntry] | None = None,
) -> dict[TreePath, TreeEntry]:
    """Retain rooted paths; rebase suffixes only at explicitly identified trees.

    A missing prefix has no invented identity. Its rooted descendant assertion
    nevertheless survives, so a prefix supplied in a later ACK cannot hide it.
    Closure only shortens supplied paths over a finite set of observed IDs.
    Compatible partial lists do not assert that unlisted children are absent.
    """
    bindings: dict[TreePath, TreeEntry] = {}
    by_tree: dict[str, dict[str, TreeEntry]] = {}
    pending = [*((known or {}).items()), *assertions]
    while pending:
        (tree, path), description = pending.pop()
        mode, kind, child = description
        sha1_oid(tree)
        sha1_oid(child)
        if mode not in _TREE_MODES[kind]:
            raise ValueError
        verify_tree_paths({path: kind})
        key = tree, path
        if key in bindings:
            if bindings[key] != description:
                raise ValueError
            continue
        siblings = by_tree.setdefault(tree, {})
        for other_path, other in siblings.items():
            if path.startswith(other_path + '/'):
                prefix, ancestor, descendant = other_path, other, (path, description)
            elif other_path.startswith(path + '/'):
                prefix, ancestor, descendant = path, description, (other_path, other)
            else:
                continue
            if ancestor[1] != 'tree':
                raise ValueError
            suffix = descendant[0][len(prefix) + 1:]
            pending.append(((ancestor[2], suffix), descendant[1]))
        bindings[key] = description
        siblings[path] = description
    return bindings
