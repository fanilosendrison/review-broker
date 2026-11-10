"""Exact policy and independent provenance/decision rejection tests (Phase A)."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import WorkerIdentityV3
from review_broker.pre_model_policy_v3 import parse_expected_policy_v3
from review_broker.pre_model_policy_source_v3 import (
    PolicySourceObservationV3, verify_policy_source_v3,
)
from review_broker.pre_model_policy_selection_v3 import (
    PolicySelectionReceiptV3, verify_policy_selection_v3,
)
from tests.issue70_rwp03_test_support import (
    CONTENT_ID, CONTEXT, DIGEST, EXPECTED, POLICY_BYTES, SELECTION, SOURCE,
    FixturePolicySelectionAuthority, FixturePolicySourceAuthority,
)

ROOT = Path(__file__).resolve().parents[1] / "src/review_broker"


class Rwp03PolicyTests(unittest.TestCase):
    def verify(self, *, data=POLICY_BYTES, source=SOURCE, receipt=SELECTION,
               context=CONTEXT, expectation=EXPECTED,
               source_authority=FixturePolicySourceAuthority(),
               selection_authority=FixturePolicySelectionAuthority()):
        return verify_policy_selection_v3(
            data, source, receipt, context, expectation,
            source_authority, selection_authority)

    def test_N01_exact_expected_policy_bytes_schema_and_identity(self):
        data = (ROOT / SOURCE.source_path.removeprefix("src/review_broker/")).read_bytes()
        self.assertEqual(data, POLICY_BYTES)
        self.assertEqual(len(data), 589)
        self.assertEqual(hashlib.sha256(data).hexdigest(), DIGEST)
        self.assertEqual(hashlib.sha1(b"blob 589\0" + data).hexdigest(),
                         "5bdd27d4d8fd66b591f07a6d165a73aca15a50de")
        schema = json.loads((ROOT / "schemas/pre-model-v3-expected-policy.candidate.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads(data))
        policy = parse_expected_policy_v3(data)
        self.assertEqual(policy.technical_policy_id, CONTENT_ID)
        self.assertEqual(canonical_bytes(policy.document) + b"\n", data)
        with self.assertRaises(FrozenInstanceError):
            policy.original_bytes = b"forged"
        changed = policy.document
        changed["reviewer"]["model"] = "changed"
        self.assertNotEqual(changed, policy.document)

    def test_N02_independent_authorization_and_reviewer_agreement(self):
        policy = self.verify()
        from tests.packet_v2_test_support import admitted
        admission = admitted()
        self.assertEqual(canonical_bytes(admission.request), admission.canonical_request_bytes)
        policy.require_reviewer_agreement(admission.request)
        for receipt in (SOURCE, SELECTION):
            self.assertEqual(type(receipt).from_bytes(receipt.canonical_receipt_bytes), receipt)
            self.assertEqual(receipt.evidence_id, artifact_identity(
                canonical_bytes(receipt.basis) + b"\n"))
            self.assertNotIn("evidence_id", receipt.basis)

    def test_F01_correct_hash_without_source_authority(self):
        with self.assertRaises(ValueError):
            self.verify(source_authority=None)

    def test_F02_correct_source_without_selection_authority(self):
        with self.assertRaises(ValueError):
            self.verify(selection_authority=None)

    def test_F03_requester_controlled_policy_substitution(self):
        with self.assertRaises(ValueError):
            self.verify(data=b'{"requester_policy":"allow"}\n')

    def test_F04_consumer_repository_masquerading_as_broker_policy(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, broker_repository="consumer/repo"))

    def test_F05_wrong_repository_or_numeric_id(self):
        for change in ({"broker_repository": "other/broker"},
                       {"broker_repository_id": 7}, {"broker_repository_id": True},
                       {"broker_repository_id": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify(source=replace(SOURCE, **change))

    def test_F06_wrong_policy_source_path(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, source_path="profiles/consumer.json"))

    def test_F07_wrong_source_commit(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, source_commit_sha="a" * 40))

    def test_F08_mutable_ref_instead_of_commit(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, source_commit_sha="refs/heads/main"))

    def test_F09_wrong_blob_oid(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, git_blob_oid="a" * 40))

    def test_F10_changed_bytes_or_length(self):
        for data in (POLICY_BYTES[:-1], POLICY_BYTES + b"\n", POLICY_BYTES.replace(b"never", b"other")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.verify(data=data)
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, original_byte_length=590))

    def test_F11_wrong_policy_name_or_revision(self):
        for changes in ({"policy_name": "consumer"}, {"policy_revision": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.verify(receipt=replace(SELECTION, **changes))

    def test_F12_closed_schema_and_noncanonical_bytes(self):
        schema = json.loads((ROOT / "schemas/pre-model-v3-expected-policy.candidate.schema.json").read_bytes())
        validator = Draft202012Validator(schema)
        original = json.loads(POLICY_BYTES)
        for key in original:
            missing = json.loads(POLICY_BYTES)
            del missing[key]
            with self.subTest(missing=key):
                self.assertFalse(validator.is_valid(missing))
        for section in (None, "reviewer", "requirements"):
            for operation in ("extra", "wrong_type", "missing"):
                document = json.loads(POLICY_BYTES)
                target = document if section is None else document[section]
                key = next(iter(target))
                if operation == "extra":
                    target["unexpected"] = 1
                elif operation == "wrong_type":
                    target[key] = []
                else:
                    del target[key]
                with self.subTest(section=section, operation=operation):
                    self.assertFalse(validator.is_valid(document))
                    with self.assertRaises(ValueError):
                        parse_expected_policy_v3(canonical_bytes(document) + b"\n")
        for data in (POLICY_BYTES.replace(b'"schema_version":1', b'"schema_version":1.0'),
                     b"\xef\xbb\xbf" + POLICY_BYTES, POLICY_BYTES.replace(b"{", b"{ ", 1)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_expected_policy_v3(data)

    def test_F13_backend_mismatch(self):
        self.reviewer_mismatch("backend")

    def test_F14_model_mismatch(self):
        self.reviewer_mismatch("model")

    def test_F15_reasoning_effort_mismatch(self):
        self.reviewer_mismatch("reasoning_effort")

    def reviewer_mismatch(self, field):
        policy = self.verify()
        reviewer = policy.document["reviewer"]
        reviewer[field] = "substituted"
        with self.assertRaises(ValueError):
            policy.require_reviewer_agreement({"reviewer": reviewer})

    def test_F16_selection_for_another_request(self):
        self.reject_receipt(request_id="request:sha256:" + "9" * 64)

    def test_F17_selection_for_another_attempt(self):
        self.reject_receipt(attempt_id="attempt:sha256:" + "9" * 64)

    def test_F18_other_reservation_or_generation(self):
        self.reject_receipt(reservation_id="other")
        self.reject_receipt(generation=2)
        self.reject_receipt(generation=True)

    def test_F19_other_worker_run_or_attempt(self):
        self.reject_receipt(worker=WorkerIdentityV3(999, 1))
        self.reject_receipt(worker=WorkerIdentityV3(70001, 2))

    def test_F20_other_executable_sha(self):
        self.reject_receipt(executing_source_sha="9" * 40)

    def test_F21_other_claim_or_admitted_commit(self):
        self.reject_receipt(claim_ref="refs/other")
        self.reject_receipt(admitted_commit_sha="9" * 40)

    def test_F22_forged_decision_evidence(self):
        # A valid artifact identity must still be independently recognized.
        self.reject_receipt(decision_authority_evidence_id=artifact_identity(b"forged"))

    def test_F23_replayed_selection_in_different_context(self):
        with self.assertRaises(ValueError):
            self.verify(context=replace(CONTEXT, admitted_commit_sha="9" * 40))

    def reject_receipt(self, **changes):
        with self.assertRaises(ValueError):
            self.verify(receipt=replace(SELECTION, **changes))

    def test_forged_source_authority_evidence(self):
        with self.assertRaises(ValueError):
            self.verify(source=replace(SOURCE, source_authority_evidence_id=artifact_identity(b"forged")))

    def test_receipts_reject_extra_fields_duplicates_and_noncanonical_encoding(self):
        for receipt in (SOURCE, SELECTION):
            data = receipt.canonical_receipt_bytes
            for malformed in (data + b"\n", data[:-1],
                              b'{"extra":1,' + data[1:],
                              b'{"schema_version":1,' + data[1:]):
                with self.subTest(receipt=type(receipt), data=malformed), self.assertRaises(ValueError):
                    type(receipt).from_bytes(malformed)


class PolicyEffectBoundaryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from tests.issue70_rwp03_test_support import RealContinuationScenario
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.s = RealContinuationScenario(self.root)

    def test_R4_revocation_after_file_creation_prevents_content_write(self):
        import os
        from unittest.mock import patch
        opened, original = [], os.open
        def create(path, *args, **kwargs):
            fd = original(path, *args, **kwargs)
            if Path(path).name == "S001.bin":
                opened.append(Path(path))
                self.s.worker.boundary.trusted = False
            return fd
        with patch("os.open", create):
            result = self.s.continuation.run(self.s.worker.context)
        self.assertIsNone(result.packet_id)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].read_bytes(), b"")
        self.assertFalse((self.root/"candidate").exists())
        self.assertFalse((self.root/"retained").exists())

    def test_R4_packet_internal_git_proof_stops_before_second_read(self):
        from unittest.mock import patch
        from review_broker.packets import GitSourceReader
        from review_broker.packet_v2 import build_packet_v2_candidate
        result = self.s.continuation.run(self.s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)
        admission, capture, profile, verification, readers = self.s.stages._inputs
        calls, original = [], GitSourceReader._git
        def execute(reader, *args, **kwargs):
            data = original(reader, *args, **kwargs)
            calls.append(args)
            self.s.worker.boundary.trusted = False
            return data
        with patch.object(GitSourceReader, "_git", execute), self.assertRaises(ValueError):
            build_packet_v2_candidate(admission, capture, profile,
                self.root/"second-candidate", readers, policy_verification=verification)
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.root/"second-candidate").exists())

    def test_R4_native_rename_checks_authority_at_operation_edge(self):
        import ctypes
        from unittest.mock import patch
        from review_broker.pre_model_policy_evidence_retention_v3 import rename_exclusive_policy_tree_v3
        result = self.s.continuation.run(self.s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)
        verification = self.s.stages._inputs[3]
        staging, destination = self.root/"rename-staging", self.root/"rename-destination"
        staging.mkdir(mode=0o700)
        calls = []
        def operation(*args):
            calls.append(args)
            raise AssertionError("rename after authority revocation")
        scenario = self.s
        class Library:
            def __getattr__(self, name):
                if name not in {"renameatx_np", "renameat2"}: raise AttributeError(name)
                scenario.worker.boundary.trusted = False
                return operation
        with patch.object(ctypes, "CDLL", return_value=Library()), self.assertRaises(ValueError):
            rename_exclusive_policy_tree_v3(staging, destination,
                                           before_effect=verification.before_effect)
        self.assertEqual(calls, [])
        self.assertTrue(staging.is_dir())
        self.assertFalse(destination.exists())

    def test_R4_cold_retained_reads_stop_on_journal_movement(self):
        from unittest.mock import patch
        from review_broker.packet_retention_v3 import load_packet_evidence_v3
        result = self.s.continuation.run(self.s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)
        verification = self.s.verification()
        reads, original = [], Path.read_bytes
        def read(path):
            data = original(path)
            if path.is_relative_to(result.retained_root):
                reads.append(path)
                snapshot = verification.snapshot
                transport = self.s.worker.transport
                sha = transport.create_journal_commit(snapshot.commit_sha, snapshot.journal_bytes)
                transport.attributed.add(sha)
                transport.refs[snapshot.claim_ref] = sha
            return data
        with patch.object(Path, "read_bytes", read), self.assertRaisesRegex(ValueError, "JOURNAL_STALE"):
            load_packet_evidence_v3(result.retained_root,
                self.s.worker.admission.journal_admission(), policy_verification=verification)
        self.assertEqual(len(reads), 1)


    def move_journal(self):
        snapshot = self.s.worker.journal.read(self.s.worker.admission.request_id)
        transport = self.s.worker.transport
        sha = transport.create_journal_commit(snapshot.commit_sha, snapshot.journal_bytes)
        transport.attributed.add(sha); transport.refs[snapshot.claim_ref] = sha

    def test_R4_actions_internal_journal_movement_prevents_jobs(self):
        calls, original = [], self.s.authority.reader._executor
        def execute(request):
            result = original(request); calls.append(request)
            self.move_journal()
            return result
        self.s.authority.reader._executor = execute
        result = self.s.continuation.run(self.s.worker.context)
        self.assertIsNone(result.packet_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.s.capture_calls, 0)

    def test_R4_acquisition_copy_then_git_has_separate_guard(self):
        import shutil, subprocess
        from unittest.mock import patch
        tree, run, launches = shutil.copytree, subprocess.run, []
        def copy(*args, **kwargs):
            result = tree(*args, **kwargs)
            if Path(args[1]).name == "source.git": self.s.worker.boundary.trusted = False
            return result
        def execute(*args, **kwargs):
            if "remote" in args[0] and "add" in args[0]: launches.append(args[0])
            return run(*args, **kwargs)
        with patch.object(shutil, "copytree", copy), patch.object(subprocess, "run", execute):
            result = self.s.continuation.run(self.s.worker.context)
        self.assertIsNone(result.packet_id)
        self.assertEqual(launches, [])

    def test_R4_cold_archive_write_then_child_launch_has_separate_guard(self):
        import subprocess, sys
        from unittest.mock import patch
        write, run, launches = Path.write_bytes, subprocess.run, []
        def save(path, data):
            result = write(path, data)
            if path == self.s.transport_archive: self.move_journal()
            return result
        def execute(*args, **kwargs):
            if args[0][0] == sys.executable:
                launches.append(args[0]); raise AssertionError("stale cold launch")
            return run(*args, **kwargs)
        with patch.object(Path, "write_bytes", save), patch.object(subprocess, "run", execute):
            result = self.s.continuation.run(self.s.worker.context)
        self.assertIsNone(result.packet_id)
        self.assertTrue(self.s.transport_archive.exists())
        self.assertEqual(launches, [])

    def metadata_revocation(self, threshold):
        from unittest.mock import patch
        from review_broker.packet_retention_v3 import load_packet_evidence_v3
        result = self.s.continuation.run(self.s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)
        verification, calls, original = self.s.verification(), [], Path.stat
        def stat(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path.is_relative_to(result.retained_root):
                calls.append(path)
                if len(calls) == threshold: self.move_journal()
            return value
        with patch.object(Path, "stat", stat), self.assertRaises(ValueError):
            load_packet_evidence_v3(result.retained_root,
                self.s.worker.admission.journal_admission(), policy_verification=verification)
        self.assertEqual(len(calls), threshold)

    def test_R4_retained_root_metadata_is_an_effect_boundary(self):
        self.metadata_revocation(1)

    def test_R4_retained_file_metadata_is_an_effect_boundary(self):
        self.metadata_revocation(8)


if __name__ == "__main__":
    unittest.main()
