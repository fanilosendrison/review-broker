"""Tests of a small NONNORMATIVE v2 wrapper around the real AttemptRecord.

These do not modify production queue.py, GitHubRefJournal, or credentials.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import threading
import unittest

from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState, transition_record
from tests.reference_v1_journal_migration import (
    CompatCAS, MigrationError, control_initial, decode, encode,
)


REQUEST = "request:sha256:" + "a" * 64


class MinimalJournalMigrationTests(unittest.TestCase):
    def record(self):
        return AttemptRecord(
            request_id=REQUEST,
            attempt_id=attempt_identity(REQUEST, 1),
            state=AttemptState.REQUESTED,
            admission={"subject": "verified", "version": 3},
            history=({"state": "REQUESTED", "evidence_ids": []},),
        )

    def test_v1_serialization_exact_history_and_fields_unchanged(self):
        legacy = self.record()
        original = canonical_bytes(legacy.as_dict()) + b"\n"
        self.assertEqual(canonical_bytes(AttemptRecord.from_dict(
            json.loads(original)).as_dict()) + b"\n", original)
        self.assertNotIn("pre_model_control", legacy.as_dict())

    def test_v2_adds_only_control_without_packet_evidence_id(self):
        legacy = self.record()
        value = json.loads(encode(legacy, control_initial()))
        expected = set(legacy.as_dict()) | {"pre_model_control"}
        self.assertEqual(set(value), expected)
        self.assertNotIn("packet_evidence_id", value)
        self.assertEqual(value["history"], legacy.as_dict()["history"])
        self.assertEqual(value["schema_version"], 2)

    def test_strict_v2_roundtrip_preserves_original_history_byte_meaning(self):
        legacy = self.record()
        v2 = encode(legacy, control_initial())
        decoded, control = decode(v2)
        self.assertEqual(encode(decoded, control), v2)
        self.assertEqual(decoded.history, legacy.history)
        self.assertEqual(decoded.as_dict(), legacy.as_dict())

    def test_prepared_packet_id_from_actual_state_history_not_new_field(self):
        claim = CompatCAS(self.record())
        claim.reserve()
        claim.worker()
        token = claim.token()
        claim.transition(AttemptState.ADMITTED, "admission-evidence", token)
        claim.transition(AttemptState.PREPARED, "packet-evidence", token)
        _, legacy, control = claim.snapshot()
        self.assertEqual(legacy.state, AttemptState.PREPARED)
        self.assertEqual(legacy.history[-1],
                         {"state": "PREPARED", "evidence_ids": ["packet-evidence"]})
        self.assertIn("packet-evidence", legacy.evidence_ids)
        self.assertNotIn("packet_evidence_id", json.loads(claim.encoded()))
        self.assertEqual(control["disposition"], "RESERVED")

    def test_real_armed_0_is_legitimate_intermediate_state(self):
        claim = CompatCAS(self.record())
        claim.reserve()
        claim.worker()
        token = claim.token()
        claim.transition(AttemptState.ADMITTED, "admission", token)
        claim.transition(AttemptState.PREPARED, "packet", token)
        claim.transition(AttemptState.ARMED, "arm", token)
        raw = claim.encoded()
        legacy, control = decode(raw)
        self.assertEqual(legacy.state, AttemptState.ARMED)
        self.assertEqual(legacy.invocation_count, 0)
        self.assertEqual(control["worker"]["run_id"], 123)
        claim.invoked(token)
        self.assertEqual(claim.snapshot()[1].invocation_count, 1)
        with self.assertRaisesRegex(MigrationError, "INVOCATION_ALREADY_USED"):
            claim.invoked(token)

    def test_unrecognized_version_unknown_field_and_missing_control_rejected(self):
        value = json.loads(encode(self.record(), control_initial()))
        for label, change in (
            ("unknown version", lambda x: x.__setitem__("schema_version", 3)),
            ("unexpected field", lambda x: x.__setitem__("packet_evidence_id", "fake")),
            ("lost control", lambda x: x.pop("pre_model_control")),
        ):
            with self.subTest(label=label):
                candidate = deepcopy(value)
                change(candidate)
                with self.assertRaisesRegex(MigrationError, "JOURNAL_V2_SCHEMA_INVALID"):
                    decode(canonical_bytes(candidate) + b"\n")

    def test_v2_wire_requires_canonical_json_plus_lf(self):
        value = json.loads(encode(self.record(), control_initial()))
        bad = json.dumps(value, indent=2).encode("utf-8") + b"\n"
        with self.assertRaisesRegex(MigrationError, "JOURNAL_V2_NONCANONICAL"):
            decode(bad)

    def test_legacy_publication_and_locator_data_preserved_byte_meaning(self):
        legacy = replace(
            self.record(),
            evidence_locator_plan={"attempt_id": attempt_identity(REQUEST, 1)},
            evidence_locator={"file": "immutable"},
            publication_intent={"publication_id": "stable"},
            publication_receipt={"comment_id": 12},
            history=({"state": "REQUESTED", "evidence_ids": []},
                     {"event": "PUBLICATION_RESERVED",
                      "evidence_ids": ["artifact:sha256:" + "b" * 64]}),
        )
        parsed, _ = decode(encode(legacy, control_initial()))
        self.assertEqual(parsed.as_dict(), legacy.as_dict())

    def test_two_concurrent_reservations_have_one_cas_winner(self):
        claim = CompatCAS(self.record())
        barrier = threading.Barrier(2)
        def runner(_):
            barrier.wait()
            try:
                return "WIN", claim.reserve()
            except MigrationError:
                return "LOSE", None
        with ThreadPoolExecutor(max_workers=2) as executor:
            values = list(executor.map(runner, range(2)))
        self.assertEqual(sorted(x[0] for x in values), ["LOSE", "WIN"])
        self.assertEqual(claim.snapshot()[2]["generation"], 1)

    def test_stale_prepared_generation_cas_is_refused(self):
        claim = CompatCAS(self.record())
        claim.reserve()
        claim.worker()
        token = claim.token()
        claim.transition(AttemptState.ADMITTED, "admission", token)
        rev, _, _ = claim.snapshot()
        claim.transition(AttemptState.PREPARED, "packet", token)
        with self.assertRaisesRegex(MigrationError, "STALE_CAS"):
            claim.transition(AttemptState.ARMED, "arm", token, revision=rev)

    def test_history_appends_v3_event_without_rewriting_v1_prefix(self):
        original = self.record()
        claim = CompatCAS(original)
        claim.reserve()
        claim.worker()
        _, record, _ = claim.snapshot()
        self.assertEqual(record.history[0], original.history[0])
        self.assertEqual(record.history[1]["event"], "PRE_MODEL_DISPATCH_RESERVED")
        self.assertEqual(record.history[2]["event"], "PRE_MODEL_WORKER_BOUND")
        self.assertEqual(set(record.history[1]), {"event", "evidence_ids", "pre_model"})

    def test_legacy_codec_rewriting_v2_remains_known_rollout_blocker(self):
        wrapped = json.loads(encode(self.record(), control_initial()))
        old = AttemptRecord.from_dict(deepcopy(wrapped)).as_dict()
        self.assertEqual(old["schema_version"], 1)
        self.assertNotIn("pre_model_control", old)
        # The new strict wrapper cannot prevent an already deployed old worker.
        with self.assertRaisesRegex(MigrationError, "JOURNAL_V2_SCHEMA_INVALID"):
            decode(canonical_bytes(old) + b"\n")


if __name__ == "__main__":
    unittest.main()
