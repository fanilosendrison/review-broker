"""Proposed disjoint v3 Git ref namespace vs ACTUAL legacy reconciliation.

This is an offline reference boundary. There is NO new v3 writer, no GitHub
ref creation or authenticated matching-refs mutation. GitHub's live
ruleset/permission behavior for a new prefix is still unqualified.
"""
from __future__ import annotations

from copy import deepcopy
import re
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptRecord
from review_broker.reconciliation import reconcile_repository

REQUEST_ID="request:sha256:"+"a"*64
OLD_PREFIX="refs/heads/review-claims/"
V3_PREFIX="refs/heads/review-claims-v3/"
BROKER="fanilosendrison/review-broker"


def v3_candidate_ref(request_id: str) -> str:
    if not isinstance(request_id,str) or not re.fullmatch(
        r"request:sha256:[0-9a-f]{64}", request_id
    ):
        raise ValueError("INVALID_V3_CLAIM_ID")
    return V3_PREFIX + request_id.split(":")[-1]


def belongs_to_old_ref_scan(ref: str) -> bool:
    # Old reconciliation asks GET .../matching-refs/heads/review-claims/.
    # The sibling v3 prefix is intentionally not a child of that prefix.
    return ref.startswith(OLD_PREFIX)


class FailingEffect:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise AssertionError("UNEXPECTED_PRODUCTION_SIDE_EFFECT:"+name)
        return fail


class LegacyV3NamespaceIsolationTests(unittest.TestCase):
    def test_n01_real_legacy_journal_ref_is_v1_v2_namespace(self):
        journal=GitHubRefJournal("sample/broker")
        self.assertEqual(journal._claim_ref(REQUEST_ID),OLD_PREFIX+"a"*64)

    def test_n02_v3_sibling_prefix_cannot_be_seen_in_old_prefix_scan(self):
        new=v3_candidate_ref(REQUEST_ID)
        self.assertEqual(new,V3_PREFIX+"a"*64)
        self.assertFalse(belongs_to_old_ref_scan(new))
        self.assertTrue(belongs_to_old_ref_scan(OLD_PREFIX+"a"*64))

    def test_n03_v3_ref_under_old_prefix_would_be_discovered_unsafe(self):
        # Explicit counterexample to "review-claims/v3/" naming.
        bad=OLD_PREFIX+"v3/"+"a"*64
        self.assertTrue(belongs_to_old_ref_scan(bad))
        self.assertFalse(belongs_to_old_ref_scan(v3_candidate_ref(REQUEST_ID)))

    def test_n04_old_reconciler_source_has_one_old_prefix_query(self):
        # Source-locked current v1/v2 implementation, not future v3.
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                "src/review_broker/reconciliation.py").read_text()
        self.assertIn("matching-refs/heads/review-claims/",source)
        self.assertNotIn("matching-refs/heads/review-claims-v3/",source)

    def test_n05_old_reconciler_skips_v3_issue_with_disjoint_ref_scan(self):
        # The actual reconcile_repository function runs with ALL I/O stubbed.
        body=("<!-- review-broker-request:v3 -->\n"
              +canonical_bytes({"schema_version":3,"references":[]}).decode()
              +"\n<!-- /review-broker-request:v3 -->\n")
        issue={"number":91,"user":{"login":"trusted"},"body":body}
        called=[]
        def get(endpoint):
            called.append(endpoint)
            if endpoint.startswith(f"repos/{BROKER}/issues?state=open&per_page=100&page="):
                return [issue]
            if endpoint.startswith(f"repos/{BROKER}/git/matching-refs/heads/review-claims/?per_page=100&page="):
                return []
            raise AssertionError("UNEXPECTED_GITHUB_READ:"+endpoint)
        result=reconcile_repository(
            BROKER,"fake-codespace",
            environment={
                "REVIEW_BROKER_AUTHORIZED_REQUESTERS":"trusted",
                "REVIEW_BROKER_AUTHORIZED_REPOSITORIES":"fanilosendrison/proto-scope",
                "REVIEW_BROKER_DEFAULT_BRANCH":"dev",
                "REVIEW_BROKER_SECURITY_QUALIFIED":"true",
                "REVIEW_BROKER_SECURITY_EVIDENCE_ID":"test",
            },
            get_json=get,
            journal=FailingEffect(),
            controller=FailingEffect(),
            dispatch=FailingEffect(),
        )
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["action"],"REJECTED_REQUEST")
        self.assertEqual(result[0]["outcome"],"BLOCKED")
        self.assertEqual(len(called),2)

    def test_n06_real_legacy_codec_would_silently_drop_v2_control_if_seen(self):
        from review_broker.queue import AttemptState
        from review_broker.identity import attempt_identity
        attempt=AttemptRecord(
            request_id=REQUEST_ID,
            attempt_id=attempt_identity(REQUEST_ID,1),
            state=AttemptState.REQUESTED,
            history=({"state":"REQUESTED","evidence_ids":[]},),
        )
        candidate=attempt.as_dict()
        candidate["schema_version"]=2
        candidate["pre_model_control"]={"schema_version":1,
             "generation":1,"disposition":"REFUSED_PERMANENT"}
        reloaded=AttemptRecord.from_dict(deepcopy(candidate)).as_dict()
        self.assertEqual(reloaded["schema_version"],1)
        self.assertNotIn("pre_model_control",reloaded)

    def test_n07_reconcile_old_valid_claim_ref_still_matches_old_scan(self):
        self.assertTrue(belongs_to_old_ref_scan(
            GitHubRefJournal("sample/broker")._claim_ref(REQUEST_ID)
        ))
        self.assertFalse(belongs_to_old_ref_scan(v3_candidate_ref(REQUEST_ID)))

    def test_n08_candidate_ref_rejects_invalid_or_noncanonical_identity(self):
        for invalid in ("request:sha256:"+"A"*64,
                        "request:sha256:short", "a"*64,
                        "request:sha256:"+"a"*64+"/", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    v3_candidate_ref(invalid)

    def test_n09_disjoint_claim_prefix_is_not_global_codespace_lock(self):
        # This test intentionally does not assert live rulesets, permissions,
        # credential revocation or physical Codespace exclusivity.
        self.assertNotEqual(OLD_PREFIX,V3_PREFIX)
        self.assertNotIn("Codespace",V3_PREFIX)
        self.assertFalse(belongs_to_old_ref_scan(v3_candidate_ref(REQUEST_ID)))


if __name__=="__main__":
    unittest.main()
