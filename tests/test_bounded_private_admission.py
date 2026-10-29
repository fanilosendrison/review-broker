"""Exact, default-disabled bounded private-source admission."""
import copy
import json
import os
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
from review_broker.identity import attempt_identity
from review_broker.queue import AttemptRecord, AttemptState, transition_record
from review_broker.request import build_issue_body
from review_broker.source_authorization import (
    SourceAuthorizationError,
    require_private_source_environment,
)


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

    def test_private_source_environment_is_transient_and_ignores_ambient_git_auth(self):
        ambient = {
            "HOME": "/safe/home",
            "PATH": "/safe/bin",
            "GH_TOKEN": "ambient-publication-token",
            "GITHUB_TOKEN": "ambient-workflow-token",
            "GIT_CONFIG_GLOBAL": "/ambient/gitconfig",
            "GIT_CONFIG_COUNT": "99",
        }
        with mock.patch.dict("os.environ", ambient, clear=True):
            environment = require_private_source_environment(
                REPOSITORY, frozenset({REPOSITORY}), "synthetic-source-token"
            )
        self.assertEqual(environment, {
            "HOME": "/safe/home",
            "PATH": "/safe/bin",
            "GH_TOKEN": "synthetic-source-token",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
            "GIT_CONFIG_VALUE_1": "!gh auth git-credential",
        })
        self.assertNotIn("ambient", " ".join(environment.values()))
        self.assertNotIn("synthetic-source-token", " ".join(
            value for key, value in environment.items() if key != "GH_TOKEN"
        ))

    def test_private_clone_fetch_and_reader_share_dedicated_source_environment(self):
        source_token = "synthetic-source-token"
        source_environment = {
            "PATH": "/usr/bin",
            "GH_TOKEN": source_token,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
            "GIT_CONFIG_VALUE_1": "!gh auth git-credential",
        }
        environment = {
            **self.environment,
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": REQUESTER,
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": REPOSITORY,
            "REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES": REPOSITORY,
        }
        base = "1" * 40
        merge_base = "2" * 40
        commands = []
        reader_environments = []

        def getter(endpoint, **_kwargs):
            if endpoint == "repos/sample/broker/issues/46":
                return {"body": build_issue_body(self.request),
                        "user": {"login": REQUESTER}}
            if endpoint == f"repos/{REPOSITORY}":
                return {"full_name": REPOSITORY, "visibility": "private", "private": True}
            if endpoint == "installation/repositories?per_page=100":
                return {"total_count": 1, "repositories": [{"full_name": REPOSITORY}]}
            if endpoint == f"repos/{REPOSITORY}/pulls/45":
                return {"head": {"sha": HEAD},
                        "base": {"sha": base, "repo": {"id": 7}}}
            if "/compare/" in endpoint:
                return {"merge_base_commit": {"sha": merge_base}}
            if "/files?" in endpoint:
                return [{"filename": "proposal.md", "status": "added"}]
            if "/git/matching-refs/heads/review-claims/" in endpoint:
                return []
            raise AssertionError(endpoint)

        class Journal:
            def __init__(self, *_args, **_kwargs):
                self.record = None
            def claim(self, request_id, admission=None):
                self.record = AttemptRecord(
                    request_id, attempt_identity(request_id, 1),
                    AttemptState.REQUESTED, admission=admission,
                )
                return self.record
            def transition(self, request_id, state, evidence_ids):
                self.record = transition_record(self.record, state, evidence_ids)
                return self.record

        class Reader:
            def __init__(self, _repository, environment=None):
                reader_environments.append(environment)
            @staticmethod
            def changed_paths(_merge_base, _head):
                return {"proposal.md"}
            @staticmethod
            def read(_source):
                return object()
            @staticmethod
            def diff(_merge_base, _head):
                return b"diff"

        def transport(command, **kwargs):
            commands.append((command, kwargs.get("env")))
            return mock.Mock(returncode=0)

        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True), \
             mock.patch("review_broker.orchestration._gh_json", side_effect=getter), \
             mock.patch("review_broker.orchestration.GitHubRefJournal", Journal), \
             mock.patch("review_broker.orchestration.GitSourceReader", Reader), \
             mock.patch("review_broker.orchestration.subprocess.run", side_effect=transport), \
             mock.patch("review_broker.orchestration.build_packet", return_value={
                 "source_manifest_id": "source-manifest:sha256:" + "3" * 64,
                 "packet_id": "packet:sha256:" + "4" * 64,
             }):
            output = Path(temporary) / "packet"
            output.mkdir()
            prepare_issue(
                "sample/broker", 46, output,
                environment=environment, source_token=source_token,
            )

        self.assertEqual(commands[0][0][3], f"https://github.com/{REPOSITORY}.git")
        self.assertTrue(all(command_environment == source_environment
                            for _, command_environment in commands))
        self.assertEqual(reader_environments, [source_environment])
        self.assertNotIn(source_token, " ".join(
            argument for command, _ in commands for argument in command
        ))

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
