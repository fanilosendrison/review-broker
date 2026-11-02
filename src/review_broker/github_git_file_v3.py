"""Authenticated read-only Git Database acquisition for candidate v3 git_file references."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import base64
import binascii
import hashlib
import json
import re
from typing import Callable, Mapping
from urllib.parse import quote
from urllib.request import Request

from .github_http_live_v3 import HttpExecutorV3, HttpResponseV3, urllib_executor_bounded
from .identity import artifact_identity, canonical_bytes
from .physical import PhysicalLineError, decode_physical_lines

_API = "https://api.github.com"
_VERSION = "2022-11-28"
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_MAX_BYTES = 2_000_000
_MAX_RESPONSE = 3_000_000


class GitHubGitFileV3Error(RuntimeError):
    """A Git object read failed without exposing credentials or private bytes."""


@dataclass(frozen=True)
class GitHubGitFileObservationV3:
    repository: str
    repository_id: int
    commit_sha: str
    root_tree_sha: str
    path: str
    git_blob_oid: str
    original_bytes: bytes
    original_byte_length: int
    sha256: str
    observed_at: str
    api_source: str
    qualification: str
    authority_evidence_id: str
    installation_id: int | None
    evidence_id: str

    def provenance_basis(self) -> dict[str, object]:
        return {"schema_version": 1, "evidence_type": "github-git-file-observation",
            "repository": self.repository, "repository_id": self.repository_id,
            "commit_sha": self.commit_sha, "root_tree_sha": self.root_tree_sha,
            "path": self.path, "git_blob_oid": self.git_blob_oid,
            "original_byte_length": self.original_byte_length, "sha256": self.sha256,
            "observed_at": self.observed_at, "api_source": self.api_source,
            "qualification": self.qualification, "authority_evidence_id": self.authority_evidence_id,
            "installation_id": self.installation_id}


ClockV3 = Callable[[], datetime]


def _positive(value: object, marker: str) -> int:
    if type(value) is not int or value < 1: raise GitHubGitFileV3Error(marker)
    return value


def _object(response: HttpResponseV3, marker: str) -> Mapping[str, object]:
    if len(response.body) > _MAX_RESPONSE: raise GitHubGitFileV3Error("GIT_FILE_RESPONSE_TOO_LARGE")
    try: value = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError): raise GitHubGitFileV3Error(marker) from None
    if not isinstance(value, dict): raise GitHubGitFileV3Error(marker)
    return value


class GitHubGitFileReaderV3:
    """Resolve an exact commit/tree/blob chain under authenticated repository identity."""

    def __init__(self, token: str, repository: str, repository_id: int, *,
                 authority_evidence_id: str, expected_installation_id: int | None = None,
                 source_authority: object | None = None, qualification_only: bool = False,
                 executor: HttpExecutorV3 | None = None,
                 clock: ClockV3 | None = None):
        if not token or token.strip() != token or any(c in token for c in "\r\n"):
            raise ValueError("GITHUB_TOKEN_INVALID")
        if _REPOSITORY.fullmatch(repository) is None or ".." in repository:
            raise ValueError("GITHUB_REPOSITORY_INVALID")
        _positive(repository_id, "GITHUB_REPOSITORY_ID_INVALID")
        if (not authority_evidence_id.startswith("artifact:sha256:")
                or len(authority_evidence_id) != 80): raise ValueError("GITHUB_SOURCE_AUTHORITY_INVALID")
        self.repository, self.repository_id, self._token = repository, repository_id, token
        if not qualification_only:
            from .github_source_authority_v3 import GitHubSourceAuthorityV3
            if type(source_authority) is not GitHubSourceAuthorityV3: raise ValueError("GITHUB_SOURCE_AUTHORITY_REQUIRED")
        self.authority_evidence_id = authority_evidence_id
        self.source_authority,self.qualification_only=source_authority,qualification_only
        self.expected_installation_id=(expected_installation_id if qualification_only else getattr(source_authority,"installation_id",None))
        if not qualification_only: _positive(self.expected_installation_id,"GITHUB_INSTALLATION_ID_INVALID")
        self._owner, self._name = repository.split("/", 1)
        self._executor = executor or (lambda request: urllib_executor_bounded(request, _MAX_RESPONSE))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _get(self, suffix: str) -> HttpResponseV3:
        root = f"/repos/{quote(self._owner, safe='')}/{quote(self._name, safe='')}"
        if not (suffix == "" or re.fullmatch(r"/git/(?:commits|trees|blobs)/[0-9a-f]{40}", suffix)):
            raise GitHubGitFileV3Error("GIT_FILE_ENDPOINT_INVALID")
        url = _API + root + suffix
        request = Request(url, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": _VERSION}, method="GET")
        try: response = self._executor(request)
        except Exception: raise GitHubGitFileV3Error("GIT_FILE_READ_AUTHORITY_UNAVAILABLE") from None
        if not isinstance(response, HttpResponseV3): raise GitHubGitFileV3Error("GIT_FILE_RESPONSE_INVALID")
        if response.status in {403, 404}: raise GitHubGitFileV3Error("GIT_FILE_READ_AUTHORITY_AMBIGUOUS")
        if response.status != 200: raise GitHubGitFileV3Error("GIT_FILE_OBJECT_UNAVAILABLE")
        return response

    def _verify_credential_authority(self) -> None:
        if self.qualification_only: return
        from .admission_v3 import SourceRepositoryAuthorizationV3
        from .github_source_authority_v3 import GitHubSourceAuthorityV3
        if (type(self.source_authority) is not GitHubSourceAuthorityV3
                or not self.source_authority.permits_token(
                    self._token, self.repository, self.repository_id)):
            raise GitHubGitFileV3Error("GIT_FILE_SOURCE_AUTHORITY_MISMATCH")
        authorization = self.source_authority.authorize(self.repository, self.repository_id)
        if (type(authorization) is not SourceRepositoryAuthorizationV3
                or authorization.repository != self.repository
                or type(authorization.repository_id) is not int
                or authorization.repository_id != self.repository_id
                or type(authorization.installation_id) is not int
                or authorization.installation_id != self.expected_installation_id
                or not isinstance(authorization.evidence_id, str)
                or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", authorization.evidence_id) is None
                or authorization.evidence_id != self.authority_evidence_id):
            raise GitHubGitFileV3Error("GIT_FILE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH")

    def _verify_repository(self) -> None:
        value = _object(self._get(""), "GIT_FILE_REPOSITORY_RESPONSE_INVALID")
        if value.get("full_name") != self.repository or _positive(
                value.get("id"), "GIT_FILE_REPOSITORY_ID_INVALID") != self.repository_id:
            raise GitHubGitFileV3Error("GIT_FILE_REPOSITORY_IDENTITY_MISMATCH")

    def observe(self, commit_sha: str, path: str,
                expected_sha256: str | None = None) -> GitHubGitFileObservationV3:
        if _SHA.fullmatch(commit_sha) is None: raise GitHubGitFileV3Error("GIT_FILE_COMMIT_INVALID")
        if (_PATH.fullmatch(path) is None or any(part in {".", ".."} for part in path.split("/"))):
            raise GitHubGitFileV3Error("GIT_FILE_PATH_INVALID")
        if expected_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
            raise GitHubGitFileV3Error("GIT_FILE_EXPECTED_SHA256_INVALID")
        self._verify_credential_authority(); self._verify_repository()
        commit = _object(self._get(f"/git/commits/{commit_sha}"), "GIT_FILE_COMMIT_RESPONSE_INVALID")
        tree = commit.get("tree")
        if commit.get("sha") != commit_sha or not isinstance(tree, dict) or _SHA.fullmatch(str(tree.get("sha"))) is None:
            raise GitHubGitFileV3Error("GIT_FILE_COMMIT_IDENTITY_MISMATCH")
        root_tree = str(tree["sha"]); current = root_tree; components = path.split("/")
        for index, component in enumerate(components):
            value = _object(self._get(f"/git/trees/{current}"), "GIT_FILE_TREE_RESPONSE_INVALID")
            if value.get("sha") != current or value.get("truncated") is not False or not isinstance(value.get("tree"), list):
                raise GitHubGitFileV3Error("GIT_FILE_TREE_INCOMPLETE")
            matches = [item for item in value["tree"] if isinstance(item, dict) and item.get("path") == component]
            if len(matches) != 1: raise GitHubGitFileV3Error("GIT_FILE_PATH_MISSING_OR_DUPLICATED")
            entry = matches[0]; final = index == len(components) - 1
            if set(entry) < {"path", "mode", "type", "sha"} or _SHA.fullmatch(str(entry.get("sha"))) is None:
                raise GitHubGitFileV3Error("GIT_FILE_TREE_ENTRY_INVALID")
            if not final:
                if entry.get("type") != "tree" or entry.get("mode") != "040000":
                    raise GitHubGitFileV3Error("GIT_FILE_INTERMEDIATE_NOT_TREE")
                current = str(entry["sha"]); continue
            if entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}:
                raise GitHubGitFileV3Error("GIT_FILE_FINAL_OBJECT_UNSUPPORTED")
            blob_oid = str(entry["sha"])
        blob = _object(self._get(f"/git/blobs/{blob_oid}"), "GIT_FILE_BLOB_RESPONSE_INVALID")
        if blob.get("sha") != blob_oid or blob.get("encoding") != "base64" or not isinstance(blob.get("content"), str):
            raise GitHubGitFileV3Error("GIT_FILE_BLOB_IDENTITY_MISMATCH")
        encoded = blob["content"]
        if "\r" in encoded: raise GitHubGitFileV3Error("GIT_FILE_BASE64_INVALID")
        try: original = base64.b64decode(encoded.replace("\n", ""), validate=True)
        except (binascii.Error, ValueError) as exc: raise GitHubGitFileV3Error("GIT_FILE_BASE64_INVALID") from exc
        if (len(original) > _MAX_BYTES or type(blob.get("size")) is not int
                or blob.get("size") != len(original)):
            raise GitHubGitFileV3Error("GIT_FILE_SOURCE_SIZE_INVALID")
        header = b"blob " + str(len(original)).encode("ascii") + b"\0" + original
        if hashlib.sha1(header).hexdigest() != blob_oid: raise GitHubGitFileV3Error("GIT_FILE_BLOB_OID_MISMATCH")
        if self._token.encode("utf-8") in original: raise GitHubGitFileV3Error("GIT_FILE_SOURCE_CREDENTIAL_IN_CONTENT")
        digest = hashlib.sha256(original).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise GitHubGitFileV3Error("GIT_FILE_EXPECTED_SHA256_MISMATCH")
        try: decode_physical_lines(original)
        except PhysicalLineError as exc: raise GitHubGitFileV3Error("GIT_FILE_TEXT_ENCODING_INVALID") from exc
        self._verify_repository(); observed = self._clock()
        if observed.tzinfo is None: raise GitHubGitFileV3Error("GIT_FILE_OBSERVATION_TIME_INVALID")
        observed_at = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        api_source = f"{_API}/repos/{self.repository}/git/commits/{commit_sha}"
        self._verify_credential_authority()
        provisional = GitHubGitFileObservationV3(self.repository, self.repository_id, commit_sha,
            root_tree, path, blob_oid, original, len(original), digest, observed_at, api_source,
            ("SAME_REPOSITORY_ACTIONS_QUALIFICATION" if self.qualification_only
             else "AUTHENTICATED_READ_ONLY"), self.authority_evidence_id,
            self.expected_installation_id, "")
        evidence_id = artifact_identity(canonical_bytes(provisional.provenance_basis()) + b"\n")
        return replace(provisional, evidence_id=evidence_id)
