from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveTransportIsolationTests(unittest.TestCase):
    def test_v1_v2_modules_do_not_import_live_v3_transport(self):
        forbidden = "github_transport_live_v3"
        allowed = {ROOT / "src/review_broker/github_transport_live_v3.py"}
        for path in (ROOT / "src/review_broker").glob("*.py"):
            if path not in allowed:
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"), str(path))

    def test_production_workflows_do_not_reference_live_v3_transport(self):
        for name in ("review-request.yml", "review-reconciler.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn("github_transport_live_v3", text)
            self.assertNotIn("review-claims-v3", text)

    def test_qualification_workflow_is_pull_request_only_and_secret_free(self):
        text = (ROOT / ".github/workflows/v3-github-transport-qualification.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pull_request:", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets.", text)
        self.assertIn("QUALIFICATION_TOKEN: ${{ github.token }}", text)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"', text)
        self.assertIn("EVENT_MERGE_SHA: ${{ github.sha }}", text)
        self.assertIn("contents: write", text)
        self.assertIn("github.triggering_actor == 'fanilosendrison'", text)
        self.assertIn("class RejectRedirects", text)
        self.assertIn("consecutive_matches == 2", text)
        self.assertIn('error.startswith("GRAPHQL_TYPED_")', text)
        self.assertNotIn("reviewctl", text)


if __name__ == "__main__":
    unittest.main()
