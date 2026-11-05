"""Canonical candidate manifest validation and snapshot path confinement, shared by loaders."""
from __future__ import annotations

from importlib import resources
import json
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator

from .identity import canonical_bytes
from .packet_v2_technical_policy import PacketV2CandidateError


def validate_packet_manifest_v2(manifest: object) -> dict[str, object]:
    path = resources.files("review_broker.schemas").joinpath("packet-v2.candidate.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise PacketV2CandidateError("PACKET_V2_SCHEMA_INVALID")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest),
                    key=lambda error: [str(part) for part in error.path])
    if errors:
        raise PacketV2CandidateError("PACKET_V2_SCHEMA_MISMATCH")
    return json.loads(canonical_bytes(manifest))


def load_packet_manifest_v2(raw: bytes) -> dict[str, object]:
    try:
        manifest = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise PacketV2CandidateError("PACKET_V2_MANIFEST_INVALID") from exc
    if raw != canonical_bytes(manifest) + b"\n":
        raise PacketV2CandidateError("PACKET_V2_MANIFEST_NONCANONICAL")
    return validate_packet_manifest_v2(manifest)


def packet_snapshot_relative_path_v2(entry: Mapping[str, object]) -> str:
    expected = f"sources/{entry['source_id']}.bin"
    if entry.get("snapshot") != expected or Path(expected).is_absolute() or ".." in Path(expected).parts:
        raise PacketV2CandidateError("PACKET_V2_SNAPSHOT_PATH_INVALID")
    return expected
