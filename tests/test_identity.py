import json
from pathlib import Path
import unittest

from review_broker.admission import AdmissionError, resolve_request
from review_broker.identity import (
    artifact_identity,
    attempt_identity,
    mission_identity,
    policy_identity,
    request_identity,
    subject_identity,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample-request.json"


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.resolved = {
            "kind": "github_pr",
            "repository": "fanilosendrison/proto-scope",
            "pull_request": 57,
            "head_commit": "0" * 40,
            "base_commit": "1" * 40,
            "merge_base": "2" * 40,
        }

    def test_identity_domains_are_distinct(self):
        identities = {
            request_identity(self.request),
            mission_identity(self.request["mission"]),
            policy_identity(self.request["policy"]),
            subject_identity(self.resolved),
            attempt_identity(request_identity(self.request), 1),
            artifact_identity(b"evidence"),
        }
        self.assertEqual(len(identities), 6)

    def test_head_change_changes_subject_not_logical_request(self):
        logical = request_identity(self.request)
        first = subject_identity(self.resolved)
        self.resolved["head_commit"] = "3" * 40
        self.assertEqual(request_identity(self.request), logical)
        self.assertNotEqual(subject_identity(self.resolved), first)

    def test_attempt_ordinal_is_explicit(self):
        request_id = request_identity(self.request)
        self.assertNotEqual(attempt_identity(request_id, 1), attempt_identity(request_id, 2))

    def test_artifact_identity_is_over_exact_bytes(self):
        self.assertNotEqual(artifact_identity(b"x\r\n"), artifact_identity(b"x\n"))

    def test_incorrect_expected_pr_head_is_rejected(self):
        def get_json(endpoint):
            if "/pulls/" in endpoint:
                return {
                    "head": {"sha": "0" * 40},
                    "base": {"sha": "1" * 40, "repo": {"id": 7}},
                }
            return {"merge_base_commit": {"sha": "2" * 40}}

        with self.assertRaisesRegex(AdmissionError, "PR_HEAD_MISMATCH"):
            resolve_request(self.request, get_json, expected_head="f" * 40)


if __name__ == "__main__":
    unittest.main()
