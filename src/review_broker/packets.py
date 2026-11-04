"""Byte-preserving Git source acquisition and line-addressed packets."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable, Mapping

from .changes import ChangeScopeError, build_change_basis, verify_change_basis
from .identity import canonical_bytes, packet_identity
from .git_change_scope import GitChangeScopeError, added_change_modes
from .physical import PhysicalLineError, decode_physical_lines
from .packet_rendering import render_source as _render_source, render_prompt

MAX_SOURCE_BYTES = 2_000_000
MAX_PACKET_BYTES = 8_000_000
MAX_SOURCE_COUNT = 999  # ReviewerFindings v1 source IDs are S001 through S999.
PATH_PATTERN = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
SHA_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class PacketError(ValueError):
    """A source or packet fails an immutable identity check."""


@dataclass(frozen=True)
class SourceSpec:
    repository: str
    commit: str
    path: str


@dataclass(frozen=True)
class SourceRecord:
    repository: str
    commit: str
    path: str
    git_blob_oid: str
    original_bytes: bytes
    encoding: str
    lines: tuple[str, ...]
    physical_lines: tuple[dict[str, Any], ...]

    @classmethod
    def from_bytes(
        cls,
        repository: str,
        commit: str,
        path: str,
        git_blob_oid: str,
        data: bytes,
    ) -> "SourceRecord":
        encoding, lines, mapping = _decode_physical_lines(data)
        return cls(repository, commit, path, git_blob_oid, data, encoding, lines, mapping)


class GitSourceReader:
    """Read blobs without checking out or executing reviewed repository code."""

    def __init__(self, repository_root: Path, timeout_seconds: int = 30,
                 environment: Mapping[str, str] | None = None):
        self.repository_root = repository_root
        self.timeout_seconds = timeout_seconds
        self.environment = dict(environment) if environment is not None else None

    def _git(self, *arguments: str, input_data: bytes | None = None) -> bytes:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repository_root), *arguments],
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout_seconds,
                shell=False,
                env=self.environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PacketError("GIT_COMMAND_FAILED") from exc
        if result.returncode != 0:
            raise PacketError("GIT_COMMAND_FAILED")
        return result.stdout

    def diff(self, merge_base: str, head: str) -> bytes:
        self._validate_change_commits(merge_base, head)
        data = self._git("diff", "--binary", "--full-index", "--no-ext-diff",
                         "--no-textconv", "--find-renames", "--find-copies-harder",
                         merge_base, head, "--")
        if not data or len(data) > MAX_PACKET_BYTES:
            raise PacketError("CHANGE_DIFF_UNAVAILABLE_OR_TOO_LARGE")
        return data

    def changed_paths(self, merge_base: str, head: str) -> set[str]:
        self._validate_change_commits(merge_base, head)
        raw = self._git("diff", "--name-only", "-z", "--find-renames",
                        "--find-copies-harder", merge_base, head, "--")
        try:
            paths = [part.decode("ascii") for part in raw.split(b"\0")[:-1]]
        except UnicodeDecodeError as exc:
            raise PacketError("CHANGE_PATH_UNSUPPORTED") from exc
        if not raw.endswith(b"\0") or not paths or len(set(paths)) != len(paths):
            raise PacketError("CHANGE_PATH_SET_INVALID")
        return set(paths)

    def added_change_modes(self, merge_base: str, head: str) -> dict[str, str]:
        self._validate_change_commits(merge_base, head)
        try:
            return added_change_modes(self._git, merge_base, head)
        except GitChangeScopeError as exc:
            raise PacketError(str(exc)) from exc

    @staticmethod
    def _validate_change_commits(merge_base: str, head: str) -> None:
        if not SHA_PATTERN.fullmatch(merge_base) or not SHA_PATTERN.fullmatch(head):
            raise PacketError("CHANGE_COMMIT_INVALID")

    def read(self, source: SourceSpec) -> SourceRecord:
        _validate_source_spec(source)
        try:
            actual = self._git("rev-parse", "--verify", source.commit + "^{commit}").decode().strip()
        except PacketError as exc:
            raise PacketError("SOURCE_COMMIT_INVALID") from exc
        if actual != source.commit:
            raise PacketError("SOURCE_COMMIT_MISMATCH")
        try:
            oid = self._git("rev-parse", "--verify", f"{source.commit}:{source.path}").decode().strip()
            if self._git("cat-file", "-t", oid).strip() != b"blob":
                raise PacketError("SOURCE_NOT_BLOB")
            data = self._git("cat-file", "blob", oid)
        except PacketError as exc:
            raise PacketError("SOURCE_MISSING") from exc
        if len(data) > MAX_SOURCE_BYTES:
            raise PacketError("SOURCE_TOO_LARGE")
        calculated = self._git("hash-object", "--stdin", input_data=data).decode().strip()
        if calculated != oid:
            raise PacketError("SOURCE_GIT_BLOB_MISMATCH")
        return SourceRecord.from_bytes(source.repository, source.commit, source.path, oid, data)


def build_packet(
    records: Iterable[SourceRecord],
    *,
    request_id: str,
    subject_id: str,
    mission_instruction: str,
    profile: dict[str, Any],
    output_directory: Path,
    changes: list[dict[str, Any]] | None = None,
    change_diff: bytes | None = None,
    merge_base: str | None = None,
    head: str | None = None,
    rendering_format: str | None = None,
    added_file_modes: dict[str, str] | None = None,
) -> dict[str, Any]:
    records = list(records)
    if not records:
        raise PacketError("PACKET_HAS_NO_SOURCES")
    if len(records) > MAX_SOURCE_COUNT:
        raise PacketError("PACKET_SOURCE_ID_LIMIT")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise PacketError("PACKET_OUTPUT_NOT_EMPTY")
    output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    source_directory = output_directory / "sources"
    source_directory.mkdir(mode=0o700)
    source_entries: list[dict[str, Any]] = []
    rendered: list[str] = []
    for index, record in enumerate(records, 1):
        source_id = f"S{index:03d}"
        snapshot = f"sources/{source_id}.bin"
        original = record.original_bytes
        if len(original) > MAX_SOURCE_BYTES:
            raise PacketError("SOURCE_TOO_LARGE")
        entry = {
            "source_id": source_id,
            "repository": record.repository,
            "commit": record.commit,
            "path": record.path,
            "git_blob_oid": record.git_blob_oid,
            "sha256": hashlib.sha256(original).hexdigest(),
            "original_byte_length": len(original),
            "encoding": record.encoding,
            "physical_lines": list(record.physical_lines),
            "snapshot": snapshot,
        }
        source_entries.append(entry)
        _write_exclusive(output_directory / snapshot, original)
        rendered.append(_render_source(entry, record.lines))
    program = {"mission_instruction": mission_instruction, "profile": profile}
    program_id = _prefixed_hash("program", program)
    source_manifest_id = _prefixed_hash("source-manifest", source_entries)
    basis = {
        "schema_version": 1,
        "request_id": request_id,
        "subject_id": subject_id,
        "program_id": program_id,
        "source_manifest_id": source_manifest_id,
        "sources": source_entries,
    }
    change_text = ""
    if changes is not None:
        if change_diff is None or merge_base is None or head is None:
            raise PacketError("CHANGE_SCOPE_INCOMPLETE")
        try:
            change_basis, change_text = build_change_basis(
                changes, source_entries, merge_base=merge_base, head=head, diff=change_diff,
                rendering_format=rendering_format, image_directory=output_directory,
                added_file_modes=added_file_modes,
            )
        except ChangeScopeError as exc:
            raise PacketError(str(exc)) from exc
        basis.update(change_basis)
    elif (change_diff is not None or merge_base is not None or head is not None
          or rendering_format is not None or added_file_modes is not None):
        raise PacketError("CHANGE_SCOPE_INCOMPLETE")
    packet_id = packet_identity(basis)
    prompt = _render_prompt(
        program,
        packet_id=packet_id,
        request_id=request_id,
        subject_id=subject_id,
        rendered_sources=rendered,
        change_text=change_text,
    )
    if len(prompt) > MAX_PACKET_BYTES:
        raise PacketError("PACKET_EXCEEDS_TRANSPORT_LIMIT")
    manifest = {
        **basis,
        "program": program,
        "packet_id": packet_id,
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
        "prompt_byte_length": len(prompt),
    }
    if change_diff is not None:
        _write_exclusive(output_directory / "changes.patch", change_diff)
    _write_exclusive(output_directory / "input.txt", prompt)
    _write_exclusive(output_directory / "input-manifest.json", canonical_bytes(manifest) + b"\n")
    return manifest


def verify_packet(output_directory: Path) -> dict[str, Any]:
    manifest_path = output_directory / "input-manifest.json"
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest)
    except (OSError, json.JSONDecodeError) as exc:
        raise PacketError("INPUT_MANIFEST_INVALID") from exc
    if raw_manifest != canonical_bytes(manifest) + b"\n":
        raise PacketError("INPUT_MANIFEST_NONCANONICAL")
    entries = manifest.get("sources")
    if not isinstance(entries, list) or not entries:
        raise PacketError("SOURCE_SET_INVALID")
    rendered: list[str] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise PacketError("SOURCE_ENTRY_INVALID")
        source_id = f"S{index:03d}"
        if entry.get("source_id") != source_id or entry.get("snapshot") != f"sources/{source_id}.bin":
            raise PacketError("SOURCE_ENTRY_INVALID")
        path = output_directory / entry["snapshot"]
        if path.is_symlink() or not path.is_file():
            raise PacketError("SOURCE_SNAPSHOT_INVALID")
        data = path.read_bytes()
        if len(data) != entry.get("original_byte_length") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise PacketError("SOURCE_SHA256_MISMATCH")
        if _git_blob_oid(data, entry.get("git_blob_oid", "")) != entry.get("git_blob_oid"):
            raise PacketError("SOURCE_GIT_BLOB_MISMATCH")
        encoding, lines, mapping = _decode_physical_lines(data)
        if encoding != entry.get("encoding") or list(mapping) != entry.get("physical_lines"):
            raise PacketError("PHYSICAL_LINE_MAPPING_MISMATCH")
        if len(lines) != len(mapping):
            raise PacketError("PHYSICAL_LINE_COUNT_MISMATCH")
        rendered.append(_render_source(entry, lines))
    if _prefixed_hash("source-manifest", entries) != manifest.get("source_manifest_id"):
        raise PacketError("SOURCE_MANIFEST_ID_MISMATCH")
    program = manifest.get("program")
    if not isinstance(program, dict) or set(program) != {"mission_instruction", "profile"}:
        raise PacketError("PROGRAM_INVALID")
    if _prefixed_hash("program", program) != manifest.get("program_id"):
        raise PacketError("PROGRAM_ID_MISMATCH")
    basis = {key: manifest[key] for key in (
        "schema_version", "request_id", "subject_id", "program_id", "source_manifest_id", "sources"
    )}
    change_text = ""
    if "changes" not in manifest and ("rendering_format" in manifest or "added_file_modes" in manifest):
        raise PacketError("CHANGE_SCOPE_INCOMPLETE")
    if "changes" in manifest:
        try:
            change_basis, change_text = verify_change_basis(manifest, entries, output_directory)
        except ChangeScopeError as exc:
            raise PacketError(str(exc)) from exc
        basis.update(change_basis)
    if packet_identity(basis) != manifest.get("packet_id"):
        raise PacketError("PACKET_ID_MISMATCH")
    prompt = (output_directory / "input.txt").read_bytes()
    expected_prompt = _render_prompt(
        program,
        packet_id=manifest["packet_id"],
        request_id=manifest["request_id"],
        subject_id=manifest["subject_id"],
        rendered_sources=rendered,
        change_text=change_text,
    )
    if prompt != expected_prompt:
        raise PacketError("PROMPT_CONTENT_MISMATCH")
    if len(prompt) != manifest.get("prompt_byte_length") or hashlib.sha256(prompt).hexdigest() != manifest.get("prompt_sha256"):
        raise PacketError("PROMPT_IDENTITY_MISMATCH")
    return manifest


def assert_complete_scope(expected_paths: Iterable[str], manifest: dict[str, Any]) -> None:
    expected = list(expected_paths)
    actual = ([change.get("path") for change in manifest["changes"]]
              if "changes" in manifest else
              [entry.get("path") for entry in manifest.get("sources", [])])
    if expected != actual:
        raise PacketError("INCOMPLETE_SCOPE")


def source_lines(output_directory: Path, manifest: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    indexed: dict[str, tuple[str, ...]] = {}
    for entry in manifest["sources"]:
        data = (output_directory / entry["snapshot"]).read_bytes()
        _, lines, _ = _decode_physical_lines(data)
        indexed[entry["source_id"]] = lines
    return indexed


def _render_prompt(
    program: dict[str, Any],
    *,
    packet_id: str,
    request_id: str,
    subject_id: str,
    rendered_sources: Iterable[str],
    change_text: str = "",
) -> bytes:
    mission_instruction = program.get("mission_instruction")
    if not isinstance(mission_instruction, str) or not isinstance(program.get("profile"), dict):
        raise PacketError("PROGRAM_INVALID")
    return render_prompt(program, packet_id=packet_id, request_id=request_id,
                         subject_id=subject_id, rendered_sources=rendered_sources,
                         change_text=change_text)


def _decode_physical_lines(data: bytes) -> tuple[str, tuple[str, ...], tuple[dict[str, Any], ...]]:
    try:
        return decode_physical_lines(data)
    except PhysicalLineError as exc:
        raise PacketError(str(exc)) from exc


def _validate_source_spec(source: SourceSpec) -> None:
    if not SHA_PATTERN.fullmatch(source.commit):
        raise PacketError("SOURCE_COMMIT_INVALID")
    if not PATH_PATTERN.fullmatch(source.path) or any(part in (".", "..") for part in source.path.split("/")):
        raise PacketError("SOURCE_PATH_INVALID")


def _git_blob_oid(data: bytes, expected: str) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if len(expected) == 40:
        return hashlib.sha1(header).hexdigest()
    if len(expected) == 64:
        return hashlib.sha256(header).hexdigest()
    return ""


def _prefixed_hash(prefix: str, value: Any) -> str:
    return f"{prefix}:sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
