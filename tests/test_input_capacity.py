"""Capacity units, durable pre-model rejection, and fresh final armament checks."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from review_broker.identity import artifact_identity, attempt_identity, canonical_bytes
from review_broker.packets import SourceRecord, build_packet
from review_broker.queue import InMemoryJournal, AttemptState, StateTransitionError
from review_broker.recovery import decide_recovery, decide_preparation_recovery, RecoveryAction, PreparationRecoveryAction
from review_broker.input_capacity import MAX_CHARS, CapacityError, measure_input, validate_capacity_receipt
from review_broker.armament import CapacityRejected, check_prepared_capacity

REQUEST = "request:sha256:" + "1" * 64
SUBJECT = "subject:sha256:" + "2" * 64
BROKER = "a" * 40
ATTEMPT = attempt_identity(REQUEST, 1)


class RequestJournal:
    """Adapt the actual deterministic journal's attempt-keyed test interface."""
    def __init__(self, manifest):
        self.memory = InMemoryJournal()
        self.memory.claim(REQUEST)
        self.memory.transition(ATTEMPT, AttemptState.ADMITTED, ["resolved-fixture"])
        self.memory.transition(ATTEMPT, AttemptState.PREPARED, [artifact_identity(canonical_bytes(manifest))])

    def get(self, request):
        assert request == REQUEST
        return self.memory.get(ATTEMPT)

    def record_capacity(self, request, receipt):
        assert request == REQUEST
        return self.memory.record_capacity(ATTEMPT, receipt)

    def transition(self, request, state, evidence):
        assert request == REQUEST
        return self.memory.transition(ATTEMPT, state, evidence)

    def record_invocation(self, request):
        assert request == REQUEST
        return self.memory.record_invocation(ATTEMPT)


class InputCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.sequence = 0

    def packet(self, mission="Examine this complete source."):
        self.sequence += 1
        directory = self.root / f"packet-{self.sequence}"
        data = b"complete source content\n"
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        record = SourceRecord.from_bytes("sample/repo", "b" * 40, "source.txt", oid, data)
        manifest = build_packet([record], request_id=REQUEST, subject_id=SUBJECT,
            mission_instruction=mission, profile={"id": "scientific", "version": 1},
            output_directory=directory)
        metadata = {"request_id": REQUEST, "attempt_id": ATTEMPT, "executing_broker_sha": BROKER}
        (directory / "broker-metadata.json").write_bytes(canonical_bytes(metadata) + b"\n")
        return directory, manifest, RequestJournal(manifest)

    def check(self, directory, manifest, journal, *, arm=False, **overrides):
        arguments = dict(journal=journal, packet_directory=directory, request_id=REQUEST,
                         packet_id=manifest["packet_id"], executing_broker_sha=BROKER, arm=arm)
        arguments.update(overrides)
        return check_prepared_capacity(**arguments)

    def test_distinct_units_and_conservative_rule(self):
        counts = measure_input("a\u00e9\U0001f680".encode())
        self.assertEqual(counts["unicode_scalar_characters"], 3)
        self.assertEqual(counts["utf16_code_units"], 4)
        self.assertEqual(counts["utf8_bytes"], 7)
        self.assertEqual(counts["capacity_units"], 7)
        self.assertEqual(counts["input_sha256"], hashlib.sha256("a\u00e9\U0001f680".encode()).hexdigest())
        for invalid in [b"\xff", b"\xed\xa0\x80", b"\xc0\x80"]:
            with self.assertRaises(CapacityError):
                measure_input(invalid)

    def test_actual_exact_limit_passes_and_plus_one_refuses_without_arm(self):
        small, _, _ = self.packet("")
        overhead = len((small / "input.txt").read_bytes())
        for total, expected in [(MAX_CHARS - 1, "PASS"), (MAX_CHARS, "PASS"), (MAX_CHARS + 1, "REJECTED")]:
            with self.subTest(total=total):
                directory, manifest, journal = self.packet("x" * (total - overhead))
                self.assertEqual(len((directory / "input.txt").read_bytes()), total)
                if expected == "PASS":
                    receipt = self.check(directory, manifest, journal)
                    self.assertEqual(receipt["status"], expected)
                else:
                    with self.assertRaises(CapacityRejected) as caught:
                        self.check(directory, manifest, journal, arm=True)
                    receipt = caught.exception.receipt
                self.assertEqual(receipt["capacity_units"], total)
                self.assertEqual(journal.get(REQUEST).state, AttemptState.PREPARED)
                self.assertEqual(journal.get(REQUEST).invocation_count, 0)

    def test_preflight_does_not_arm_and_final_boundary_arms_exact_same_binding(self):
        directory, manifest, journal = self.packet()
        first = self.check(directory, manifest, journal)
        self.assertEqual(first["request_id"], REQUEST)
        self.assertEqual(first["packet_id"], manifest["packet_id"])
        self.assertEqual(first["executing_broker_sha"], BROKER)
        self.assertEqual(first["status"], "PASS")
        validate_capacity_receipt(first)
        second = self.check(directory, manifest, journal, arm=True)
        self.assertEqual(first, second)
        self.assertEqual(journal.get(REQUEST).state, AttemptState.ARMED)
        self.assertEqual(journal.get(REQUEST).invocation_count, 1)
        with self.assertRaises((CapacityError, StateTransitionError)):
            self.check(directory, manifest, journal, arm=True)

    def test_mutated_input_after_preflight_refuses_arm_even_if_hash_metadata_is_rewritten(self):
        for rewrite in [False, True]:
            with self.subTest(rewrite=rewrite):
                directory, manifest, journal = self.packet()
                self.check(directory, manifest, journal)
                value = (directory / "input.txt").read_bytes() + b"substitution"
                (directory / "input.txt").write_bytes(value)
                if rewrite:
                    forged = dict(manifest, prompt_sha256=hashlib.sha256(value).hexdigest(), prompt_byte_length=len(value))
                    (directory / "input-manifest.json").write_bytes(canonical_bytes(forged) + b"\n")
                with self.assertRaises(CapacityError):
                    self.check(directory, manifest, journal, arm=True)
                self.assertEqual(journal.get(REQUEST).state, AttemptState.PREPARED)
                self.assertEqual(journal.get(REQUEST).invocation_count, 0)

    def test_input_changed_during_journal_binding_cannot_arm(self):
        directory, manifest, journal = self.packet()
        original = journal.record_capacity
        def mutate_after_binding(request, receipt):
            result = original(request, receipt)
            (directory / "input.txt").write_bytes(b"changed during journal I/O")
            return result
        journal.record_capacity = mutate_after_binding
        with self.assertRaises(CapacityError):
            self.check(directory, manifest, journal, arm=True)
        self.assertEqual(journal.get(REQUEST).state, AttemptState.PREPARED)
        self.assertEqual(journal.get(REQUEST).invocation_count, 0)

    def test_changed_packet_or_broker_identity_refuses_arm(self):
        for change in [{"packet_id": "packet:sha256:" + "f" * 64}, {"executing_broker_sha": "b" * 40}]:
            directory, manifest, journal = self.packet()
            self.check(directory, manifest, journal)
            with self.assertRaises(CapacityError):
                self.check(directory, manifest, journal, arm=True, **change)
            self.assertEqual(journal.get(REQUEST).invocation_count, 0)

    def test_rejection_is_durable_and_generic_arm_or_recovery_cannot_bypass(self):
        directory, manifest, journal = self.packet("x" * MAX_CHARS)
        with self.assertRaises(CapacityRejected):
            self.check(directory, manifest, journal, arm=True)
        current = journal.get(REQUEST)
        self.assertEqual(current.state, AttemptState.PREPARED)
        self.assertEqual(current.input_capacity["status"], "REJECTED")
        self.assertEqual(current.invocation_count, 0)
        reconstructed = type(current).from_dict(current.as_dict())
        self.assertEqual(reconstructed, current)
        with self.assertRaises(StateTransitionError):
            journal.transition(REQUEST, AttemptState.ARMED, [manifest["packet_id"]])
        with self.assertRaises(CapacityRejected):
            self.check(directory, manifest, journal, arm=True)
        self.assertEqual(decide_recovery(current, codespace_state="Shutdown").action,
                         RecoveryAction.BLOCKED_INPUT_CAPACITY)
        self.assertEqual(decide_preparation_recovery(current, "unused"),
                         PreparationRecoveryAction.BLOCKED_INPUT_CAPACITY)
        self.assertEqual(journal.get(REQUEST).invocation_count, 0)

    def test_capacity_receipt_tampering_is_not_a_different_capacity_policy(self):
        directory, manifest, journal = self.packet()
        receipt = self.check(directory, manifest, journal)
        for key, value in [("max_chars", MAX_CHARS + 1), ("capacity_units", 0),
                           ("utf8_bytes", True), ("status", "REJECTED"),
                           ("limit_policy", "unapproved-v2")]:
            changed = dict(receipt, **{key: value})
            with self.assertRaises(CapacityError):
                validate_capacity_receipt(changed)

    def test_historical_journal_serialization_has_no_new_null_field(self):
        _, _, journal = self.packet()
        self.assertNotIn("input_capacity", journal.get(REQUEST).as_dict())


if __name__ == "__main__":
    unittest.main()
