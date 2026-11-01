import base64
from datetime import datetime, timezone
import hashlib
import json
import unittest

from review_broker.github_git_file_v3 import GitHubGitFileReaderV3, GitHubGitFileV3Error
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.identity import artifact_identity, canonical_bytes
from tests.issue69_test_support import source_authority

REPO = "fanilosendrison/review-broker"; REPO_ID = 1433701208
COMMIT = "a" * 40; TREE = "b" * 40; DATA = b"alpha\r\nbeta\n"
AUTHORITY = artifact_identity(canonical_bytes({"schema_version": 1,
    "evidence_type": "v3-source-repository-authorization", "repository": REPO,
    "repository_id": REPO_ID, "principal_id": "github-app:source", "installation_id": 123}) + b"\n")
def blob_oid(data=DATA):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Api:
    def __init__(self, *, data=DATA, repo_id=REPO_ID, status=None, truncated=False,
                 mode="100644", duplicate=False, commit=COMMIT, encoding="base64"):
        self.data, self.repo_id, self.status = data, repo_id, status
        self.truncated, self.mode, self.duplicate = truncated, mode, duplicate
        self.commit, self.encoding, self.calls = commit, encoding, []
    def __call__(self, request):
        self.calls.append((request.method, request.full_url))
        suffix = ("/installation" if request.full_url.endswith("/installation")
                  else request.full_url.split("/review-broker", 1)[1])
        if self.status and suffix != "": return HttpResponseV3(self.status, b"{}", {})
        if request.full_url.endswith("/installation"): value = {"id": 123}
        elif suffix == "": value = {"id": self.repo_id, "full_name": REPO}
        elif suffix == f"/git/commits/{COMMIT}": value = {"sha": self.commit, "tree": {"sha": TREE}}
        elif suffix == f"/git/trees/{TREE}":
            entry = {"path": "contract.md", "mode": self.mode,
                     "type": "blob" if self.mode not in {"040000", "160000"} else "commit",
                     "sha": blob_oid(self.data)}
            value = {"sha": TREE, "truncated": self.truncated,
                     "tree": [entry, dict(entry)] if self.duplicate else [entry]}
        elif suffix == f"/git/blobs/{blob_oid(self.data)}":
            content = base64.b64encode(self.data).decode() if self.encoding == "base64" else "%%%"
            value = {"sha": blob_oid(self.data), "encoding": self.encoding,
                     "size": len(self.data), "content": content}
        else: raise AssertionError(suffix)
        return HttpResponseV3(200, json.dumps(value).encode(), {})


def reader(api):
    return GitHubGitFileReaderV3("token", REPO, REPO_ID, authority_evidence_id=AUTHORITY,
        source_authority=source_authority(), executor=api,
        clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc))


class GitHubGitFileReaderTests(unittest.TestCase):
    def test_exact_authenticated_commit_tree_blob_and_bytes(self):
        api = Api(); value = reader(api).observe(COMMIT, "contract.md", hashlib.sha256(DATA).hexdigest())
        self.assertEqual(value.original_bytes, DATA)
        self.assertEqual(value.git_blob_oid, blob_oid())
        self.assertEqual(value.root_tree_sha, TREE)
        self.assertEqual(value.qualification, "AUTHENTICATED_READ_ONLY")
        self.assertTrue(value.evidence_id.startswith("artifact:sha256:"))
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_identity_digest_authority_and_object_failures(self):
        cases = [
            (Api(repo_id=9), "REPOSITORY_IDENTITY_MISMATCH"),
            (Api(commit="c" * 40), "COMMIT_IDENTITY_MISMATCH"),
            (Api(truncated=True), "TREE_INCOMPLETE"),
            (Api(duplicate=True), "MISSING_OR_DUPLICATED"),
            (Api(mode="120000"), "FINAL_OBJECT_UNSUPPORTED"),
            (Api(mode="160000"), "FINAL_OBJECT_UNSUPPORTED"),
            (Api(encoding="bad"), "BLOB_IDENTITY_MISMATCH"),
            (Api(status=403), "AUTHORITY_AMBIGUOUS"),
            (Api(status=404), "AUTHORITY_AMBIGUOUS"),
        ]
        for api, marker in cases:
            with self.subTest(marker=marker), self.assertRaisesRegex(GitHubGitFileV3Error, marker):
                reader(api).observe(COMMIT, "contract.md")
        with self.assertRaisesRegex(GitHubGitFileV3Error, "EXPECTED_SHA256_MISMATCH"):
            reader(Api()).observe(COMMIT, "contract.md", "0" * 64)
        with self.assertRaisesRegex(GitHubGitFileV3Error, "SOURCE_CREDENTIAL_IN_CONTENT"):
            reader(Api(data=b"token")).observe(COMMIT, "contract.md")

    def test_invalid_commit_path_base64_utf8_and_size_fail(self):
        for commit, path, api, marker in (
            ("bad", "contract.md", Api(), "COMMIT_INVALID"),
            (COMMIT, "../secret", Api(), "PATH_INVALID"),
            (COMMIT, "contract.md", Api(encoding="base64"), ""),
            (COMMIT, "contract.md", Api(data=b"\xff"), "TEXT_ENCODING_INVALID"),
            (COMMIT, "contract.md", Api(data=b"x" * 2_000_001), "SOURCE_SIZE_INVALID"),
        ):
            if not marker: continue
            with self.subTest(marker=marker), self.assertRaisesRegex(GitHubGitFileV3Error, marker):
                reader(api).observe(commit, path)


if __name__ == "__main__": unittest.main()
