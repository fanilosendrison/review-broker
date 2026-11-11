"""Non-network concrete opener tests; redirects are returned, never followed."""
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request
import unittest

from review_broker.actions_artifact_http_v3 import GitHubActionsArtifactHttpV3


class Reply(BytesIO):
    code = 200
    headers = {}


class ArtifactHttpTests(unittest.TestCase):
    def test_authenticated_302_is_observed_then_fresh_storage_has_no_headers(self):
        calls, factories = [], []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                if request.full_url.startswith("https://api.github.com/"):
                    raise HTTPError(request.full_url, 302, "redirect", {
                        "Location": "https://fixture.blob.core.windows.net/raw"}, BytesIO(b""))
                return Reply(b"raw-exact")
        def factory(handler):
            factories.append(handler)
            self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://untrusted.invalid"))
            return Opener()
        guarded = []
        http = GitHubActionsArtifactHttpV3(before_effect=lambda: guarded.append(1), opener_factory=factory)
        request = Request("https://api.github.com/repos/fanilosendrison/review-broker/actions/artifacts/1/zip",
            headers={"Authorization": "Bearer fixture-control"})
        metadata = http.metadata(request, max_bytes=100)
        self.assertEqual(metadata.status, 302)
        raw = b"".join(http.storage(Request(metadata.headers["Location"]), max_bytes=100))
        self.assertEqual(raw, b"raw-exact")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(factories), 2)
        self.assertEqual(dict(calls[-1].header_items()), {})
        self.assertGreater(len(guarded), 1)

    def test_budget_and_storage_credential_refusal(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                return Reply(b"x" * 100)
        http = GitHubActionsArtifactHttpV3(before_effect=lambda: None,
            opener_factory=lambda handler: Opener())
        with self.assertRaises(ValueError):
            http.metadata(Request("https://api.github.com/repos/fanilosendrison/review-broker"), max_bytes=10)
        with self.assertRaises(ValueError):
            list(http.storage(Request("https://fixture.blob.core.windows.net/raw"), max_bytes=10))
        count = len(calls)
        with self.assertRaises(ValueError):
            list(http.storage(Request("https://fixture.blob.core.windows.net/raw",
                headers={"Authorization": "Bearer must-not-leave"}), max_bytes=100))
        self.assertEqual(len(calls), count)
