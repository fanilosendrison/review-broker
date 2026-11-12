from __future__ import annotations

import base64
import traceback
import unittest
from urllib.request import Request

from github_transport_live_v3_support import (
    FakeGitHubApi, NODE_ID, PARENT, QUAL_REF, REF, REPOSITORY, git_blob_sha,
)
from review_broker.github_http_live_v3 import GitHubHttpLiveV3Error, _RejectRedirects
from review_broker.github_journal_transport_v3 import ReadStatusV3
from review_broker.github_transport_live_v3 import (
    GitHubTransportLiveV3, GitHubTransportLiveV3Error,
)


class LiveTransportIdentityAndReadTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHubApi()
        self.transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=self.api)

    def test_graphql_identity_rejects_every_present_errors_envelope(self):
        for errors in (None, [], {}, "invalid"):
            with self.subTest(errors=errors):
                api = FakeGitHubApi()
                api.identity_graphql_body = {
                    "data": {"repository": {"id": NODE_ID, "nameWithOwner": REPOSITORY}},
                    "errors": errors,
                }
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    _ = transport.repository_node_id
                self.assertEqual(transport.mutation_attempt_count, 0)
                self.assertEqual(api.mutation_calls, 0)

    def test_repository_rest_and_graphql_identity_agree(self):
        self.assertEqual(self.transport.repository_node_id, NODE_ID)
        self.assertEqual(len(self.api.calls), 2)
        self.assertTrue(all(call[3] == "Bearer secret-token" for call in self.api.calls))

    def test_repository_name_or_node_mismatch_rejects_before_mutation(self):
        for attribute, value in (("repository", "other/repository"),
                                 ("graphql_name", "other/repository"),
                                 ("graphql_node", "R_other")):
            with self.subTest(attribute=attribute):
                api = FakeGitHubApi()
                setattr(api, attribute, value)
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                commit, _ = api.install_journal(publish=False)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    transport.create_ref(REF, commit)
                self.assertEqual(api.mutation_calls, 0)

    def test_legacy_arbitrary_and_qualification_refs_reject_before_http(self):
        for ref in ("refs/heads/review-claims/" + "a" * 64, "refs/heads/dev",
                    "refs/heads/review-claims-v3/not-a-digest", QUAL_REF):
            with self.subTest(ref=ref):
                with self.assertRaises(GitHubTransportLiveV3Error):
                    self.transport.read_claim(ref)
                self.assertEqual(self.api.calls, [])
        qualified = GitHubTransportLiveV3(
            "secret-token", REPOSITORY, executor=self.api, allow_qualification_refs=True
        )
        self.assertEqual(qualified.read_claim(QUAL_REF).status, ReadStatusV3.MISSING)

    def test_invalid_sha_rejects_before_mutation(self):
        with self.assertRaises(GitHubTransportLiveV3Error):
            self.transport.create_journal_commit("not-a-sha", b"x")
        self.assertEqual(self.api.mutation_calls, 0)

    def test_exact_blob_bytes_and_parent_are_returned(self):
        content = b"original\x00bytes\r\nnot-normalized\xff"
        commit_sha, _ = self.api.install_journal(content=content)
        result = self.transport.read_claim(REF)
        self.assertEqual(result.status, ReadStatusV3.FOUND)
        self.assertEqual(result.snapshot.commit_sha, commit_sha)
        self.assertEqual(result.snapshot.parent_sha, PARENT)
        self.assertEqual(result.snapshot.journal_bytes, content)
        self.assertEqual(self.api.mutation_calls, 0)

    def test_definitively_missing_ref_requires_complete_matching_ref_observation(self):
        self.assertEqual(self.transport.read_claim(REF).status, ReadStatusV3.MISSING)
        self.assertEqual(self.api.mutation_calls, 0)

        api = FakeGitHubApi()
        api.matching_refs_status = 404
        result = GitHubTransportLiveV3(
            "secret-token", REPOSITORY, executor=api
        ).read_claim(REF)
        self.assertEqual(result.status, ReadStatusV3.UNAVAILABLE)
        self.assertEqual(api.mutation_calls, 0)

    def test_cached_identity_does_not_turn_unauthenticated_404_into_missing(self):
        self.assertEqual(self.transport.repository_node_id, NODE_ID)
        self.api.repository_status = 404
        self.assertEqual(self.transport.read_claim(REF).status, ReadStatusV3.UNAVAILABLE)
        self.assertEqual(self.api.mutation_calls, 0)

    def test_wrong_ref_object_and_inconsistent_observations_are_unavailable(self):
        self.api.install_journal()
        original = self.api.__call__

        def corrupt(request):
            result = original(request)
            if "/git/ref/" in request.full_url:
                return type(result)(result.status, result.body.replace(b'"type":"commit"', b'"type":"tag"'), {})
            return result

        transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=corrupt)
        self.assertEqual(transport.read_claim(REF).status, ReadStatusV3.UNAVAILABLE)
        self.assertEqual(self.api.mutation_calls, 0)

    def test_missing_truncated_or_malformed_tree_is_unavailable(self):
        self.api.install_journal()
        cases = (
            {"sha": "6" * 40, "truncated": False, "tree": []},
            {"sha": "6" * 40, "truncated": True, "tree": []},
            {"sha": "6" * 40, "truncated": False, "tree": "not-a-list"},
        )
        for tree in cases:
            with self.subTest(tree=tree):
                api = FakeGitHubApi()
                api.install_journal()
                api.tree_override = tree
                result = GitHubTransportLiveV3(
                    "secret-token", REPOSITORY, executor=api
                ).read_claim(REF)
                self.assertEqual(result.status, ReadStatusV3.UNAVAILABLE)
                self.assertEqual(api.mutation_calls, 0)

    def test_duplicate_wrong_mode_or_wrong_type_journal_entry_is_unavailable(self):
        commit, blob = self.api.install_journal()
        del commit
        valid = {"path": ".review-broker/attempt.json", "mode": "100644",
                 "type": "blob", "sha": blob}
        cases = ([valid, valid], [{**valid, "mode": "120000"}],
                 [{**valid, "type": "tree"}])
        for entries in cases:
            with self.subTest(entries=entries):
                api = FakeGitHubApi()
                api.install_journal()
                api.tree_override = {"sha": "6" * 40, "truncated": False, "tree": entries}
                result = GitHubTransportLiveV3(
                    "secret-token", REPOSITORY, executor=api
                ).read_claim(REF)
                self.assertEqual(result.status, ReadStatusV3.UNAVAILABLE)
                self.assertEqual(api.mutation_calls, 0)

    def test_malformed_base64_and_blob_identity_mismatch_are_unavailable(self):
        content = b"payload"
        _, blob = self.api.install_journal(content=content)
        cases = (
            {"sha": blob, "encoding": "base64", "size": 3, "content": "%%%"},
            {"sha": blob, "encoding": "base64", "size": len(content),
             "content": base64.b64encode(b"different").decode()},
            {"sha": "f" * 40, "encoding": "base64", "size": len(content),
             "content": base64.b64encode(content).decode()},
        )
        for blob_body in cases:
            with self.subTest(blob=blob_body):
                api = FakeGitHubApi()
                api.install_journal(content=content)
                api.blob_override = blob_body
                result = GitHubTransportLiveV3(
                    "secret-token", REPOSITORY, executor=api
                ).read_claim(REF)
                self.assertEqual(result.status, ReadStatusV3.UNAVAILABLE)
                self.assertEqual(api.mutation_calls, 0)

    def test_github_wrapped_base64_preserves_exact_bytes(self):
        content = b"wrapped base64 payload"
        _, blob = self.api.install_journal(content=content)
        encoded = base64.b64encode(content).decode()
        self.api.blob_override = {"sha": blob, "encoding": "base64", "size": len(content),
                                  "content": encoded[:8] + "\n" + encoded[8:] + "\n"}
        result = self.transport.read_claim(REF)
        self.assertEqual(result.status, ReadStatusV3.FOUND)
        self.assertEqual(result.snapshot.journal_bytes, content)

    def test_blob_identity_or_size_is_independently_computed(self):
        content = b"payload"
        self.assertEqual(len(git_blob_sha(content)), 40)
        _, blob = self.api.install_journal(content=content)
        self.api.blob_override = {"sha": blob, "encoding": "base64", "size": 999,
                                  "content": base64.b64encode(content).decode()}
        self.assertEqual(self.transport.read_claim(REF).status, ReadStatusV3.UNAVAILABLE)
        self.assertEqual(self.api.mutation_calls, 0)
        self.assertEqual(self.transport.mutation_attempt_count, 0)

    def test_redirects_are_rejected_before_an_authenticated_followup(self):
        handler = _RejectRedirects()
        request = Request("https://api.github.com/repos/fanilosendrison/review-broker",
                          headers={"Authorization": "Bearer secret-token"})
        with self.assertRaisesRegex(GitHubHttpLiveV3Error, "GITHUB_REDIRECT_REJECTED"):
            handler.redirect_request(request, None, 302, "Found", {}, "https://example.invalid/")

    def test_token_never_appears_in_raised_error(self):
        self.api.raise_on = ("GET", "https://api.github.com/repos/fanilosendrison/review-broker")
        commit, _ = self.api.install_journal(publish=False)
        with self.assertRaises(GitHubTransportLiveV3Error) as raised:
            self.transport.create_ref(REF, commit)
        rendered = "".join(traceback.format_exception(raised.exception))
        self.assertNotIn("secret-token", rendered)
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertEqual(self.api.mutation_calls, 0)


if __name__ == "__main__":
    unittest.main()
