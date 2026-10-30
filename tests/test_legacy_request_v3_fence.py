"""Replay exact historical ReviewRequest parsers: v3 must fail before Codespace.

Source-bound to 18 observed Review request Actions runs, 8 unique executing
commits, and TWO exact historical request.py Git blobs. No GitHub network,
Codespace, tokens or live workflows are used in these tests.

Does not prove that old v1/v2 runs cannot access the same PHYSICAL Codespace
for their legitimate historical requests, nor block out-of-band controllers.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from review_broker.identity import canonical_bytes
from review_broker.request import RequestContractError, parse_issue_body, validate_request


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests/fixtures/pre_model_v3"
INVENTORY = json.loads((DIRECTORY / "legacy_review_request_run_inventory.v1.json").read_text())
FILES = {
    "v1_only": "legacy_request_v1.py",
    "v1_v2": "legacy_request_v1_v2.py",
}
MARKER_V3 = "<!-- review-broker-request:v3 -->"
END_V3 = "<!-- /review-broker-request:v3 -->"
CANDIDATE_V3 = {"schema_version": 3, "references": []}


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def load_legacy_parser(family: str):
    path = DIRECTORY / FILES[family]
    fullname = "review_broker._legacy_qualification_" + family
    spec = importlib.util.spec_from_file_location(fullname, path)
    if spec is None or spec.loader is None:
        raise AssertionError("LEGACY_PARSER_IMPORT_UNAVAILABLE")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def issue_body(request, version: int):
    return (f"<!-- review-broker-request:v{version} -->\n"
            + canonical_bytes(request).decode("utf-8")
            + f"\n<!-- /review-broker-request:v{version} -->\n")


class HistoricalReviewRequestV3FencingTests(unittest.TestCase):
    def test_h01_two_frozen_historical_parsers_exact_git_blob_bytes(self):
        expected = INVENTORY["parser_fixture_blobs"]
        self.assertEqual(set(expected), set(FILES))
        for family, name in FILES.items():
            with self.subTest(family=family):
                raw = (DIRECTORY / name).read_bytes()
                self.assertEqual(git_blob_sha(raw), expected[family])
                self.assertTrue(raw.endswith(b"\n"))

    def test_h02_exact_eight_historical_revisions_map_to_two_parser_families(self):
        versions = INVENTORY["source_variants"]
        self.assertEqual(len(versions), 8)
        self.assertEqual(len(set(r["executing_sha"] for r in versions)), 8)
        self.assertEqual({r["parser_family"] for r in versions}, set(FILES))
        for entry in versions:
            with self.subTest(executing_sha=entry["executing_sha"]):
                self.assertEqual(entry["parser_blob_sha"],
                                 INVENTORY["parser_fixture_blobs"][entry["parser_family"]])
                self.assertRegex(entry["workflow_blob_sha"], r"^[0-9a-f]{40}$")
                self.assertTrue(entry["prepared_before_codespace_start"])
                self.assertFalse(entry["v3_marker_present"])

    def test_h03_eighteen_observed_runs_all_accounted_in_source_snapshot(self):
        runs = INVENTORY["observed_request_runs"]
        self.assertEqual((len(runs), INVENTORY["observed_reviewrequest_runs"]), (18,18))
        self.assertEqual(INVENTORY["observed_reviewrequest_revision_count"],8)
        expected_sha = {r["executing_sha"] for r in INVENTORY["source_variants"]}
        self.assertEqual({r["executing_sha"] for r in runs}, expected_sha)
        self.assertEqual(len(set(r["run_id"] for r in runs)),len(runs))
        self.assertTrue(all(r["trigger"] in {"workflow_dispatch","issues"} for r in runs))
        self.assertTrue(all(r["status"] == "completed" for r in runs))
        # All were completed AT THE HISTORICAL SNAPSHOT DATE. This is not
        # proof of permanent disabling or exclusion from future re-runs.

    def test_h04_replayed_old_parser_rejects_v3_schema_version(self):
        for family in FILES:
            with self.subTest(family=family):
                legacy = load_legacy_parser(family)
                with self.assertRaises(legacy.RequestContractError):
                    legacy.validate_request(CANDIDATE_V3)

    def test_h05_replayed_old_parser_rejects_v3_issue_marker(self):
        body = issue_body(CANDIDATE_V3,3)
        self.assertIn(MARKER_V3,body)
        self.assertIn(END_V3,body)
        for family in FILES:
            with self.subTest(family=family):
                legacy = load_legacy_parser(family)
                with self.assertRaises(legacy.RequestContractError):
                    legacy.parse_issue_body(body)

    def test_h06_cannot_smuggle_v3_payload_under_historical_marker(self):
        for family in FILES:
            legacy = load_legacy_parser(family)
            versions = (1,) if family == "v1_only" else (1,2)
            for marker_version in versions:
                with self.subTest(family=family, marker=marker_version):
                    body = issue_body(CANDIDATE_V3, marker_version)
                    with self.assertRaises(legacy.RequestContractError):
                        legacy.parse_issue_body(body)

    def test_h07_current_production_parser_still_rejects_v3(self):
        with self.assertRaises(RequestContractError):
            validate_request(CANDIDATE_V3)
        with self.assertRaises(RequestContractError):
            parse_issue_body(issue_body(CANDIDATE_V3,3))

    def test_h08_request_v3_rejected_without_any_codespace_transport(self):
        # No caller controls a Codespace in these tests. A mock transport
        # must not be invoked because the parser throws first.
        for family in FILES:
            calls=[]
            def pretend_prepare():
                calls.append("CODESPACE_START")
            legacy = load_legacy_parser(family)
            with self.assertRaises(legacy.RequestContractError):
                legacy.parse_issue_body(issue_body(CANDIDATE_V3,3))
                pretend_prepare()
            self.assertEqual(calls,[])

    def test_h09_old_v1_v2_runs_can_still_be_physical_resource_actors(self):
        # A version-gate excludes old workers AS request-v3 worker A.
        # It does NOT disable a valid old v1/v2 review of B. The test
        # refuses to upgrade logical attribution to global resource lock.
        self.assertTrue(any(r["parser_family"]=="v1_only"
                            for r in INVENTORY["source_variants"]))
        self.assertTrue(any(r["parser_family"]=="v1_v2"
                            for r in INVENTORY["source_variants"]))
        self.assertNotIn("global_exclusive_codespace_owner",INVENTORY)
        self.assertNotIn("legacy_workflows_permanently_disabled",INVENTORY)


if __name__ == "__main__":
    unittest.main()
