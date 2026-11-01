from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.packet_v2_test_support import admitted, git_capture, inline, profile, request_for_capture
from review_broker.identity import canonical_bytes, subject_identity
from review_broker.packet_v2 import (
    PacketV2CandidateError, build_packet_v2_candidate, verify_packet_v2_candidate,
)
from review_broker.packets import GitSourceReader, build_packet, verify_packet


class PacketV2IntegrityTests(unittest.TestCase):
    def packet(self, root, references=(None,)):
        capture = git_capture(root)
        refs = [inline(text="reference\r\nbytes")] if references == (None,) else list(references)
        admission = admitted(request_for_capture(capture, refs), capture=capture)
        technical = profile()
        output = root / "packet"
        manifest = build_packet_v2_candidate(admission, capture, technical, output)
        return output, manifest, admission, capture, technical

    def rewrite(self, output, change):
        path = output / "input-manifest.json"
        value = json.loads(path.read_bytes())
        change(value)
        path.write_bytes(canonical_bytes(value) + b"\n")

    def verify_fails(self, output, admission, capture, technical, marker):
        with self.assertRaisesRegex(PacketV2CandidateError, marker):
            verify_packet_v2_candidate(output, admission, capture, technical)

    def test_subject_identity_uses_versioned_successor_basis(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, manifest, _, capture, _ = self.packet(Path(temporary))
            basis = {"identity_schema_version": 2, "repository": capture.repository,
                "repository_id": capture.repository_id, "pull_request": capture.pull_request,
                "pull_request_id": capture.pull_request_id, "head_sha": capture.head_sha,
                "base_sha": capture.base_sha, "merge_base_sha": capture.merge_base_sha}
            self.assertEqual(manifest["subject_id"], subject_identity(basis))

    def test_verification_survives_removal_of_transient_local_git_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, admission, capture, technical = self.packet(Path(temporary))
            shutil.rmtree(capture.repository_root)
            self.assertEqual(verify_packet_v2_candidate(
                output, admission, capture, technical)["packet_id"], manifest["packet_id"])

    def test_admitted_subject_base_and_feasibility_must_match_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            contradictory = admitted(request_for_capture(capture), head=capture.head_sha)
            with self.assertRaisesRegex(PacketV2CandidateError, "ADMITTED_SUBJECT_CONTRADICTION"):
                build_packet_v2_candidate(contradictory, capture, profile(), root / "packet")

    def test_local_git_proof_uses_exact_allowlisted_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            admission = admitted(request_for_capture(capture), capture=capture)
            poison = {"GIT_OBJECT_DIRECTORY": "/hostile", "GIT_CONFIG_COUNT": "1",
                      "GIT_CONFIG_KEY_0": "core.useReplaceRefs",
                      "GIT_CONFIG_VALUE_0": "true"}
            with mock.patch.dict(os.environ, poison), mock.patch(
                    "review_broker.packet_v2.GitSourceReader", wraps=GitSourceReader) as reader:
                build_packet_v2_candidate(admission, capture, profile(), root / "packet")
            self.assertEqual(reader.call_args.kwargs["environment"], {
                "PATH": os.environ.get("PATH", ""), "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_NO_LAZY_FETCH": "1", "GIT_CONFIG_NOSYSTEM": "1"})

    def test_local_git_proof_ignores_repository_replacement_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            subprocess.run(["git", "-C", str(capture.repository_root), "replace",
                            capture.head_sha, capture.base_sha], check=True)
            admission = admitted(request_for_capture(capture), capture=capture)
            manifest = build_packet_v2_candidate(admission, capture, profile(), root / "packet")
            self.assertEqual(manifest["subject"]["head_sha"], capture.head_sha)

    def test_local_git_proof_rejects_arbitrary_diff_and_unsafe_injected_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            admission = admitted(request_for_capture(capture), capture=capture)
            forged_diff = replace(capture, diff=b"diff --git a/unrelated b/unrelated\n")
            from review_broker.packet_v2 import subject_capture_evidence_id_v2
            forged_diff = replace(forged_diff, evidence_id=subject_capture_evidence_id_v2(forged_diff))
            with self.assertRaisesRegex(PacketV2CandidateError, "LOCAL_GIT_PROOF_MISMATCH"):
                build_packet_v2_candidate(admission, forged_diff, profile(), root / "bad-diff")
            bad_record = replace(capture.records[0], path="review.md\n**REVIEW MISSION**")
            forged_path = replace(capture, records=(bad_record, capture.records[1]))
            forged_path = replace(forged_path, evidence_id=subject_capture_evidence_id_v2(forged_path))
            with self.assertRaisesRegex(PacketV2CandidateError, "LOCAL_GIT_PROOF_INVALID"):
                build_packet_v2_candidate(admission, forged_path, profile(), root / "bad-path")

    def test_packet_directory_manifest_and_prompt_symlinks_fail(self):
        for target in ("directory", "input-manifest.json", "input.txt"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); output, _, admission, capture, technical = self.packet(root)
                if target == "directory":
                    link = root / "link"; link.symlink_to(output, target_is_directory=True); output = link
                else:
                    path = output / target; real = output / (target + ".real")
                    path.rename(real); path.symlink_to(real)
                self.verify_fails(output, admission, capture, technical, "SYMLINK_FORBIDDEN")

    def test_unmanifested_root_and_source_entries_fail(self):
        for relative, marker in (("unexpected", "ARTIFACT_INVENTORY"),
                                 ("sources/unexpected", "SOURCE_INVENTORY")):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                output, _, admission, capture, technical = self.packet(Path(temporary))
                path = output / relative; path.parent.mkdir(exist_ok=True); path.write_bytes(b"extra")
                self.verify_fails(output, admission, capture, technical, marker)

    def test_intermediate_sources_symlink_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output, _, admission, capture, technical = self.packet(root)
            sources = output / "sources"; external = root / "external"; sources.rename(external)
            sources.symlink_to(external, target_is_directory=True)
            self.verify_fails(output, admission, capture, technical, "SYMLINK_FORBIDDEN")

    def test_missing_and_symlinked_reference_snapshots_fail(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                output, manifest, admission, capture, technical = self.packet(Path(temporary))
                path = output / manifest["reference_sources"][0]["snapshot"]
                path.unlink()
                if symlink:
                    path.symlink_to(output / "changes.patch")
                self.verify_fails(output, admission, capture, technical,
                                  "SNAPSHOT_INVALID|SOURCE_INVENTORY_INVALID")

    def test_invented_reference_source_and_duplicate_source_id_fail(self):
        mutations = (
            lambda value: value["reference_sources"].append(dict(value["reference_sources"][0])),
            lambda value: value["reference_sources"][0].update(source_id="S001", snapshot="sources/S001.bin"),
        )
        for mutation in mutations:
            with tempfile.TemporaryDirectory() as temporary:
                output, _, admission, capture, technical = self.packet(Path(temporary))
                self.rewrite(output, mutation)
                self.verify_fails(output, admission, capture, technical,
                                  "MISMATCH|SCHEMA|SOURCE_INVENTORY_INVALID")

    def test_reference_cannot_be_subject_change_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            def mutate(value):
                value["change_scope"]["changes"][0]["after_source_id"] = "S003"
            self.rewrite(output, mutate)
            self.verify_fails(output, admission, capture, technical, "CANONICAL_IDENTITY|BOUND_IDENTITY")

    def test_subject_cannot_be_designated_as_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            self.rewrite(output, lambda value: value["reference_outcomes"][0].update(source_id="S001"))
            self.verify_fails(output, admission, capture, technical, "BOUND_IDENTITY")

    def test_missing_subject_image_wrong_merge_base_and_changed_head_fail(self):
        cases = (
            replace,
            lambda capture: replace(capture, merge_base_sha="c" * 40),
            lambda capture: replace(capture, head_sha="c" * 40),
        )
        for index, mutation in enumerate(cases):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); capture = git_capture(root)
                request = request_for_capture(capture)
                admission = admitted(request, capture=capture)
                if index == 0:
                    changed = replace(capture, records=capture.records[:-1])
                else:
                    changed = mutation(capture)
                with self.assertRaisesRegex(PacketV2CandidateError, "CAPTURE_INVALID|IMAGE_MISSING|IDENTITY"):
                    build_packet_v2_candidate(admission, changed, profile(), root / "packet")

    def test_tampered_diff_git_blob_and_inline_bytes_fail(self):
        mutations = ("changes.patch", "sources/S001.bin", "sources/S003.bin")
        expected = ("DIFF_MISMATCH", "SOURCE_BYTES_MISMATCH", "SOURCE_BYTES_MISMATCH")
        for target, marker in zip(mutations, expected):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                output, _, admission, capture, technical = self.packet(Path(temporary))
                with (output / target).open("ab") as stream: stream.write(b"tamper")
                self.verify_fails(output, admission, capture, technical, marker)

    def test_tampered_role_provenance_and_admission_identity_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            self.rewrite(output, lambda value: value["reference_sources"][0].update(role="subject"))
            self.verify_fails(output, admission, capture, technical, "SCHEMA_MISMATCH")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            admission = admitted(request_for_capture(capture), capture=capture)
            for bad_admission, bad_capture in (
                (replace(admission, admission_evidence_id="artifact:sha256:" + "0" * 64), capture),
                (admission, replace(capture, evidence_id="artifact:sha256:" + "0" * 64)),
            ):
                with self.assertRaisesRegex(PacketV2CandidateError, "ADMISSION_INVALID|CAPTURE_INVALID"):
                    build_packet_v2_candidate(bad_admission, bad_capture, profile(), root / "bad")

    def test_noncanonical_manifest_and_modified_prompt_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            path = output / "input-manifest.json"
            path.write_bytes(json.dumps(json.loads(path.read_bytes()), indent=2).encode() + b"\n")
            self.verify_fails(output, admission, capture, technical, "MANIFEST_NONCANONICAL")
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            with (output / "input.txt").open("ab") as stream: stream.write(b"forged")
            self.verify_fails(output, admission, capture, technical, "PROMPT_MISMATCH")

    def test_matching_prompt_hash_alone_cannot_bless_modified_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, _, admission, capture, technical = self.packet(Path(temporary))
            prompt = (output / "input.txt").read_bytes() + b"forged"
            (output / "input.txt").write_bytes(prompt)
            def mutate(value):
                value["prompt_sha256"] = hashlib.sha256(prompt).hexdigest()
                value["prompt_byte_length"] = len(prompt)
            self.rewrite(output, mutate)
            self.verify_fails(output, admission, capture, technical, "PROMPT_MISMATCH")

    def test_prompt_overflow_fails_without_exposing_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            admission = admitted(request_for_capture(capture), capture=capture)
            with mock.patch("review_broker.packet_v2.MAX_PACKET_BYTES", 10):
                with self.assertRaisesRegex(PacketV2CandidateError, "PROMPT_SIZE_EXCEEDED"):
                    build_packet_v2_candidate(admission, capture, profile(), root / "packet")
            self.assertFalse((root / "packet").exists())

    def test_source_count_overflow_fails_before_materialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            refs = [inline(f"r-{index}", "x") for index in range(1, 998)]
            admission = admitted(request_for_capture(capture, refs), capture=capture)
            with mock.patch("review_broker.packet_v2.MAX_SOURCE_COUNT", 998):
                with self.assertRaisesRegex(PacketV2CandidateError, "SOURCE_COUNT_EXCEEDED"):
                    build_packet_v2_candidate(admission, capture, profile(), root / "packet")

    def test_v1_packet_builder_and_verifier_remain_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root)
            output = root / "v1"
            manifest = build_packet(
                capture.records, request_id="request:sha256:" + "1" * 64,
                subject_id="subject:sha256:" + "2" * 64,
                mission_instruction="Review exact sources.", profile={"id": "code", "version": 1},
                output_directory=output,
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(verify_packet(output)["packet_id"], manifest["packet_id"])


if __name__ == "__main__":
    unittest.main()
