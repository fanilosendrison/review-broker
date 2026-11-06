"""Bounded ZIP data handling with private creation modes and exact inventory checks."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import stat
import zipfile

from .identity import artifact_identity, canonical_bytes
from .packet_preparation_authority_v3 import retained_inventory_v3
from .prepared_artifact_transport_v3 import BeforeEffectV3, PreparedArtifactBudgetV3


def _path(name: str, directory: bool) -> str:
    if (not name or "\\" in name or "\x00" in name or ":" in name
            or name.startswith("/") or name.endswith("//")):
        raise ValueError("PREPARED_ZIP_PATH_INVALID")
    normalized = name[:-1] if directory and name.endswith("/") else name
    parts = normalized.split("/")
    if (any(p in {"", ".", ".."} for p in parts)
            or parts[0] not in {"packet", "evidence"}
            or len(parts) == 1 and not directory):
        raise ValueError("PREPARED_ZIP_PATH_INVALID")
    return normalized


def archive_packet_v3(root: Path, inventory: dict[str, object],
                      budget: PreparedArtifactBudgetV3, before_effect: BeforeEffectV3) -> bytes:
    """Exact bytes from a verified tree, guarded at each file read and ZIP write."""
    if len(inventory["files"]) > budget.max_members:
        raise ValueError("PREPARED_ZIP_MEMBER_BUDGET")
    output, total = io.BytesIO(), 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for entry in inventory["files"]:
            name = _path(entry["path"], False)
            if total + entry["byte_length"] > budget.max_uncompressed_bytes:
                raise ValueError("PREPARED_ZIP_UNCOMPRESSED_BUDGET")
            before_effect()
            with (root / name).open("rb", buffering=0) as source:
                chunks, count = [], 0
                limit = min(entry["byte_length"], budget.max_uncompressed_bytes - total)
                while True:
                    before_effect()
                    chunk = source.read(min(65536, limit - count + 1))
                    if not chunk: break
                    count += len(chunk)
                    if count > limit: raise ValueError("PREPARED_UPLOAD_ACTUAL_BYTES_EXCEEDED")
                    chunks.append(chunk)
                data = b"".join(chunks)
            total += len(data)
            if total > budget.max_uncompressed_bytes:
                raise ValueError("PREPARED_ZIP_UNCOMPRESSED_BUDGET")
            if len(data) != entry["byte_length"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("PREPARED_UPLOAD_INVENTORY_CHANGED")
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            before_effect()
            bundle.writestr(info, data)
            if output.tell() > budget.max_archive_bytes:
                raise ValueError("PREPARED_ZIP_ARCHIVE_BUDGET")
        before_effect()
    raw = output.getvalue()
    if len(raw) > budget.max_archive_bytes:
        raise ValueError("PREPARED_ZIP_ARCHIVE_BUDGET")
    return raw


def extract_prepared_packet_v3(raw: bytes, destination: Path, budget: PreparedArtifactBudgetV3,
                               before_effect: BeforeEffectV3, *, expected_inventory=None, failure_observer=None):
    if type(raw) is not bytes or not raw or len(raw) > budget.max_archive_bytes:
        raise ValueError("PREPARED_ZIP_ARCHIVE_BUDGET")
    before_effect()
    destination.mkdir(mode=0o700)  # Fresh private child of a trusted private parent.
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        infos = bundle.infolist()
        if len(infos) > budget.max_members:
            raise ValueError("PREPARED_ZIP_MEMBER_BUDGET")
        entries, kinds, announced = [], {}, 0
        for info in infos:
            directory = info.is_dir()
            name = _path(info.orig_filename, directory)
            if info.orig_filename != info.filename or name in kinds:
                raise ValueError("PREPARED_ZIP_DUPLICATE_OR_ALIAS")
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in ({0, stat.S_IFDIR} if directory else {0, stat.S_IFREG}):
                raise ValueError("PREPARED_ZIP_SPECIAL_MEMBER")
            if info.flag_bits & 1 or directory and info.file_size != 0:
                raise ValueError("PREPARED_ZIP_MEMBER_INVALID")
            kinds[name] = directory
            entries.append((info, name, directory))
            announced += info.file_size
            if announced > budget.max_uncompressed_bytes:
                raise ValueError("PREPARED_ZIP_UNCOMPRESSED_BUDGET")
        for _, name, _ in entries:
            parents = Path(name).parents
            if any(kinds.get(p.as_posix()) is False for p in parents if str(p) != "."):
                raise ValueError("PREPARED_ZIP_FILE_DIRECTORY_COLLISION")
        expected_files = None if expected_inventory is None else {
            entry["path"] for entry in expected_inventory["files"]}
        if expected_files is not None and {name for _, name, is_dir in entries if not is_dir} != expected_files:
            raise ValueError("PREPARED_ZIP_CLOSED_INVENTORY_MISMATCH")
        actual = 0
        def mkdir(path):
            if path == destination: return
            mkdir(path.parent)
            before_effect()
            if path.exists():
                before_effect()
                if not path.is_dir() or path.is_symlink():
                    raise ValueError("PREPARED_ZIP_PARENT_COLLISION")
                return
            before_effect()
            path.mkdir(mode=0o700)
        for info, name, directory in entries:
            target = destination / name
            if directory:
                mkdir(target)
                continue
            mkdir(target.parent)
            before_effect()
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb", buffering=0) as output:
                before_effect()
                with bundle.open(info) as source:
                    written = 0
                    while True:
                        before_effect()
                        chunk = source.read(min(65536, budget.max_uncompressed_bytes - actual + 1))
                        if not chunk: break
                        actual += len(chunk)
                        written += len(chunk)
                        if actual > budget.max_uncompressed_bytes or written > info.file_size:
                            raise ValueError("PREPARED_ZIP_ACTUAL_EXPANSION_BUDGET")
                        before_effect()
                        output.write(chunk)
                    if written != info.file_size:
                        raise ValueError("PREPARED_ZIP_MEMBER_TRUNCATED")
        # This is structural, never a fabricated missing file.
        mkdir(destination / "evidence/admitted-references")
    before_effect()
    actual_inventory = retained_inventory_v3(destination, before_effect=before_effect)
    if expected_inventory is not None and actual_inventory != expected_inventory:
        if failure_observer is not None:
            failure_observer.verification_failed("INVENTORY", inventory_identity_v3(expected_inventory),
                inventory_identity_v3(actual_inventory), extract_prepared_packet_v3,
                (destination, expected_inventory, actual_inventory))
        raise ValueError("PREPARED_ZIP_CONTENT_IDENTITY_MISMATCH")
    return actual_inventory


def inventory_identity_v3(inventory: dict[str, object]) -> str:
    return artifact_identity(canonical_bytes(inventory) + b"\n")
