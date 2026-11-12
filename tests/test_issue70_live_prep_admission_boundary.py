"""Source-confronted admission ordering evidence for the blocked live composition."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.admission_v3 import admit_initial_inline_v3
from review_broker.github_git_file_v3 import GitHubGitFileReaderV3
from review_broker.github_issue_reference_v3 import GitHubIssueReferenceReaderV3
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
from tests.issue70_test_support import AuthenticatedScenario
from tests.issue69_test_support import PullApi, TOKEN
from tests.request_v3_test_support import HistoryAuthority, origin


class AdmissionBoundaryTests(unittest.TestCase):
    def test_existing_admission_reads_all_remote_references_before_any_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            scenario = AuthenticatedScenario(Path(temporary))
            reader = origin(scenario.request)
            observation = reader.observe(51)
            requester = GitHubRequesterAuthorityV3(requester_id=observation.requester_id,
                broker_issue_id=observation.issue_id, origin_evidence_id=observation.evidence_id,
                authorized=True)  # Explicit offline owner fixture, not deployed authority.
            observed = []
            def wrap(original, kind):
                def call(instance, *args, **kwargs):
                    self.assertEqual(scenario.transport.refs, {})
                    observed.append(kind)
                    return original(instance, *args, **kwargs)
                return call
            with patch.object(GitHubGitFileReaderV3, "observe",
                    wrap(GitHubGitFileReaderV3.observe, "git_file")), \
                 patch.object(GitHubIssueReferenceReaderV3, "observe_issue_body",
                    wrap(GitHubIssueReferenceReaderV3.observe_issue_body, "github_issue_body")), \
                 patch.object(GitHubIssueReferenceReaderV3, "observe_issue_comment",
                    wrap(GitHubIssueReferenceReaderV3.observe_issue_comment, "github_issue_comment")):
                admitted = admit_initial_inline_v3(reader, broker_issue_number=51,
                    expected_broker_issue_id=observation.issue_id,
                    expected_requester_id=observation.requester_id, requester_authority=requester,
                    pr_authority=scenario.pr_reader, source_authority=scenario.source,
                    history_authority=HistoryAuthority(), git_file_readers=scenario.git_readers,
                    issue_reference_readers=scenario.issue_readers)
            self.assertEqual(observed, ["git_file", "github_issue_body", "github_issue_comment"])
            self.assertEqual(admitted.journal_admission(), scenario.admission.journal_admission())
            self.assertEqual(scenario.transport.refs, {})

    def test_qualified_pr_reader_needs_finalized_capture_and_rejects_control_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            scenario = AuthenticatedScenario(Path(temporary))
            capture = scenario.capture
            values = (capture.repository, capture.repository_id, capture.pull_request)
            reader = GitHubPullRequestObservationReaderV3(TOKEN, *values, capture.head_sha,
                source_authority=scenario.source,
                executor=PullApi(capture.base_sha, capture.head_sha, capture.merge_base_sha,
                    [{"status": "modified", "filename": "review.md"}]))
            reader.observe_scope()
            self.assertIsNone(reader.observe(*values))
            with self.assertRaisesRegex(ValueError, "PR_SOURCE_AUTHORITY_REQUIRED"):
                GitHubPullRequestObservationReaderV3("fixture-control-token", *values,
                    capture.head_sha, source_authority=scenario.source)
            # Actual existing capture satisfies finalize; no provisional source receipt is invented.
            reader.finalize(reader._scope, capture)
            self.assertIsNotNone(reader.observe(*values))
