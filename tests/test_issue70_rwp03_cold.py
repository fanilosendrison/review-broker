"""Authorized four-reference packet and independent fresh-process verification."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib
import json
import os
from pathlib import Path
import shutil
from contextlib import ExitStack
import tempfile
import unittest
from unittest.mock import patch

from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.packet_retention_v3 import load_packet_evidence_v3, persist_packet_evidence_v3
from review_broker.packet_v2 import build_packet_v2_candidate, verify_packet_v2_candidate
from review_broker.packet_v2_technical_policy import AuthorizedPolicySnapshotV3
from review_broker.pre_model_policy_selection_v3 import PolicySelectionReceiptV3
from tests.issue70_rwp03_test_support import (
    CONTENT_ID, RealContinuationScenario, ArchivedSelectionAuthority,
)


class AuthorizedColdTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scenario = RealContinuationScenario(self.root)

    def complete(self):
        s = self.scenario
        result = s.continuation.run(s.worker.context)
        self.assertEqual(result.status.value, "COMMITTED", result.reason)
        self.assertIsNotNone(result.packet_id)
        self.result = result
        self.verification = s.verification()
        self.retained = result.retained_root
        self.admission, self.capture, self.profile, self.manifest = load_packet_evidence_v3(
            self.retained, s.worker.admission.journal_admission(),
            policy_verification=self.verification)
        return result

    def reload(self):
        return load_packet_evidence_v3(self.retained, self.admission.journal_admission(),
                                       policy_verification=self.verification)

    def test_N06_authorized_four_reference_packet_full_verification(self):
        self.complete()
        self.assertEqual(self.manifest["technical_policy"]["qualification"],
                         "PREMODEL_POLICY_SOURCE_VERIFIED_ONLY")
        self.assertEqual(self.manifest["technical_policy"]["technical_policy_id"], CONTENT_ID)
        self.assertEqual([r["source_kind"] for r in self.manifest["reference_sources"]],
                         ["inline", "git_file", "github_issue_body", "github_issue_comment"])
        self.assertFalse((self.retained/"evidence/technical-profile.bin").exists())
        self.assertEqual(self.scenario.capture_calls, 1)
        self.assertEqual(self.scenario.worker.journal.read(self.admission.request_id).record.attempt.state.value,
                         "ADMITTED")
        self.assertEqual(self.scenario.continuation.run(self.scenario.worker.context).reason,
                         "OBSERVER_ONLY_NO_RETRY")

    def test_N08_competing_continuations_have_one_complete_attributed_winner(self):
        from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
        s = self.scenario
        first = s.continuation
        second = PreModelPacketContinuationV3(
            journal=s.worker.journal, current_worker_authority=s.authority,
            original_admission=s.worker.admission, capture_provider=s,
            reference_readers=s.reference_readers, policy_source_authority=s.source_authority,
            policy_selection_authority=s.selection_authority, packet_stages=s.stages)
        s.worker.transport.identical_commits = True
        s.worker.transport.update_barrier = Barrier(2, timeout=10)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda component: component.run(s.worker.context), (first, second)))
        self.assertEqual(sum(result.status.value == "COMMITTED" for result in results), 1)
        self.assertEqual(sum(result.packet_id is not None for result in results), 1)
        self.assertEqual(s.capture_calls, 1)
        self.assertEqual(s.worker.journal.read(s.worker.admission.request_id).record.attempt.state.value,
                         "ADMITTED")

    def test_N07_fresh_process_cold_reconstruction_after_worker_memory_removed(self):
        self.complete()
        s = self.scenario
        s.stages._inputs = None
        shutil.rmtree(s.inputs.capture.repository_root)
        shutil.rmtree(self.root/"continued-source")
        self.assertEqual(s.cold(self.retained, self.verification.snapshot), self.manifest)

    def test_N04_same_policy_different_authorized_selection_changes_packet_id(self):
        self.complete()
        changed = replace(self.profile.selection,
                          decision_authority_evidence_id=artifact_identity(b"second-independent-decision"))
        archive = self.root/"second-independent-decision.json"
        archive.write_bytes(changed.canonical_receipt_bytes)
        verifier = replace(self.verification, selection_authority=ArchivedSelectionAuthority(archive))
        profile = replace(self.profile, selection=changed)
        manifest = build_packet_v2_candidate(self.admission, self.scenario.inputs.capture,
            profile, self.root/"second-packet", self.scenario.inputs.issue_readers,
            policy_verification=verifier)
        self.assertEqual(manifest["technical_policy"]["technical_policy_id"], CONTENT_ID)
        self.assertNotEqual(manifest["packet_id"], self.manifest["packet_id"])

    def test_N03_historical_synthetic_packet_is_byte_identical_to_base(self):
        from tests.packet_v2_test_support import profile
        # Independent immutable oracle generated using the exact base implementation
        # 60faf3fc892321f6887572402f189215f222ea6d, whose packet_v2.py SHA-256 is
        # 4e7f14fe0ea7e0fa8b1a45bfbb7291401075e1619a4b59162fdce28c8eac48c3.
        # Never regenerate this oracle from candidate output. No historical Git
        # objects or network access are required in a shallow CI checkout.
        expected = {
            "changes.patch": "6fac6d8810ecee7bf674bf673f5a91e1c6827324dc6461a539a1a34293ef6db4",
            "input-manifest.json": "4620992cbacfc137ef16d867413f05b94125683925d0971475f4482cc73a4ebf",
            "input.txt": "3054ba54ae873677b07fa2986bc44b616006ef5bd225aee3285d8048c6f6a6fe",
            "sources/S001.bin": "a6456ed3bde94789512c42c563637b929da22b9b5611962bd2c8ff63343d8195",
            "sources/S002.bin": "7b9a72466d3960eb2aacccfc848939453490db0678bd4725def3f789b891c919",
            "sources/S003.bin": "404e8f6684e7b3ec413e8bbb0c3d2100000717e7d301827836525145945a152c",
            "sources/S004.bin": "4f85d1b0cff7bb76f0c9a58366030c6dc1eb8e1243e3709c72452278ddce7c13",
            "sources/S005.bin": "2e599d46723a6e7f099e12d2bd8f8b8d77a2e043fde6f9a9c8149b204360b2b2",
            "sources/S006.bin": "038b5e1a18d4c8097abfe67baf4ee19e1d1ea5f646d537fc0795df7a2c5f6e30",
        }
        s, output = self.scenario.inputs, self.root/"synthetic-current"
        manifest = build_packet_v2_candidate(s.admission, s.capture, profile(), output, s.issue_readers)
        actual = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in output.rglob("*") if path.is_file()}
        self.assertEqual(actual, expected)
        self.assertEqual(manifest["packet_id"],
                         "packet:sha256:cbeb6096002da9fdd16f731f569c89f2e1c7d409474eabf8a194e51450429584")
        schema = json.loads((Path(__file__).resolve().parents[1]/
            "src/review_broker/schemas/packet-v2.candidate.schema.json").read_bytes())
        self.assertEqual(hashlib.sha256(canonical_bytes(schema["$defs"]["syntheticTechnicalPolicy"])).hexdigest(),
                         "a80872216b5666d6990ce274b571c618f38016920328dd1d8daa5598c2e0509f")

    def test_F31_pr_head_drift_changed_merge_base_or_invalid_diff(self):
        s = self.scenario
        api = s.inputs.pr_reader._executor
        api.drift_head = "9" * 40
        result = s.continuation.run(s.worker.context)
        self.assertNotEqual(result.status.value, "COMMITTED")
        self.assertIsNone(result.packet_id)
        self.complete_separate_fixture()
        for change in ({"merge_base_sha": "9" * 40}, {"diff": b"invented diff\n"}):
            changed = replace(self.capture, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_packet_v2_candidate(self.retained/"packet", self.admission,
                    changed, self.profile, policy_verification=self.verification)

    def complete_separate_fixture(self):
        root = self.root/"separate"
        root.mkdir()
        self.scenario = RealContinuationScenario(root)
        self.complete()

    def test_F32_changed_required_references_and_lost_order(self):
        self.complete()
        for entry in self.manifest["reference_sources"]:
            path = self.retained/"packet"/entry["snapshot"]
            data = path.read_bytes()
            path.write_bytes(data + b"changed")
            with self.subTest(kind=entry["source_kind"]), self.assertRaises(ValueError):
                self.reload()
            path.write_bytes(data)
        path = self.retained/"packet/input-manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["reference_sources"].reverse()
        path.write_bytes(canonical_bytes(manifest)+b"\n")
        with self.assertRaises(ValueError):
            self.reload()

    def test_F32_incomplete_source_pagination_prevents_packet(self):
        s = self.scenario
        s.inputs.pr_reader._executor.files_total = 2
        result = s.continuation.run(s.worker.context)
        self.assertNotEqual(result.status.value, "COMMITTED")
        self.assertIsNone(result.packet_id)
        self.assertFalse((self.root/"retained").exists())

    def test_F33_source_bytes_modified_between_capture_and_verification(self):
        self.complete()
        entry = self.manifest["subject_sources"][0]
        path = self.retained/"packet"/entry["snapshot"]
        path.write_bytes(b"changed\n")
        with self.assertRaises(ValueError):
            self.reload()

    def test_F34_missing_or_substituted_policy_evidence(self):
        self.complete()
        for name in ("expected-policy.bin", "policy-source-observation.json", "policy-selection-receipt.json"):
            path = self.retained/"evidence"/name
            original = path.read_bytes()
            with self.subTest(name=name, change="missing"):
                path.unlink()
                with self.assertRaises((ValueError, OSError)):
                    self.reload()
                path.write_bytes(original)
                path.chmod(0o600)
            with self.subTest(name=name, change="substitution"):
                path.write_bytes(b"substituted\n")
                with self.assertRaises((ValueError, OSError)):
                    self.reload()
                path.write_bytes(original)

    def test_F35_cold_reconstruction_without_independent_trust(self):
        self.complete()
        with self.assertRaises(ValueError):
            load_packet_evidence_v3(self.retained, self.admission.journal_admission())
        for field in ("source_authority", "selection_authority"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_packet_evidence_v3(self.retained, self.admission.journal_admission(),
                    policy_verification=replace(self.verification, **{field: None}))

    def test_F36_inventory_permissions_symlink_prompt_manifest(self):
        self.complete()
        for target in ("evidence/unexpected.bin", "packet/unexpected.bin", "packet/sources/unexpected.bin"):
            path = self.retained/target
            path.write_bytes(b"unexpected")
            path.chmod(0o600)
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.reload()
            path.unlink()
        for target in (".", "packet/sources", "evidence/expected-policy.bin", "packet/input.txt"):
            path = self.retained/target
            mode = path.stat().st_mode & 0o777
            path.chmod(0o755 if path.is_dir() else 0o644)
            with self.subTest(mode=target), self.assertRaises(ValueError):
                self.reload()
            path.chmod(mode)
        for target in ("evidence/policy-source-observation.json", "packet/input.txt", "packet/input-manifest.json"):
            path = self.retained/target
            original = path.read_bytes()
            alternate = self.root/"alternate"
            alternate.write_bytes(original)
            alternate.chmod(0o600)
            path.unlink()
            path.symlink_to(alternate)
            with self.subTest(symlink=target), self.assertRaises(ValueError):
                self.reload()
            path.unlink()
            path.write_bytes(original)
            path.chmod(0o600)
            path.write_bytes(original + b" ")
            with self.subTest(altered=target), self.assertRaises(ValueError):
                self.reload()
            path.write_bytes(original)

    def test_authority_loss_or_journal_movement_after_capture_prevents_packet(self):
        for mode in ("authority", "journal"):
            root = self.root/mode
            root.mkdir()
            s = RealContinuationScenario(root)
            original = s.capture
            def capture(admission, guard):
                result = original(admission, guard)
                if mode == "authority":
                    s.worker.boundary.trusted = False
                else:
                    snapshot = s.worker.journal.read(admission.request_id)
                    sha = s.worker.transport.create_journal_commit(snapshot.commit_sha, snapshot.journal_bytes)
                    s.worker.transport.attributed.add(sha)
                    s.worker.transport.refs[snapshot.claim_ref] = sha
                return result
            s.capture = capture
            with self.subTest(mode=mode):
                result = s.continuation.run(s.worker.context)
                self.assertNotEqual(result.status.value, "COMMITTED")
                self.assertIsNone(result.packet_id)
                self.assertFalse((root/"candidate").exists())
                self.assertFalse((root/"retained").exists())

    def test_F36_prohibited_external_effects_are_absent(self):
        targets = (
            "review_broker.github_journal_v3.GitHubJournalV3.prepare",
            "review_broker.packet_preparation_authority_v3.prepare_packet_receipt_v3",
            "review_broker.packet_preparation_authority_v3.RetainedPacketAuthorityV3.permits",
            "review_broker.codex.invoke_once",
            "socket.socket.connect",
        )
        with ExitStack() as stack:
            forbidden = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                         for target in targets]
            self.complete()
            for call in forbidden:
                call.assert_not_called()

    def test_interruption_before_after_each_policy_evidence_write(self):
        names = ("expected-policy.bin", "policy-source-observation.json", "policy-selection-receipt.json")
        for index, (name, after) in enumerate((name, after) for name in names for after in (False, True)):
            with self.subTest(name=name, after=after):
                root = self.root/f"interruption-{index}"
                root.mkdir()
                s = RealContinuationScenario(root)
                opened = {}
                original_open, original_fsync = os.open, os.fsync
                def interrupt_open(path, *args, **kwargs):
                    if Path(path).name == name and not after:
                        raise RuntimeError("fixture interruption before evidence write")
                    fd = original_open(path, *args, **kwargs)
                    opened[fd] = Path(path).name
                    return fd
                def interrupt_sync(fd):
                    original_fsync(fd)
                    if opened.get(fd) == name and after:
                        raise RuntimeError("fixture interruption after evidence write")
                with patch("os.open", interrupt_open), patch("os.fsync", interrupt_sync):
                    result = s.continuation.run(s.worker.context)
                self.assertNotEqual(result.status.value, "COMMITTED")
                self.assertIsNone(result.packet_id)
                from review_broker.packet_retention_v3 import packet_retention_locator_v3
                locator = packet_retention_locator_v3(root/"retained", result.journal_outcome.snapshot.claim_ref)
                self.assertFalse(locator.exists())
                self.assertEqual(s.continuation.run(s.worker.context).reason, "OBSERVER_ONLY_NO_RETRY")
                self.assertEqual(s.worker.transport.events.count("ADMITTED"), 1)

    def test_closed_packet_schema_rejects_mixed_or_incomplete_policy_variants(self):
        from jsonschema import Draft202012Validator
        self.complete()
        schema = json.loads((Path(__file__).resolve().parents[1]/
            "src/review_broker/schemas/packet-v2.candidate.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for change in ("missing-source", "missing-selection", "extra", "synthetic-promotion"):
            manifest = json.loads(canonical_bytes(self.manifest))
            policy = manifest["technical_policy"]
            if change == "missing-source":
                del policy["policy_source_evidence_id"]
            elif change == "missing-selection":
                del policy["selection_authorization_evidence_id"]
            elif change == "extra":
                policy["authorized"] = True
            else:
                policy["qualification"] = "SYNTHETIC_OFFLINE_ONLY"
            with self.subTest(change=change):
                self.assertFalse(validator.is_valid(manifest))

    def test_authorized_profile_instance_without_verifier_cannot_promote(self):
        self.complete()
        with self.assertRaises(ValueError):
            verify_packet_v2_candidate(self.retained/"packet", self.admission, self.capture, self.profile)

    def test_existing_destination_never_overwritten(self):
        self.complete()
        with self.assertRaises(ValueError):
            persist_packet_evidence_v3(self.admission, self.capture, self.profile,
                self.scenario.root/"retained", self.verification.snapshot, self.verification.journal,
                policy_verification=self.verification, candidate_directory=self.root/"candidate")
        self.assertEqual(self.reload()[3], self.manifest)


if __name__ == "__main__":
    unittest.main()
