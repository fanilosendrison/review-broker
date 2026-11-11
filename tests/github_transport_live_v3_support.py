"""Deterministic HTTP executor for live-v3 transport tests."""
from __future__ import annotations

import base64
import hashlib
import json
from urllib.request import Request

from review_broker.github_transport_live_v3 import HttpResponseV3

REPOSITORY = "fanilosendrison/review-broker"
NODE_ID = "R_repo_node"
PARENT = "1" * 40
GRANDPARENT = "0" * 40
PARENT_TREE = "2" * 40
REF = "refs/heads/review-claims-v3/" + "a" * 64
QUAL_REF = "refs/heads/review-claims-v3/qualification-transport-123-1"


def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def response(status: int, value: object) -> HttpResponseV3:
    return HttpResponseV3(status, json.dumps(value, separators=(",", ":")).encode(), {})


class FakeGitHubApi:
    def __init__(self):
        self.calls: list[tuple[str, str, object | None, str]] = []
        self.repository = REPOSITORY
        self.repository_status = 200
        self.repository_calls = 0
        self.repository_drift_after: int | None = None
        self.node_drift_after: int | None = None
        self.rest_node = NODE_ID
        self.graphql_node = NODE_ID
        self.graphql_name = REPOSITORY
        self.refs: dict[str, str] = {}
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, list[dict[str, object]]] = {PARENT_TREE: [
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "3" * 40},
        ]}
        self.commits: dict[str, tuple[str, list[str]]] = {
            PARENT: (PARENT_TREE, [GRANDPARENT]),
        }
        self.next_tree = "4" * 40
        self.next_commit = "5" * 40
        self.create_ref_status = 201
        self.matching_refs_status = 200
        self.create_ref_body: object | None = None
        self.graphql_status = 200
        self.identity_graphql_body: object | None = None
        self.graphql_body: object = {"data": {"updateRefs": {"clientMutationId": None}}}
        self.raise_on: tuple[str, str] | None = None
        self.raise_graphql_mutation = False
        self.mutation_calls = 0
        self.truncated = False
        self.tree_override: object | None = None
        self.blob_override: object | None = None
        self.drop_parent_entries = False

    def install_journal(self, ref: str = REF, content: bytes = b"exact\x00bytes",
                        *, publish: bool = True) -> tuple[str, str]:
        blob_sha = git_blob_sha(content)
        tree_sha = "6" * 40
        commit_sha = "7" * 40
        self.blobs[blob_sha] = content
        self.trees[tree_sha] = [
            {"path": ".review-broker", "mode": "040000", "type": "tree", "sha": "d" * 40},
            {"path": ".review-broker/attempt.json", "mode": "100644", "type": "blob", "sha": blob_sha},
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "3" * 40},
        ]
        self.commits[commit_sha] = (tree_sha, [PARENT])
        if publish:
            self.refs[ref] = commit_sha
        return commit_sha, blob_sha

    def install_successor(self, before: str, after: str = "8" * 40,
                          content: bytes = b"successor journal") -> str:
        blob_sha = git_blob_sha(content)
        tree_sha = "9" * 40
        self.blobs[blob_sha] = content
        self.trees[tree_sha] = [
            {"path": ".review-broker", "mode": "040000", "type": "tree", "sha": "d" * 40},
            {"path": ".review-broker/attempt.json", "mode": "100644",
             "type": "blob", "sha": blob_sha},
        ]
        self.commits[after] = (tree_sha, [before])
        return after

    def _record(self, request: Request) -> tuple[str, str, object | None]:
        method = request.get_method()
        url = request.full_url
        body = json.loads(request.data) if request.data is not None else None
        authorization = request.headers.get("Authorization", "")
        self.calls.append((method, url, body, authorization))
        if self.raise_on == (method, url):
            raise OSError("token must not appear: secret-token")
        return method, url, body

    def __call__(self, request: Request) -> HttpResponseV3:
        method, url, body = self._record(request)
        path = url.removeprefix("https://api.github.com")
        root = "/repos/fanilosendrison/review-broker"
        if method == "GET" and path == root:
            self.repository_calls += 1
            full_name = ("other/repository"
                         if self.repository_drift_after is not None
                         and self.repository_calls > self.repository_drift_after
                         else self.repository)
            node_id = ("R_replacement"
                       if self.node_drift_after is not None
                       and self.repository_calls > self.node_drift_after
                       else self.rest_node)
            return response(self.repository_status,
                            {"full_name": full_name, "node_id": node_id})
        if method == "POST" and path == "/graphql":
            query = body.get("query", "") if isinstance(body, dict) else ""
            if query.startswith("query"):
                if self.identity_graphql_body is not None:
                    return response(200, self.identity_graphql_body)
                return response(200, {"data": {"repository": {
                    "id": ("R_replacement"
                           if self.node_drift_after is not None
                           and self.repository_calls > self.node_drift_after
                           else self.graphql_node),
                    "nameWithOwner": self.graphql_name,
                }}})
            if self.raise_graphql_mutation:
                raise OSError("lost GraphQL mutation acknowledgment")
            self.mutation_calls += 1
            return response(self.graphql_status, self.graphql_body)
        if method == "GET" and path.startswith(root + "/git/matching-refs/"):
            short = path.removeprefix(root + "/git/matching-refs/")
            matches = [
                {"ref": ref, "object": {"type": "commit", "sha": sha}}
                for ref, sha in self.refs.items() if ref.removeprefix("refs/").startswith(short)
            ]
            return response(self.matching_refs_status, matches)
        if method == "GET" and path.startswith(root + "/git/ref/"):
            short = path.removeprefix(root + "/git/ref/")
            ref = "refs/" + short
            sha = self.refs.get(ref)
            if sha is None:
                return response(404, {"message": "Not Found"})
            return response(200, {"ref": ref, "object": {"type": "commit", "sha": sha}})
        if method == "GET" and path.startswith(root + "/git/commits/"):
            sha = path.rsplit("/", 1)[1]
            commit = self.commits.get(sha)
            if commit is None:
                return response(404, {"message": "Not Found"})
            tree, parents = commit
            return response(200, {"sha": sha, "tree": {"sha": tree},
                                  "parents": [{"sha": parent} for parent in parents]})
        if method == "GET" and path.startswith(root + "/git/trees/"):
            sha = path.removeprefix(root + "/git/trees/").removesuffix("?recursive=1")
            if self.tree_override is not None:
                return response(200, self.tree_override)
            return response(200, {"sha": sha, "truncated": self.truncated,
                                  "tree": self.trees.get(sha, [])})
        if method == "GET" and path.startswith(root + "/git/blobs/"):
            sha = path.rsplit("/", 1)[1]
            if self.blob_override is not None:
                return response(200, self.blob_override)
            content = self.blobs.get(sha)
            if content is None:
                return response(404, {"message": "Not Found"})
            return response(200, {"sha": sha, "encoding": "base64", "size": len(content),
                                  "content": base64.b64encode(content).decode()})
        if method == "POST" and path == root + "/git/blobs":
            self.mutation_calls += 1
            content = base64.b64decode(body["content"])
            sha = git_blob_sha(content)
            self.blobs[sha] = content
            return response(201, {"sha": sha})
        if method == "POST" and path == root + "/git/trees":
            self.mutation_calls += 1
            assert body["base_tree"] == PARENT_TREE
            entries = [] if self.drop_parent_entries else list(self.trees[PARENT_TREE])
            entries = [entry for entry in entries if entry["path"] != body["tree"][0]["path"]]
            entries.append({"path": ".review-broker", "mode": "040000",
                            "type": "tree", "sha": "e" * 40})
            entries.extend(body["tree"])
            self.trees[self.next_tree] = entries
            return response(201, {"sha": self.next_tree})
        if method == "POST" and path == root + "/git/commits":
            self.mutation_calls += 1
            self.commits[self.next_commit] = (body["tree"], list(body["parents"]))
            return response(201, {"sha": self.next_commit})
        if method == "POST" and path == root + "/git/refs":
            self.mutation_calls += 1
            if self.create_ref_status == 201:
                self.refs[body["ref"]] = body["sha"]
            value = self.create_ref_body
            if value is None:
                value = {"ref": body["ref"], "object": {"type": "commit", "sha": body["sha"]}}
            return response(self.create_ref_status, value)
        raise AssertionError((method, path, body))
