import json
import subprocess
import unittest
from unittest import mock

from review_broker.publication import GitHubPublisher, PublicationError
from review_broker.publisher_identity import ACTIONS_BOT_ID, ACTIONS_BOT_LOGIN


ACTIONS_ENVIRONMENT = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_API_URL": "https://api.github.com",
}


class PublisherIdentityTests(unittest.TestCase):
    def publisher(self, response):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

        return GitHubPublisher("sample/repo", runner=runner), calls

    def test_actions_identity_uses_public_bot_lookup_without_user_endpoint(self):
        publisher, calls = self.publisher({
            "login": ACTIONS_BOT_LOGIN,
            "id": ACTIONS_BOT_ID,
            "type": "Bot",
        })
        with mock.patch.dict("os.environ", ACTIONS_ENVIRONMENT, clear=True):
            self.assertEqual(
                publisher.identity(),
                {"login": ACTIONS_BOT_LOGIN, "id": ACTIONS_BOT_ID},
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][4], "users/github-actions%5Bbot%5D")
        self.assertNotEqual(calls[0][4], "user")

    def test_actions_identity_rejects_wrong_login_id_or_type(self):
        valid = {"login": ACTIONS_BOT_LOGIN, "id": ACTIONS_BOT_ID, "type": "Bot"}
        for field, value in (
            ("login", "someone-else[bot]"),
            ("id", ACTIONS_BOT_ID + 1),
            ("type", "User"),
        ):
            with self.subTest(field=field):
                publisher, _ = self.publisher({**valid, field: value})
                with mock.patch.dict("os.environ", ACTIONS_ENVIRONMENT, clear=True):
                    with self.assertRaisesRegex(PublicationError, "ACTIONS_ACTOR_INVALID"):
                        publisher.identity()

    def test_actions_identity_rejects_non_github_dot_com_context(self):
        publisher, calls = self.publisher({})
        environment = {**ACTIONS_ENVIRONMENT, "GITHUB_SERVER_URL": "https://example.invalid"}
        with mock.patch.dict("os.environ", environment, clear=True):
            with self.assertRaisesRegex(PublicationError, "ACTIONS_CONTEXT_UNSUPPORTED"):
                publisher.identity()
        self.assertEqual(calls, [])

    def test_user_token_identity_path_remains_supported(self):
        publisher, calls = self.publisher({"login": "operator", "id": 17, "type": "User"})
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(publisher.identity(), {"login": "operator", "id": 17})
        self.assertEqual(calls[0][4], "user")


if __name__ == "__main__":
    unittest.main()
