"""Injected authenticated-path composition; never live GitHub evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from review_broker.packet_preparation_authority_v3 import verify_prepared_readback_v3
from review_broker.packet_retention_v3 import load_packet_evidence_v3, packet_retention_locator_v3
from tests.issue68_test_support import ExactAdmissionAuthority, IntegratedScenario, REPOSITORY, restore_transport
from tests.issue69_test_support import PullApi, TOKEN
from tests.journal_v3_test_support import (
    BASE_SHA, NODE_ID, TrustedMutationAuthority, TrustedPredecessorAuthority, TrustedRejectionAuthority,
)


class AuthenticatedScenario(IntegratedScenario):
    """Use actual PR/requester authorities before any journal claim is constructed."""

    def __init__(self, root: Path):
        super().__init__(root)
        capture = self.capture
        self.pr_reader = GitHubPullRequestObservationReaderV3(
            TOKEN, capture.repository, capture.repository_id, capture.pull_request,
            capture.head_sha, source_authority=self.source,
            executor=PullApi(capture.base_sha, capture.head_sha, capture.merge_base_sha,
                             [{"status": "modified", "filename": "review.md"}]),
        )
        scope = self.pr_reader.observe_scope()
        observation = self.pr_reader.finalize(scope, capture)
        assert observation.evidence_id == capture.pr_observation_evidence_id
        # Extend the PR72 helper's real requester/origin construction with the four
        # concrete reference readers. No cached admission is used as authority.
        from review_broker.admission_v3 import admit_initial_inline_v3
        from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
        from tests.request_v3_test_support import HistoryAuthority, origin
        origin_reader = origin(self.request)
        observed = origin_reader.observe(51)
        requester = GitHubRequesterAuthorityV3(
            requester_id=observed.requester_id, broker_issue_id=observed.issue_id,
            origin_evidence_id=observed.evidence_id, authorized=True,
        )
        self.admission = admit_initial_inline_v3(
            origin_reader, broker_issue_number=51, expected_broker_issue_id=6106789428,
            expected_requester_id=30498238, requester_authority=requester,
            pr_authority=self.pr_reader, source_authority=self.source,
            history_authority=HistoryAuthority(), git_file_readers=self.git_readers,
            issue_reference_readers=self.issue_readers,
        )
        self.journal_admission = self.admission.journal_admission()
        self.journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            ExactAdmissionAuthority(self.journal_admission), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )


def cold_probe() -> None:
    """Verify only serialized journal and retained bytes, with networking forbidden."""
    retention_base, transport_path, request_id = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    with patch("socket.socket.connect", side_effect=AssertionError("COLD_NETWORK_FORBIDDEN")):
        transport = restore_transport(transport_path)
        claim = GitHubJournalV3.claim_ref(request_id)
        raw = transport.commits[transport.refs[claim]].journal_bytes
        admission = json.loads(raw)["admission"]
        journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, transport, ExactAdmissionAuthority(admission),
            TrustedMutationAuthority(), TrustedRejectionAuthority(), TrustedPredecessorAuthority(),
        )
        snapshot = journal.read(request_id)
        rebuilt, capture, _, _ = load_packet_evidence_v3(
            packet_retention_locator_v3(retention_base, snapshot.claim_ref),
            snapshot.record.attempt.admission,
        )
        result = verify_prepared_readback_v3(retention_base, snapshot)
        result.update({
            "source_scope_evidence_id": rebuilt.source_scope_evidence_id,
            "source_authorization_evidence_id": capture.source_authorization_evidence_id,
            "pr_observation_evidence_id": capture.pr_observation_evidence_id,
            "capture_qualification": capture.verification,
        })
        sys.stdout.write(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    cold_probe()
