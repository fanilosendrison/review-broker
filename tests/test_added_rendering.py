"""Real Git additions, complete image custody, and versioned rendering oracles."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from review_broker.identity import canonical_bytes
from review_broker.packets import GitSourceReader, PacketError, SourceSpec, build_packet, verify_packet

FORMAT = "added-source-images-v1"


class AddedRenderingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repository"
        self.git("init", "-q", str(self.repo), cwd=self.root)
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "core.hooksPath", str(self.root / "absent-hooks"))
        (self.repo / "retained.txt").write_bytes(b"retained baseline\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        self.material = {"one.txt": b"unique alpha\r\nsecond\r\n", "two.txt": "unique astral \U0001f680".encode()}
        for name, data in self.material.items():
            (self.repo / name).write_bytes(data)
        self.commit()
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.reader = GitSourceReader(self.repo)
        self.records = [self.reader.read(SourceSpec("sample/repo", self.head, name)) for name in self.material]
        self.changes = [{"status": "added", "path": name, "previous_path": None,
                         "before_source_id": None, "after_source_id": f"S{n:03d}"}
                        for n, name in enumerate(self.material, 1)]
        self.diff = self.reader.diff(self.base, self.head)
        self.sequence = 0

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", "-C", str(cwd or self.repo), *args], stderr=subprocess.PIPE)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "test: retain fixture")

    def build(self, mode=FORMAT, **overrides):
        self.sequence += 1
        output = self.root / f"packet-{self.sequence}"
        arguments = dict(request_id="request:sha256:" + "a" * 64,
                         subject_id="subject:sha256:" + "b" * 64,
                         mission_instruction="Full mission must remain present.",
                         profile={"id": "scientific", "version": 1}, output_directory=output,
                         changes=self.changes, change_diff=self.diff,
                         merge_base=self.base, head=self.head)
        if mode is not None:
            arguments["rendering_format"] = mode
        arguments.update(overrides)
        if mode == FORMAT:
            arguments["added_file_modes"] = self.reader.added_change_modes(arguments["merge_base"], arguments["head"])
        records = arguments.pop("records", self.records)
        return output, build_packet(records, **arguments)

    def test_versioned_compact_custody_identity_and_determinism(self):
        legacy, old = self.build(None)
        compact, manifest = self.build()
        again, repeated = self.build()
        self.assertNotIn("rendering_format", old)
        self.assertEqual(manifest["rendering_format"], FORMAT)
        self.assertNotEqual(old["packet_id"], manifest["packet_id"])
        self.assertEqual(manifest["packet_id"], repeated["packet_id"])
        self.assertEqual((compact / "input.txt").read_bytes(), (again / "input.txt").read_bytes())
        self.assertEqual(old["sources"], manifest["sources"])
        self.assertEqual((compact / "changes.patch").read_bytes(), self.diff)
        self.assertEqual(manifest["change_diff_sha256"], hashlib.sha256(self.diff).hexdigest())
        self.assertEqual(manifest["change_diff_byte_length"], len(self.diff))
        prompt = (compact / "input.txt").read_text()
        self.assertLess(len(prompt), len((legacy / "input.txt").read_text()))
        self.assertIn("Full mission must remain present.", prompt)
        self.assertIn("full diff is retained", prompt)
        self.assertNotIn("EXACT_GIT_DIFF_BEGIN", prompt)
        self.assertIn("EXACT_GIT_DIFF_BEGIN", (legacy / "input.txt").read_text())
        for entry in manifest["sources"]:
            self.assertEqual((compact / entry["snapshot"]).read_bytes(), self.material[entry["path"]])
            self.assertEqual(prompt.count(f"BEGIN SOURCE {entry['source_id']}"), 1)
            self.assertIn(entry["path"], prompt)
        self.assertEqual(prompt.count("unique alpha"), 1)
        self.assertEqual(verify_packet(compact), manifest)
        self.assertEqual(verify_packet(legacy), old)

    def test_single_added_file_is_complete(self):
        base = self.head
        (self.repo / "single.txt").write_bytes(b"single actual addition\n")
        self.commit()
        head = self.git("rev-parse", "HEAD").decode().strip()
        one = [self.reader.read(SourceSpec("sample/repo", head, "single.txt"))]
        changes = [{"status": "added", "path": "single.txt", "previous_path": None,
                    "before_source_id": None, "after_source_id": "S001"}]
        output, manifest = self.build(records=one, changes=changes,
            change_diff=self.reader.diff(base, head), merge_base=base, head=head)
        self.assertEqual(len(verify_packet(output)["sources"]), 1)

    def test_added_paths_with_git_copy_heuristics_and_empty_executable_modes(self):
        material = dict(self.material, **{"copy.txt": b"retained baseline\n", "empty.txt": b""})
        for name in ["copy.txt", "empty.txt"]:
            (self.repo / name).write_bytes(material[name])
            (self.repo / name).chmod(0o755)
        self.commit()
        head = self.git("rev-parse", "HEAD").decode().strip()
        records = [self.reader.read(SourceSpec("sample/repo", head, name)) for name in material]
        changes = [{"status": "added", "path": name, "previous_path": None,
                    "before_source_id": None, "after_source_id": f"S{n:03d}"}
                   for n, name in enumerate(material, 1)]
        diff = self.reader.diff(self.base, head)
        self.assertIn(b"copy from ", diff)
        directory, manifest = self.build(records=records, changes=changes, change_diff=diff, head=head)
        self.assertEqual(verify_packet(directory), manifest)
        self.assertEqual((directory / "changes.patch").read_bytes(), diff)
        self.assertEqual(manifest["added_file_modes"]["copy.txt"], "100755")
        self.assertEqual(manifest["added_file_modes"]["empty.txt"], "100755")

    def test_non_addition_and_mixed_scopes_cannot_select_compact(self):
        for status in ["modified", "removed", "renamed", "copied", "changed", "unsupported"]:
            with self.subTest(status=status):
                changes = copy.deepcopy(self.changes)
                changes[0]["status"] = status
                with self.assertRaises(PacketError):
                    self.build(changes=changes)

    def test_missing_reused_and_duplicate_coverage_is_rejected(self):
        for key, value in [("after_source_id", "S002"), ("after_source_id", "S999"),
                           ("previous_path", "other.txt"), ("before_source_id", "S001"),
                           ("path", "wrong.txt")]:
            with self.subTest(key=key, value=value):
                changes = copy.deepcopy(self.changes)
                changes[0][key] = value
                with self.assertRaises(PacketError):
                    self.build(changes=changes)
        with self.assertRaises(PacketError):
            self.build(changes=self.changes[:1])
        with self.assertRaises(PacketError):
            self.build(records=[self.records[0], self.records[0]])

    def test_git_diff_must_reconstruct_exact_added_objects(self):
        wrong = self.diff.replace(b"unique alpha", b"forged alpha")
        with self.assertRaises(PacketError):
            self.build(change_diff=wrong)
        wrong_changes = copy.deepcopy(self.changes)
        wrong_changes[0]["path"] = "retained.txt"
        with self.assertRaises(PacketError):
            self.build(changes=wrong_changes)

    def test_mutation_of_diff_image_input_or_format_is_rejected(self):
        for target in ["changes.patch", "sources/S001.bin", "input.txt"]:
            with self.subTest(target=target):
                directory, _ = self.build()
                path = directory / target
                path.write_bytes(path.read_bytes() + b"mutated\n")
                with self.assertRaises(PacketError):
                    verify_packet(directory)
        directory, manifest = self.build()
        manifest["rendering_format"] = "unknown-v2"
        (directory / "input-manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
        with self.assertRaises(PacketError):
            verify_packet(directory)

    def test_valid_mixed_modification_uses_legacy_and_cannot_select_compact(self):
        (self.repo / "retained.txt").write_bytes(b"modified baseline\n")
        self.commit()
        head = self.git("rev-parse", "HEAD").decode().strip()
        records = [self.reader.read(SourceSpec("sample/repo", self.base, "retained.txt")),
                   self.reader.read(SourceSpec("sample/repo", head, "retained.txt"))]
        changes = [{"status": "modified", "path": "retained.txt", "previous_path": None,
                    "before_source_id": "S001", "after_source_id": "S002"}]
        for name in self.material:
            records.append(self.reader.read(SourceSpec("sample/repo", head, name)))
            changes.append({"status": "added", "path": name, "previous_path": None,
                            "before_source_id": None, "after_source_id": f"S{len(records):03d}"})
        arguments = dict(records=records, changes=changes, head=head,
                         change_diff=self.reader.diff(self.base, head))
        directory, legacy = self.build(None, **arguments)
        self.assertEqual(verify_packet(directory), legacy)
        self.assertIn("EXACT_GIT_DIFF_BEGIN", (directory / "input.txt").read_text())
        with self.assertRaises(PacketError):
            self.build(**arguments)

    def test_duplicate_source_identifier_is_rejected_by_verification(self):
        directory, manifest = self.build()
        manifest["sources"][1]["source_id"] = "S001"
        (directory / "input-manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
        with self.assertRaises(PacketError):
            verify_packet(directory)

    def test_wrong_commit_and_git_object_identity_fail(self):
        from dataclasses import replace
        for replacement in [replace(self.records[0], commit="f" * 40),
                            replace(self.records[0], git_blob_oid="0" * 40)]:
            with self.assertRaises(PacketError):
                self.build(records=[replacement, self.records[1]])

    def test_preparation_reconstructs_legacy_and_new_prepared_identities(self):
        from review_broker.identity import artifact_identity
        from review_broker.packet_preparation import prepare_packet
        for mode in [None, FORMAT]:
            _, original = self.build(mode)
            self.sequence += 1
            output = self.root / f"recovered-{self.sequence}"
            rebuilt = prepare_packet(
                self.records, request_id=original["request_id"], subject_id=original["subject_id"],
                mission_instruction=original["program"]["mission_instruction"],
                profile=original["program"]["profile"], output_directory=output,
                changes=self.changes, change_diff=self.diff, merge_base=self.base, head=self.head,
                prepared_evidence_ids=(artifact_identity(canonical_bytes(original)),),
                source_reader=self.reader,
            )
            self.assertEqual(rebuilt, original)
            self.assertEqual(verify_packet(output), original)

    def test_format_marker_cannot_be_removed_from_a_new_packet(self):
        directory, manifest = self.build()
        del manifest["rendering_format"]
        (directory / "input-manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
        with self.assertRaises(PacketError):
            verify_packet(directory)


if __name__ == "__main__":
    unittest.main()
