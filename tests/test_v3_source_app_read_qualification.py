"""Offline injected oracle tests; no production credentials or network calls."""
import base64
import copy
from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

from scripts.qualification import v3_source_app_read as q

TOKEN = "synthetic-source-credential"
REPO = "fanilosendrison/review-broker"
HEAD = "9258617056e9d2e20cce7f05e6be71ea82dfbd23"
BASE = "83b02c1b9b5bad6c6f64af76affb140957fcbd38"
TREE = "a" * 40
CONTENT = b"Synthetic original file, never to be logged.\n"
BLOB = hashlib.sha1(b"blob " + str(len(CONTENT)).encode() + b"\0" + CONTENT).hexdigest()
ISSUE_BODY = "Synthetic Issue body, not retained."
COMMENT_BODY = "Synthetic comment body, not retained."
ENV = {
    "REVIEW_BROKER_SOURCE_TOKEN": TOKEN, "SOURCE_APP_SLUG": "source-reader",
    "SOURCE_INSTALLATION_ID": "123", "EXPECTED_REPOSITORY": REPO,
    "EXPECTED_REPOSITORY_ID": "1433701208", "GITHUB_SHA": "b" * 40,
    "GITHUB_RUN_ID": "456", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "qualify",
}
ROOT = "/repos/" + REPO
REPOSITORY = {"full_name": REPO, "id": 1433701208, "private": True, "visibility": "private"}
PR = {"id": 5101281733, "number": 71, "changed_files": 9,
      "head": {"sha": HEAD, "repo": REPOSITORY},
      "base": {"sha": BASE, "repo": REPOSITORY}}


def fixtures():
    """Independent fixed expected response sequence, not production validators."""
    return copy.deepcopy([
        {"total_count": 1, "repositories": [REPOSITORY]}, REPOSITORY,
        {"id": 6101161202, "number": 43, "body": ISSUE_BODY,
         "url": "https://api.github.com" + ROOT + "/issues/43"},
        {"id": 6535094733, "user": {"id": 30498238}, "body": COMMENT_BODY,
         "issue_url": "https://api.github.com" + ROOT + "/issues/51"},
        {"id": 123456, "number": 51, "body": "parent",
         "url": "https://api.github.com" + ROOT + "/issues/51"},
        PR, {"base_commit": {"sha": BASE}, "merge_base_commit": {"sha": BASE},
             "status": "ahead", "total_commits": 1, "commits": [{"sha": HEAD}]},
        [{"filename": f"docs/file-{i}.md", "status": "modified"} for i in range(9)],
        {"sha": HEAD, "tree": {"sha": TREE}},
        {"sha": TREE, "truncated": False,
         "tree": [{"path": "AGENTS.md", "mode": "100644", "type": "blob",
                   "sha": BLOB, "size": len(CONTENT)}]},
        {"sha": BLOB, "encoding": "base64", "size": len(CONTENT),
         "content": base64.b64encode(CONTENT).decode() + "\n"}, PR,
    ])


PATHS = ["/installation/repositories?per_page=100&page=1", ROOT, ROOT + "/issues/43",
         ROOT + "/issues/comments/6535094733", ROOT + "/issues/51", ROOT + "/pulls/71",
         ROOT + "/compare/" + BASE + "..." + HEAD,
         ROOT + "/pulls/71/files?per_page=100&page=1", ROOT + "/git/commits/" + HEAD,
         ROOT + "/git/trees/" + TREE, ROOT + "/git/blobs/" + BLOB, ROOT + "/pulls/71"]


class Response(io.BytesIO):
    def __init__(self, data, headers=(), status=200):
        super().__init__(data)
        self.status = status
        self.headers = Message()
        for key, value in headers:
            self.headers[key] = value


class Transport:
    def __init__(self, responses=None, headers=(), raw=None):
        self.responses = fixtures() if responses is None else responses
        self.calls = []
        self.headers, self.raw = headers, raw

    def __call__(self, request, timeout):
        index = len(self.calls)
        self.calls.append(request)
        assert request.full_url == "https://api.github.com" + PATHS[index]
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bearer " + TOKEN
        assert request.get_header("X-github-api-version") == "2022-11-28"
        assert request.get_header("Accept") == "application/vnd.github+json"
        assert timeout == 10
        return Response(self.raw if self.raw is not None else json.dumps(self.responses[index]).encode(),
                        self.headers)


class V3SourceAppReadTests(unittest.TestCase):
    def observe(self, responses=None, environment=None, **kwargs):
        transport = Transport(responses, **kwargs)
        result = q.observe(q.Client(TOKEN, transport), ENV if environment is None else environment)
        return result, transport

    def reject(self, responses, marker):
        with self.assertRaisesRegex(q.QualificationError, "^" + marker + "$"):
            self.observe(responses)

    def test_exact_positive_receipt_is_deterministic_and_content_free(self):
        receipt, transport = self.observe()
        self.assertEqual(len(transport.calls), 12)
        self.assertEqual(receipt, self.observe()[0])
        self.assertEqual(receipt["installation_id"], 123)
        self.assertEqual(receipt["installation_repository_count"], 1)
        self.assertEqual(receipt["repository_id"], 1433701208)
        self.assertEqual((receipt["issue_id"], receipt["comment_id"], receipt["comment_parent_issue"],
                          receipt["comment_author_id"]), (6101161202, 6535094733, 51, 30498238))
        self.assertEqual(receipt["issue_body_sha256"], hashlib.sha256(ISSUE_BODY.encode()).hexdigest())
        self.assertEqual(receipt["comment_body_sha256"], hashlib.sha256(COMMENT_BODY.encode()).hexdigest())
        self.assertEqual((receipt["pr_id"], receipt["base_sha"], receipt["head_sha"],
                          receipt["changed_file_count"]), (5101281733, BASE, HEAD, 9))
        self.assertEqual(receipt["observed_compare_merge_base_sha"], BASE)
        self.assertEqual((receipt["git_commit_oid"], receipt["git_root_tree_oid"],
                          receipt["git_blob_oid"]), (HEAD, TREE, BLOB))
        self.assertEqual(receipt["git_original_sha256"], hashlib.sha256(CONTENT).hexdigest())
        self.assertEqual(set(receipt["boundaries"].values()), {"PASS"})
        for key in ("github_mutations", "codespace_effects", "model_invocations"):
            self.assertEqual(receipt[key], 0)
        saved = receipt.pop("receipt_sha256")
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        self.assertEqual(saved, hashlib.sha256(canonical).hexdigest())
        for private in (TOKEN, ISSUE_BODY, COMMENT_BODY, CONTENT.decode()):
            self.assertNotIn(private, canonical.decode())

    def test_identity_and_body_mutations_fail_with_specific_markers(self):
        cases = [
            (0, "total_count", 2, "INSTALLATION_SCOPE"),
            (0, "repositories", [], "INSTALLATION_SCOPE"),
            (1, "full_name", "other/repo", "REPOSITORY_IDENTITY"),
            (1, "id", 1, "REPOSITORY_IDENTITY"),
            (1, "private", False, "REPOSITORY_VISIBILITY"),
            (1, "visibility", "public", "REPOSITORY_VISIBILITY"),
            (2, "id", 1, "ISSUE_IDENTITY"), (2, "number", 44, "ISSUE_IDENTITY"),
            (2, "body", None, "BODY_INVALID"), (2, "body", {}, "BODY_INVALID"),
            (3, "body", None, "BODY_INVALID"), (3, "id", 1, "COMMENT_IDENTITY"),
            (3, "issue_url", "https://api.github.com" + ROOT + "/issues/43", "COMMENT_PARENT"),
            (3, "user", {"id": 1}, "COMMENT_AUTHOR"),
            (4, "number", 50, "ISSUE_IDENTITY"), (5, "id", 1, "PR_IDENTITY"),
            (5, "head", {"sha": "c" * 40, "repo": REPOSITORY}, "PR_HEAD"),
            (5, "base", {"sha": "c" * 40, "repo": REPOSITORY}, "PR_BASE"),
            (6, "merge_base_commit", {"sha": "c" * 40}, "COMPARE_MERGE_BASE"),
            (6, "merge_base_commit", {}, "COMPARE_MERGE_BASE"),
            (6, "base_commit", {"sha": "c" * 40}, "COMPARE_IDENTITY"),
            (8, "sha", "c" * 40, "GIT_COMMIT"),
            (9, "truncated", True, "GIT_TREE"), (9, "tree", [], "GIT_ENTRY"),
            (10, "content", "!!!", "GIT_BASE64"), (10, "size", 1, "GIT_SIZE"),
            (10, "sha", "c" * 40, "GIT_BLOB"),
            (10, "content", base64.b64encode(b"X" * len(CONTENT)).decode(), "GIT_BLOB_IDENTITY"),
            (11, "head", {"sha": "c" * 40, "repo": REPOSITORY}, "PR_HEAD"),
            (11, "base", {"sha": "c" * 40, "repo": REPOSITORY}, "PR_BASE"),
        ]
        for index, key, value, marker in cases:
            with self.subTest(index=index, key=key, marker=marker):
                responses = fixtures(); responses[index][key] = value
                self.reject(responses, marker)

    def test_scope_duplicates_and_missing_evidence(self):
        responses = fixtures(); responses[0]["repositories"] *= 2
        self.reject(responses, "INSTALLATION_SCOPE")
        responses = fixtures(); responses[0]["repositories"][0]["id"] = 1
        self.reject(responses, "REPOSITORY_IDENTITY")
        responses = fixtures(); del responses[2]["body"]
        self.reject(responses, "BODY_INVALID")
        responses = fixtures(); responses[6] = {}
        self.reject(responses, "COMPARE_IDENTITY")

    def test_file_inventory_and_git_mode_mutations(self):
        for mutation, marker in [
            (lambda r: r[7].pop(), "FILE_INVENTORY"),
            (lambda r: r[7].__setitem__(1, r[7][0]), "FILE_DUPLICATE"),
            (lambda r: r[7][0].update(filename="../escape"), "FILE_PATH"),
            (lambda r: r[7][0].update(status="unknown"), "FILE_STATUS"),
            (lambda r: r[9]["tree"][0].update(mode="120000"), "GIT_MODE"),
            (lambda r: r[9]["tree"][0].update(type="tree"), "GIT_MODE"),
            (lambda r: r[9]["tree"].append(r[9]["tree"][0]), "GIT_TREE"),
        ]:
            with self.subTest(marker=marker):
                responses = fixtures(); mutation(responses); self.reject(responses, marker)

    def test_trusted_mint_and_execution_metadata(self):
        for key, value, marker in [
            ("SOURCE_INSTALLATION_ID", "0", "INSTALLATION_IDENTITY"),
            ("SOURCE_INSTALLATION_ID", "other", "INSTALLATION_IDENTITY"),
            ("SOURCE_APP_SLUG", "", "APP_IDENTITY"),
            ("EXPECTED_REPOSITORY", "other/repo", "REPOSITORY_CONFIG"),
            ("EXPECTED_REPOSITORY_ID", "1", "REPOSITORY_CONFIG"),
            ("GITHUB_SHA", "", "EXECUTION_IDENTITY"),
            ("GITHUB_RUN_ID", "bad", "EXECUTION_IDENTITY"),
        ]:
            with self.subTest(key=key):
                env = dict(ENV); env[key] = value
                with self.assertRaisesRegex(q.QualificationError, "^" + marker + "$"):
                    self.observe(environment=env)

    def test_method_and_mutation_endpoint_rejected_without_transport(self):
        transport = Transport(); client = q.Client(TOKEN, transport)
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            with self.assertRaisesRegex(q.QualificationError, "^METHOD_REJECTED$"):
                client.get(ROOT, method)
        for path in (ROOT + "/issues", "https://attacker.invalid/", ROOT + "/git/refs"):
            with self.assertRaisesRegex(q.QualificationError, "^ENDPOINT_REJECTED$"):
                client.get(path)
        self.assertEqual(transport.calls, [])

    def test_http_auth_failures_redirect_and_transport_are_sanitized(self):
        for code in (401, 403, 404):
            def opener(*_args, **_kwargs):
                raise urllib.error.HTTPError("https://api.github.com", code, TOKEN, {}, None)
            with self.subTest(code=code), self.assertRaisesRegex(q.QualificationError, f"^HTTP_{code}$"):
                q.Client(TOKEN, opener).get(ROOT)
        with self.assertRaisesRegex(q.QualificationError, "^HTTP_REDIRECT$"):
            q.NoRedirect().redirect_request(None, None, 302, TOKEN, {}, "https://attacker.invalid")
        def unavailable(*_args, **_kwargs):
            raise urllib.error.URLError(TOKEN)
        with self.assertRaisesRegex(q.QualificationError, "^HTTP_TRANSPORT$"):
            q.Client(TOKEN, unavailable).get(ROOT)

    def test_response_bounds_pagination_and_json(self):
        cases = [(Transport(raw=b"x" * (q.MAX_BODY + 1)), "HTTP_OVERSIZED"),
                 (Transport(headers=[("Link", '<https://api.github.com/next>; rel="next"')]),
                  "PAGINATION_INCOMPLETE"),
                 (Transport(headers=[("Link", ""), ("Link", "malformed")]), "PAGINATION_INCOMPLETE"),
                 (Transport(raw=b'{"id":1,"id":2}'), "DUPLICATE_JSON_KEY"),
                 (Transport(raw=b"bad-json"), "HTTP_JSON")]
        for opener, marker in cases:
            with self.subTest(marker=marker), self.assertRaisesRegex(q.QualificationError, "^"+marker+"$"):
                q.Client(TOKEN, opener).get(PATHS[0])
        with patch.object(q.time, "monotonic", side_effect=[0, 31]):
            with self.assertRaisesRegex(q.QualificationError, "^HTTP_DEADLINE$"):
                q.Client(TOKEN, Transport()).get(PATHS[0])

    def test_credential_contamination_in_bodies_and_original_blob(self):
        for original in (TOKEN, "ghp_" + "a" * 30):
            responses = fixtures(); responses[2]["body"] = original
            self.reject(responses, "CREDENTIAL_CONTAMINATION")
        responses = fixtures(); responses[10]["content"] = base64.b64encode(TOKEN.encode()).decode()
        self.reject(responses, "CREDENTIAL_CONTAMINATION")
        raw = b'{"body":"\\u0073ynthetic-source-credential"}'
        with self.assertRaisesRegex(q.QualificationError, "^CREDENTIAL_CONTAMINATION$"):
            q.Client(TOKEN, Transport(raw=raw)).get(PATHS[0])

    def test_cli_outputs_only_receipt_or_fixed_failure_never_originals(self):
        for env, marker in [(ENV, None), ({**ENV, "REVIEW_BROKER_SOURCE_TOKEN": ""}, "SOURCE_TOKEN_REQUIRED")]:
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(q.sys, "stdout", output), patch.object(q.sys, "stderr", errors):
                code = q.main(env, Transport())
            self.assertEqual(code, int(marker is not None))
            if marker:
                self.assertEqual(errors.getvalue(), marker + "\n"); self.assertEqual(output.getvalue(), "")
            else:
                self.assertEqual(json.loads(output.getvalue())["schema_version"], "1.0.0")
                self.assertEqual(errors.getvalue(), "")
            for private in (TOKEN, ISSUE_BODY, COMMENT_BODY, CONTENT.decode()):
                self.assertNotIn(private, output.getvalue() + errors.getvalue())
        output, errors = io.StringIO(), io.StringIO()
        responses = fixtures(); responses[2]["body"] = TOKEN + "\nPASS"
        with patch.object(q.sys, "stdout", output), patch.object(q.sys, "stderr", errors):
            self.assertEqual(q.main(ENV, Transport(responses)), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "CREDENTIAL_CONTAMINATION\n")


if __name__ == "__main__":
    unittest.main()
