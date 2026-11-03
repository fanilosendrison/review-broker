"""Fail-closed qualification of bounded low-sensitivity v1 admission."""
import hashlib
import json
from pathlib import Path
import unittest

from review_broker.admission import (
    BOUNDED_V1_ADMISSION,
    COMPREHENSIVE_ADMISSION,
    AdmissionError,
    AuthorizationPolicy,
    authorize,
    select_operational_admission,
)
from review_broker.reconciliation import reconcile_repository
from review_broker.request import build_issue_body


ROOT = Path(__file__).parents[1]
REQUEST = json.loads((Path(__file__).parent / "fixtures" / "sample-request.json").read_text())
SHA = "6e3236b0e078d1cbbe363662054d4757880131da"
REPOSITORY = REQUEST["subject"]["repository"]


class CountingJournal:
    claim_count = 0

    def claim(self, _request_id):
        self.claim_count += 1
        raise AssertionError("claim forbidden")


class CountingController:
    name = "review-broker-safe"
    state_count = 0

    def state(self):
        self.state_count += 1
        raise AssertionError("Codespace observation forbidden")


class BoundedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
            "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": REPOSITORY,
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED": "true",
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_ADMITTED_SHA": SHA,
            "REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES": REPOSITORY,
            "GITHUB_SHA": SHA,
        }
        self.policy = AuthorizationPolicy(frozenset({"trusted"}), frozenset({REPOSITORY}))

    @staticmethod
    def public_repository(_endpoint):
        return {"full_name": REPOSITORY, "visibility": "public", "private": False}

    def admit(self, environment=None, *, actor="trusted", policy=None, getter=None):
        authorize(actor, REQUEST, policy or self.policy)
        return select_operational_admission(
            REQUEST, environment or self.environment, getter or self.public_repository,
        )

    def test_eligible_public_repository_is_boundedly_admitted(self):
        self.assertEqual(self.admit(), BOUNDED_V1_ADMISSION)

    def test_default_and_missing_enablement_are_disabled(self):
        for value in (None, "", "True", "false"):
            with self.subTest(value=value):
                environment = dict(self.environment)
                if value is None:
                    environment.pop("REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED")
                else:
                    environment["REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED"] = value
                with self.assertRaisesRegex(AdmissionError, "OPERATIONAL_ADMISSION_DISABLED"):
                    self.admit(environment)

    def test_missing_or_incorrect_admitted_sha_is_rejected(self):
        for admitted, executing in (("", SHA), ("f" * 40, SHA), (SHA, ""), (SHA, "invalid")):
            with self.subTest(admitted=admitted, executing=executing):
                environment = dict(self.environment)
                environment["REVIEW_BROKER_LOW_SENSITIVITY_V1_ADMITTED_SHA"] = admitted
                environment["GITHUB_SHA"] = executing
                with self.assertRaisesRegex(AdmissionError, "LOW_SENSITIVITY_SHA_NOT_ADMITTED"):
                    self.admit(environment)

    def test_empty_or_absent_bounded_repository_allowlist_is_rejected(self):
        for value in ("", "other/repository"):
            environment = dict(self.environment)
            environment["REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES"] = value
            with self.assertRaisesRegex(AdmissionError, "LOW_SENSITIVITY_REPOSITORY_NOT_ADMITTED"):
                self.admit(environment)

    def test_existing_requester_and_repository_authorization_remain_mandatory(self):
        with self.assertRaisesRegex(AdmissionError, "REQUESTER_UNAUTHORIZED"):
            self.admit(actor="untrusted")
        with self.assertRaisesRegex(AdmissionError, "REPOSITORY_UNAUTHORIZED"):
            self.admit(policy=AuthorizationPolicy(frozenset({"trusted"}), frozenset()))

    def test_public_repository_absent_from_bounded_allowlist_is_rejected(self):
        environment = dict(self.environment)
        environment["REVIEW_BROKER_LOW_SENSITIVITY_V1_REPOSITORIES"] = "public/other"
        with self.assertRaisesRegex(AdmissionError, "LOW_SENSITIVITY_REPOSITORY_NOT_ADMITTED"):
            self.admit(environment)

    def test_private_repository_is_rejected_despite_general_authorization(self):
        private = {"full_name": REPOSITORY, "visibility": "private", "private": True}
        with self.assertRaisesRegex(AdmissionError, "PUBLIC_REPOSITORY_NOT_VERIFIED"):
            self.admit(getter=lambda _endpoint: private)

    def test_unavailable_or_ambiguous_visibility_fails_closed(self):
        values = ({}, {"full_name": REPOSITORY, "visibility": "public"},
                  {"full_name": REPOSITORY, "visibility": "internal", "private": False},
                  {"full_name": "other/repo", "visibility": "public", "private": False})
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(
                AdmissionError, "PUBLIC_REPOSITORY_NOT_VERIFIED"
            ):
                self.admit(getter=lambda _endpoint, value=value: value)

    def test_comprehensive_security_path_is_independent_and_preserved(self):
        environment = {
            "REVIEW_BROKER_SECURITY_QUALIFIED": "true",
            "REVIEW_BROKER_SECURITY_EVIDENCE_ID": "evidence:qualified",
        }
        self.assertEqual(self.admit(environment, getter=lambda _: self.fail("visibility")),
                         COMPREHENSIVE_ADMISSION)
        environment["REVIEW_BROKER_SECURITY_EVIDENCE_ID"] = ""
        with self.assertRaisesRegex(AdmissionError, "SECURITY_EVIDENCE_MISSING"):
            self.admit(environment)

    def test_reconciler_rejects_before_claim_or_codespace_observation(self):
        issue = {"number": 42, "body": build_issue_body(REQUEST),
                 "user": {"login": "trusted"}}
        def getter(endpoint):
            if "/issues?" in endpoint:
                return [issue]
            if "/matching-refs/" in endpoint:
                return []
            raise AssertionError(endpoint)
        journal = CountingJournal(); controller = CountingController()
        decisions = reconcile_repository(
            "fanilosendrison/review-broker", controller.name,
            environment={
                "REVIEW_BROKER_AUTHORIZED_REQUESTERS": "trusted",
                "REVIEW_BROKER_AUTHORIZED_REPOSITORIES": REPOSITORY,
            }, get_json=getter, journal=journal, controller=controller,
            dispatch=lambda *_: self.fail("dispatch forbidden"),
        )
        self.assertEqual(decisions[0]["action"], "REJECTED_REQUEST")
        self.assertEqual(journal.claim_count, 0)
        self.assertEqual(controller.state_count, 0)

    def test_public_contracts_and_reviewer_policy_are_unchanged(self):
        for name in ("review-request-v1.schema.json", "review-result-v1.schema.json"):
            self.assertEqual(
                json.loads((ROOT / "schemas" / name).read_text()),
                json.loads((ROOT / "src/review_broker/schemas" / name).read_text()),
            )
        wire = ROOT / "src/review_broker/schemas/reviewer-findings-v1.codex-wire.schema.json"
        self.assertEqual(hashlib.sha256(wire.read_bytes()).hexdigest(),
                         "ca4449b3b0e4431938d3d1ab0226c0031e8596fc4a21ca3106c6ae0d44f124ab")
        from review_broker import codex as adapter, codex_policy
        self.assertIs(adapter.CodexPolicy, codex_policy.CodexPolicy)
        self.assertIs(adapter.build_command, codex_policy.build_command)
        codex = (ROOT / "src/review_broker/codex_policy.py").read_text()
        self.assertIn('"gpt-5.6-sol"', codex)
        self.assertIn('reasoning_effort: str = "xhigh"', codex)
        self.assertIn("features.shell_tool=false", codex)

    def test_historical_rb05_statuses_remain_distinct(self):
        specification = (ROOT / "docs/specification/review-broker-spec.md").read_text()
        assessment = (ROOT / "docs/qualification/security-assessment.md").read_text()
        for value in (
            "RB_PILOT_05_FUNCTIONAL=PASS",
            "RB_PILOT_05_ORIGINAL_ACCEPTANCE=FAIL",
            "RB_PILOT_05_SUPPLEMENTAL_RECOVERY=PASS",
            "PRODUCTION_SECURITY_QUALIFIED=NO",
        ):
            self.assertIn(value, specification)
        for reference in ("6480361923", "6480916478", "6481195784", "6481554872"):
            self.assertIn(reference, specification + assessment)
        self.assertNotIn("RB_PILOT_05_ACCEPTANCE=PASS", specification + assessment)

    def test_workflow_and_source_place_admission_before_side_effects(self):
        workflow = (ROOT / ".github/workflows/review-request.yml").read_text()
        source = (ROOT / "src/review_broker/orchestration.py").read_text()
        self.assertIn("REVIEW_BROKER_LOW_SENSITIVITY_V1_ENABLED", workflow)
        self.assertIn("REVIEW_BROKER_SECURITY_QUALIFIED", workflow)
        self.assertLess(source.index("select_operational_admission("),
                        source.index("journal.claim("))
        self.assertLess(workflow.index("internal-prepare"),
                        workflow.index("Start and observe dedicated Codespace"))
        self.assertNotIn("pull_request_review", workflow)
        self.assertNotIn("merge", workflow.lower())


if __name__ == "__main__":
    unittest.main()
