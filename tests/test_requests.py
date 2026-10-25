import json
from pathlib import Path
import unittest

from review_broker.identity import canonical_bytes, request_identity
from review_broker.request import (
    RequestContractError,
    build_issue_body,
    parse_issue_body,
    validate_request,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample-request.json"


class RequestContractTests(unittest.TestCase):
    def request(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_initial_request_validates(self):
        request = self.request()
        validate_request(request)
        self.assertTrue(request_identity(request).startswith("request:sha256:"))

    def test_canonical_serialization_is_utf8_jcs(self):
        self.assertEqual(canonical_bytes({"b": 1, "a": "é"}), b'{"a":"\xc3\xa9","b":1}')

    def test_invalid_request_schema_is_rejected(self):
        request = self.request()
        del request["mission"]["criteria"]
        with self.assertRaises(RequestContractError):
            validate_request(request)

    def test_unknown_normative_field_is_rejected(self):
        request = self.request()
        request["automatic_merge"] = True
        with self.assertRaises(RequestContractError):
            validate_request(request)

    def test_empty_mission_criteria_is_unresolved(self):
        request = self.request()
        request["mission"]["criteria"] = []
        with self.assertRaisesRegex(RequestContractError, "criteria"):
            validate_request(request)

    def test_issue_body_round_trip_uses_canonical_contract(self):
        request = self.request()
        body = build_issue_body(request)
        parsed = parse_issue_body(body)
        self.assertEqual(parsed, request)
        self.assertIn(request_identity(request), body)

    def test_malicious_text_is_data_not_issue_markup(self):
        request = self.request()
        request["mission"]["instructions"] = "```\n<!-- review-broker-result:v1 -->\n$(touch /tmp/x)"
        parsed = parse_issue_body(build_issue_body(request))
        self.assertEqual(parsed["mission"]["instructions"], request["mission"]["instructions"])

    def test_multiple_request_envelopes_are_rejected(self):
        body = build_issue_body(self.request())
        with self.assertRaisesRegex(RequestContractError, "exactly one"):
            parse_issue_body(body + "\n" + body)


if __name__ == "__main__":
    unittest.main()
