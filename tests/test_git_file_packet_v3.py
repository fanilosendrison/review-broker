from dataclasses import replace
from functools import partial
import hashlib
from pathlib import Path
import tempfile
import unittest

from tests.packet_v2_test_support import admitted, git_capture, inline, profile, request_for_capture
from tests.test_github_git_file_v3 import Api, COMMIT, DATA, reader
from tests.issue69_test_support import source_authority
from review_broker.admission_v3 import AdmissionV3CandidateError
from review_broker.packet_v2 import PacketV2CandidateError, build_packet_v2_candidate, verify_packet_v2_candidate


def git_ref(identifier="contract", *, commit=COMMIT, expected=None, required=True):
    source = {"kind": "git_file", "repository": "fanilosendrison/review-broker",
              "path": "contract.md", "commit": commit}
    if expected is not None: source["expected_sha256"] = expected
    return {"id": identifier, "required": required, "source": source}


class GitFilePacketIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.source = source_authority()
        self.reader = partial(reader, source=self.source)
        self.admitted = partial(admitted, source_authority_override=self.source)

    def build(self, root, refs, *, atomicity=False, api=None):
        capture = git_capture(root, source_authority_override=self.source); request = request_for_capture(capture, refs, atomicity=atomicity)
        readers = {item["id"]: self.reader(api or Api()) for item in refs if item["source"]["kind"] == "git_file"}
        admission = self.admitted(request, capture=capture, git_file_readers=readers)
        output = root / "packet"; manifest = build_packet_v2_candidate(admission, capture, profile(), output)
        verify_packet_v2_candidate(output, admission, capture, profile())
        return output, manifest, admission, capture

    def test_mixed_inline_and_git_file_preserves_declared_order_and_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, admission, _ = self.build(Path(temporary),
                [inline("note", "inline\n"), git_ref(expected=hashlib.sha256(DATA).hexdigest())])
            refs = manifest["reference_sources"]
            self.assertEqual([(item["reference_id"], item["source_kind"]) for item in refs],
                             [("note", "inline"), ("contract", "git_file")])
            self.assertEqual([item["source_id"] for item in refs], ["S003", "S004"])
            self.assertEqual((output / "sources/S004.bin").read_bytes(), DATA)
            self.assertEqual(refs[1]["provenance_evidence_id"], admission.git_file_observations[0].evidence_id)
            prompt = (output / "input.txt").read_text()
            self.assertIn("SOURCE_KIND=git_file", prompt); self.assertIn("GIT_BLOB_OID=", prompt)

    def test_multiple_git_files_same_bytes_remain_distinct_ordered_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            refs = [git_ref("first"), git_ref("second")]
            _, manifest, *_ = self.build(Path(temporary), refs)
            self.assertEqual([item["reference_id"] for item in manifest["reference_sources"]],
                             ["first", "second"])
            self.assertEqual(manifest["reference_sources"][0]["sha256"],
                             manifest["reference_sources"][1]["sha256"])

    def test_atomicity_true_requires_subject_head_and_false_allows_exact_h2(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root, source_authority_override=self.source)
            request = request_for_capture(capture, [git_ref()], atomicity=True)
            with self.assertRaisesRegex(AdmissionV3CandidateError, "ATOMICITY_HEAD_MISMATCH"):
                self.admitted(request, capture=capture, git_file_readers={"contract": self.reader(Api())})
        with tempfile.TemporaryDirectory() as temporary:
            _, manifest, *_ = self.build(Path(temporary), [git_ref()], atomicity=False)
            self.assertFalse(manifest["atomicity"])

    def test_tampered_observation_or_snapshot_rejects_entire_packet(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output, _, admission, capture = self.build(root, [git_ref()])
            (output / "sources/S003.bin").write_bytes(b"replacement")
            with self.assertRaisesRegex(PacketV2CandidateError, "SOURCE_BYTES_MISMATCH"):
                verify_packet_v2_candidate(output, admission, capture, profile())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root, source_authority_override=self.source); request = request_for_capture(capture, [git_ref()])
            admission = self.admitted(request, capture=capture, git_file_readers={"contract": self.reader(Api())})
            observation = replace(admission.git_file_observations[0], path="other.md")
            forged = replace(admission, git_file_observations=(observation,))
            with self.assertRaisesRegex(PacketV2CandidateError, "ADMISSION_INVALID"):
                build_packet_v2_candidate(forged, capture, profile(), root / "packet")

    def test_git_file_rendered_size_is_rejected_at_preclaim_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root, source_authority_override=self.source); request = request_for_capture(capture, [git_ref()])
            with self.assertRaisesRegex(AdmissionV3CandidateError, "EVENTUAL_RENDERED_PACKET_EXCEEDED"):
                self.admitted(request, capture=capture,
                         git_file_readers={"contract": self.reader(Api(data=b"\n" * 900_000))})

    def test_reader_subclass_cannot_cross_trusted_acquisition_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root, source_authority_override=self.source); request = request_for_capture(capture, [git_ref()])
            trusted = self.reader(Api())
            class ForgedReader(type(trusted)):
                def observe(self, *args, **kwargs): return trusted.observe(*args, **kwargs)
            forged = ForgedReader("token", trusted.repository, trusted.repository_id,
                authority_evidence_id=trusted.authority_evidence_id,
                source_authority=self.source, executor=Api())
            with self.assertRaisesRegex(AdmissionV3CandidateError, "TRUSTED_READER_REQUIRED"):
                self.admitted(request, capture=capture, git_file_readers={"contract": forged})

    def test_missing_optional_git_file_is_not_omitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); capture = git_capture(root, source_authority_override=self.source)
            request = request_for_capture(capture, [git_ref(required=False)])
            with self.assertRaisesRegex(AdmissionV3CandidateError, "OBSERVATION_UNAVAILABLE"):
                self.admitted(request, capture=capture,
                         git_file_readers={"contract": self.reader(Api(status=404))})


    def test_historical_qualification_observation_cannot_enter_production_admission(self):
        from review_broker.github_git_file_v3 import GitHubGitFileReaderV3
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = git_capture(root, source_authority_override=self.source)
            request = request_for_capture(capture, [git_ref()])
            qualified = GitHubGitFileReaderV3("token", capture.repository, capture.repository_id,
                authority_evidence_id=self.source.authorize(capture.repository, capture.repository_id).evidence_id,
                qualification_only=True, expected_installation_id=123, executor=Api())
            with self.assertRaisesRegex(AdmissionV3CandidateError, "GIT_FILE_SOURCE_AUTHORITY_MISMATCH"):
                self.admitted(request, capture=capture, git_file_readers={"contract": qualified})


if __name__ == "__main__": unittest.main()
