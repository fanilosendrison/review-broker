from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from argparse import Namespace

from review_broker.cli import _result
from review_broker.verifiedresult import ResultUnavailable, read_verified_result

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import canonical_bytes
from review_broker.orchestration import publish_validated_result
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

    def test_cli_rejects_unjournaled_forged_go_comment(self):
        journal, _ = self.journal()
        with mock.patch("review_broker.verifiedresult.GitHubRefJournal", return_value=journal):
            with self.assertRaisesRegex(ResultUnavailable, "RESULT_UNAVAILABLE"):
                _result(Namespace(broker_repo="sample/repo", request=REQUEST_ID, json=True))

    def published_fixture(self):
        journal, holder = self.journal()
        publication_intent = intent("f")
        comment = {
            "id": 17, "node_id": "IC_17",
            "html_url": "https://example.invalid/comment/17",
            "issue_url": "https://api.github.com/repos/sample/repo/issues/7",
            "created_at": "2026-10-26T00:01:00+00:00",
            "body": render_result_comment(result(), publication_id=publication_intent["publication_id"]),
            "user": {"login": "broker", "id": 9},
        }
        receipt = {
            "schema_version": 1,
            "evidence_type": "github-result-publication-observation",
            "publication_id": publication_intent["publication_id"],
            "result_id": publication_intent["result_id"],
            "issue_number": 7,
            "publisher": {"login": "broker", "id": 9},
            "comment_id": 17,
            "comment_node_id": "IC_17",
            "comment_url": comment["html_url"],
            "comment_created_at": comment["created_at"],
            "observed_at": "2026-10-26T00:02:00+00:00",
        }
        holder["record"] = replace(holder["record"], state=AttemptState.REPORTED,
                                   publication_intent=publication_intent,
                                   publication_receipt=receipt)
        class Publisher:
            def __init__(self):
                self.listed = [comment]
                self.exact = comment
            def comments(self, issue_number):
                return self.listed
            def comment(self, comment_id):
                return self.exact
        return journal, holder, Publisher(), comment

    def test_cli_accepts_only_exact_journaled_comment(self):
        journal, _, publisher, _ = self.published_fixture()
        self.assertEqual(read_verified_result("sample/repo", REQUEST_ID,
                                             journal=journal, publisher=publisher), result())

    def test_cli_ignores_unattributable_marker_and_body_copies(self):
        journal, holder, publisher, comment = self.published_fixture()
        marker = ("<!-- review-broker-publication:v1 "
                  + holder["record"].publication_intent["publication_id"] + " -->")
        adversaries = [
            {**comment, "id": 18, "body": marker,
             "user": {"login": "attacker", "id": 10}},
            {**comment, "id": 19, "user": {"login": "attacker", "id": 10}},
            {**comment, "id": 20, "body": marker},
            {**comment, "id": 21, "body": comment["body"] + " altered"},
        ]
        for adversary in adversaries:
            with self.subTest(comment_id=adversary["id"]):
                publisher.listed = [adversary, comment]
                self.assertEqual(read_verified_result("sample/repo", REQUEST_ID,
                    journal=journal, publisher=publisher), result())
                observer = GitHubPublisher("sample/repo")
                observer.comments = lambda _issue: publisher.listed
                self.assertEqual(observer.observe(holder["record"].publication_intent,
                    result())["comment_id"], 17)

    def test_cli_rejects_forged_publisher_and_conflicting_result(self):
        journal, _, publisher, comment = self.published_fixture()
        publisher.exact = {**comment, "user": {"login": "untrusted", "id": 10}}
        with self.assertRaisesRegex(PublicationError, "IDENTITY_MISMATCH"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)
        publisher.exact = {**comment, "body": render_result_comment(
            {**result(), "review_verdict": "NO_GO"},
            publication_id=intent("f")["publication_id"])}
        with self.assertRaisesRegex(PublicationError, "IDENTITY_MISMATCH"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)

    def test_cli_rejects_missing_or_modified_exact_comment_and_duplicates(self):
        journal, holder, publisher, comment = self.published_fixture()
        receipt = holder["record"].publication_receipt
        holder["record"] = replace(holder["record"], publication_receipt=None)
        with self.assertRaisesRegex(ResultUnavailable, "PUBLICATION_INDETERMINATE"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)
        holder["record"] = replace(holder["record"], publication_receipt=receipt)
        publisher.listed = []
        with self.assertRaisesRegex(PublicationError, "MISSING_OR_AMBIGUOUS"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)
        publisher.listed = [comment, {**comment, "id": 18}]
        with self.assertRaisesRegex(PublicationError, "MISSING_OR_AMBIGUOUS"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)
        publisher.listed = [comment]
        publisher.exact = {**comment, "body": "modified"}
        with self.assertRaisesRegex(PublicationError, "IDENTITY_MISMATCH"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)

    def test_cli_rejects_receipt_and_comment_identity_variants(self):
        for field, replacement in (
            ("comment_id", 18), ("comment_node_id", "IC_OTHER"),
            ("comment_url", "https://example.invalid/other"),
            ("comment_created_at", "2026-10-27T00:01:00+00:00"),
            ("publication_id", "publication:sha256:" + "0" * 64),
            ("result_id", "result:sha256:" + "0" * 64),
            ("issue_number", 8), ("publisher", {"login": "other", "id": 10}),
        ):
            with self.subTest(field=field):
                journal, holder, publisher, _ = self.published_fixture()
                prior = holder["record"]
                holder["record"] = replace(prior, publication_receipt={
                    **prior.publication_receipt, field: replacement})
                with self.assertRaises(PublicationError):
                    read_verified_result("sample/repo", REQUEST_ID,
                        journal=journal, publisher=publisher)

    def test_cli_rejects_wrong_issue_and_incomplete_observations(self):
        journal, _, publisher, comment = self.published_fixture()
        publisher.exact = {**comment,
            "issue_url": "https://api.github.com/repos/sample/repo/issues/8"}
        with self.assertRaisesRegex(PublicationError, "IDENTITY_MISMATCH"):
            read_verified_result("sample/repo", REQUEST_ID,
                journal=journal, publisher=publisher)
        for code in ("PUBLICATION_COMMENT_SCAN_INCOMPLETE", "PUBLICATION_API_FAILED"):
            with self.subTest(code=code):
                publisher.comments = mock.Mock(side_effect=PublicationError(code))
                with self.assertRaisesRegex(PublicationError, code):
                    read_verified_result("sample/repo", REQUEST_ID,
                        journal=journal, publisher=publisher)

    def test_pagination_cap_and_api_failure_are_fail_closed(self):
        for status, output, expected in (
            (0, json.dumps([{}] * 100), "COMMENT_SCAN_INCOMPLETE"),
            (1, "", "API_FAILED"),
        ):
            with self.subTest(status=status):
                runner = mock.Mock(return_value=subprocess.CompletedProcess(
                    [], status, output, ""))
                with self.assertRaisesRegex(PublicationError, expected):
                    GitHubPublisher("sample/repo", runner=runner).comments(7)
                self.assertEqual(runner.call_count, 100 if status == 0 else 1)

    def test_cli_preserves_historical_superseded_result(self):
        journal, holder, publisher, _ = self.published_fixture()
        historical = {**result(), "applicability": {"status": "SUPERSEDED",
            "checked_head_commit": "b" * 40}}
        replacement_intent = build_publication_intent(
            historical, issue_number=7, publisher={"login": "broker", "id": 9},
            nonce="f" * 64, reserved_at="2026-10-26T00:00:00+00:00",
        )
        prior = holder["record"]
        holder["record"] = replace(prior, publication_intent=replacement_intent,
            publication_receipt={**prior.publication_receipt,
                "publication_id": replacement_intent["publication_id"],
                "result_id": replacement_intent["result_id"]})
        publisher.listed[0] = {**publisher.listed[0], "body": render_result_comment(
            historical, publication_id=replacement_intent["publication_id"])}
        publisher.exact = publisher.listed[0]
        self.assertEqual(read_verified_result("sample/repo", REQUEST_ID,
            journal=journal, publisher=publisher)["applicability"]["status"], "SUPERSEDED")

    def test_nested_validation_diagnostic_cannot_be_rendered_or_posted(self):
        canary = "sk-" + "E" * 24
        value = result()
        value["validation"] = {"validation_reasons": ["synthetic diagnostic " + canary]}
        with self.assertRaisesRegex(PublicationError, "CREDENTIAL_PATTERN_IN_RESULT"):
            render_result_comment(value, publication_id=intent("a")["publication_id"])

    def test_lost_response_intent_without_receipt_is_not_a_cli_result(self):
        journal, holder, publisher, _ = self.published_fixture()
        holder["record"] = replace(holder["record"], state=AttemptState.VALIDATED,
                                   publication_receipt=None)
        with self.assertRaisesRegex(ResultUnavailable, "PUBLICATION_INDETERMINATE"):
            read_verified_result("sample/repo", REQUEST_ID, journal=journal, publisher=publisher)

    def test_identity_failure_precedes_reservation_and_comment_publication(self):
        class Journal:
            def get(self, request_id):
                return AttemptRecord(
                    request_id=request_id,
                    attempt_id=ATTEMPT_ID,
                    state=AttemptState.VALIDATED,
                )

            def reserve_publication(self, *args):
                raise AssertionError("reservation forbidden")

        class Publisher:
            def __init__(self, repository):
                pass

            def identity(self):
                raise PublicationError("PUBLICATION_ACTIONS_ACTOR_INVALID")

            def publish_reserved(self, *args, **kwargs):
                raise AssertionError("comment publication forbidden")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            values = {
                "resolved-request.json": {
                    "request_id": REQUEST_ID,
                    "subject": {"repository": "sample/subject", "pull_request": 7},
                },
                "broker-metadata.json": {"issue_number": 7},
                "input-manifest.json": {},
                "attempt.json": {"attempt_id": ATTEMPT_ID},
                "validation.json": {},
            }
            for name, value in values.items():
                (root / name).write_bytes(canonical_bytes(value) + b"\n")
            patches = (
                mock.patch("review_broker.orchestration._gh_json", return_value={"head": {"sha": "a" * 40}}),
                mock.patch("review_broker.orchestration.build_review_result", return_value=result()),
                mock.patch("review_broker.orchestration.GitHubRefJournal", return_value=Journal()),
                mock.patch("review_broker.orchestration.GitHubPublisher", Publisher),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(PublicationError, "ACTIONS_ACTOR_INVALID"):
                    publish_validated_result("sample/repo", root)

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
