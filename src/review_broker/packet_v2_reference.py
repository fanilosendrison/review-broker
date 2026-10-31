"""Role-specific packet-v2 reference source materialization metadata."""
from __future__ import annotations
import hashlib
from typing import Mapping

from .physical import PhysicalLineError, decode_physical_lines
from .request_v3 import request_identity_v3


class PacketV2ReferenceError(ValueError):
    pass


def build_reference_entries_v2(request: Mapping[str, object], start: int,
                               observations: tuple[object, ...] = ()
                               ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[bytes]]:
    entries, outcomes, data, remote_index = [], [], [], 0
    for offset, reference in enumerate(request["references"], start):
        source_id, selector, observed = f"S{offset:03d}", reference["source"], None
        if selector["kind"] == "inline": original = selector["text"].encode("utf-8")
        else:
            if remote_index >= len(observations): raise PacketV2ReferenceError("PACKET_V2_GIT_FILE_OBSERVATION_MISSING")
            observed = observations[remote_index]; remote_index += 1; original = observed.original_bytes
            header = b"blob " + str(len(original)).encode() + b"\0" + original
            if (len(original) != observed.original_byte_length
                    or hashlib.sha256(original).hexdigest() != observed.sha256
                    or hashlib.sha1(header).hexdigest() != observed.git_blob_oid):
                raise PacketV2ReferenceError("PACKET_V2_GIT_FILE_OBSERVATION_BYTES_MISMATCH")
        try: encoding, _, mapping = decode_physical_lines(original)
        except (UnicodeEncodeError, PhysicalLineError) as exc: raise PacketV2ReferenceError("PACKET_V2_REFERENCE_MATERIALIZATION_INVALID") from exc
        entry = {"source_id": source_id, "reference_id": reference["id"],
            "request_id": request_identity_v3(request), "role": "reference",
            "required": reference["required"], "source_kind": selector["kind"],
            "sha256": hashlib.sha256(original).hexdigest(), "original_byte_length": len(original),
            "encoding": encoding, "physical_lines": list(mapping), "snapshot": f"sources/{source_id}.bin"}
        if observed is not None:
            entry.update(repository=observed.repository, repository_id=observed.repository_id,
                commit=observed.commit_sha, path=observed.path, root_tree_sha=observed.root_tree_sha,
                git_blob_oid=observed.git_blob_oid, provenance_evidence_id=observed.evidence_id)
        entries.append(entry); outcomes.append({"id": reference["id"], "status": "captured", "source_id": source_id}); data.append(original)
    if remote_index != len(observations): raise PacketV2ReferenceError("PACKET_V2_GIT_FILE_OBSERVATION_INVENTED")
    return entries, outcomes, data
