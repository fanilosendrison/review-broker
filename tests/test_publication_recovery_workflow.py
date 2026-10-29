from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/publication-recovery.yml")


class PublicationRecoveryWorkflowTests(unittest.TestCase):
    def test_workflow_is_default_branch_publication_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.repository.default_branch", text)
        self.assertIn("review-broker-single-reviewer", text)
        self.assertIn("internal-recover-publication", text)
        self.assertIn("inputs.issue_number == 28", text)
        self.assertNotIn("review-request.yml", text)
        self.assertNotIn("internal-reconcile", text)
        self.assertNotIn("internal-invoke", text)
        self.assertNotIn("codespace", text.lower())
        self.assertNotIn("REVIEW_BROKER_LOW_SENSITIVITY", text)

    def test_workflow_binds_original_durable_identities(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        expected = (
            "request:sha256:b7be8e246a6794135979b9e7818c96d8cab59bcfa9c5e7f219683aa316ea260f",
            "attempt:sha256:81b20128c1e1bb4c2263ab64e3ef70b51d5ba79deb40df5fb52ef73eaf7a5702",
            "packet:sha256:6d3066d097f493be0f4fe1545a5b02f07e77a2c25d089862323975c538545f8c",
            "sha256:6fe42b53aa31f7ed520396b2ba86c40f2f2c0fad1911b1c5d9457ad0c188ac39",
            "06da37a80c49cd33c6a50c7b6edd256395873a8c",
        )
        for identity in expected:
            self.assertIn(identity, text)
        self.assertIn("--artifact-id 12863912132", text)
        self.assertIn("result --request", text)


if __name__ == "__main__":
    unittest.main()
