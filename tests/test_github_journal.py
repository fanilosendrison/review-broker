import base64
import json
import subprocess
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, StateTransitionError


REQUEST_ID = "request:sha256:" + "a" * 64
COMMIT_A = "1" * 40
COMMIT_B = "2" * 40


def record(state: AttemptState) -> AttemptRecord:
    return AttemptRecord(
        request_id=REQUEST_ID,
        attempt_id=attempt_identity(REQUEST_ID, 1),
        state=state,
        history=({"state": state.value, "evidence_ids": []},),
    )


def response(command, value, returncode=0):
    return subprocess.CompletedProcess(command, returncode, json.dumps(value), "")


class GitHubJournalReadTests(unittest.TestCase):
    def test_ref_advance_cannot_mix_observed_commit_with_new_branch_content(self):
        endpoints = []
        record_a = record(AttemptState.REQUESTED)
        record_b = record(AttemptState.ARMED)

        def runner(command, **_kwargs):
            endpoint = command[4]
            endpoints.append(endpoint)
            if "/git/refs/heads/review-claims/" in endpoint:
                return response(command, {"object": {"sha": COMMIT_A}})
            if endpoint.endswith("?ref=" + COMMIT_A):
                encoded = base64.b64encode(
                    canonical_bytes(record_a.as_dict()) + b"\n"
                ).decode("ascii")
                return response(command, {"encoding": "base64", "content": encoded})
            if "?ref=review-claims/" in endpoint:
                encoded = base64.b64encode(
                    canonical_bytes(record_b.as_dict()) + b"\n"
                ).decode("ascii")
                return response(command, {"encoding": "base64", "content": encoded})
            raise AssertionError(endpoint)

        observed_sha, observed = GitHubRefJournal(
            "sample/repo", runner=runner
        )._read(REQUEST_ID)

        self.assertEqual(observed_sha, COMMIT_A)
        self.assertEqual(observed.state, AttemptState.REQUESTED)
        self.assertIn("?ref=" + COMMIT_A, endpoints[-1])
        self.assertNotIn("?ref=review-claims/", endpoints[-1])

    def test_stale_ref_read_returns_the_exact_stale_snapshot(self):
        record_a = record(AttemptState.PREPARED)

        def runner(command, **_kwargs):
            endpoint = command[4]
            if "/git/refs/heads/review-claims/" in endpoint:
                return response(command, {"object": {"sha": COMMIT_A}})
            self.assertTrue(endpoint.endswith("?ref=" + COMMIT_A))
            encoded = base64.b64encode(
                canonical_bytes(record_a.as_dict()) + b"\n"
            ).decode("ascii")
            return response(command, {"encoding": "base64", "content": encoded})

        observed_sha, observed = GitHubRefJournal(
            "sample/repo", runner=runner
        )._read(REQUEST_ID)
        self.assertEqual((observed_sha, observed.state), (COMMIT_A, AttemptState.PREPARED))

    def test_incomplete_ref_response_fails_closed(self):
        def runner(command, **_kwargs):
            return response(command, {"object": {}})

        with self.assertRaisesRegex(StateTransitionError, "JOURNAL_REF_RESPONSE_INVALID"):
            GitHubRefJournal("sample/repo", runner=runner)._read(REQUEST_ID)

    def test_incomplete_content_response_fails_closed(self):
        def runner(command, **_kwargs):
            endpoint = command[4]
            if "/git/refs/heads/review-claims/" in endpoint:
                return response(command, {"object": {"sha": COMMIT_A}})
            return response(command, {"encoding": "base64"})

        with self.assertRaisesRegex(StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"):
            GitHubRefJournal("sample/repo", runner=runner)._read(REQUEST_ID)

    def test_competing_update_rejects_stale_compare_and_swap(self):
        journal = GitHubRefJournal("sample/repo")
        journal._read = lambda _request: (COMMIT_A, record(AttemptState.REQUESTED))
        journal._state_commit = lambda _parent, _record: "3" * 40
        journal._api = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "reference update failed"
        )

        with self.assertRaisesRegex(StateTransitionError, "STATE_COMPARE_AND_SWAP_FAILED"):
            journal.transition(
                REQUEST_ID,
                AttemptState.ADMITTED,
                ["artifact:sha256:" + "4" * 64],
            )


if __name__ == "__main__":
    unittest.main()
