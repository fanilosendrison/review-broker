"""Reconciler enforcement of bounded private-source authority."""
import json
from pathlib import Path
import threading
import unittest
from unittest import mock

from review_broker.queue import AttemptRecord, AttemptState
from review_broker.reconciliation import reconcile_repository
from review_broker.request import build_issue_body


FIXTURE = Path(__file__).parent / "fixtures" / "sample-request.json"
REPOSITORY = "fanilosendrison/review-broker"
REQUESTER = "fanilosendrison"
HEAD = "d728086bd8faf082e5b2725a59c21cc6ab2b55ea"
BROKER_SHA = "5" * 40


class CountingJournal:
    def __init__(self):
        self._lock = threading.Lock()
        self.claim_count = 0

    def claim(self, request_id, admission=None):
        with self._lock:
            self.claim_count += 1
            return AttemptRecord(
                request_id=request_id,
                attempt_id="attempt:sha256:" + "a" * 64,
                state=AttemptState.REQUESTED,
                admission=admission,
            )


class ShutdownController:
    name = "review-broker-safe"

    @staticmethod
    def state():
        return "Shutdown"


class ReconcilerPrivateAdmissionTests(unittest.TestCase):
    def setUp(self):
        request = json.loads(FIXTURE.read_text(encoding="utf-8"))
        request["schema_version"] = 2
        request["subject"] = {
            "kind": "github_pr",
            "repository": REPOSITORY,
            "pull_request": 45,
            "expected_head_commit": HEAD,
        }
        request["review_operation"] = {"kind": "initial"}
        self.issue = {
            "number": 46,
            "body": build_issue_body(request),
            "user": {"login": REQUESTER},
        }
        self.environment = {
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": REQUESTER,
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": REPOSITORY,
            "REVIEW_BROKER_DEFAULT_BRANCH": "dev",
            "REVIEW_BROKER_V2_ENABLED": "true",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED": "true",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_ADMITTED_SHA": BROKER_SHA,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_REQUESTER": REQUESTER,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_REPOSITORY": REPOSITORY,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_PULL_REQUEST": "45",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_EXPECTED_HEAD": HEAD,
            "GITHUB_SHA": BROKER_SHA,
        }

    def test_missing_allowlist_rejects_before_metadata_claim_or_dispatch(self):
        endpoints = []

        def getter(endpoint):
            endpoints.append(endpoint)
            if "/issues?" in endpoint:
                return [self.issue]
            if "/git/matching-refs/" in endpoint:
                return []
            raise AssertionError("private subject metadata access forbidden")

        journal = CountingJournal()
        dispatched = []
        with mock.patch.dict(
            "os.environ", {"GH_TOKEN": "privileged-workflow-token"}, clear=True
        ):
            decisions = reconcile_repository(
                "fanilosendrison/review-broker",
                ShutdownController.name,
                environment=self.environment,
                get_json=getter,
                journal=journal,
                controller=ShutdownController(),
                dispatch=lambda *args: dispatched.append(args),
                source_token="dedicated-source-token",
            )
        self.assertEqual(
            decisions[0]["action"], "PRIVATE_SOURCE_REPOSITORY_NOT_AUTHORIZED"
        )
        self.assertEqual(decisions[0]["outcome"], "BLOCKED")
        self.assertEqual(journal.claim_count, 0)
        self.assertEqual(dispatched, [])
        self.assertFalse(any(endpoint == f"repos/{REPOSITORY}" for endpoint in endpoints))

    def test_fully_authorized_private_request_is_discoverable(self):
        def getter(endpoint):
            if "/issues?" in endpoint:
                return [self.issue]
            if "/git/matching-refs/" in endpoint:
                return []
            if endpoint == f"repos/{REPOSITORY}":
                return {"full_name": REPOSITORY, "visibility": "private", "private": True}
            if endpoint == "installation/repositories?per_page=100":
                return {"total_count": 1, "repositories": [{"full_name": REPOSITORY}]}
            if endpoint.endswith("/pulls/45"):
                return {
                    "head": {"sha": HEAD},
                    "base": {"sha": "1" * 40, "repo": {"id": 7}},
                }
            if "/compare/" in endpoint:
                return {"merge_base_commit": {"sha": "2" * 40}}
            raise AssertionError(endpoint)

        journal = CountingJournal()
        dispatched = []
        decisions = reconcile_repository(
            "fanilosendrison/review-broker",
            ShutdownController.name,
            environment={
                **self.environment,
                "REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES": REPOSITORY,
            },
            get_json=getter,
            journal=journal,
            controller=ShutdownController(),
            dispatch=lambda *args: dispatched.append(args),
            source_token="dedicated-source-token",
        )
        self.assertEqual(journal.claim_count, 1)
        self.assertEqual(dispatched, [("fanilosendrison/review-broker", "dev", 46)])
        self.assertEqual(decisions[0]["action"], "DISPATCH_PRE_MODEL")


if __name__ == "__main__":
    unittest.main()
