"""Fresh Linux-isolated historical packet reconstruction with external fixture trust."""
from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
import sys
from unittest.mock import patch

from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.prepared_journal_history_v3 import PreparedJournalHistoryV3
from review_broker.prepared_packet_archive_v3 import extract_prepared_packet_v3
from review_broker.prepared_packet_readback_v3 import reconstruct_prepared_packet_v3
from tests.issue68_test_support import restore_transport, ExactAdmissionAuthority, REPOSITORY
from tests.issue70_rwp02_test_support import SyntheticDispatchAuthority, PRINCIPAL
from tests.issue70_rwp03_test_support import EXPECTED, FixturePolicySourceAuthority, ArchivedSelectionAuthority
from tests.issue70_rwp04_test_support import install_historical_reads, BUDGET
from tests.journal_v3_test_support import BASE_SHA, NODE_ID, TrustedMutationAuthority, TrustedRejectionAuthority


class ExternalHistoricalOrigin:
    def __init__(self, archive):
        self.archive = json.loads(Path(archive).read_bytes())

    def evidence_id(self, *, repository, claim_ref, snapshot):
        observed = dict(repository=repository, claim_ref=claim_ref, commit_sha=snapshot.commit_sha,
                        parent_sha=snapshot.parent_sha, journal_bytes_id=artifact_identity(snapshot.journal_bytes))
        return artifact_identity(canonical_bytes(observed)+b"\n") if observed in self.archive else None

    def permits_evidence(self, *, repository, claim_ref, snapshot, evidence_id):
        return evidence_id is not None and evidence_id == self.evidence_id(
            repository=repository, claim_ref=claim_ref, snapshot=snapshot)


class ExternalHistoricalMutation:
    """Independent server mutation observation, not journal content alone."""
    def __init__(self, archive, origin):
        self.updates, self.origin = json.loads(Path(archive).read_bytes()), origin

    def permits(self, update, evidence_id):
        expected = dict(repository_id=update.repository_id, name=update.name,
                        before_oid=update.before_oid, after_oid=update.after_oid, force=update.force)
        return expected in self.updates and any(
            row["commit_sha"] == update.after_oid and
            artifact_identity(canonical_bytes(row)+b"\n") == evidence_id for row in self.origin.archive)


def reconstruct(arguments):
    targets = {
        "capture_calls": "review_broker.github_subject_capture_v3.capture_authenticated_subject_v3",
        "selections": "tests.issue70_rwp03_test_support.ArchivedSelectionAuthority.select_policy",
        "uploads": "review_broker.github_prepared_artifact_v3.PreparedArtifactUploaderV3.upload_once",
        "journal_mutations": "tests.journal_v3_test_support.FakeGitHubTransportV3.update_ref",
        "builds": "review_broker.packet_v2.build_packet_v2_candidate",
        "source_reads": "tests.issue70_rwp03_test_support.FixturePolicySourceAuthority.read_policy",
        "claims": "review_broker.github_journal_v3.GitHubJournalV3.claim",
        "commits": "tests.journal_v3_test_support.FakeGitHubTransportV3.create_journal_commit",
        "creates": "tests.journal_v3_test_support.FakeGitHubTransportV3.create_ref",
    }
    with ExitStack() as stack:
        forbidden = {key: stack.enter_context(patch(target, side_effect=AssertionError(key)))
                     for key, target in targets.items()}
        _reconstruct(arguments, forbidden)
        if any(mock.call_count for mock in forbidden.values()):
            raise AssertionError("cold process attempted a forbidden effect")


def _reconstruct(arguments, forbidden):
    if sys.platform == "linux":
        from tests.issue70_rwp03_linux_cold_isolation import require_installed_filter
        require_installed_filter()
    root = Path(arguments[0])
    request_id = (root/"request-id.txt").read_text()
    transport = restore_transport(root/"journal.json")
    install_historical_reads(transport)
    admission = json.loads((root/"admission.json").read_bytes())
    origin = ExternalHistoricalOrigin(root/"server-origin.json")
    dispatch = SyntheticDispatchAuthority(None, None)
    dispatch.archive = json.loads((root/"dispatch.json").read_bytes())
    journal = GitHubJournalV3(REPOSITORY, NODE_ID, BASE_SHA, transport,
        ExactAdmissionAuthority(admission), ExternalHistoricalMutation(root/"server-mutation.json", origin),
        TrustedRejectionAuthority(), origin)
    history = PreparedJournalHistoryV3.read(journal, request_id, EXPECTED, dispatch, PRINCIPAL)
    raw = (root/"downloaded.zip").read_bytes()
    storage = json.loads((root/"authenticated-storage.json").read_bytes())
    import hashlib
    if len(raw) != storage["artifact_size_in_bytes"] or "sha256:"+hashlib.sha256(raw).hexdigest() != storage["artifact_digest"]:
        raise ValueError("COLD_ARCHIVE_BYTES_CHANGED")
    extract_prepared_packet_v3(raw, root/"cold-packet", BUDGET, history.verify)
    result = reconstruct_prepared_packet_v3(root/"cold-packet", history=history,
        source_authority=FixturePolicySourceAuthority(),
        selection_authority=ArchivedSelectionAuthority(root/"independent-selection.json"),
        authenticated_storage=storage)
    if transport.updates or transport.create_statuses:
        raise AssertionError("cold process mutated journal")
    sys.stdout.write(json.dumps(dict(manifest=json.loads(result.manifest_bytes),
        inventory=json.loads(result.inventory_bytes), offline=json.loads(result.offline_receipt_bytes),
        remote=result.remote_receipt.value, remote_id=result.remote_receipt.evidence_id,
        **{key: mock.call_count for key, mock in forbidden.items()})))


def main():
    if sys.platform == "linux":
        from tests.issue70_rwp03_linux_cold_isolation import (
            install_filter, require_installed_filter, require_no_socket_descriptors,
        )
        require_no_socket_descriptors()
        install_filter()
        require_installed_filter()
    reconstruct(sys.argv[1:])


if __name__ == "__main__":
    main()
