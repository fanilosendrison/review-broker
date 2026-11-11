"""Git Database immutable journal commit assembly; no ref mutation or actor authority."""
from __future__ import annotations

import base64
from typing import Mapping

from .github_git_database_error_v3 import GitHubTransportLiveV3Error
from .github_journal_transport_v3 import JOURNAL_COMMIT_MESSAGE_V3

JOURNAL_PATH_V3 = ".review-broker/attempt.json"


def create_journal_commit_v3(self, parent_sha: str, journal_bytes: bytes) -> str:
    """Shared transport method, mechanically extracted without changing effect order."""
    parent_sha = self._sha(parent_sha)
    if not isinstance(journal_bytes, bytes):
        raise GitHubTransportLiveV3Error("JOURNAL_BYTES_INVALID")
    self._establish_repository_identity()
    parent = self._get_commit(parent_sha)
    base_tree = parent["tree"]["sha"]
    parent_entries = self._get_tree_entries(base_tree)
    namespace_entries = [entry for entry in parent_entries if entry.get("path") == ".review-broker"]
    if (namespace_entries and (len(namespace_entries) != 1
            or namespace_entries[0].get("mode") != "040000"
            or namespace_entries[0].get("type") != "tree")):
        raise GitHubTransportLiveV3Error("JOURNAL_NAMESPACE_TYPE_INVALID")
    self._establish_repository_identity(refresh=True)
    blob = self._rest("POST", "/git/blobs", {
        "content": base64.b64encode(journal_bytes).decode("ascii"), "encoding": "base64",
    })
    if blob.status != 201:
        raise GitHubTransportLiveV3Error("GIT_BLOB_CREATION_UNRESOLVED")
    blob_sha = self._json(blob).get("sha")
    if blob_sha != self._git_blob_sha(journal_bytes):
        raise GitHubTransportLiveV3Error("GIT_BLOB_CREATION_IDENTITY_MISMATCH")
    self._establish_repository_identity(refresh=True)
    tree_response = self._rest("POST", "/git/trees", {
        "base_tree": base_tree,
        "tree": [{"path": JOURNAL_PATH_V3, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    if tree_response.status != 201:
        raise GitHubTransportLiveV3Error("GIT_TREE_CREATION_UNRESOLVED")
    tree_sha = self._sha(self._json(tree_response).get("sha"))
    self._establish_repository_identity(refresh=True)
    commit_response = self._rest("POST", "/git/commits", {
        "message": JOURNAL_COMMIT_MESSAGE_V3,
        "tree": tree_sha, "parents": [parent_sha],
    })
    if commit_response.status != 201:
        raise GitHubTransportLiveV3Error("GIT_COMMIT_CREATION_UNRESOLVED")
    commit_sha = self._sha(self._json(commit_response).get("sha"))
    observed = self._get_commit(commit_sha, require_one_parent=True)
    if observed["tree"]["sha"] != tree_sha or observed["parents"][0]["sha"] != parent_sha:
        raise GitHubTransportLiveV3Error("GIT_COMMIT_CREATION_IDENTITY_MISMATCH")
    created_entries = self._get_tree_entries(tree_sha)
    def retained(entries: list[Mapping[str, object]]) -> list[tuple[object, object, object, object]]:
        return sorted(
            (entry.get("path"), entry.get("mode"), entry.get("type"), entry.get("sha"))
            for entry in entries
            if entry.get("path") not in {JOURNAL_PATH_V3, ".review-broker"}
        )
    if retained(created_entries) != retained(parent_entries):
        raise GitHubTransportLiveV3Error("GIT_TREE_PRESERVATION_MISMATCH")
    if self._read_journal_blob(tree_sha) != journal_bytes:
        raise GitHubTransportLiveV3Error("GIT_COMMIT_PAYLOAD_MISMATCH")
    return commit_sha
