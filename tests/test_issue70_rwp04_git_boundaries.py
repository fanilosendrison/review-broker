"""Concrete Git Database HTTP composition with current-journal revocation per request."""
from pathlib import Path
import tempfile
import unittest

from review_broker.github_transport_live_v3 import GitHubTransportLiveV3, GitHubTransportLiveV3Error
from review_broker.github_journal_transport_v3 import GraphQLRefUpdateV3
from review_broker.pre_model_remote_retention_v3 import _GuardedPreparedWriter
from tests.github_transport_live_v3_support import FakeGitHubApi, REPOSITORY, NODE_ID, PARENT, REF
from tests.issue70_rwp04_test_support import RemoteScenario


class ConcreteGitBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.r = RemoteScenario(Path(cls.temporary.name))
        cls.a = cls.r.verification.snapshot

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.r.s.worker.transport.refs[self.a.claim_ref] = self.a.commit_sha

    def tearDown(self):
        self.r.s.worker.transport.refs[self.a.claim_ref] = self.a.commit_sha

    def move(self):
        transport = self.r.s.worker.transport
        sha = transport.create_journal_commit(self.a.commit_sha, self.a.journal_bytes)
        transport.attributed.add(sha)
        transport.refs[self.a.claim_ref] = sha

    def test_RQ16_http_guard_stops_after_each_blob_tree_commit_effect(self):
        root = f"https://api.github.com/repos/{REPOSITORY}"
        for trigger, expected_writes in (("blobs", 1), ("trees", 2), ("commits", 3)):
            self.setUp()
            api = FakeGitHubApi()
            def execute(request):
                response = api(request)
                if request.get_method() == "POST" and request.full_url == root+"/git/"+trigger:
                    self.move()
                return response
            transport = GitHubTransportLiveV3("fixture-token", REPOSITORY, executor=execute)
            guarded = _GuardedPreparedWriter(transport, self.r.verification.before_effect)
            with self.subTest(trigger=trigger), self.assertRaises(GitHubTransportLiveV3Error):
                guarded.create_journal_commit(PARENT, b"exact fixture journal bytes")
            writes = [url for method, url, body, auth in api.calls
                      if method == "POST" and "/git/" in url]
            self.assertEqual(writes, [root+"/git/"+name for name in ("blobs", "trees", "commits")[:expected_writes]])
            self.assertNotEqual(self.r.s.worker.journal.read(self.r.s.worker.admission.request_id), self.a)
            self.assertEqual(len(self.r.service.uploads), 0)

    def test_RQ16_http_guard_stops_graphql_cas_after_final_identity_observation(self):
        api = FakeGitHubApi()
        successor = api.install_successor(PARENT)
        transport = GitHubTransportLiveV3("fixture-token", REPOSITORY, executor=api)
        transport.verify_repository_identity()  # Cache established identity before the guarded update.
        api.calls.clear()
        def execute(request):
            response = api(request)
            if request.get_method() == "POST" and request.full_url.endswith("/graphql"):
                import json
                if json.loads(request.data)["query"].startswith("query"):
                    self.move()
            return response
        transport._executor = execute
        guarded = _GuardedPreparedWriter(transport, self.r.verification.before_effect)
        result = guarded.update_ref(GraphQLRefUpdateV3(NODE_ID, REF, PARENT, successor, False))
        self.assertIsNone(result.http_status)
        self.assertEqual(api.mutation_calls, 0)
        import json
        # Count actual emitted HTTP payloads, not merely the broker's outcome reason.
        mutations = [body for method, url, body, auth in api.calls
                     if method == "POST" and url.endswith("/graphql") and body["query"].startswith("mutation")]
        self.assertEqual(mutations, [])
        self.assertNotEqual(self.r.s.worker.journal.read(self.r.s.worker.admission.request_id), self.a)

    def test_RQ16_historical_sha_reader_uses_real_git_object_checks_not_head(self):
        api = FakeGitHubApi()
        sha, _ = api.install_journal(content=b"historical journal bytes")
        api.refs[REF] = api.install_successor(sha)
        transport = GitHubTransportLiveV3("fixture-token", REPOSITORY, executor=api)
        result = transport.read_journal_commit(sha)
        self.assertEqual(result.status.value, "FOUND")
        self.assertEqual(result.snapshot.commit_sha, sha)
        self.assertEqual(result.snapshot.journal_bytes, b"historical journal bytes")
        self.assertFalse(any("/git/ref/" in url for _, url, _, _ in api.calls))
        self.assertEqual(api.mutation_calls, 0)
