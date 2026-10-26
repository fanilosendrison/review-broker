import json
import subprocess
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.publication import (
    GitHubPublisher,
    PublicationError,
    build_publication_intent,
    render_result_comment,
    validate_publication_intent,
)
from review_broker.queue import AttemptRecord, AttemptState


REQUEST_ID = "request:sha256:" + "1" * 64
ATTEMPT_ID = "attempt:sha256:" + "2" * 64


def result():
    return {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "subject_id": "subject:sha256:" + "3" * 64,
        "policy_id": "policy:sha256:" + "4" * 64,
        "packet_id": "packet:sha256:" + "5" * 64,
        "attempt_id": ATTEMPT_ID,
        "execution_status": "COMPLETED",
        "evidence_status": "VALID",
        "review_verdict": "GO",
        "resolved_request": {"subject": {"head_commit": "a" * 40}},
        "reviewer": {
            "backend": "codex-cli",
            "model_requested": "gpt-5.6-sol",
            "reasoning_effort_requested": "xhigh",
            "effective_model_identity_verified": False,
            "effective_reasoning_effort_verified": False,
        },
        "sources_examined": [],
        "findings": [],
        "remaining_uncertainties": [],
        "validation": {"semantic_correctness_validated": False},
        "applicability": {
            "status": "CURRENT",
            "checked_head_commit": "a" * 40,
        },
    }


def intent(nonce: str):
    return build_publication_intent(
        result(),
        issue_number=7,
        publisher={"login": "broker", "id": 9},
        nonce=nonce * 64,
        reserved_at="2026-10-26T00:00:00+00:00",
    )


class PublicationJournalTests(unittest.TestCase):
    def journal(self):
        journal = GitHubRefJournal("sample/repo")
        current = AttemptRecord(
            request_id=REQUEST_ID,
            attempt_id=ATTEMPT_ID,
            state=AttemptState.VALIDATED,
        )
        holder = {"sha": "a" * 40, "record": current}
        journal._read = lambda _request: (holder["sha"], holder["record"])
        journal.get = lambda _request: holder["record"]

        def compare(_request, expected_sha, updated):
            if expected_sha != holder["sha"]:
                raise AssertionError("stale compare")
            holder["sha"] = "b" * 40
            holder["record"] = updated

        journal._compare_and_swap = compare
        return journal, holder

    def test_publication_intent_preserves_exact_result_across_later_head_movement(self):
        publication_intent = intent("e")
        changed = result()
        changed["applicability"] = {
            "status": "SUPERSEDED",
            "checked_head_commit": "b" * 40,
        }
        self.assertEqual(publication_intent["result"], result())
        with self.assertRaisesRegex(PublicationError, "RESULT_IDENTITY_MISMATCH"):
            validate_publication_intent(publication_intent, result=changed)

    def test_competing_publication_reservations_authorize_one_poster(self):
        journal, holder = self.journal()
        first_record, first_created = journal.reserve_publication(
            REQUEST_ID, intent("a")
        )
        second_record, second_created = journal.reserve_publication(
            REQUEST_ID, intent("b")
        )
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(
            second_record.publication_intent,
            first_record.publication_intent,
        )
        self.assertEqual(holder["record"].publication_intent, intent("a"))

    def test_non_reservation_observer_never_posts_when_comment_is_absent(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "[]", "")

        with self.assertRaisesRegex(PublicationError, "OUTCOME_INDETERMINATE"):
            GitHubPublisher("sample/repo", runner=runner).publish_reserved(
                intent("c"), result(), reservation_created=False
            )
        self.assertTrue(calls)
        self.assertTrue(all(command[3] == "GET" for command in calls))

    def test_multiple_exact_attributable_comments_are_an_incident(self):
        publication_intent = intent("d")
        body = render_result_comment(
            result(), publication_id=publication_intent["publication_id"]
        )
        comment = {
            "id": 1,
            "node_id": "IC_1",
            "html_url": "https://example.invalid/1",
            "created_at": "2026-10-26T00:01:00+00:00",
            "body": body,
            "user": {"login": "broker", "id": 9},
        }

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command, 0, json.dumps([comment, {**comment, "id": 2}]), ""
            )

        with self.assertRaisesRegex(PublicationError, "DUPLICATE_PUBLICATION_INCIDENT"):
            GitHubPublisher("sample/repo", runner=runner).observe(
                publication_intent, result()
            )


if __name__ == "__main__":
    unittest.main()
