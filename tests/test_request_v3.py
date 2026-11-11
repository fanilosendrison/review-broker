from __future__ import annotations

from copy import deepcopy
from importlib import resources
import json
import unittest

from jsonschema import Draft202012Validator

from review_broker.identity import request_identity, review_intent_identity
from review_broker.request import parse_issue_body
from review_broker.request_v3 import (
    RequestV3CandidateError, V3_END_MARKER, V3_MARKER, build_issue_envelope_v3,
    parse_issue_envelope_v3, request_identity_v3, validate_request_v3,
)
from review_broker.review_intent_v3 import review_intent_identity_v3
from tests.request_v3_test_support import HEAD, REPOSITORY, request


class RequestV3CandidateTests(unittest.TestCase):
    def test_exact_canonical_v3_and_empty_references(self) -> None:
        value = request()
        self.assertEqual(parse_issue_envelope_v3(build_issue_envelope_v3(value)), value)
        self.assertEqual(validate_request_v3(value)["references"], [])
        self.assertTrue(request_identity_v3(value).startswith("request:sha256:"))

    def test_missing_or_null_references_is_invalid(self) -> None:
        for value in ({k: v for k, v in request().items() if k != "references"},
                      request(references=None)):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RequestV3CandidateError, "SCHEMA_INVALID"):
                    validate_request_v3(value)

    def test_duplicate_ids_and_unsupported_kind_are_invalid(self) -> None:
        inline = {"id": "note", "required": False,
                  "source": {"kind": "inline", "text": "x"}}
        with self.assertRaisesRegex(RequestV3CandidateError, "ID_DUPLICATE"):
            validate_request_v3(request(references=[inline, inline]))
        invalid = {"id": "note", "required": False,
                   "source": {"kind": "web_url", "url": "https://example.invalid"}}
        with self.assertRaisesRegex(RequestV3CandidateError, "SCHEMA_INVALID"):
            validate_request_v3(request(references=[invalid]))

    def test_policy_unknown_fields_and_alias_types_are_invalid(self) -> None:
        cases = [
            request(policy={"profile": "code"}),
            request(extra=True),
            request(atomicity=1),
            request(schema_version=3.0),
            request(subject={**request()["subject"], "repository_id": True}),
            request(subject={**request()["subject"], "pull_request": 1.0}),
            request(references=[{"id": "note", "required": 1,
                                 "source": {"kind": "inline", "text": "x"}}]),
        ]
        for value in cases:
            with self.subTest(keys=value.keys()):
                with self.assertRaises(RequestV3CandidateError):
                    validate_request_v3(value)

    def test_schema_and_runtime_numeric_bounds_are_aligned(self) -> None:
        schema = json.loads(resources.files("review_broker.schemas").joinpath(
            "review-request-v3.candidate.schema.json"
        ).read_text())
        validator = Draft202012Validator(schema)
        oversized = request(subject={
            **request()["subject"], "repository_id": 9_007_199_254_740_992,
        })
        self.assertTrue(tuple(validator.iter_errors(oversized)))
        with self.assertRaises(RequestV3CandidateError):
            validate_request_v3(oversized)
        # JSON Schema integer is mathematical; runtime preserves the stricter JSON/Python type.
        with self.assertRaisesRegex(RequestV3CandidateError, "JSON_INTEGER_INVALID"):
            validate_request_v3(request(schema_version=3.0))

    def test_inline_utf8_byte_limit_is_enforced(self) -> None:
        reference = {"id": "note", "required": True,
                     "source": {"kind": "inline", "text": "é" * 1_000_001}}
        with self.assertRaisesRegex(RequestV3CandidateError, "BYTES_EXCEEDED"):
            validate_request_v3(request(references=[reference]))

    def test_safe_git_path_and_exact_selectors(self) -> None:
        valid = {"id": "contract", "required": True, "source": {
            "kind": "git_file", "repository": REPOSITORY,
            "path": "docs/contracts/review-request-v2.md", "commit": "b" * 40,
            "expected_sha256": "c" * 64,
        }}
        validate_request_v3(request(references=[valid]))
        for path in ("../secret", "/absolute", "docs//file", "docs/./file"):
            invalid = deepcopy(valid); invalid["source"]["path"] = path
            with self.assertRaises(RequestV3CandidateError):
                validate_request_v3(request(references=[invalid]))

    def test_rendered_packet_conservative_bound_rejects_all_line_amplification(self) -> None:
        for ending in ("\n", "\r", "\r\n"):
            reference = {"id": "note", "required": True,
                         "source": {"kind": "inline", "text": ending * 900_000}}
            with self.subTest(ending=repr(ending)):
                with self.assertRaisesRegex(RequestV3CandidateError, "PACKET_BOUND_EXCEEDED"):
                    validate_request_v3(request(references=[reference]))

    def test_noncanonical_mixed_duplicate_and_wrong_declared_id_fail(self) -> None:
        value = request()
        pretty = json.dumps(value, indent=2)
        with self.assertRaisesRegex(RequestV3CandidateError, "NONCANONICAL"):
            parse_issue_envelope_v3(f"{V3_MARKER}\n{pretty}\n{V3_END_MARKER}")
        with self.assertRaisesRegex(RequestV3CandidateError, "MIXED_VERSION"):
            parse_issue_envelope_v3(
                build_issue_envelope_v3(value) + "\n<!-- review-broker-request:v2 -->"
            )
        with self.assertRaisesRegex(RequestV3CandidateError, "EXACTLY_ONE"):
            parse_issue_envelope_v3(
                build_issue_envelope_v3(value) + "\n" + build_issue_envelope_v3(value)
            )
        with self.assertRaisesRegex(RequestV3CandidateError, "REQUEST_ID_MISMATCH"):
            parse_issue_envelope_v3(
                "Request-ID: `request:sha256:" + "0" * 64 + "`\n" +
                build_issue_envelope_v3(value)
            )
        declared = request_identity_v3(value)
        for malformed in ("Request-ID: `" + declared, "Request-ID: " + declared + "`"):
            with self.assertRaisesRegex(RequestV3CandidateError, "REQUEST_ID_INVALID"):
                parse_issue_envelope_v3(malformed + "\n" + build_issue_envelope_v3(value))
        with self.assertRaisesRegex(RequestV3CandidateError, "REQUEST_ID_INVALID"):
            parse_issue_envelope_v3(
                "Request-ID: " + declared + "junk\n" + build_issue_envelope_v3(value)
            )

    def test_unicode_line_separators_round_trip_and_blank_padding_is_rejected(self) -> None:
        for separator in ("\u0085", "\u2028", "\u2029"):
            value = request(mission={**request()["mission"], "instructions": separator})
            self.assertEqual(parse_issue_envelope_v3(build_issue_envelope_v3(value)), value)
        envelope = build_issue_envelope_v3(request())
        padded = envelope.replace(V3_MARKER + "\n", V3_MARKER + "\n\n", 1)
        with self.assertRaises(RequestV3CandidateError):
            parse_issue_envelope_v3(padded)

    def test_cr_and_mixed_physical_line_smuggling_is_rejected(self) -> None:
        envelope = build_issue_envelope_v3(request())
        declared = request_identity_v3(request())
        for prefix in (
            "Request-ID: " + declared + "\rRequest-ID: request:sha256:" + "0" * 64 + "\r",
            "<!-- review-broker-request:v2 -->\r",
            "> <!-- review-broker-request:v2 -->\r\n",
            "Review-Intent-ID: `review-intent:sha256:" + "0" * 64 + "`\n",
        ):
            with self.subTest(prefix=prefix[:20]):
                with self.assertRaises(RequestV3CandidateError):
                    parse_issue_envelope_v3(prefix + envelope)

    def test_marker_literals_inside_canonical_strings_round_trip(self) -> None:
        value = request(
            mission={**request()["mission"], "instructions": V3_MARKER},
            references=[{"id": "note", "required": False,
                         "source": {"kind": "inline", "text": "<!-- review-broker-request:v2 -->"}}],
        )
        self.assertEqual(parse_issue_envelope_v3(build_issue_envelope_v3(value)), value)

    def test_exact_request_and_logical_intent_domains_diverge_as_specified(self) -> None:
        inline = {"id": "note", "required": False,
                  "source": {"kind": "inline", "text": "one"}}
        first = request(references=[inline])
        second = deepcopy(first); second["references"][0]["source"]["text"] = "two"
        self.assertNotEqual(request_identity_v3(first), request_identity_v3(second))
        self.assertEqual(review_intent_identity_v3(first), review_intent_identity_v3(second))

        repository_changed = deepcopy(first)
        repository_changed["subject"]["repository_id"] += 1
        self.assertNotEqual(request_identity_v3(first), request_identity_v3(repository_changed))
        self.assertNotEqual(review_intent_identity_v3(first), review_intent_identity_v3(repository_changed))

        atomic = deepcopy(first); atomic["atomicity"] = True
        self.assertNotEqual(request_identity_v3(first), request_identity_v3(atomic))
        self.assertNotEqual(review_intent_identity_v3(first), review_intent_identity_v3(atomic))

    def test_git_commit_and_hash_change_exact_request_but_not_intent(self) -> None:
        reference = {"id": "contract", "required": True, "source": {
            "kind": "git_file", "repository": REPOSITORY, "path": "docs/a.md",
            "commit": "b" * 40, "expected_sha256": "c" * 64,
        }}
        first = request(references=[reference])
        second = deepcopy(first)
        second["references"][0]["source"]["commit"] = "d" * 40
        second["references"][0]["source"]["expected_sha256"] = "e" * 64
        self.assertNotEqual(request_identity_v3(first), request_identity_v3(second))
        self.assertEqual(review_intent_identity_v3(first), review_intent_identity_v3(second))

    def test_head_and_operation_affect_request_but_not_intent(self) -> None:
        first = request()
        changed = deepcopy(first)
        changed["subject"]["expected_head_commit"] = "f" * 40
        changed["review_operation"] = {
            "kind": "changed_head", "previous_request_id": request_identity_v3(first),
        }
        self.assertNotEqual(request_identity_v3(first), request_identity_v3(changed))
        self.assertEqual(review_intent_identity_v3(first), review_intent_identity_v3(changed))

    def test_v1_v2_identity_and_markers_remain_unchanged(self) -> None:
        v2 = {
            "schema_version": 2,
            "subject": {"kind": "github_pr", "repository": REPOSITORY,
                        "pull_request": 1, "expected_head_commit": HEAD},
            "mission": request()["mission"],
            "policy": {"profile": "code", "version": 1},
            "reviewer": request()["reviewer"],
            "review_operation": {"kind": "initial"},
        }
        expected_canonical = ('{"mission":{"criteria":["Find gaps."],"id":'
                              '"reference-contract-review","instructions":'
                              '"Use only packet-bound sources.","objective":'
                              '"Falsify the candidate."},"policy":{"profile":"code",'
                              '"version":1},"review_operation":{"kind":"initial"},'
                              '"reviewer":{"backend":"codex-cli","model":"gpt-5.6-sol",'
                              '"reasoning_effort":"xhigh"},"schema_version":2,"subject":'
                              '{"expected_head_commit":"' + HEAD + '","kind":"github_pr",'
                              '"pull_request":1,"repository":"' + REPOSITORY + '"}}')
        expected_request_id = "request:sha256:4ad71ad07c5f4c0acbc6628f2c0a8ea98d6a43da97eb933d668ed0594e3f5196"
        expected_intent_id = "review-intent:sha256:362aa2d4c5b12927cd2e26c7706e8f564ed9749c352345adb3d281fa79bd3fdf"
        parsed = parse_issue_body(
            "<!-- review-broker-request:v2 -->\n" +
            expected_canonical +
            "\n<!-- /review-broker-request:v2 -->"
        )
        self.assertEqual(parsed, v2)
        self.assertEqual(request_identity(v2), expected_request_id)
        self.assertEqual(review_intent_identity(v2), expected_intent_id)


if __name__ == "__main__":
    unittest.main()
