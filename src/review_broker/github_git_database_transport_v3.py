"""Authenticated GitHub REST/GraphQL transport for the experimental v3 journal."""
from __future__ import annotations

import base64
from dataclasses import replace
import hashlib
import json
import re
from typing import Mapping
from urllib.parse import quote
from urllib.request import Request

from .github_http_live_v3 import (
    HttpExecutorV3, HttpResponseV3, _RejectRedirects, urllib_executor,
)
from .github_graphql_response_v3 import graphql_error_code
from .github_journal_transport_v3 import (
    CreateRefResultV3, CreateRefStatusV3, GraphQLRefUpdateV3, JOURNAL_UPDATE_REFS_QUERY_V3,
    encode_journal_http_payload_v3, JOURNAL_REPOSITORY_QUERY_V3,
    GraphQLUpdateResultV3, ReadResultV3, ReadStatusV3, TransportSnapshotV3,
)

_API = "https://api.github.com"
_VERSION = "2022-11-28"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_CLAIM = re.compile(r"^refs/heads/review-claims-v3/[0-9a-f]{64}$")
_QUALIFICATION = re.compile(
    r"^refs/heads/review-claims-v3/qualification-transport-[1-9][0-9]*-[1-9][0-9]*$"
)
from .github_journal_commit_writer_v3 import JOURNAL_PATH_V3 as _JOURNAL_PATH

from .github_git_database_error_v3 import GitHubTransportLiveV3Error


class GitHubTransportLiveV3:
    """Repository-bound GitHub Git Database transport; it provides no authority evidence."""

    def __init__(self, token: str, repository: str, *,
                 executor: HttpExecutorV3 | None = None,
                 allow_qualification_refs: bool = False):
        if not token or token.strip() != token or any(c in token for c in "\r\n"):
            raise ValueError("GITHUB_TOKEN_INVALID")
        parts = repository.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        self._token = token
        self.repository = repository
        self._owner, self._name = parts
        self._executor = executor or urllib_executor
        self._allow_qualification_refs = allow_qualification_refs
        self._repository_node_id: str | None = None
        self._mutation_attempt_count = 0

    @property
    def repository_node_id(self) -> str:
        return self._establish_repository_identity()

    def verify_repository_identity(self) -> str:
        """Freshly revalidate the pinned REST/GraphQL repository identity."""
        return self._establish_repository_identity(refresh=True)

    @property
    def mutation_attempt_count(self) -> int:
        """Observed write attempts, exposed only for qualification accounting."""
        return self._mutation_attempt_count

    @staticmethod
    def _sha(value: str) -> str:
        if not isinstance(value, str) or _SHA.fullmatch(value) is None:
            raise GitHubTransportLiveV3Error("GIT_SHA_INVALID")
        return value

    def _ref(self, value: str) -> str:
        if _CLAIM.fullmatch(value):
            return value
        if self._allow_qualification_refs and _QUALIFICATION.fullmatch(value):
            return value
        raise GitHubTransportLiveV3Error("JOURNAL_REF_INVALID")

    def _request(self, method: str, path: str, payload: object | None = None) -> HttpResponseV3:
        if (not path.startswith("/") or "//" in path
                or ("?" in path and not path.endswith("?recursive=1"))):
            raise GitHubTransportLiveV3Error("GITHUB_ENDPOINT_INVALID")
        body = None if payload is None else encode_journal_http_payload_v3(payload)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": _VERSION,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(_API + path, data=body, headers=headers, method=method)
        if method == "POST" and (path != "/graphql" or (
                isinstance(payload, dict) and str(payload.get("query", "")).startswith("mutation")
        )):
            self._mutation_attempt_count += 1
        failed = False
        try:
            if getattr(self, "before_effect", None) is not None: self.before_effect()
            response = self._executor(request)
        except Exception:
            failed = True
            response = None
        if failed:
            raise GitHubTransportLiveV3Error("GITHUB_TRANSPORT_UNAVAILABLE")
        if not isinstance(response, HttpResponseV3):
            raise GitHubTransportLiveV3Error("GITHUB_RESPONSE_INVALID")
        return response

    @staticmethod
    def _json(response: HttpResponseV3) -> Mapping[str, object]:
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubTransportLiveV3Error("GITHUB_JSON_INVALID") from exc
        if not isinstance(value, dict):
            raise GitHubTransportLiveV3Error("GITHUB_JSON_INVALID")
        return value

    def _rest(self, method: str, suffix: str, payload: object | None = None) -> HttpResponseV3:
        root = f"/repos/{quote(self._owner, safe='')}/{quote(self._name, safe='')}"
        return self._request(method, root + suffix, payload)

    def _graphql(self, query: str, variables: Mapping[str, object]) -> HttpResponseV3:
        return self._request("POST", "/graphql", {"query": query, "variables": variables})

    def _establish_repository_identity(self, *, refresh: bool = False) -> str:
        if self._repository_node_id is not None and not refresh:
            return self._repository_node_id
        rest = self._rest("GET", "")
        if rest.status != 200:
            raise GitHubTransportLiveV3Error("REPOSITORY_IDENTITY_UNAVAILABLE")
        rest_body = self._json(rest)
        if rest_body.get("full_name") != self.repository:
            raise GitHubTransportLiveV3Error("REPOSITORY_IDENTITY_MISMATCH")
        rest_node = rest_body.get("node_id")
        if not isinstance(rest_node, str) or not rest_node:
            raise GitHubTransportLiveV3Error("REPOSITORY_NODE_ID_INVALID")
        response = self._graphql(
            JOURNAL_REPOSITORY_QUERY_V3,
            {"owner": self._owner, "name": self._name},
        )
        if response.status != 200:
            raise GitHubTransportLiveV3Error("REPOSITORY_GRAPHQL_IDENTITY_UNAVAILABLE")
        body = self._json(response)
        if "errors" in body:
            raise GitHubTransportLiveV3Error("REPOSITORY_GRAPHQL_IDENTITY_UNAVAILABLE")
        repository = (body.get("data") or {}).get("repository") if isinstance(body.get("data"), dict) else None
        if not isinstance(repository, dict) or repository.get("nameWithOwner") != self.repository:
            raise GitHubTransportLiveV3Error("REPOSITORY_IDENTITY_MISMATCH")
        if repository.get("id") != rest_node:
            raise GitHubTransportLiveV3Error("REPOSITORY_NODE_ID_MISMATCH")
        if self._repository_node_id is not None and rest_node != self._repository_node_id:
            raise GitHubTransportLiveV3Error("REPOSITORY_NODE_ID_DRIFT")
        self._repository_node_id = rest_node
        return rest_node

    def _get_commit(self, sha: str, *, require_one_parent: bool = False) -> Mapping[str, object]:
        expected = self._sha(sha)
        response = self._rest("GET", f"/git/commits/{expected}")
        if response.status != 200:
            raise GitHubTransportLiveV3Error("GIT_COMMIT_UNAVAILABLE")
        commit = self._json(response)
        if commit.get("sha") != expected:
            raise GitHubTransportLiveV3Error("GIT_COMMIT_IDENTITY_MISMATCH")
        tree = commit.get("tree")
        parents = commit.get("parents")
        if not isinstance(tree, dict) or self._sha(tree.get("sha")) != tree.get("sha"):
            raise GitHubTransportLiveV3Error("GIT_COMMIT_TREE_INVALID")
        if (not isinstance(parents, list)
                or (require_one_parent and len(parents) != 1)):
            raise GitHubTransportLiveV3Error("GIT_COMMIT_PARENT_INVALID")
        for parent in parents:
            if (not isinstance(parent, dict)
                    or self._sha(parent.get("sha")) != parent.get("sha")):
                raise GitHubTransportLiveV3Error("GIT_COMMIT_PARENT_INVALID")
        return commit

    def _get_tree_entries(self, tree_sha: str) -> list[Mapping[str, object]]:
        response = self._rest("GET", f"/git/trees/{self._sha(tree_sha)}?recursive=1", None)
        if response.status != 200:
            raise GitHubTransportLiveV3Error("GIT_TREE_UNAVAILABLE")
        tree = self._json(response)
        entries = tree.get("tree")
        if (tree.get("sha") != tree_sha or tree.get("truncated") is not False
                or not isinstance(entries, list)
                or any(not isinstance(entry, dict) for entry in entries)):
            raise GitHubTransportLiveV3Error("GIT_TREE_INVALID")
        return entries

    def _read_journal_blob(self, tree_sha: str) -> bytes:
        entries = self._get_tree_entries(tree_sha)
        matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == _JOURNAL_PATH]
        if len(matches) != 1:
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_AMBIGUOUS")
        entry = matches[0]
        if entry.get("mode") != "100644" or entry.get("type") != "blob":
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_TYPE_INVALID")
        blob_sha = self._sha(entry.get("sha"))
        blob_response = self._rest("GET", f"/git/blobs/{blob_sha}")
        if blob_response.status != 200:
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_UNAVAILABLE")
        blob = self._json(blob_response)
        if blob.get("sha") != blob_sha or blob.get("encoding") != "base64":
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_IDENTITY_MISMATCH")
        content = blob.get("content")
        if not isinstance(content, str):
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_INVALID")
        encoded = content.replace("\n", "")
        if "\r" in encoded:
            encoded = encoded.replace("\r", "")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_BASE64_INVALID") from exc
        identity = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if identity != blob_sha or blob.get("size") != len(raw):
            raise GitHubTransportLiveV3Error("JOURNAL_BLOB_IDENTITY_MISMATCH")
        return raw

    def read_claim(self, claim_ref: str) -> ReadResultV3:
        ref = self._ref(claim_ref)
        try:
            self._establish_repository_identity(refresh=True)
        except GitHubTransportLiveV3Error:
            return ReadResultV3(ReadStatusV3.UNAVAILABLE)
        suffix = quote(ref.removeprefix("refs/"), safe="/")
        response = self._rest("GET", f"/git/ref/{suffix}")
        if response.status == 404:
            matching = self._rest("GET", f"/git/matching-refs/{suffix}")
            if matching.status != 200:
                return ReadResultV3(ReadStatusV3.UNAVAILABLE)
            try:
                candidates = json.loads(matching.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return ReadResultV3(ReadStatusV3.UNAVAILABLE)
            if candidates == []:
                return ReadResultV3(ReadStatusV3.MISSING)
            return ReadResultV3(ReadStatusV3.UNAVAILABLE)
        if response.status != 200:
            return ReadResultV3(ReadStatusV3.UNAVAILABLE)
        try:
            body = self._json(response)
            if body.get("ref") != ref:
                raise GitHubTransportLiveV3Error("GIT_REF_IDENTITY_MISMATCH")
            obj = body.get("object")
            if not isinstance(obj, dict) or obj.get("type") != "commit":
                raise GitHubTransportLiveV3Error("GIT_REF_OBJECT_INVALID")
            commit_sha = self._sha(obj.get("sha"))
            commit = self._get_commit(commit_sha, require_one_parent=True)
            parent_sha = commit["parents"][0]["sha"]
            journal = self._read_journal_blob(commit["tree"]["sha"])
            return ReadResultV3(
                ReadStatusV3.FOUND, TransportSnapshotV3(commit_sha, parent_sha, journal)
            )
        except GitHubTransportLiveV3Error:
            return ReadResultV3(ReadStatusV3.UNAVAILABLE)

    from .github_journal_history_transport_v3 import read_journal_commit_v3 as read_journal_commit

    @staticmethod
    def _git_blob_sha(content: bytes) -> str:
        return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()

    from .github_journal_commit_writer_v3 import create_journal_commit_v3 as create_journal_commit

    def create_ref(self, claim_ref: str, commit_sha: str) -> CreateRefResultV3:
        ref, sha = self._ref(claim_ref), self._sha(commit_sha)
        commit = self._get_commit(sha, require_one_parent=True)
        self._read_journal_blob(commit["tree"]["sha"])
        self._establish_repository_identity(refresh=True)
        try:
            response = self._rest("POST", "/git/refs", {"ref": ref, "sha": sha})
        except GitHubTransportLiveV3Error:
            return CreateRefResultV3(CreateRefStatusV3.UNKNOWN)
        if response.status == 201:
            try:
                body = self._json(response)
                obj = body.get("object")
                if body.get("ref") == ref and isinstance(obj, dict) and obj.get("type") == "commit" and obj.get("sha") == sha:
                    return CreateRefResultV3(CreateRefStatusV3.CREATED)
            except GitHubTransportLiveV3Error:
                pass
            return CreateRefResultV3(CreateRefStatusV3.UNKNOWN)
        if response.status == 422:
            try:
                body = self._json(response)
                errors = body.get("errors")
                if (body.get("message") == "Reference already exists" and isinstance(errors, list)
                        and any(isinstance(error, dict)
                                and error.get("resource") == "Reference"
                                and error.get("field") == "ref"
                                and error.get("code") == "already_exists"
                                for error in errors)):
                    return CreateRefResultV3(CreateRefStatusV3.ALREADY_EXISTS)
            except GitHubTransportLiveV3Error:
                pass
        return CreateRefResultV3(CreateRefStatusV3.UNKNOWN)

    def update_ref(self, update: GraphQLRefUpdateV3) -> GraphQLUpdateResultV3:
        ref = self._ref(update.name)
        before, after = self._sha(update.before_oid), self._sha(update.after_oid)
        if update.force is not False:
            raise GitHubTransportLiveV3Error("GRAPHQL_FORCE_FORBIDDEN")
        repository_id = self._establish_repository_identity()
        if update.repository_id != repository_id:
            raise GitHubTransportLiveV3Error("GRAPHQL_REPOSITORY_ID_MISMATCH")
        successor = self._get_commit(after, require_one_parent=True)
        self._read_journal_blob(successor["tree"]["sha"])
        if successor["parents"][0]["sha"] != before:
            raise GitHubTransportLiveV3Error("GRAPHQL_SUCCESSOR_PARENT_MISMATCH")
        variables = {"repositoryId": repository_id, "name": ref, "beforeOid": before,
                     "afterOid": after, "force": False}
        mutation = JOURNAL_UPDATE_REFS_QUERY_V3
        try:
            if self._establish_repository_identity(refresh=True) != repository_id:
                raise GitHubTransportLiveV3Error("GRAPHQL_REPOSITORY_IDENTITY_DRIFT")
            response = self._graphql(mutation, variables)
        except GitHubTransportLiveV3Error:
            return GraphQLUpdateResultV3(None, ("GITHUB_TRANSPORT_UNAVAILABLE",))
        try:
            body = self._json(response)
        except GitHubTransportLiveV3Error:
            return GraphQLUpdateResultV3(response.status, ("GITHUB_JSON_INVALID",))
        errors: tuple[str, ...] = ()
        if "errors" in body:
            raw_errors = body["errors"]
            if not isinstance(raw_errors, list) or not raw_errors:
                errors = ("GRAPHQL_RESPONSE_INVALID",)
            else:
                errors = tuple(graphql_error_code(error) for error in raw_errors)
        data = body.get("data")
        if response.status != 200:
            return GraphQLUpdateResultV3(response.status, errors or ("GRAPHQL_HTTP_ERROR",))
        if errors:
            return GraphQLUpdateResultV3(200, errors)
        update_refs = data.get("updateRefs") if isinstance(data, dict) else None
        if (not isinstance(update_refs, dict) or "clientMutationId" not in update_refs
                or (update_refs["clientMutationId"] is not None
                    and not isinstance(update_refs["clientMutationId"], str))):
            return GraphQLUpdateResultV3(200, ("GRAPHQL_RESPONSE_INVALID",))
        return GraphQLUpdateResultV3(200, ())


class GitHubJournalEvidenceTransportV3(GitHubTransportLiveV3):
    """Acknowledged target evidence only; mandatory actor guard at every HTTP call.

    Kept at the existing concrete transport import boundary. Target continuity
    is not an author signature and never fills a lost operation acknowledgment.
    """
    def __init__(self, token: str, *, before_effect, executor=None):
        if not callable(before_effect):
            raise ValueError("LIVE_JOURNAL_GUARD_REQUIRED")
        super().__init__(token, "fanilosendrison/review-broker", executor=executor)
        self.before_effect = before_effect

    def _target_evidence(self, claim_ref, before, after):
        from .github_journal_transition_authority_v3 import transition_target_identity_v3
        return transition_target_identity_v3(repository=self.repository,
            repository_node_id=self.repository_node_id, claim_ref=claim_ref,
            predecessor_sha=before, successor_sha=after)

    def create_ref(self, claim_ref, commit_sha):
        predecessor = self._get_commit(commit_sha, require_one_parent=True)["parents"][0]["sha"]
        result = super().create_ref(claim_ref, commit_sha)
        if result.status is not CreateRefStatusV3.CREATED:
            return result
        return replace(result, writer_evidence_id=self._target_evidence(
            claim_ref, predecessor, commit_sha))

    def update_ref(self, update):
        result = super().update_ref(update)
        if result.http_status != 200 or result.errors:
            return result
        return replace(result, writer_evidence_id=self._target_evidence(
            update.name, update.before_oid, update.after_oid))
