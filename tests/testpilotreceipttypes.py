"""Exact JSON integer-type regressions for synthetic-pilot receipts."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from review_broker.pilot_controller_state import arm_controller_attempt
from review_broker.pilot_private_retention import DIAGNOSTIC_LIMITS, retain_private_pilot_artifacts
from tests.testpilotretention import (
    ARMED_UTC, ATTEMPT, FakeSource, PILOT, REQUEST, SOURCE, mutate_json, valid_receipts,
)


class PilotReceiptIntegerTypeTests(unittest.TestCase):
    def retain(self, temporary: str, values: dict[str, bytes]):
        root = Path(temporary).resolve() / "pilots"
        arm_controller_attempt(
            pilot_id=PILOT, request_id=REQUEST, attempt_id=ATTEMPT,
            source_sha=SOURCE, _state_root=root, _created_utc=ARMED_UTC,
        )
        source = FakeSource(values)
        manifest = retain_private_pilot_artifacts(
            pilot_id=PILOT, request_id=REQUEST, attempt_id=ATTEMPT,
            source_sha=SOURCE, source=source, _state_root=root,
            _retained_at="2026-10-28T00:01:00+00:00",
        )
        self.assertEqual(manifest["receipt_set_validation"], "RECEIPT_SET_INVALID")
        self.assertNotEqual(manifest["sanitized_receipt_retention"], "PASS")
        self.assertFalse(set(source.copies) & set(DIAGNOSTIC_LIMITS))

    def test_schema_version_requires_exact_json_integer_one(self):
        receipts = ("pilot-claim.json", "pilot-armed.json", "pilot-summary.json", "pilot-failure.json")
        for receipt in receipts:
            for version in (True, False, None, "1", 0, 2):
                with self.subTest(receipt=receipt, version=version), tempfile.TemporaryDirectory() as temporary:
                    values = valid_receipts(); mutate_json(values, receipt, "schema_version", version)
                    self.retain(temporary, values)
            with self.subTest(receipt=receipt, version="1.0"), tempfile.TemporaryDirectory() as temporary:
                values = valid_receipts()
                values[receipt] = values[receipt].replace(b'"schema_version":1', b'"schema_version":1.0')
                self.retain(temporary, values)

    def test_exact_integer_fields_reject_boolean_and_decimal_forms(self):
        cases = (("pilot-armed.json", "issue"), ("pilot-summary.json", "issue"),
                 ("pilot-failure.json", "issue"),
                 ("pilot-failure.json", "request_ordinal"), ("pilot-failure.json", "attempt_ordinal"))
        for receipt, field in cases:
            for lexical in (False, True):
                with self.subTest(receipt=receipt, field=field, lexical=lexical), tempfile.TemporaryDirectory() as temporary:
                    values = valid_receipts(); mutate_json(values, receipt, field, True)
                    if lexical:
                        token = f'"{field}":true'.encode()
                        decimal = f'"{field}":{26.0 if field == "issue" else 1.0}'.encode()
                        values[receipt] = values[receipt].replace(token, decimal)
                    self.retain(temporary, values)


if __name__ == "__main__":
    unittest.main()
