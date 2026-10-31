from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from urllib.request import Request

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_issue_origin_v3 import (
    GitHubIssueOriginReaderV3, GitHubIssueOriginV3Error,
)


REPOSITORY = "fanilosendrison/review-broker"
NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


class IssueApi:
    def __init__(self) -> None:
        self.repository_id = 1433701208
        self.issue_id = 9001
        self.requester_id = 42
        self.body: object = "exact private body\n"
        self.status = 200
        self.pull_request = False
        self.repository_calls = 0
        self.repository_drift_after: int | None = None
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: Request) -> HttpResponseV3:
        self.calls.append((request.get_method(), request.full_url))
        self.assert_auth(request)
        if request.full_url.endswith("/repos/fanilosendrison/review-broker"):
            self.repository_calls += 1
            repository_id = (1 if self.repository_drift_after is not None
                             and self.repository_calls > self.repository_drift_after
                             else self.repository_id)
            return self.response(200, {"id": repository_id, "full_name": REPOSITORY})
        value: dict[str, object] = {
            "id": self.issue_id, "number": 51, "body": self.body,
            "user": {"id": self.requester_id, "login": "owner"},
        }
        if self.pull_request:
            value["pull_request"] = {"url": "https://api.github.com/pulls/51"}
        return self.response(self.status, value)

    @staticmethod
    def assert_auth(request: Request) -> None:
        assert request.get_method() == "GET"
        assert request.headers["Authorization"] == "Bearer token"

    @staticmethod
    def response(status: int, value: object) -> HttpResponseV3:
        return HttpResponseV3(status, json.dumps(value).encode(), {})


class GitHubIssueOriginV3Tests(unittest.TestCase):
    def reader(self, api: IssueApi) -> GitHubIssueOriginReaderV3:
        return GitHubIssueOriginReaderV3(
            "token", REPOSITORY, 1433701208, executor=api, clock=lambda: NOW
        )

    def test_authenticated_issue_origin_preserves_body_and_identity(self) -> None:
        api = IssueApi()
        observation = self.reader(api).observe(51)
        self.assertEqual(observation.repository_id, 1433701208)
        self.assertEqual(observation.issue_id, 9001)
        self.assertEqual(observation.requester_id, 42)
        self.assertEqual(observation.body, "exact private body\n")
        self.assertEqual(len(observation.body_sha256 or ""), 64)
        self.assertTrue(observation.evidence_id.startswith("artifact:sha256:"))
        self.assertEqual([method for method, _ in api.calls], ["GET", "GET", "GET"])

    def test_null_and_empty_body_remain_distinct(self) -> None:
        null_api, empty_api = IssueApi(), IssueApi()
        null_api.body = None
        empty_api.body = ""
        null = self.reader(null_api).observe(51)
        empty = self.reader(empty_api).observe(51)
        self.assertIsNone(null.body_sha256)
        self.assertIsNotNone(empty.body_sha256)
        self.assertNotEqual(null.evidence_id, empty.evidence_id)

    def test_changed_body_produces_new_observation(self) -> None:
        api = IssueApi()
        first = self.reader(api).observe(51)
        api.body = "changed"
        second = self.reader(api).observe(51)
        self.assertNotEqual(first.body_sha256, second.body_sha256)
        self.assertNotEqual(first.evidence_id, second.evidence_id)

    def test_wrong_repository_numeric_id_fails_closed(self) -> None:
        api = IssueApi()
        api.repository_id = 1
        with self.assertRaisesRegex(GitHubIssueOriginV3Error, "REPOSITORY_IDENTITY_MISMATCH"):
            self.reader(api).observe(51)

    def test_repository_identity_drift_after_issue_read_fails_closed(self) -> None:
        api = IssueApi()
        api.repository_drift_after = 1
        with self.assertRaisesRegex(GitHubIssueOriginV3Error, "IDENTITY_MISMATCH"):
            self.reader(api).observe(51)
        self.assertEqual(api.repository_calls, 2)
        self.assertEqual([method for method, _ in api.calls], ["GET", "GET", "GET"])

    def test_issue_and_requester_identity_are_strict(self) -> None:
        for attribute, value, marker in (
            ("issue_id", 0, "ISSUE_ID_INVALID"),
            ("requester_id", True, "REQUESTER_ID_INVALID"),
        ):
            with self.subTest(attribute=attribute):
                api = IssueApi()
                setattr(api, attribute, value)
                with self.assertRaisesRegex(GitHubIssueOriginV3Error, marker):
                    self.reader(api).observe(51)

    def test_pull_request_record_is_rejected(self) -> None:
        api = IssueApi()
        api.pull_request = True
        with self.assertRaisesRegex(GitHubIssueOriginV3Error, "PULL_REQUEST_FORBIDDEN"):
            self.reader(api).observe(51)

    def test_missing_read_permission_fails_closed_without_body_output(self) -> None:
        api = IssueApi()
        api.status = 403
        with self.assertRaisesRegex(GitHubIssueOriginV3Error, "ISSUE_UNAVAILABLE") as caught:
            self.reader(api).observe(51)
        self.assertNotIn("exact private body", str(caught.exception))

    def test_selectors_are_validated_before_requests(self) -> None:
        api = IssueApi()
        with self.assertRaisesRegex(GitHubIssueOriginV3Error, "ISSUE_NUMBER_INVALID"):
            self.reader(api).observe(True)
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
