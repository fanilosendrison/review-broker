from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest
from urllib.request import Request

from review_broker.github_actions_identity_v3 import (
    GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3,
    GitHubActionsIdentityV3Error, GitHubActionsRuntimeClaimV3,
)
from review_broker.github_http_live_v3 import HttpResponseV3


REPOSITORY = "fanilosendrison/review-broker"
REPOSITORY_ID = 1433701208
RUN_ID = 1234
RUN_ATTEMPT = 2
HEAD_SHA = "a" * 40
MERGE_SHA = "b" * 40
WORKFLOW = ".github/workflows/v3-authority-observation-qualification.yml"
SOURCE_REF = "refs/heads/feat/v3-observation"
WORKFLOW_REF = f"{REPOSITORY}/{WORKFLOW}@{SOURCE_REF}"
WORKFLOW_SHA = "f" * 40
NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


class Boundary:
    def __init__(self, claim: GitHubActionsRuntimeClaimV3, trusted: bool = True):
        self.claim = claim
        self.trusted = trusted

    def authenticates(self, claim: GitHubActionsRuntimeClaimV3) -> bool:
        return self.trusted and claim == self.claim


class ActionsApi:
    def __init__(self) -> None:
        self.run_attempt = RUN_ATTEMPT
        self.repository_id = REPOSITORY_ID
        self.path = WORKFLOW
        self.workflow_id = 77
        self.event = "pull_request"
        self.head_sha = HEAD_SHA
        self.pr_head = HEAD_SHA
        self.actor_id = 10
        self.triggering_actor_id = 11
        self.jobs = [{"id": 501, "name": "qualify"}]
        self.total_count = 1
        self.incomplete = False
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: Request) -> HttpResponseV3:
        self.calls.append((request.get_method(), request.full_url))
        assert request.get_method() == "GET"
        assert request.headers["Authorization"] == "Bearer token"
        if request.full_url.endswith(f"/actions/runs/{RUN_ID}"):
            return self.response({
                "id": RUN_ID,
                "run_attempt": self.run_attempt,
                "workflow_id": self.workflow_id,
                "path": self.path,
                "event": self.event,
                "head_sha": self.head_sha,
                "repository": {"id": self.repository_id, "full_name": REPOSITORY},
                "head_repository": {"id": self.repository_id, "full_name": REPOSITORY},
                "actor": {"id": self.actor_id, "login": "actor"},
                "triggering_actor": {"id": self.triggering_actor_id, "login": "trigger"},
                "pull_requests": [{"head": {"sha": self.pr_head, "ref": SOURCE_REF.removeprefix("refs/heads/")}}],
            })
        headers = {}
        if self.incomplete:
            headers = {"Link": (
                f'<https://api.github.com/repos/{REPOSITORY}/actions/runs/{RUN_ID}/'
                f'attempts/{RUN_ATTEMPT}/jobs?per_page=100&page=3>; rel="next"'
            )}
        return self.response({"total_count": self.total_count, "jobs": self.jobs}, headers)

    @staticmethod
    def response(value: object, headers: dict[str, str] | None = None) -> HttpResponseV3:
        return HttpResponseV3(200, json.dumps(value).encode(), headers or {})


def claim() -> GitHubActionsRuntimeClaimV3:
    return GitHubActionsRuntimeClaimV3(
        REPOSITORY, REPOSITORY_ID, RUN_ID, RUN_ATTEMPT, "qualify",
        WORKFLOW_REF, WORKFLOW_SHA, HEAD_SHA, "pull_request", HEAD_SHA, MERGE_SHA,
    )


def expectation() -> GitHubActionsExpectationV3:
    return GitHubActionsExpectationV3(
        REPOSITORY, REPOSITORY_ID, 77, WORKFLOW, WORKFLOW_REF, SOURCE_REF,
        "pull_request", WORKFLOW_SHA, HEAD_SHA, "qualify", "qualify",
    )


class GitHubActionsIdentityV3Tests(unittest.TestCase):
    def reader(self, api: ActionsApi) -> GitHubActionsIdentityReaderV3:
        return GitHubActionsIdentityReaderV3(
            "token", REPOSITORY, REPOSITORY_ID, executor=api, clock=lambda: NOW
        )

    def observe(self, api: ActionsApi, value: GitHubActionsRuntimeClaimV3 | None = None):
        runtime = value or claim()
        return self.reader(api).observe(runtime, expectation(), Boundary(runtime))

    def test_run_job_actor_and_pr_identities_are_preserved_separately(self) -> None:
        api = ActionsApi()
        observed = self.observe(api)
        self.assertEqual(observed.run_id, RUN_ID)
        self.assertEqual(observed.job_id, 501)
        self.assertEqual(observed.job_name, "qualify")
        self.assertEqual(observed.runtime_job_key, "qualify")
        self.assertEqual(observed.actor_id, 10)
        self.assertEqual(observed.triggering_actor_id, 11)
        self.assertEqual(observed.run_head_sha, HEAD_SHA)
        self.assertEqual(observed.pull_request_head_sha, HEAD_SHA)
        self.assertEqual(observed.synthetic_merge_sha, MERGE_SHA)
        self.assertEqual(observed.workflow_definition_sha, WORKFLOW_SHA)
        self.assertNotEqual(observed.workflow_definition_sha, observed.executing_source_sha)
        self.assertNotEqual(observed.synthetic_merge_sha, observed.executing_source_sha)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_runtime_claim_requires_designated_boundary(self) -> None:
        runtime, api = claim(), ActionsApi()
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "BOUNDARY_REQUIRED"):
            self.reader(api).observe(runtime, expectation(), Boundary(runtime, False))
        self.assertEqual(api.calls, [])

    def test_spoofed_different_run_claim_is_rejected_before_api(self) -> None:
        trusted, spoofed, api = claim(), replace(claim(), run_id=9999), ActionsApi()
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "BOUNDARY_REQUIRED"):
            self.reader(api).observe(spoofed, expectation(), Boundary(trusted))
        self.assertEqual(api.calls, [])

    def test_run_attempt_and_repository_mismatch_fail_closed(self) -> None:
        for attribute, value, marker in (
            ("run_attempt", 3, "RUN_ATTEMPT_MISMATCH"),
            ("repository_id", 1, "REPOSITORY_MISMATCH"),
        ):
            with self.subTest(attribute=attribute):
                api = ActionsApi()
                setattr(api, attribute, value)
                with self.assertRaisesRegex(GitHubActionsIdentityV3Error, marker):
                    self.observe(api)

    def test_boolean_api_and_expected_identifiers_are_rejected(self) -> None:
        api = ActionsApi()
        api.run_attempt = True
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "RUN_ATTEMPT_MISMATCH"):
            self.observe(api)
        with self.assertRaisesRegex(ValueError, "EXPECTATION_INVALID"):
            replace(expectation(), workflow_id=True)
        with self.assertRaisesRegex(ValueError, "RUNTIME_CLAIM_INVALID"):
            replace(claim(), run_id=True)

    def test_workflow_path_and_executable_sha_mismatch_fail_closed(self) -> None:
        api = ActionsApi()
        api.path = ".github/workflows/other.yml"
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "WORKFLOW_PATH_MISMATCH"):
            self.observe(api)
        runtime = replace(claim(), workflow_sha="c" * 40)
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "WORKFLOW_SHA_MISMATCH"):
            self.reader(ActionsApi()).observe(runtime, expectation(), Boundary(runtime))
        runtime = replace(claim(), checked_out_source_sha="c" * 40)
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "EXECUTABLE_SHA_MISMATCH"):
            self.reader(ActionsApi()).observe(runtime, expectation(), Boundary(runtime))

    def test_runtime_job_key_must_match_expected_api_job_mapping(self) -> None:
        runtime = replace(claim(), job_key="other")
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "RUNTIME_CLAIM_MISMATCH"):
            self.reader(ActionsApi()).observe(runtime, expectation(), Boundary(runtime))

    def test_pull_request_head_is_not_synthetic_merge_sha(self) -> None:
        api = ActionsApi()
        api.pr_head = "c" * 40
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "PR_HEAD_UNVERIFIED"):
            self.observe(api)

    def test_rerun_triggering_actor_change_is_observed_not_collapsed(self) -> None:
        first_api, second_api = ActionsApi(), ActionsApi()
        second_api.triggering_actor_id = 99
        first = self.observe(first_api)
        second = self.observe(second_api)
        self.assertNotEqual(first.triggering_actor_id, second.triggering_actor_id)
        self.assertNotEqual(first.evidence_id, second.evidence_id)

    def test_incomplete_job_pagination_fails_closed(self) -> None:
        api = ActionsApi()
        api.total_count = 2
        api.incomplete = True
        with self.assertRaisesRegex(GitHubActionsIdentityV3Error, "PAGINATION_INCOMPLETE"):
            self.observe(api)

    def test_duplicate_or_ambiguous_job_identity_fails_closed(self) -> None:
        for jobs, marker in (
            ([{"id": 501, "name": "qualify"}, {"id": 502, "name": "qualify"}],
             "JOB_IDENTITY_AMBIGUOUS"),
            ([{"id": 501, "name": "qualify"}, {"id": 501, "name": "other"}],
             "JOB_ID_DUPLICATE"),
            ([{"id": 501, "name": "qualify"}, {"id": True, "name": "other"}],
             "JOB_ID_INVALID"),
        ):
            with self.subTest(marker=marker):
                api = ActionsApi()
                api.jobs, api.total_count = jobs, len(jobs)
                with self.assertRaisesRegex(GitHubActionsIdentityV3Error, marker):
                    self.observe(api)

    def test_unsupported_event_context_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "RUNTIME_CLAIM_INVALID"):
            replace(
                claim(), event_name="workflow_dispatch",
                pull_request_head_sha=None, synthetic_merge_sha=None,
            )


if __name__ == "__main__":
    unittest.main()
