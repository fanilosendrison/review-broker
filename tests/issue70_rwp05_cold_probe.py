"""Fresh, Linux-isolated BLOCKED reader; all execution/publication entry points tripwired."""
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys
from unittest.mock import patch

from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3
from review_broker.pre_model_failure_readback_v3 import read_pre_model_failure_v3
from tests.issue68_test_support import restore_transport,ExactAdmissionAuthority,REPOSITORY
from tests.issue70_rwp04_cold_probe import ExternalHistoricalOrigin,ExternalHistoricalMutation
from tests.issue70_rwp04_test_support import install_historical_reads
from tests.issue70_rwp05_evidence_support import ExternalFailureAuthority,ExternalObservationArchive
from tests.journal_v3_test_support import BASE_SHA,NODE_ID,TrustedRejectionAuthority


def reconstruct(root, external):
    if sys.platform=='linux':
        from tests.issue70_rwp03_linux_cold_isolation import require_installed_filter
        require_installed_filter()
    request_id=(root/'request-id.txt').read_text()
    transport=restore_transport(root/'journal.json');install_historical_reads(transport)
    admission=json.loads((root/'admission.json').read_bytes())
    origin=ExternalHistoricalOrigin(root/'server-origin.json')
    journal=GitHubJournalV3(REPOSITORY,NODE_ID,BASE_SHA,transport,ExactAdmissionAuthority(admission),
        ExternalHistoricalMutation(root/'server-mutation.json',origin),TrustedRejectionAuthority(),origin)
    evidence=PreModelFailureEvidenceV3(ExternalFailureAuthority(external/'trusted-origin',create=False),
                                      ExternalObservationArchive(external/'observation-objects',create=False),16_000)
    targets={
        'capture':'review_broker.github_subject_capture_v3.capture_authenticated_subject_v3',
        'selection':'tests.issue70_rwp03_test_support.ArchivedSelectionAuthority.select_policy',
        'builder':'review_broker.packet_v2.build_packet_v2_candidate',
        'upload':'review_broker.github_prepared_artifact_v3.PreparedArtifactUploaderV3.upload_once',
        'new_observation':'tests.issue70_rwp05_evidence_support.ExternalFailureAuthority.observe',
        'conservation':'tests.issue70_rwp05_evidence_support.ExternalObservationArchive.put_once',
        'ticket':'review_broker.pre_model_packet_continuation_v3._issue_active_decision_v3',
        'claim':'review_broker.github_journal_v3.GitHubJournalV3.claim',
        'reservation':'review_broker.github_journal_v3.GitHubJournalV3.reserve_initial',
        'binding':'review_broker.github_journal_v3.GitHubJournalV3.register_worker',
        'admission':'review_broker.github_journal_v3.GitHubJournalV3.record_admission',
        'failure':'review_broker.github_journal_v3.GitHubJournalV3.block_pre_model',
        'prepared':'review_broker.github_journal_v3.GitHubJournalV3.prepare',
        'commit':'tests.journal_v3_test_support.FakeGitHubTransportV3.create_journal_commit',
        'create_ref':'tests.journal_v3_test_support.FakeGitHubTransportV3.create_ref',
        'update_ref':'tests.journal_v3_test_support.FakeGitHubTransportV3.update_ref',
    }
    with ExitStack() as stack:
        counters={key:stack.enter_context(patch(target,side_effect=AssertionError(key))) for key,target in targets.items()}
        result=read_pre_model_failure_v3(journal=journal,request_id=request_id,evidence=evidence)
        counts={key:mock.call_count for key,mock in counters.items()}
        assert all(count==0 for count in counts.values()),counts
    assert not transport.updates and not transport.create_statuses
    sys.stdout.write(json.dumps(dict(result=asdict(result),forbidden_counts=counts)))


def main():
    if sys.platform=='linux':
        from tests.issue70_rwp03_linux_cold_isolation import install_filter,require_no_socket_descriptors
        require_no_socket_descriptors();install_filter()
    reconstruct(Path(sys.argv[1]),Path(sys.argv[2]))


if __name__=='__main__':main()
