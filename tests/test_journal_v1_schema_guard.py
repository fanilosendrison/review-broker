"""RB91-JQ-001: legacy v1 readers/writers must reject future journal authority.

This is a pre-v2 safety patch only; the accepted v1 execution protocol is
unchanged, and these tests never call GitHub, Codespaces, OIDC or Codex.
"""
import base64
from dataclasses import replace
import copy
import json
import subprocess
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.input_capacity import capacity_receipt
from review_broker.queue import (
    AttemptRecord, AttemptState, StateTransitionError, transition_record,
)

REQUEST_ID = "request:sha256:" + "a" * 64
COMMIT = "1" * 40
PACKET_ID = "packet:sha256:" + "c" * 64


def legacy(state=AttemptState.REQUESTED, *, count=0):
    return AttemptRecord(
        request_id=REQUEST_ID,
        attempt_id=attempt_identity(REQUEST_ID, 1),
        state=state,
        invocation_count=count,
        history=({"state": state.value, "evidence_ids": []},),
    ).as_dict()


def future_record():
    value = legacy(AttemptState.ARMED, count=1)
    value.update({
        "schema_version": 2,
        "protocol_id": "j-ch-v1",
        "arm_binding": {"challenge": "b" * 64, "prepared_parent_sha": COMMIT},
    })
    return value


class LegacySchemaTests(unittest.TestCase):
    def test_v1_legacy_serialized_shapes_are_lossless(self):
        cases = [
            legacy(),
            legacy(AttemptState.STOPPED, count=1),
            legacy(AttemptState.INDETERMINATE, count=0),
            legacy(AttemptState.INDETERMINATE, count=1),
        ]
        with_admission = legacy(AttemptState.STOPPED, count=1)
        with_admission["admission"] = {"schema_version": 1, "subject_id": "historical"}
        cases.append(with_admission)
        with_review_request_v2 = legacy(AttemptState.STOPPED, count=1)
        with_review_request_v2["admission"] = {"schema_version": 2, "review_operation": {"kind": "initial"}}
        cases.append(with_review_request_v2)
        with_capacity = legacy(AttemptState.PREPARED)
        with_capacity["input_capacity"] = capacity_receipt(
            b"synthetic-input",
            request_id=REQUEST_ID, packet_id=PACKET_ID,
            attempt_id=with_capacity["attempt_id"], executing_broker_sha="d" * 40,
        )
        cases.append(with_capacity)
        with_metadata = legacy(AttemptState.REPORTED, count=1)
        with_metadata["evidence_locator_plan"] = {"historical": "plan"}
        with_metadata["evidence_locator"] = {"historical": "locator"}
        with_metadata["publication_intent"] = {"historical": "intent"}
        with_metadata["publication_receipt"] = {"historical": "receipt"}
        cases.append(with_metadata)
        for value in cases:
            with self.subTest(state=value["state"], optional=sorted(set(value) - set(legacy()))):
                decoded = AttemptRecord.from_dict(copy.deepcopy(value))
                self.assertEqual(decoded.as_dict(), value)
                self.assertEqual(canonical_bytes(decoded.as_dict()), canonical_bytes(value))

    def test_unsupported_journal_versions_refused_before_decode(self):
        original = legacy()
        for value in (2, 3, 0, -1, True, False, 1.0, "1", "2", None):
            item = dict(original, schema_version=value)
            with self.subTest(version=value, value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "JOURNAL_V1_SCHEMA_UNSUPPORTED"):
                    AttemptRecord.from_dict(item)
        item = dict(original)
        item.pop("schema_version")
        with self.assertRaisesRegex(ValueError, "JOURNAL_V1_SCHEMA_UNSUPPORTED"):
            AttemptRecord.from_dict(item)
        with self.assertRaisesRegex(ValueError, "JOURNAL_V1_SCHEMA_UNSUPPORTED"):
            AttemptRecord.from_dict([])

    def test_v2_and_future_fields_never_pass_through_v1_writer(self):
        items = [
            future_record(),
            dict(legacy(), protocol_id="j-ch-v1"),
            dict(legacy(), arm_binding={"challenge": "b" * 64}),
            dict(legacy(), transaction_nonce="6" * 64),
            dict(legacy(), new_future_metadata={"grant": "unsafe"}),
        ]
        for item in items:
            with self.subTest(fields=sorted(item)):
                with self.assertRaisesRegex(ValueError, "JOURNAL_V1_(SCHEMA_UNSUPPORTED|FIELD_SET_INVALID)"):
                    AttemptRecord.from_dict(item)
        # A hostile/mistaken version-1 label may not make the v2 binding disappear.
        hybrid = future_record()
        hybrid["schema_version"] = 1
        with self.assertRaisesRegex(ValueError, "JOURNAL_V1_FIELD_SET_INVALID"):
            AttemptRecord.from_dict(hybrid)

    def test_missing_v1_fields_cannot_be_reserialized_with_defaults(self):
        base = legacy()
        for key in base:
            item = copy.deepcopy(base)
            item.pop(key)
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    AttemptRecord.from_dict(item)

    def test_lossy_legacy_values_and_malformed_collections_are_rejected(self):
        base = legacy()
        alterations = (
            {"admission": None},
            {"input_capacity": None},
            {"evidence_ids": ("a",)},
            {"evidence_ids": "a"},
            {"history": "not-a-list"},
            {"history": ("a",)},
            {"invocation_count": True},
            {"invocation_count": 2},
            {"invocation_count": "0"},
        )
        for change in alterations:
            item = dict(base, **change)
            with self.subTest(change=change):
                with self.assertRaises((ValueError, StateTransitionError)):
                    AttemptRecord.from_dict(item)

    def test_v1_consumed_terminal_attempt_has_no_rearm(self):
        original = AttemptRecord.from_dict(legacy(AttemptState.STOPPED, count=1))
        self.assertEqual(original.invocation_count, 1)
        with self.assertRaises(StateTransitionError):
            transition_record(original, AttemptState.ARMED, ["replay"])
        self.assertEqual(original.as_dict()["schema_version"], 1)

    def test_gh_journal_read_and_writers_refuse_unknown_without_any_mutation(self):
        operations = {
            "get": lambda j: j.get(REQUEST_ID),
            "get_snapshot": lambda j: j.get_snapshot(REQUEST_ID),
            "claim": lambda j: j.claim(REQUEST_ID),
            "transition": lambda j: j.transition(REQUEST_ID, AttemptState.ARMED, ["review"]),
            "record_invocation": lambda j: j.record_invocation(REQUEST_ID),
            "record_capacity": lambda j: j.record_capacity(REQUEST_ID, {}),
            "record_terminal_capture": lambda j: j.record_terminal_capture(REQUEST_ID, {}),
            "record_stopped": lambda j: j.record_stopped(REQUEST_ID, {}),
            "record_publication": lambda j: j.record_publication(REQUEST_ID, {}),
        }
        future = future_record()
        hybrid = copy.deepcopy(future)
        hybrid["schema_version"] = 1
        for item in (future, hybrid):
            for name, operation in operations.items():
                calls = []
                def runner(command, **_kwargs):
                    calls.append(tuple(command))
                    self.assertEqual(command[3], "GET", "refused journal must not be written")
                    endpoint = command[4]
                    if "/git/refs/heads/review-claims/" in endpoint:
                        return subprocess.CompletedProcess(
                            command, 0, json.dumps({"object": {"sha": COMMIT}}), ""
                        )
                    if endpoint.endswith("?ref=" + COMMIT):
                        encoded = base64.b64encode(canonical_bytes(item) + b"\n").decode("ascii")
                        return subprocess.CompletedProcess(
                            command, 0, json.dumps({"content": encoded, "encoding": "base64"}), ""
                        )
                    self.fail("Unexpected journal endpoint: " + endpoint)
                journal = GitHubRefJournal("sample/repo", runner=runner)
                with self.subTest(schema=item["schema_version"], operation=name):
                    with self.assertRaisesRegex(
                        StateTransitionError, "JOURNAL_CONTENT_RESPONSE_INVALID"
                    ):
                        operation(journal)
                    self.assertEqual(len(calls), 2)
                    self.assertTrue(all(call[3] == "GET" for call in calls))

    def test_gh_journal_still_reads_v1_and_does_not_reencode_optional_admission(self):
        item = legacy(AttemptState.STOPPED, count=1)  # No admission is historical and valid.
        calls = []
        def runner(command, **_kwargs):
            calls.append(tuple(command))
            self.assertEqual(command[3], "GET")
            if "/git/refs/heads/review-claims/" in command[4]:
                return subprocess.CompletedProcess(command, 0, json.dumps({"object": {"sha": COMMIT}}), "")
            if command[4].endswith("?ref=" + COMMIT):
                encoded = base64.b64encode(canonical_bytes(item) + b"\n").decode("ascii")
                return subprocess.CompletedProcess(command, 0, json.dumps({"content": encoded, "encoding": "base64"}), "")
            self.fail(command[4])
        journal = GitHubRefJournal("sample/repo", runner=runner)
        observed_sha, value = journal.get_snapshot(REQUEST_ID)
        self.assertEqual(observed_sha, COMMIT)
        self.assertEqual(value.as_dict(), item)
        self.assertNotIn("admission", value.as_dict())
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
