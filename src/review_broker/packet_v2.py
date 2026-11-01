"""Offline construction and full verification of candidate Reviewer Packet v2."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping
from jsonschema import Draft202012Validator
from .admission_evidence_v3 import validate_journal_admission_v3
from .admission_v3 import PreclaimAdmissionV3
from .changes import ChangeScopeError, build_change_basis, validate_change_scope
from .github_issue_reference_v3 import GitHubIssueReferenceReaderV3
from .identity import artifact_identity, canonical_bytes, packet_identity, subject_identity
from .issue_reference_preparation_v3 import prepare_ordered_remote_observations_v3, retained_ordered_remote_observations_v3
from .issue_reference_reconstruction_v3 import reconstruct_issue_observations_v3
from .packet_v2_reference import build_reference_entries_v2
from .packet_v2_renderer import RENDERER_ID, render_packet_v2_prompt
from .packet_v2_subject import SubjectCaptureV2
from .packet_v2_subject_provenance import evidence_basis_v2,manifest_fields_v2,validate_capture_provenance_v2
from .packets import (
    GitSourceReader, MAX_PACKET_BYTES, MAX_SOURCE_BYTES, MAX_SOURCE_COUNT,
    SourceRecord, SourceSpec,
)
from .physical import PhysicalLineError, decode_physical_lines
from .request_v3 import request_identity_v3, validate_request_v3
from .review_intent_v3 import review_intent_identity_v3
from .reviewer_output_contract import CANONICAL_REVIEWER_OUTPUT_INSTRUCTIONS

_SOURCE_ID = re.compile(r"S[0-9]{3}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
class PacketV2CandidateError(ValueError):
    """Candidate packet construction or verification failed closed."""
@dataclass(frozen=True)
class TechnicalProfileSnapshotV2:
    expected_name: str; actual_name: str
    original_bytes: bytes; evidence_id: str
    verification: str = "SYNTHETIC_OFFLINE_VERIFIED"
def _fail(marker: str, cause: BaseException | None = None) -> None:
    if cause is None:
        raise PacketV2CandidateError(marker)
    raise PacketV2CandidateError(marker) from cause
def _hash(prefix: str, value: object) -> str:
    return f"{prefix}:sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"
def _schema() -> dict[str, object]:
    path = resources.files("review_broker.schemas").joinpath("packet-v2.candidate.schema.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("PACKET_V2_SCHEMA_INVALID")
    return value
def _validate_schema(manifest: object) -> dict[str, object]:
    errors = sorted(Draft202012Validator(_schema()).iter_errors(manifest),
                    key=lambda error: [str(part) for part in error.path])
    if errors:
        _fail("PACKET_V2_SCHEMA_MISMATCH")
    return json.loads(canonical_bytes(manifest))
def _admission(admission: PreclaimAdmissionV3) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(admission, PreclaimAdmissionV3):
        _fail("PACKET_V2_ADMISSION_REQUIRED")
    try:
        request = validate_request_v3(admission.request)
        validated = validate_journal_admission_v3(
            admission.journal_admission(), admission.origin_body_bytes)
    except Exception as exc:
        _fail("PACKET_V2_ADMISSION_INVALID", exc)
    if (admission.canonical_request_bytes != canonical_bytes(request)
            or admission.request_id != request_identity_v3(request)
            or admission.review_intent_id != review_intent_identity_v3(request)
            or validated["admission_evidence_id"] != admission.admission_evidence_id):
        _fail("PACKET_V2_ADMISSION_IDENTITY_MISMATCH")
    if request["review_operation"]["kind"] != "initial":
        _fail("PACKET_V2_OPERATION_NOT_QUALIFIED")
    if any(item["source"]["kind"] not in {"inline", "git_file", "github_issue_body", "github_issue_comment"}
           for item in request["references"]):
        _fail("PACKET_V2_REMOTE_REFERENCE_NOT_QUALIFIED")
    return request, validated
def _subject_basis(capture: SubjectCaptureV2) -> dict[str, object]:
    return {
        "repository": capture.repository, "repository_id": capture.repository_id,
        "pull_request": capture.pull_request, "pull_request_id": capture.pull_request_id,
        "head_sha": capture.head_sha, "base_sha": capture.base_sha,
        "merge_base_sha": capture.merge_base_sha,
    }
def subject_capture_evidence_id_v2(capture: SubjectCaptureV2) -> str:
    """Identify exact synthetic capture metadata and bytes without authority inflation."""
    records = [{"repository": item.repository, "commit": item.commit, "path": item.path,
                "git_blob_oid": item.git_blob_oid, "sha256": hashlib.sha256(item.original_bytes).hexdigest()}
               for item in capture.records]
    basis = {**_subject_basis(capture), "changes": list(capture.changes), "records": records,
             "diff_sha256": hashlib.sha256(capture.diff).hexdigest(),
             "verification": capture.verification}
    basis.update(evidence_basis_v2(capture))
    return artifact_identity(canonical_bytes(basis) + b"\n")
def _validate_capture(capture: SubjectCaptureV2, admission: PreclaimAdmissionV3,
                      request: Mapping[str, object], *, prove_local_git: bool) -> None:
    subject = request["subject"]
    if (not isinstance(capture, SubjectCaptureV2)
            or capture.verification not in {"SYNTHETIC_OFFLINE_VERIFIED", "AUTHENTICATED_SOURCE_READ_ONLY"}
            or capture.evidence_id != subject_capture_evidence_id_v2(capture)
            or type(capture.repository_id) is not int or type(capture.pull_request) is not int
            or type(capture.pull_request_id) is not int
            or min(capture.repository_id, capture.pull_request, capture.pull_request_id) < 1
            or any(_SHA.fullmatch(value) is None for value in (
                capture.head_sha, capture.base_sha, capture.merge_base_sha))
            or capture.repository != subject["repository"]
            or capture.repository_id != subject["repository_id"]
            or capture.pull_request != subject["pull_request"]
            or capture.pull_request_id != admission.pull_request_id
            or capture.head_sha != subject["expected_head_commit"]
            or capture.head_sha != admission.head_sha
            or not isinstance(capture.diff, bytes) or not capture.diff
            or not capture.changes or not capture.records):
        _fail("PACKET_V2_SUBJECT_CAPTURE_INVALID")
    paths = [change.get("path") for change in capture.changes]
    if any(not isinstance(path, str) for path in paths) or len(paths) != len(set(paths)):
        _fail("PACKET_V2_CHANGED_PATH_INVENTORY_INVALID")
    admitted_source = json.loads(admission.source_provenance_bytes)
    try: validate_capture_provenance_v2(capture,admitted_source,admission.source_scope_evidence_id)
    except ValueError as exc: _fail(str(exc),exc)
    observed = admitted_source.get("subject_sources")
    captured = [{"source_id": f"S{index:03d}", "original_bytes": len(record.original_bytes),
                 "rendered_bytes": sum(len(line.encode("utf-8")) + 9 for line in record.lines)}
                for index, record in enumerate(capture.records, 1)]
    if admitted_source.get("base_sha") != capture.base_sha or observed != captured:
        _fail("PACKET_V2_ADMITTED_SUBJECT_CONTRADICTION")
    if not prove_local_git:
        return
    try:
        git_environment = {"PATH": os.environ.get("PATH", ""), "GIT_NO_REPLACE_OBJECTS": "1",
                           "GIT_CONFIG_NOSYSTEM": "1"}
        reader = GitSourceReader(capture.repository_root, environment=git_environment)
        reread = tuple(reader.read(SourceSpec(item.repository, item.commit, item.path))
                       for item in capture.records)
        exact = reader.diff(capture.merge_base_sha, capture.head_sha)
        changed_paths = reader.changed_paths(capture.merge_base_sha, capture.head_sha)
        merge_base = reader._git("merge-base", capture.base_sha, capture.head_sha).decode().strip()
        raw = reader._git("diff", "--name-status", "-z", "--find-renames",
                          "--find-copies-harder", capture.merge_base_sha, capture.head_sha, "--")
        parts, inventory, cursor = raw.split(b"\0")[:-1], [], 0
        while cursor < len(parts):
            status = parts[cursor].decode("ascii"); cursor += 1; previous = None
            if status[0] in "RC": previous = parts[cursor].decode("ascii"); cursor += 1
            path = parts[cursor].decode("ascii"); cursor += 1
            kind = {"A": "added", "D": "removed", "M": "modified", "T": "changed",
                    "R": "renamed", "C": "copied"}.get(status[0])
            inventory.append({"status": kind, "path": path, "previous_path": previous})
    except Exception as exc: _fail("PACKET_V2_LOCAL_GIT_PROOF_INVALID", exc)
    if (reread != capture.records or exact != capture.diff or changed_paths != set(paths)
            or merge_base != capture.merge_base_sha or inventory != list(capture.changes)):
        _fail("PACKET_V2_LOCAL_GIT_PROOF_MISMATCH")
def _subject_entries(capture: SubjectCaptureV2) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    entries, changes, cursor = [], [], 0
    for change in capture.changes:
        if not isinstance(change, dict) or set(change) != {"status", "path", "previous_path"}:
            _fail("PACKET_V2_CHANGE_METADATA_INVALID")
        status, path, previous = change["status"], change["path"], change["previous_path"]
        before = after = None
        for image, expected_commit, expected_path, present in (
            ("before", capture.merge_base_sha, previous or path, status != "added"),
            ("after", capture.head_sha, path, status != "removed"),
        ):
            if not present:
                continue
            if cursor >= len(capture.records):
                _fail("PACKET_V2_SUBJECT_IMAGE_MISSING")
            record, source_id = capture.records[cursor], f"S{cursor + 1:03d}"
            if (record.repository != capture.repository or record.commit != expected_commit
                    or record.path != expected_path or len(record.original_bytes) > MAX_SOURCE_BYTES):
                _fail("PACKET_V2_SUBJECT_IMAGE_IDENTITY_MISMATCH")
            entry = {
                "source_id": source_id, "role": "subject", "image": image,
                "repository": record.repository, "commit": record.commit, "path": record.path,
                "git_blob_oid": record.git_blob_oid,
                "sha256": hashlib.sha256(record.original_bytes).hexdigest(),
                "original_byte_length": len(record.original_bytes), "encoding": record.encoding,
                "physical_lines": list(record.physical_lines),
                "snapshot": f"sources/{source_id}.bin",
            }
            entries.append(entry)
            if image == "before": before = source_id
            else: after = source_id
            cursor += 1
        changes.append({"status": status, "path": path, "previous_path": previous,
                        "before_source_id": before, "after_source_id": after})
    if cursor != len(capture.records):
        _fail("PACKET_V2_SUBJECT_IMAGE_INVENTED")
    try:
        validate_change_scope(changes, entries, merge_base=capture.merge_base_sha,
                              head=capture.head_sha)
    except ChangeScopeError as exc:
        _fail(str(exc), exc)
    return entries, changes
def _technical_policy(profile: TechnicalProfileSnapshotV2) -> dict[str, object]:
    if (not isinstance(profile, TechnicalProfileSnapshotV2)
            or profile.verification != "SYNTHETIC_OFFLINE_VERIFIED"
            or not profile.expected_name or profile.actual_name != profile.expected_name
            or not isinstance(profile.original_bytes, bytes)
            or profile.evidence_id != artifact_identity(profile.original_bytes)):
        _fail("PACKET_V2_TECHNICAL_PROFILE_INVALID")
    basis = {"identity_schema_version": 1, "permission_profile_name": profile.actual_name,
             "permission_profile_sha256": hashlib.sha256(profile.original_bytes).hexdigest()}
    return {"technical_policy_id": _hash("technical-policy", basis), "basis": basis,
            "profile_evidence_id": profile.evidence_id,
            "qualification": "SYNTHETIC_OFFLINE_ONLY"}
def _program(request: Mapping[str, object], policy: Mapping[str, object]) -> dict[str, object]:
    return {"mission": request["mission"], "reviewer": request["reviewer"],
            "technical_policy_id": policy["technical_policy_id"],
            "renderer_id": RENDERER_ID,
            "output_instructions": CANONICAL_REVIEWER_OUTPUT_INSTRUCTIONS}
def _packet_basis(manifest: Mapping[str, object]) -> dict[str, object]:
    return {key: manifest[key] for key in (
        "schema_version", "request_id", "review_intent_id", "subject_id",
        "admission_evidence_id", "subject", "atomicity", "change_scope",
        "subject_sources", "reference_sources", "reference_outcomes",
        "technical_policy", "program", "source_manifest_id", "program_id")}
def _exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True); raise
def build_packet_v2_candidate(admission: PreclaimAdmissionV3, capture: SubjectCaptureV2,
                              profile: TechnicalProfileSnapshotV2, output_directory: Path,
                              issue_reference_readers: Mapping[str, GitHubIssueReferenceReaderV3] | None = None) -> dict[str, object]:
    """Build atomically without network, execution, inference, or publication."""
    request, _ = _admission(admission)
    _validate_capture(capture, admission, request, prove_local_git=True)
    subject_sources, changes = _subject_entries(capture)
    remote=prepare_ordered_remote_observations_v3(request,admission,issue_reference_readers)
    reference_sources, outcomes, reference_data = build_reference_entries_v2(
        request, len(subject_sources) + 1, tuple(remote))
    if len(subject_sources) + len(reference_sources) > MAX_SOURCE_COUNT:
        _fail("PACKET_V2_SOURCE_COUNT_EXCEEDED")
    policy = _technical_policy(profile); program = _program(request, policy)
    change_basis, _ = build_change_basis(changes, subject_sources,
        merge_base=capture.merge_base_sha, head=capture.head_sha, diff=capture.diff)
    change_scope = {**change_basis, "diff_snapshot": "changes.patch",
                    "changed_paths": [item["path"] for item in changes]}
    source_manifest = {"subject_sources": subject_sources,
                       "reference_sources": reference_sources,
                       "reference_outcomes": outcomes}
    manifest = {
        "schema_version": 2, "request_id": admission.request_id,
        "review_intent_id": admission.review_intent_id,
        "subject_id": subject_identity({"identity_schema_version": 2, **_subject_basis(capture)}),
        "admission_evidence_id": admission.admission_evidence_id,
        "subject": {**_subject_basis(capture), "source_admission_id": admission.source_admission_id,
                    "subject_capture_evidence_id": capture.evidence_id,
                    "capture_qualification": capture.verification,
                    **manifest_fields_v2(capture)},
        "atomicity": request["atomicity"], "change_scope": change_scope,
        **source_manifest, "technical_policy": policy, "program": program,
        "source_manifest_id": _hash("source-manifest", source_manifest),
        "program_id": _hash("program", program),
    }
    manifest["packet_id"] = packet_identity(_packet_basis(manifest))
    subject_lines = {entry["source_id"]: capture.records[index].lines
                     for index, entry in enumerate(subject_sources)}
    reference_lines = {entry["source_id"]: decode_physical_lines(data)[1]
                       for entry, data in zip(reference_sources, reference_data)}
    prompt = render_packet_v2_prompt(manifest, subject_lines=subject_lines,
                                     reference_lines=reference_lines, diff=capture.diff)
    if len(prompt) > MAX_PACKET_BYTES:
        _fail("PACKET_V2_PROMPT_SIZE_EXCEEDED")
    manifest.update(prompt_sha256=hashlib.sha256(prompt).hexdigest(),
                    prompt_byte_length=len(prompt))
    manifest = _validate_schema(manifest)
    if output_directory.is_symlink() or (output_directory.exists()
            and (not output_directory.is_dir() or any(output_directory.iterdir()))):
        _fail("PACKET_V2_OUTPUT_NOT_EMPTY")
    output_directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".packet-v2-", dir=output_directory.parent))
    try:
        for entry, record in zip(subject_sources, capture.records):
            _exclusive(staging / entry["snapshot"], record.original_bytes)
        for entry, data in zip(reference_sources, reference_data):
            _exclusive(staging / entry["snapshot"], data)
        _exclusive(staging / "changes.patch", capture.diff)
        _exclusive(staging / "input.txt", prompt)
        _exclusive(staging / "input-manifest.json", canonical_bytes(manifest) + b"\n")
        if output_directory.exists(): output_directory.rmdir()
        os.replace(staging, output_directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True); raise
    return manifest
def _read_snapshot(directory: Path, entry: Mapping[str, object], *, git: bool) -> tuple[bytes, tuple[str, ...]]:
    expected = f"sources/{entry['source_id']}.bin"
    if entry.get("snapshot") != expected or Path(expected).is_absolute() or ".." in Path(expected).parts:
        _fail("PACKET_V2_SNAPSHOT_PATH_INVALID")
    path = directory / expected
    if path.is_symlink() or not path.is_file(): _fail("PACKET_V2_SNAPSHOT_INVALID")
    data = path.read_bytes()
    if len(data) != entry["original_byte_length"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        _fail("PACKET_V2_SOURCE_BYTES_MISMATCH")
    try: encoding, lines, mapping = decode_physical_lines(data)
    except PhysicalLineError as exc: _fail("PACKET_V2_SOURCE_ENCODING_INVALID", exc)
    if encoding != entry["encoding"] or list(mapping) != entry["physical_lines"]:
        _fail("PACKET_V2_PHYSICAL_LINES_MISMATCH")
    if git:
        header = b"blob " + str(len(data)).encode() + b"\0" + data
        algorithm = hashlib.sha1 if len(entry["git_blob_oid"]) == 40 else hashlib.sha256
        if algorithm(header).hexdigest() != entry["git_blob_oid"]:
            _fail("PACKET_V2_GIT_BLOB_MISMATCH")
    return data, lines
def verify_packet_v2_candidate(output_directory: Path, admission: PreclaimAdmissionV3,
                               capture: SubjectCaptureV2, profile: TechnicalProfileSnapshotV2,
                               issue_reference_observations: tuple[object,...]=()) -> dict[str, object]:
    """Independently reconstruct every candidate packet identity and byte."""
    manifest_path, prompt_path = output_directory / "input-manifest.json", output_directory / "input.txt"
    if (output_directory.is_symlink() or (output_directory / "sources").is_symlink()
            or manifest_path.is_symlink() or prompt_path.is_symlink()):
        _fail("PACKET_V2_ARTIFACT_SYMLINK_FORBIDDEN")
    try: raw = manifest_path.read_bytes(); manifest = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc: _fail("PACKET_V2_MANIFEST_INVALID", exc)
    if raw != canonical_bytes(manifest) + b"\n": _fail("PACKET_V2_MANIFEST_NONCANONICAL")
    manifest = _validate_schema(manifest)
    if {item.name for item in output_directory.iterdir()} != {
        "input-manifest.json", "input.txt", "changes.patch", "sources"}:
        _fail("PACKET_V2_ARTIFACT_INVENTORY_INVALID")
    expected_snapshots = {entry["snapshot"].split("/")[1] for entry in
                          manifest["subject_sources"] + manifest["reference_sources"]}
    if {item.name for item in (output_directory / "sources").iterdir()} != expected_snapshots:
        _fail("PACKET_V2_SOURCE_INVENTORY_INVALID")
    request, _ = _admission(admission); _validate_capture(
        capture, admission, request, prove_local_git=False)
    if not issue_reference_observations:
        issue_reference_observations=reconstruct_issue_observations_v3(
            output_directory,manifest["reference_sources"],_read_snapshot)
    expected_subject, expected_changes = _subject_entries(capture)
    remote=retained_ordered_remote_observations_v3(request,admission,issue_reference_observations)
    expected_references, expected_outcomes, _ = build_reference_entries_v2(
        request, len(expected_subject) + 1, tuple(remote))
    expected_change, _ = build_change_basis(expected_changes, expected_subject,
        merge_base=capture.merge_base_sha, head=capture.head_sha, diff=capture.diff)
    expected_change.update(diff_snapshot="changes.patch",
                           changed_paths=[item["path"] for item in expected_changes])
    expected_subject_group = {**_subject_basis(capture), "source_admission_id": admission.source_admission_id,
        "subject_capture_evidence_id": capture.evidence_id, "capture_qualification": capture.verification,
        **manifest_fields_v2(capture)}
    if (manifest["request_id"] != admission.request_id
            or manifest["review_intent_id"] != admission.review_intent_id
            or manifest["admission_evidence_id"] != admission.admission_evidence_id
            or manifest["subject_id"] != subject_identity(
                {"identity_schema_version": 2, **_subject_basis(capture)})
            or manifest["subject"] != expected_subject_group
            or manifest["atomicity"] is not request["atomicity"]
            or manifest["change_scope"] != expected_change
            or manifest["subject_sources"] != expected_subject
            or manifest["reference_sources"] != expected_references
            or manifest["reference_outcomes"] != expected_outcomes):
        _fail("PACKET_V2_BOUND_IDENTITY_MISMATCH")
    all_entries = manifest["subject_sources"] + manifest["reference_sources"]
    if [entry["source_id"] for entry in all_entries] != [f"S{i:03d}" for i in range(1, len(all_entries)+1)]:
        _fail("PACKET_V2_SOURCE_ORDER_INVALID")
    subject_lines, reference_lines = {}, {}
    for entry in manifest["subject_sources"]:
        _, subject_lines[entry["source_id"]] = _read_snapshot(output_directory, entry, git=True)
    for entry, reference in zip(manifest["reference_sources"], request["references"]):
        data, reference_lines[entry["source_id"]] = _read_snapshot(output_directory, entry, git=False)
        selector = reference["source"]
        if selector["kind"] == "inline" and data != selector["text"].encode("utf-8"):
            _fail("PACKET_V2_INLINE_REQUEST_MISMATCH")
        if selector["kind"] == "git_file":
            header = b"blob " + str(len(data)).encode() + b"\0" + data
            if hashlib.sha1(header).hexdigest() != entry["git_blob_oid"]:
                _fail("PACKET_V2_REFERENCE_GIT_BLOB_MISMATCH")
            if selector.get("expected_sha256") not in {None, entry["sha256"]}:
                _fail("PACKET_V2_REFERENCE_EXPECTED_DIGEST_MISMATCH")
    try: validate_change_scope(expected_changes, manifest["subject_sources"],
        merge_base=capture.merge_base_sha, head=capture.head_sha)
    except ChangeScopeError as exc: _fail(str(exc), exc)
    diff_path = output_directory / "changes.patch"
    if diff_path.is_symlink() or not diff_path.is_file() or diff_path.read_bytes() != capture.diff:
        _fail("PACKET_V2_DIFF_MISMATCH")
    source_manifest = {key: manifest[key] for key in (
        "subject_sources", "reference_sources", "reference_outcomes")}
    policy, program = _technical_policy(profile), _program(request, _technical_policy(profile))
    if (manifest["source_manifest_id"] != _hash("source-manifest", source_manifest)
            or manifest["technical_policy"] != policy or manifest["program"] != program
            or manifest["program_id"] != _hash("program", program)
            or manifest["packet_id"] != packet_identity(_packet_basis(manifest))):
        _fail("PACKET_V2_CANONICAL_IDENTITY_MISMATCH")
    prompt = render_packet_v2_prompt(manifest, subject_lines=subject_lines,
        reference_lines=reference_lines, diff=capture.diff)
    actual = prompt_path.read_bytes()
    if (actual != prompt or len(actual) != manifest["prompt_byte_length"]
            or hashlib.sha256(actual).hexdigest() != manifest["prompt_sha256"]):
        _fail("PACKET_V2_PROMPT_MISMATCH")
    return manifest
