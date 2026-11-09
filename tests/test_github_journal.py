import base64
import json
import subprocess
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, StateTransitionError
from tests.journal_http_transport import scoped_response


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
    return scoped_response(command, value, returncode)


def record_bytes(value=None):
    selected = value or record(AttemptState.REQUESTED)
    return canonical_bytes(selected.as_dict()) + b"\n"


def content_journal(content, *, encoding="base64"):
    def runner(command, **_kwargs):
        endpoint = command[4]
        if "/git/refs/heads/review-claims/" in endpoint:
            return response(command, {"object": {"sha": COMMIT_A}})
        if endpoint.endswith("?ref=" + COMMIT_A):
            value = {"content": content}
            if encoding is not None:
                value["encoding"] = encoding
            return response(command, value)
        raise AssertionError(endpoint)
    return GitHubRefJournal("sample/repo", runner=runner)


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

    def test_wrapped_github_base64_recovers_canonical_requested_record(self):
        encoded = base64.b64encode(record_bytes()).decode("ascii")
        wrapped = "\n".join(encoded[index:index + 60] for index in range(0, len(encoded), 60)) + "\n"
        with self.assertRaises(ValueError):
            base64.b64decode(wrapped, validate=True)
        observed_sha, observed = content_journal(wrapped)._read(REQUEST_ID)
        self.assertEqual(observed_sha, COMMIT_A)
        self.assertEqual(observed.request_id, REQUEST_ID)
        self.assertEqual(observed.attempt_id, attempt_identity(REQUEST_ID, 1))
        self.assertEqual(observed.state, AttemptState.REQUESTED)
        self.assertEqual(observed.invocation_count, 0)

    def test_crlf_and_permitted_ascii_whitespace_are_accepted(self):
        encoded = base64.b64encode(record_bytes()).decode("ascii")
        variants = (
            "\r\n".join(encoded[index:index + 60] for index in range(0, len(encoded), 60)) + "\r\n",
            " \t\r\n" + " \t\r\n".join(encoded[index:index + 17] for index in range(0, len(encoded), 17)),
        )
        for value in variants:
            with self.subTest(value=value[:12]):
                self.assertEqual(content_journal(value)._read(REQUEST_ID)[1].state,
                                 AttemptState.REQUESTED)

    def test_invalid_alphabet_padding_and_unicode_whitespace_are_rejected(self):
        encoded = base64.b64encode(record_bytes()).decode("ascii")
        invalid = (encoded[:10] + "!" + encoded[11:], encoded.rstrip("="),
                   "Zh==", encoded[:8] + "\u00a0" + encoded[8:])
        for value in invalid:
            with self.subTest(value=value[:12]), self.assertRaisesRegex(
                StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"
            ):
                content_journal(value)._read(REQUEST_ID)

    def test_decoded_corruption_utf8_and_noncanonical_json_are_rejected(self):
        values = (
            b"{",
            b"\xff",
            json.dumps(record(AttemptState.REQUESTED).as_dict(), indent=2).encode() + b"\n",
        )
        for raw in values:
            encoded = base64.b64encode(raw).decode("ascii")
            with self.subTest(raw=raw[:12]), self.assertRaisesRegex(
                StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"
            ):
                content_journal(encoded)._read(REQUEST_ID)

    def test_mismatched_request_identity_is_rejected(self):
        other_id = "request:sha256:" + "b" * 64
        other = AttemptRecord(
            request_id=other_id,
            attempt_id=attempt_identity(other_id, 1),
            state=AttemptState.REQUESTED,
            history=({"state": AttemptState.REQUESTED.value, "evidence_ids": []},),
        )
        encoded = base64.b64encode(record_bytes(other)).decode("ascii")
        with self.assertRaisesRegex(StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"):
            content_journal(encoded)._read(REQUEST_ID)

    def test_missing_or_incorrect_encoding_is_rejected(self):
        encoded = base64.b64encode(record_bytes()).decode("ascii")
        for encoding in (None, "Base64", "utf-8"):
            with self.subTest(encoding=encoding), self.assertRaisesRegex(
                StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"
            ):
                content_journal(encoded, encoding=encoding)._read(REQUEST_ID)

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
