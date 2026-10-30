from __future__ import annotations

import json
import unittest

from github_transport_live_v3_support import (
    FakeGitHubApi, NODE_ID, PARENT, REF, REPOSITORY,
)
from review_broker.github_journal_transport_v3 import (
    CreateRefStatusV3, GraphQLRefUpdateV3,
)
from review_broker.github_transport_live_v3 import (
    GitHubTransportLiveV3, GitHubTransportLiveV3Error,
)


def unpublished_journal(api: FakeGitHubApi) -> str:
    return api.install_journal(publish=False)[0]


class LiveTransportMutationTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHubApi()
        self.transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=self.api)

    def test_repository_identity_drift_rejects_each_mutation_boundary(self):
        api = FakeGitHubApi()
        api.repository_drift_after = 1
        with self.assertRaises(GitHubTransportLiveV3Error):
            GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api).create_journal_commit(
                PARENT, b"payload"
            )
        self.assertEqual(api.mutation_calls, 0)

        for operation in ("create_ref", "update_ref"):
            with self.subTest(operation=operation):
                api = FakeGitHubApi()
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                node = transport.repository_node_id
                api.repository_drift_after = 1
                if operation == "create_ref":
                    with self.assertRaises(GitHubTransportLiveV3Error):
                        transport.create_ref(REF, unpublished_journal(api))
                else:
                    after = api.install_successor(PARENT)
                    result = transport.update_ref(
                        GraphQLRefUpdateV3(node, REF, PARENT, after, False)
                    )
                    self.assertEqual(result.errors, ("GITHUB_TRANSPORT_UNAVAILABLE",))
                self.assertEqual(api.mutation_calls, 0)

    def test_identity_drift_stops_at_each_later_object_boundary(self):
        for drift_attribute in ("repository_drift_after", "node_drift_after"):
            for completed_mutations in (1, 2):
                with self.subTest(drift=drift_attribute,
                                  completed_mutations=completed_mutations):
                    api = FakeGitHubApi()
                    setattr(api, drift_attribute, completed_mutations + 1)
                    transport = GitHubTransportLiveV3(
                        "secret-token", REPOSITORY, executor=api
                    )
                    with self.assertRaises(GitHubTransportLiveV3Error):
                        transport.create_journal_commit(PARENT, b"payload")
                    self.assertEqual(transport.mutation_attempt_count,
                                     completed_mutations)
                    self.assertEqual(api.mutation_calls, completed_mutations)
                    self.assertEqual(api.refs, {})

    def test_pinned_repository_node_rejects_same_name_replacement(self):
        api = FakeGitHubApi()
        transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
        self.assertEqual(transport.repository_node_id, NODE_ID)
        api.node_drift_after = 1
        with self.assertRaises(GitHubTransportLiveV3Error):
            transport.create_ref(REF, unpublished_journal(api))
        self.assertEqual(transport.mutation_attempt_count, 0)
        self.assertEqual(api.mutation_calls, 0)

    def test_create_commit_preserves_parent_tree_and_exact_bytes(self):
        payload = b"synthetic\x00journal\r\n\xff"
        commit = self.transport.create_journal_commit(PARENT, payload)
        self.assertEqual(commit, self.api.next_commit)
        tree, parents = self.api.commits[commit]
        self.assertEqual(parents, [PARENT])
        entries = self.api.trees[tree]
        self.assertIn("README.md", [entry["path"] for entry in entries])
        self.assertIn(".review-broker/attempt.json", [entry["path"] for entry in entries])
        blob = next(entry["sha"] for entry in entries
                    if entry["path"] == ".review-broker/attempt.json")
        self.assertEqual(self.api.blobs[blob], payload)
        self.assertEqual(self.api.mutation_calls, 3)

    def test_base_commit_may_have_zero_one_or_multiple_parents(self):
        for parents in ([], ["0" * 40], ["0" * 40, "a" * 40]):
            with self.subTest(parents=parents):
                api = FakeGitHubApi()
                api.commits[PARENT] = (api.commits[PARENT][0], parents)
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                commit = transport.create_journal_commit(PARENT, b"payload")
                self.assertEqual(api.commits[commit][1], [PARENT])
                self.assertEqual(api.mutation_calls, 3)

    def test_non_directory_journal_namespace_rejects_before_object_creation(self):
        for mode, kind in (("100644", "blob"), ("120000", "blob"), ("160000", "commit")):
            with self.subTest(mode=mode, kind=kind):
                api = FakeGitHubApi()
                api.trees[api.commits[PARENT][0]].append({
                    "path": ".review-broker", "mode": mode, "type": kind, "sha": "f" * 40,
                })
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                with self.assertRaisesRegex(GitHubTransportLiveV3Error,
                                            "JOURNAL_NAMESPACE_TYPE_INVALID"):
                    transport.create_journal_commit(PARENT, b"payload")
                self.assertEqual(transport.mutation_attempt_count, 0)
                self.assertEqual(api.mutation_calls, 0)

    def test_created_tree_must_preserve_every_unrelated_parent_entry(self):
        self.api.drop_parent_entries = True
        with self.assertRaisesRegex(GitHubTransportLiveV3Error, "GIT_TREE_PRESERVATION_MISMATCH"):
            self.transport.create_journal_commit(PARENT, b"payload")
        self.assertEqual(self.api.mutation_calls, 3)
        self.assertEqual(self.api.refs, {})

    def test_ambiguous_blob_creation_is_not_retried_and_updates_no_ref(self):
        self.transport.repository_node_id
        url = "https://api.github.com/repos/fanilosendrison/review-broker/git/blobs"
        self.api.raise_on = ("POST", url)
        with self.assertRaises(GitHubTransportLiveV3Error):
            self.transport.create_journal_commit(PARENT, b"payload")
        attempted = [call for call in self.api.calls if call[0] == "POST"
                     and "/git/" in call[1]]
        self.assertEqual([call[1] for call in attempted], [url])
        self.assertEqual(self.transport.mutation_attempt_count, 1)
        self.assertEqual(self.api.refs, {})

    def test_ambiguous_tree_and_commit_creation_are_never_retried(self):
        root = "https://api.github.com/repos/fanilosendrison/review-broker"
        for suffix, expected_attempts in (("/git/trees", 2), ("/git/commits", 3)):
            with self.subTest(suffix=suffix):
                api = FakeGitHubApi()
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                api.raise_on = ("POST", root + suffix)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    transport.create_journal_commit(PARENT, b"payload")
                attempts = [call for call in api.calls if call[0] == "POST"
                            and call[1].startswith(root + "/git/")]
                self.assertEqual(len(attempts), expected_attempts)
                self.assertEqual(transport.mutation_attempt_count, expected_attempts)
                self.assertEqual(api.refs, {})

    def test_create_ref_rejects_unverified_commit_shape_before_mutation(self):
        cases = (PARENT, "a" * 40, "b" * 40, "c" * 40)
        for index, commit in enumerate(cases):
            with self.subTest(commit=commit):
                api = FakeGitHubApi()
                if index == 2:
                    valid = unpublished_journal(api)
                    tree = api.commits[valid][0]
                    api.commits[commit] = (tree, [])
                elif index == 3:
                    valid = unpublished_journal(api)
                    tree = api.commits[valid][0]
                    api.commits[commit] = (tree, [PARENT, "d" * 40])
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    transport.create_ref(REF, commit)
                self.assertEqual(transport.mutation_attempt_count, 0)
                self.assertEqual(api.mutation_calls, 0)
                self.assertEqual(api.refs, {})

    def test_create_ref_success_has_exact_request_and_no_evidence(self):
        commit = unpublished_journal(self.api)
        result = self.transport.create_ref(REF, commit)
        self.assertEqual(result.status, CreateRefStatusV3.CREATED)
        self.assertIsNone(result.writer_evidence_id)
        mutation = [call for call in self.api.calls if call[1].endswith("/git/refs")]
        self.assertEqual(len(mutation), 1)
        self.assertEqual(mutation[0][2], {"ref": REF, "sha": commit})

    def test_definite_already_exists_is_narrowly_classified(self):
        self.api.create_ref_status = 422
        self.api.create_ref_body = {
            "message": "Reference already exists",
            "errors": [{"resource": "Reference", "code": "already_exists", "field": "ref"}],
        }
        result = self.transport.create_ref(REF, unpublished_journal(self.api))
        self.assertEqual(result.status, CreateRefStatusV3.ALREADY_EXISTS)
        self.assertEqual(self.api.mutation_calls, 1)

    def test_unrelated_422_and_malformed_success_are_unknown(self):
        cases = (
            (422, {"message": "Reference already exists", "errors": [
                {"resource": "Other", "field": "sha", "code": "already_exists"}
            ]}),
            (422, {"message": "Validation Failed", "errors": [{"code": "invalid"}]}),
            (201, {"ref": REF, "object": {"type": "commit", "sha": "f" * 40}}),
            (500, {"message": "Internal Server Error"}),
        )
        for status, body in cases:
            with self.subTest(status=status, body=body):
                api = FakeGitHubApi()
                api.create_ref_status = status
                api.create_ref_body = body
                result = GitHubTransportLiveV3(
                    "secret-token", REPOSITORY, executor=api
                ).create_ref(REF, unpublished_journal(api))
                self.assertEqual(result.status, CreateRefStatusV3.UNKNOWN)
                self.assertEqual(api.mutation_calls, 1)

    def test_lost_create_ref_acknowledgment_is_unknown_without_retry(self):
        self.transport.repository_node_id
        url = "https://api.github.com/repos/fanilosendrison/review-broker/git/refs"
        self.api.raise_on = ("POST", url)
        result = self.transport.create_ref(REF, unpublished_journal(self.api))
        self.assertEqual(result.status, CreateRefStatusV3.UNKNOWN)
        attempted = [call for call in self.api.calls if call[0] == "POST"
                     and "/git/" in call[1]]
        self.assertEqual([call[1] for call in attempted], [url])
        self.assertEqual(self.transport.mutation_attempt_count, 1)
        self.assertEqual(self.api.refs, {})

    def test_graphql_successor_requires_verified_journal_before_mutation(self):
        for entries in ([], [{"path": ".review-broker/attempt.json", "mode": "120000",
                               "type": "blob", "sha": "f" * 40}]):
            with self.subTest(entries=entries):
                api = FakeGitHubApi()
                after = api.install_successor(PARENT)
                api.trees[api.commits[after][0]] = entries
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    transport.update_ref(GraphQLRefUpdateV3(
                        NODE_ID, REF, PARENT, after, False
                    ))
                self.assertEqual(transport.mutation_attempt_count, 0)
                self.assertEqual(api.mutation_calls, 0)

    def test_graphql_update_has_exact_expected_old_shape(self):
        after = self.api.install_successor(PARENT)
        result = self.transport.update_ref(GraphQLRefUpdateV3(
            NODE_ID, REF, PARENT, after, False
        ))
        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.errors, ())
        self.assertIsNone(result.writer_evidence_id)
        mutation = [call for call in self.api.calls
                    if call[1] == "https://api.github.com/graphql"
                    and isinstance(call[2], dict) and str(call[2].get("query", "")).startswith("mutation")]
        self.assertEqual(len(mutation), 1)
        variables = mutation[0][2]["variables"]
        self.assertEqual(variables, {
            "repositoryId": NODE_ID, "name": REF, "beforeOid": PARENT,
            "afterOid": after, "force": False,
        })
        self.assertEqual(mutation[0][2]["query"].count("refUpdates:[{"), 1)

    def test_force_wrong_repository_or_wrong_parent_rejects_before_mutation(self):
        after = self.api.install_successor(PARENT)
        cases = (
            GraphQLRefUpdateV3(NODE_ID, REF, PARENT, after, True),
            GraphQLRefUpdateV3("R_wrong", REF, PARENT, after, False),
            GraphQLRefUpdateV3(NODE_ID, REF, "a" * 40, after, False),
        )
        for update in cases:
            with self.subTest(update=update):
                api = FakeGitHubApi()
                api.install_successor(PARENT, after)
                transport = GitHubTransportLiveV3("secret-token", REPOSITORY, executor=api)
                with self.assertRaises(GitHubTransportLiveV3Error):
                    transport.update_ref(update)
                self.assertEqual(api.mutation_calls, 0)

    def test_http_200_graphql_errors_are_not_success_or_typed_rejection(self):
        after = self.api.install_successor(PARENT)
        self.api.graphql_body = {"data": {"updateRefs": None},
                                 "errors": [{"message": "The ref has changed"}]}
        result = self.transport.update_ref(GraphQLRefUpdateV3(
            NODE_ID, REF, PARENT, after, False
        ))
        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.errors, ("GRAPHQL_APPLICATION_ERROR",))
        self.assertFalse(result.expected_old_rejected)
        self.assertIsNone(result.rejection_evidence_id)
        self.assertEqual(self.api.mutation_calls, 1)

    def test_typed_unprocessable_graphql_error_is_sanitized_but_unattributed(self):
        after = self.api.install_successor(PARENT)
        self.api.graphql_body = {"data": {"updateRefs": None}, "errors": [{
            "type": "UNPROCESSABLE", "path": ["mutation", "updateRefs"],
            "message": "opaque backend text"
        }]}
        result = self.transport.update_ref(GraphQLRefUpdateV3(
            NODE_ID, REF, PARENT, after, False
        ))
        self.assertEqual(result.errors, ("GRAPHQL_TYPED_UNPROCESSABLE",))
        self.assertFalse(result.expected_old_rejected)
        self.assertIsNone(result.rejection_evidence_id)
        self.assertEqual(self.api.mutation_calls, 1)

    def test_opaque_or_malformed_graphql_response_remains_unattributed(self):
        after = self.api.install_successor(PARENT)
        cases = (
            {"errors": [{"message": "opaque"}]}, {"data": {}},
            {"data": {"updateRefs": {"clientMutationId": None}}, "errors": None},
            {"data": {"updateRefs": {"clientMutationId": None}}, "errors": []},
            {"data": {"updateRefs": {"clientMutationId": None}}, "errors": {}},
            {"data": {"updateRefs": {"clientMutationId": None}}, "errors": "invalid"},
            {"data": {"updateRefs": {}}},
            {"data": {"updateRefs": {"clientMutationId": {"wrong": "type"}}}},
        )
        for body in cases:
            with self.subTest(body=body):
                api = FakeGitHubApi()
                api.install_successor(PARENT, after)
                api.graphql_body = body
                result = GitHubTransportLiveV3(
                    "secret-token", REPOSITORY, executor=api
                ).update_ref(GraphQLRefUpdateV3(NODE_ID, REF, PARENT, after, False))
                self.assertTrue(result.errors)
                self.assertFalse(result.expected_old_rejected)
                self.assertIsNone(result.writer_evidence_id)
                self.assertEqual(api.mutation_calls, 1)

    def test_network_interruption_during_graphql_mutation_is_not_retried(self):
        after = self.api.install_successor(PARENT)
        self.transport.repository_node_id
        url = "https://api.github.com/graphql"
        self.api.raise_graphql_mutation = True
        result = self.transport.update_ref(GraphQLRefUpdateV3(
            NODE_ID, REF, PARENT, after, False
        ))
        self.assertIsNone(result.http_status)
        self.assertEqual(result.errors, ("GITHUB_TRANSPORT_UNAVAILABLE",))
        mutation_attempts = [call for call in self.api.calls
                             if call[0] == "POST" and call[1] == url
                             and isinstance(call[2], dict)
                             and str(call[2].get("query", "")).startswith("mutation")]
        self.assertEqual(len(mutation_attempts), 1)
        self.assertEqual(self.transport.mutation_attempt_count, 1)
        other_writes = [call for call in self.api.calls if call[0] == "POST"
                        and call[1] != url]
        self.assertEqual(other_writes, [])
        self.assertEqual(self.api.refs, {})

    def test_temporary_stale_readback_performs_no_write_or_retry(self):
        old, _ = self.api.install_journal()
        after = self.api.install_successor(old)
        update = GraphQLRefUpdateV3(NODE_ID, REF, old, after, False)
        result = self.transport.update_ref(update)
        self.assertEqual(result.errors, ())
        before_reads = self.api.mutation_calls
        snapshot = self.transport.read_claim(REF)
        self.assertEqual(snapshot.snapshot.commit_sha, old)
        self.assertEqual(self.api.mutation_calls, before_reads)
        graphql_mutations = [call for call in self.api.calls
                             if call[1] == "https://api.github.com/graphql"
                             and isinstance(call[2], dict)
                             and str(call[2].get("query", "")).startswith("mutation")]
        self.assertEqual(len(graphql_mutations), 1)

    def test_token_is_not_serialized_in_request_bodies(self):
        after = self.api.install_successor(PARENT)
        self.transport.update_ref(GraphQLRefUpdateV3(NODE_ID, REF, PARENT, after, False))
        serialized = json.dumps([call[2] for call in self.api.calls], sort_keys=True)
        self.assertNotIn("secret-token", serialized)


if __name__ == "__main__":
    unittest.main()
