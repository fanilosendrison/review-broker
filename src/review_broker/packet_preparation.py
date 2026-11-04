"""Select a new PR rendering or reconstruct the exact journal-bound historical packet."""
from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

# Packet/program dictionaries retain the established validated JSON artifact representation.

from .added_rendering import ADDED_IMAGES_V1
from .identity import artifact_identity, canonical_bytes
from .packets import GitSourceReader, PacketError, SourceRecord, build_packet


def prepare_packet(
    records: list[SourceRecord], *, request_id: str, subject_id: str,
    mission_instruction: str, profile: dict[str, Any], output_directory: Path,
    changes: list[dict[str, Any]], change_diff: bytes, merge_base: str, head: str,
    prepared_evidence_ids: tuple[str, ...] = (),
    source_reader: GitSourceReader | None = None,
) -> dict[str, Any]:
    """A prepared claim selects by its exact old evidence, never by a new default."""
    compact_applicable = bool(changes) and all(c["status"] == "added" for c in changes)
    formats = ([None, ADDED_IMAGES_V1] if compact_applicable else [None]) if prepared_evidence_ids else (
        [ADDED_IMAGES_V1] if compact_applicable else [None])

    def construct(directory: Path, mode: str | None) -> dict[str, Any]:
        modes = None
        if mode == ADDED_IMAGES_V1:
            if source_reader is None:
                raise PacketError("ACTUAL_ADDED_SCOPE_OBSERVATION_REQUIRED")
            modes = source_reader.added_change_modes(merge_base, head)
        return build_packet(
            records, request_id=request_id, subject_id=subject_id,
            mission_instruction=mission_instruction, profile=profile,
            output_directory=directory, changes=changes, change_diff=change_diff,
            merge_base=merge_base, head=head, rendering_format=mode,
            added_file_modes=modes if mode == ADDED_IMAGES_V1 else None,
        )

    selected = formats[0]
    if prepared_evidence_ids:
        for mode in formats:
            try:
                with tempfile.TemporaryDirectory(prefix="review-broker-rebuild-") as temporary:
                    manifest = construct(Path(temporary), mode)
            except PacketError:
                # Failure grants nothing. Only an independently matching candidate can be selected.
                continue
            if artifact_identity(canonical_bytes(manifest)) in prepared_evidence_ids:
                selected = mode
                break
        else:
            raise PacketError("PREPARED_PACKET_EVIDENCE_MISMATCH")
    result = construct(output_directory, selected)
    if prepared_evidence_ids and artifact_identity(canonical_bytes(result)) not in prepared_evidence_ids:
        raise PacketError("PREPARED_PACKET_EVIDENCE_MISMATCH")
    return result
