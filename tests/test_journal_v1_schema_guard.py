"""RB91-JQ-001: legacy v1 readers/writers must reject future journal authority.

This is a pre-v2 safety patch only; the accepted v1 execution protocol is
unchanged, and these tests never call GitHub, Codespaces, OIDC or Codex.
"""
import base64
from dataclasses import replace
import copy
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from review_broker.github_journal import GitHubRefJournal
from review_broker.identity import attempt_identity, canonical_bytes
from review_broker.input_capacity import capacity_receipt
from review_broker.input_capacity import capacity_receipt
from review_broker.queue import (
    AttemptRecord, AttemptState, StateTransitionError, transition_record,
)
from review_broker.recovery import RecoveryAction, decide_recovery
from tests.journal_git_transport import JournalGitTransport
from tests.journal_http_transport import scoped_response

REQUEST_ID = "request:sha256:" + "a" * 64
COMMIT = "1" * 40
PACKET_ID = "packet:sha256:" + "c" * 64
ORIGINAL_FIELDS = frozenset({
    "schema_version", "request_id", "attempt_id", "state",
    "evidence_ids", "invocation_count", "history",
})
EXTENDED_METADATA = frozenset({
    "evidence_locator_plan", "evidence_locator",
    "publication_intent", "publication_receipt",
})
GOLDEN_WIRE = Path(__file__).parent / "fixtures" / "rb91-original-seven-field-journal-v1.json"


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

    def test_original_v1_source_derived_golden_producer_records(self):
        """Independent frozen wire corpus, not today's as_dict() snapshots."""
        corpus = json.loads(GOLDEN_WIRE.read_text(encoding="utf-8"))
        self.assertEqual(corpus["source_commit"],
                         "fb34cb687fbe46edcdae4d5aebd18d22ffdc4cdc")
        self.assertEqual(set(corpus["record_fields"]), ORIGINAL_FIELDS)
        self.assertEqual(len(corpus["cases"]), 6)
        for sample in corpus["cases"]:
            value = sample["record"]
            with self.subTest(label=sample["label"]):
                self.assertEqual(set(value), ORIGINAL_FIELDS)
                self.assertEqual(value["request_id"], REQUEST_ID)
                self.assertEqual(value["attempt_id"], attempt_identity(REQUEST_ID, 1))
                observed = AttemptRecord.from_dict(copy.deepcopy(value))
                self.assertEqual(observed.state.value, value["state"])
                self.assertEqual(observed.invocation_count, value["invocation_count"])
                self.assertEqual(observed.as_dict(), value)
                self.assertEqual(canonical_bytes(observed.as_dict()),
                                 canonical_bytes(value))
                self.assertTrue(observed._v1_original_seven_field_wire)
                recovery = decide_recovery(observed, codespace_state="Shutdown")
                if observed.state is AttemptState.STOPPED:
                    self.assertEqual(recovery.action, RecoveryAction.NONE)
                elif observed.state is AttemptState.ARMED:
                    self.assertEqual(recovery.action,
                                     RecoveryAction.MARK_INDETERMINATE_AND_STOP)
                elif observed.state in {AttemptState.REQUESTED, AttemptState.PREPARED}:
                    self.assertEqual(recovery.action, RecoveryAction.RESUME_PRE_MODEL)

    def test_source_derived_extended_metadata_profile(self):
        corpus = json.loads(GOLDEN_WIRE.read_text(encoding="utf-8"))
        extended = corpus["extended_producer"]
        self.assertEqual(extended["source_commit"],
                         "3beff06bff1deffc72772455d89489e50996d416")
        value = extended["record"]
        self.assertEqual(set(value), ORIGINAL_FIELDS | EXTENDED_METADATA)
        self.assertEqual(value["state"], "STOPPED")
        decoded = AttemptRecord.from_dict(copy.deepcopy(value))
        self.assertEqual(decoded.as_dict(), value)
        self.assertFalse(decoded._v1_original_seven_field_wire)

    def test_original_v1_real_git_read_claim_and_transition_preserve_profile(self):
        corpus = json.loads(GOLDEN_WIRE.read_text(encoding="utf-8"))
        for sample in corpus["cases"]:
            with self.subTest(label=sample["label"]), TemporaryDirectory() as temp:
                transport = JournalGitTransport(Path(temp) / "objects.git")
                journal = GitHubRefJournal("sample/repo", runner=transport)
                original = sample["record"]
                original_record = AttemptRecord.from_dict(copy.deepcopy(original))
                parent_sha = transport.seed(original_record, journal._claim_ref(REQUEST_ID))
                initial_bytes = transport.git(
                    "show", parent_sha + ":.review-broker/attempt.json"
                )
                self.assertEqual(initial_bytes, canonical_bytes(original) + b"\n")
                observed_sha, observed = journal.get_snapshot(REQUEST_ID)
                self.assertEqual(observed_sha, parent_sha)
                self.assertEqual(observed.as_dict(), original)
                # Idempotent claims and reads from original v1 never create a ref.
                self.assertEqual(journal.claim(REQUEST_ID).as_dict(), original)
                self.assertEqual(transport.patch_count, 0)
                self.assertEqual(transport.proposals, [])

                label = sample["label"]
                if label == "PREPARED_count0":
                    changed = journal.transition(
                        REQUEST_ID, AttemptState.INDETERMINATE,
                        ["artifact:sha256:" + "6" * 64],
                    )
                    self.assertEqual(set(changed.as_dict()), ORIGINAL_FIELDS)
                elif label == "ARMED_count0":
                    changed = journal.record_invocation(REQUEST_ID)
                    self.assertEqual(changed.invocation_count, 1)
                    self.assertEqual(set(changed.as_dict()), ORIGINAL_FIELDS)
                elif label == "STOPPED_count1":
                    with self.assertRaises(StateTransitionError):
                        journal.transition(
                            REQUEST_ID, AttemptState.ARMED,
                            ["artifact:sha256:" + "7" * 64],
                        )
                    self.assertEqual(transport.patch_count, 0)
                # Even after future child changes, original parent bytes never change.
                self.assertEqual(
                    transport.git("show", parent_sha + ":.review-broker/attempt.json"),
                    initial_bytes,
                )

    def test_historical_v1_metadata_upgrade_is_explicit_and_lossless(self):
        original = json.loads(GOLDEN_WIRE.read_text(encoding="utf-8"))["cases"][2]["record"]
        value = AttemptRecord.from_dict(original)
        self.assertEqual(set(value.as_dict()), ORIGINAL_FIELDS)
        # Representation-level test only, not evidence authorization: a later
        # legitimate metadata writer must emit the *extended* v1 profile and
        # retain original identity/state/count/history and the new metadata.
        upgraded = replace(value, evidence_locator_plan={"test-only": "metadata"})
        encoded = upgraded.as_dict()
        self.assertEqual(set(encoded), ORIGINAL_FIELDS | EXTENDED_METADATA)
        self.assertEqual(encoded["evidence_locator_plan"], {"test-only": "metadata"})
        self.assertEqual(encoded["history"], original["history"])
        self.assertEqual(encoded["invocation_count"], original["invocation_count"])
        self.assertEqual(AttemptRecord.from_dict(encoded).as_dict(), encoded)
        self.assertFalse(AttemptRecord.from_dict(encoded)._v1_original_seven_field_wire)
        # Verify a real Git candidate commit/readback with the original
        # seven-field parent and an extended eleven-field child. The adapter
        # call is deliberately a synthetic transport-level test, not proof
        # that an arbitrary test-only metadata receipt is authorized.
        with TemporaryDirectory() as temp:
            transport = JournalGitTransport(Path(temp) / "objects.git")
            journal = GitHubRefJournal("sample/repo", runner=transport)
            parent = transport.seed(value, journal._claim_ref(REQUEST_ID))
            journal._compare_and_swap(REQUEST_ID, parent, upgraded)
            sha, observed = journal.get_snapshot(REQUEST_ID)
            self.assertNotEqual(sha, parent)
            self.assertEqual(observed.as_dict(), encoded)
            self.assertEqual(
                set(json.loads(transport.git(
                    "show", sha + ":.review-broker/attempt.json"
                ))),
                ORIGINAL_FIELDS | EXTENDED_METADATA,
            )
            self.assertEqual(
                transport.git("show", parent + ":.review-broker/attempt.json"),
                canonical_bytes(original) + b"\n",
            )
        # Current new v1 records continue emitting the extended profile by default.
        self.assertEqual(set(legacy()), ORIGINAL_FIELDS | EXTENDED_METADATA)

    def test_original_v1_prepared_capacity_transition_upgrades_extended_wire(self):
        corpus = json.loads(GOLDEN_WIRE.read_text(encoding="utf-8"))
        original = corpus["cases"][1]["record"]
        self.assertEqual(original["state"], "PREPARED")
        receipt = capacity_receipt(
            b"synthetic-input", request_id=REQUEST_ID, packet_id=PACKET_ID,
            attempt_id=original["attempt_id"], executing_broker_sha="d" * 40,
        )
        with TemporaryDirectory() as temp:
            transport = JournalGitTransport(Path(temp) / "objects.git")
            journal = GitHubRefJournal("sample/repo", runner=transport)
            parent = transport.seed(
                AttemptRecord.from_dict(original), journal._claim_ref(REQUEST_ID),
            )
            updated = journal.record_capacity(REQUEST_ID, receipt)
            self.assertEqual(
                set(updated.as_dict()),
                ORIGINAL_FIELDS | EXTENDED_METADATA | {"input_capacity"},
            )
            self.assertEqual(updated.input_capacity, receipt)
            child_sha, recovered = journal.get_snapshot(REQUEST_ID)
            self.assertNotEqual(child_sha, parent)
            self.assertEqual(recovered.as_dict(), updated.as_dict())
            self.assertEqual(recovered.input_capacity, receipt)
            self.assertFalse(recovered._v1_original_seven_field_wire)
            self.assertEqual(
                transport.git("show", parent + ":.review-broker/attempt.json"),
                canonical_bytes(original) + b"\n",
            )

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
        for key in ORIGINAL_FIELDS:
            item = copy.deepcopy(base)
            item.pop(key)
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    AttemptRecord.from_dict(item)
        # The post-metadata v1 producer has four fields as one atomic profile.
        # Missing just one field is invalid; missing all four is the valid
        # seven-field original producer shape and must round-trip exactly.
        for key in EXTENDED_METADATA:
            item = copy.deepcopy(base)
            item.pop(key)
            with self.subTest(partial_metadata=key):
                with self.assertRaisesRegex(ValueError, "JOURNAL_V1_FIELD_SET_INVALID"):
                    AttemptRecord.from_dict(item)
        original = {key: value for key, value in base.items() if key not in EXTENDED_METADATA}
        self.assertEqual(AttemptRecord.from_dict(original).as_dict(), original)

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
                        return scoped_response(command, {"object": {"sha": COMMIT}})
                    if endpoint.endswith("?ref=" + COMMIT):
                        encoded = base64.b64encode(canonical_bytes(item) + b"\n").decode("ascii")
                        return scoped_response(command, {"content": encoded, "encoding": "base64"})
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
                return scoped_response(command, {"object": {"sha": COMMIT}})
            if command[4].endswith("?ref=" + COMMIT):
                encoded = base64.b64encode(canonical_bytes(item) + b"\n").decode("ascii")
                return scoped_response(command, {"content": encoded, "encoding": "base64"})
            self.fail(command[4])
        journal = GitHubRefJournal("sample/repo", runner=runner)
        observed_sha, value = journal.get_snapshot(REQUEST_ID)
        self.assertEqual(observed_sha, COMMIT)
        self.assertEqual(value.as_dict(), item)
        self.assertNotIn("admission", value.as_dict())
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
