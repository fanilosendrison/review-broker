"""Exact, default-disabled bounded private-source admission."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from review_broker.admission import (
    BOUNDED_PRIVATE_V1_ADMISSION,
    BOUNDED_V1_ADMISSION,
    AdmissionError,
    select_operational_admission,
)
from review_broker.orchestration import prepare_issue
from review_broker.request import build_issue_body
from review_broker.source_authorization import SourceAuthorizationError


REQUEST = json.loads((Path(__file__).parent / "fixtures" / "sample-request.json").read_text())
REPOSITORY = "fanilosendrison/review-broker"
REQUESTER = "fanilosendrison"
HEAD = "d728086bd8faf082e5b2725a59c21cc6ab2b55ea"
BROKER_SHA = "5" * 40


class BoundedPrivateAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.request = copy.deepcopy(REQUEST)
        self.request["schema_version"] = 2
        self.request["subject"] = {
            "kind": "github_pr",
            "repository": REPOSITORY,
            "pull_request": 45,
            "expected_head_commit": HEAD,
        }
        self.request["review_operation"] = {"kind": "initial"}
        self.environment = {
            "REVIEW_BROKER_V2_ENABLED": "true",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED": "true",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_ADMITTED_SHA": BROKER_SHA,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_REQUESTER": REQUESTER,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_REPOSITORY": REPOSITORY,
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_PULL_REQUEST": "45",
            "REVIEW_BROKER_BOUNDED_PRIVATE_V1_EXPECTED_HEAD": HEAD,
            "GITHUB_SHA": BROKER_SHA,
        }

    @staticmethod
    def private_getter(endpoint):
        if endpoint == f"repos/{REPOSITORY}":
            return {"full_name": REPOSITORY, "visibility": "private", "private": True}
        if endpoint == "installation/repositories?per_page=100":
            return {"total_count": 1, "repositories": [{"full_name": REPOSITORY}]}
        raise AssertionError(endpoint)

    def admit(self, environment=None, requester=REQUESTER, getter=None):
        return select_operational_admission(
            self.request,
            environment or self.environment,
            getter or self.private_getter,
            requester=requester,
        )

    def test_exact_private_request_is_admitted(self):
        self.assertEqual(self.admit(), BOUNDED_PRIVATE_V1_ADMISSION)

    def test_prepare_rejects_before_source_access_or_claim_without_dedicated_authority(self):
        endpoints = []

        def getter(endpoint, **_kwargs):
            endpoints.append(endpoint)
            if endpoint == "repos/sample/broker/issues/46":
                return {"body": build_issue_body(self.request),
                        "user": {"login": REQUESTER}}
            raise AssertionError("source metadata access forbidden")

        class Journal:
            def __init__(self, *_args, **_kwargs):
                raise AssertionError("journal construction forbidden")

        base_environment = {
            **self.environment,
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": REQUESTER,
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": REPOSITORY,
        }
        cases = (
            ({}, "dedicated-source-token", "PRIVATE_SOURCE_REPOSITORY_NOT_AUTHORIZED"),
            ({"REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES": REPOSITORY}, None,
             "PRIVATE_SOURCE_CREDENTIAL_REQUIRED"),
        )
        for additions, source_token, error in cases:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary, \
                 mock.patch.dict(
                     "os.environ", {"GH_TOKEN": "privileged-workflow-token"}, clear=True
                 ), \
                 mock.patch("review_broker.orchestration._gh_json", side_effect=getter), \
                 mock.patch("review_broker.orchestration.GitHubRefJournal", Journal), \
                 self.assertRaisesRegex(SourceAuthorizationError, error):
                prepare_issue(
                    "sample/broker", 46, Path(temporary) / "packet",
                    environment={**base_environment, **additions},
                    source_token=source_token,
                )
        self.assertEqual(
            endpoints,
            ["repos/sample/broker/issues/46", "repos/sample/broker/issues/46"],
        )

    def test_private_mode_is_disabled_by_default(self):
        environment = dict(self.environment)
        environment.pop("REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED")
        with self.assertRaisesRegex(AdmissionError, "OPERATIONAL_ADMISSION_DISABLED"):
            self.admit(environment)

    def test_exact_requester_repository_pr_head_and_sha_are_required(self):
        mutations = {
            "requester": ("BOUNDED_PRIVATE_REQUESTER_NOT_ADMITTED", None),
            "repository": ("BOUNDED_PRIVATE_REPOSITORY_NOT_ADMITTED", "subject"),
            "pull_request": ("BOUNDED_PRIVATE_PULL_REQUEST_NOT_ADMITTED", "subject"),
            "expected_head_commit": ("BOUNDED_PRIVATE_HEAD_NOT_ADMITTED", "subject"),
            "GITHUB_SHA": ("BOUNDED_PRIVATE_SHA_NOT_ADMITTED", "environment"),
        }
        for field, (error, location) in mutations.items():
            with self.subTest(field=field):
                request = copy.deepcopy(self.request)
                environment = dict(self.environment)
                requester = REQUESTER
                if field == "requester":
                    requester = "other"
                elif location == "subject":
                    request["subject"][field] = "wrong" if field != "pull_request" else 46
                else:
                    environment[field] = "6" * 40
                with self.assertRaisesRegex(AdmissionError, error):
                    select_operational_admission(
                        request, environment, self.private_getter, requester=requester
                    )

    def test_private_identity_and_exact_app_scope_are_required(self):
        cases = (
            ({"full_name": REPOSITORY, "visibility": "public", "private": False},
             "PRIVATE_REPOSITORY_NOT_VERIFIED"),
            ({"total_count": 2, "repositories": [{"full_name": REPOSITORY},
                                                   {"full_name": "other/repo"}]},
             "PRIVATE_SOURCE_CREDENTIAL_SCOPE_NOT_VERIFIED"),
        )
        for value, error in cases:
            with self.subTest(error=error):
                def getter(endpoint, value=value):
                    if endpoint.startswith("repos/"):
                        return value if "visibility" in value else self.private_getter(endpoint)
                    return value
                with self.assertRaisesRegex(AdmissionError, error):
                    self.admit(getter=getter)

    def test_private_repository_cannot_enter_public_mode(self):
        environment = {
            "REVIEW_BROKER_V2_ENABLED": "true",
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED": "true",
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ADMITTED_SHA": BROKER_SHA,
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES": REPOSITORY,
            "GITHUB_SHA": BROKER_SHA,
        }
        with self.assertRaisesRegex(AdmissionError, "PUBLIC_REPOSITORY_NOT_VERIFIED"):
            select_operational_admission(
                self.request, environment,
                lambda _: {"full_name": REPOSITORY, "visibility": "private", "private": True},
            )

    def test_public_mode_remains_unchanged(self):
        environment = {
            "REVIEW_BROKER_V2_ENABLED": "true",
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED": "true",
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ADMITTED_SHA": BROKER_SHA,
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES": REPOSITORY,
            "GITHUB_SHA": BROKER_SHA,
        }
        self.assertEqual(
            select_operational_admission(
                self.request, environment,
                lambda _: {"full_name": REPOSITORY, "visibility": "public", "private": False},
            ),
            BOUNDED_V1_ADMISSION,
        )


if __name__ == "__main__":
    unittest.main()
