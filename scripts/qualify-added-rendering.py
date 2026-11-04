"""Offline comparison only: no journal, admission, Codespace or reviewer invocation."""
import argparse
import hashlib
import json
from pathlib import Path

from review_broker.added_rendering import ADDED_IMAGES_V1
from review_broker.identity import canonical_bytes, request_identity
from review_broker.input_capacity import MAX_CHARS, measure_input
from review_broker.packets import GitSourceReader, SourceSpec, build_packet, verify_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-packet", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    original = verify_packet(args.legacy_packet)
    if "rendering_format" in original:
        raise ValueError("EXPECTED_HISTORICAL_LEGACY_PACKET")
    resolved = json.loads((args.legacy_packet / "resolved-request.json").read_bytes())
    if request_identity(resolved["request"]) != original["request_id"]:
        raise ValueError("ORIGINAL_REQUEST_IDENTITY_MISMATCH")
    changes = original["changes"]
    if not changes or any(c["status"] != "added" for c in changes):
        raise ValueError("EXPECTED_EXCLUSIVELY_ADDED_SCOPE")
    reader = GitSourceReader(args.repository_root.resolve(strict=True))
    if reader.changed_paths(original["merge_base"], original["head"]) != {c["path"] for c in changes}:
        raise ValueError("ACTUAL_GIT_SCOPE_MISMATCH")
    records = [reader.read(SourceSpec(e["repository"], e["commit"], e["path"])) for e in original["sources"]]
    diff = reader.diff(original["merge_base"], original["head"])
    if diff != (args.legacy_packet / "changes.patch").read_bytes():
        raise ValueError("RETAINED_INTERNAL_GIT_DIFF_MISMATCH")
    if args.output.exists():
        raise ValueError("QUALIFICATION_OUTPUT_MUST_BE_FRESH")
    args.output.mkdir(parents=True, mode=0o700)
    common = dict(request_id=original["request_id"], subject_id=original["subject_id"],
                  mission_instruction=original["program"]["mission_instruction"],
                  profile=original["program"]["profile"], changes=changes, change_diff=diff,
                  merge_base=original["merge_base"], head=original["head"])
    legacy_dir, compact_dir = args.output / "legacy", args.output / "compact"
    legacy = build_packet(records, output_directory=legacy_dir, **common)
    if legacy != original or (legacy_dir / "input.txt").read_bytes() != (args.legacy_packet / "input.txt").read_bytes():
        raise ValueError("HISTORICAL_PACKET_RECONSTRUCTION_MISMATCH")
    compact = build_packet(records, output_directory=compact_dir,
                           rendering_format=ADDED_IMAGES_V1,
                           added_file_modes=reader.added_change_modes(original["merge_base"], original["head"]),
                           **common)
    if verify_packet(compact_dir) != compact or verify_packet(legacy_dir) != original:
        raise ValueError("PACKET_VERIFICATION_FAILED")
    if compact["sources"] != original["sources"] or compact["program"] != original["program"]:
        raise ValueError("SOURCE_OR_MISSION_SCOPE_CHANGED")
    for entry in original["sources"]:
        if (compact_dir / entry["snapshot"]).read_bytes() != (args.legacy_packet / entry["snapshot"]).read_bytes():
            raise ValueError("ORIGINAL_SOURCE_BYTES_CHANGED")
    if (compact_dir / "changes.patch").read_bytes() != diff:
        raise ValueError("ORIGINAL_DIFF_BYTES_CHANGED")
    old_counts = measure_input((legacy_dir / "input.txt").read_bytes())
    new_counts = measure_input((compact_dir / "input.txt").read_bytes())
    source_root = Path(__file__).resolve().parents[1] / "src/review_broker"
    report = {
        "scope": "offline construction and capacity only; no independent reviewer verdict",
        "request_id": original["request_id"], "subject_id": original["subject_id"],
        "consumer_head": original["head"], "merge_base": original["merge_base"],
        "legacy_packet_id": original["packet_id"], "legacy_reconstruction": "BYTE_EXACT",
        "compact_packet_id": compact["packet_id"], "rendering_format": ADDED_IMAGES_V1,
        "legacy_input": old_counts, "compact_input": new_counts,
        "source_count": len(compact["sources"]),
        "source_bytes": sum(e["original_byte_length"] for e in compact["sources"]),
        "sources_preserved": True, "mission_preserved": True,
        "source_manifest_id": compact["source_manifest_id"],
        "diff_sha256": hashlib.sha256(diff).hexdigest(), "diff_bytes": len(diff),
        "diff_unicode_scalar_characters": len(diff.decode("utf-8")),
        "diff_similarity_copy_headers": sum(line.startswith(b"copy from ") for line in diff.splitlines()),
        "canonical_change_statuses": sorted({c["status"] for c in changes}),
        "max_chars": MAX_CHARS,
        "capacity_pass": new_counts["capacity_units"] <= MAX_CHARS,
        "model_invocations": 0, "journal_mutations": 0,
        "rendering_implementation_sha256": {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
            for name in ["packets.py", "changes.py", "added_rendering.py", "packet_rendering.py",
                         "git_change_scope.py", "packet_preparation.py", "review_program.py",
                         "input_capacity.py", "armament.py", "capacity_cli.py", "codex_policy.py",
                         "codex.py", "queue.py", "github_journal.py", "recovery.py", "reconciliation.py",
                         "bounded_preflight.py", "cli.py", "github_contents.py"]},
        "qualification_recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(canonical_bytes(report) + b"\n")
    print(json.dumps(report, indent=2))
    return 0 if report["capacity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
