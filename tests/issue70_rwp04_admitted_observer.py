"""Restarted ADMITTED process: recognized Worker and copied result are not effect permits."""
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys
from unittest.mock import patch

from review_broker.github_actions_identity_v3 import GitHubActionsIdentityReaderV3
from review_broker.github_journal_transport_v3 import JournalOutcomeV3, OutcomeStatusV3
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.github_prepared_artifact_v3 import GitHubPreparedArtifactV3, PreparedArtifactUploaderV3
from review_broker.github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from review_broker.packet_retention_v3 import load_packet_evidence_v3
from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from review_broker.pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3, PreModelPacketContinuationResultV3
from review_broker.pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from review_broker.prepared_artifact_transport_v3 import PreparedMetadataReaderV3
from review_broker.prepared_packet_archive_v3 import extract_prepared_packet_v3
from review_broker.queue import AttemptState
from tests.issue68_test_support import ExactAdmissionAuthority, restore_transport, REPOSITORY
from tests.issue70_rwp02_test_support import WorkerScenario, SyntheticDispatchAuthority, PRINCIPAL, BOUNDARY
from tests.issue70_rwp03_test_support import EXPECTED, FixturePolicySourceAuthority, ArchivedSelectionAuthority
from tests.issue70_rwp04_cold_probe import ExternalHistoricalOrigin, ExternalHistoricalMutation
from tests.issue70_rwp04_test_support import install_historical_reads, BUDGET, NOW
from tests.journal_v3_test_support import BASE_SHA, NODE_ID, TrustedRejectionAuthority


def observe(root):
    if sys.platform == "linux":
        from tests.issue70_rwp03_linux_cold_isolation import require_installed_filter
        require_installed_filter()
    counts = {key: 0 for key in ("capture", "selection", "upload", "metadata", "storage", "builder", "stages")}
    def forbidden(key):
        def call(*args, **kwargs):
            counts[key] += 1
            raise AssertionError("restarted process attempted "+key)
        return call
    transport = restore_transport(root/"journal.json")
    install_historical_reads(transport)
    request_id = (root/"request-id.txt").read_text()
    admission_wire = json.loads((root/"admission.json").read_bytes())
    origin = ExternalHistoricalOrigin(root/"server-origin.json")
    dispatch = SyntheticDispatchAuthority(None, None)
    dispatch.archive = json.loads((root/"dispatch.json").read_bytes())
    journal = GitHubJournalV3(REPOSITORY, NODE_ID, BASE_SHA, transport,
        ExactAdmissionAuthority(admission_wire), ExternalHistoricalMutation(root/"server-mutation.json", origin),
        TrustedRejectionAuthority(), origin)
    a = journal.read(request_id)
    assert a.record.attempt.state is AttemptState.ADMITTED
    source, selection = FixturePolicySourceAuthority(), ArchivedSelectionAuthority(root/"independent-selection.json")
    verification = AuthorizedPolicyVerificationV3(journal, a, EXPECTED, source, selection)
    extract_prepared_packet_v3((root/"original-packet.zip").read_bytes(), root/"observed-packet", BUDGET, verification.before_effect)
    admission, _, _, manifest = load_packet_evidence_v3(root/"observed-packet", admission_wire,
                                                       policy_verification=verification)
    s = WorkerScenario(admission)  # Construction only: no seed, registration or dispatch.
    assert asdict(s.context) == json.loads((root/"authenticated-execution.json").read_bytes())
    authority = CurrentBoundWorkerAuthorityV3(journal=journal,
        actions_reader=GitHubActionsIdentityReaderV3("fixture-token", REPOSITORY, EXPECTED.repository_id,
                                                    executor=s.api, clock=lambda: NOW),
        expected=EXPECTED, execution_boundary=s.boundary, execution_boundary_id=BOUNDARY,
        dispatch_authority=dispatch, dispatch_principal_id=PRINCIPAL)
    # Positive control: this is a valid current initial Worker, not an invalid-context refusal.
    assert authority.require_current(s.context, a, AttemptState.ADMITTED) == a.record.control.worker
    class Capture:
        capture = staticmethod(forbidden("capture"))
    class Stages:
        build = verify = persist = cold_verify = staticmethod(forbidden("stages"))
    class Upload:
        upload_once = staticmethod(forbidden("upload"))
    metadata = PreparedMetadataReaderV3(token="fixture-token", repository=REPOSITORY,
                                        executor=forbidden("metadata"), budget=BUDGET)
    adapter = GitHubPreparedArtifactV3(metadata=metadata,
        worker_history=GitHubPreparedWorkerHistoryV3(metadata, EXPECTED, dispatch, PRINCIPAL),
        storage_executor=forbidden("storage"), budget=BUDGET, clock=lambda: NOW)
    producer = PreModelPacketContinuationV3(journal=journal, current_worker_authority=authority,
        original_admission=admission, capture_provider=Capture(), reference_readers=lambda guard: {},
        policy_source_authority=source, policy_selection_authority=selection, packet_stages=Stages())
    copied = PreModelPacketContinuationResultV3(OutcomeStatusV3.COMMITTED,
        "RWP03_OFFLINE_LOCAL_PACKET_COMPLETE", JournalOutcomeV3(OutcomeStatusV3.COMMITTED, snapshot=a),
        root/"observed-packet", manifest["packet_id"])
    with ExitStack() as stack:
        stack.enter_context(patch.object(selection, "select_policy", forbidden("selection")))
        stack.enter_context(patch("review_broker.packet_v2.build_packet_v2_candidate", forbidden("builder")))
        restarted = producer.run(s.context)
        remote = PreModelRemoteRetentionV3(producer=producer, retention_base=root/"retention",
            verification=verification, uploader=PreparedArtifactUploaderV3(Upload()), adapter=adapter,
            remote_verification_root=root/"remote")
        result = remote.run(s.context, copied)
    assert restarted.status is OutcomeStatusV3.REJECTED
    assert result.status is OutcomeStatusV3.REJECTED
    assert all(count == 0 for count in counts.values()), counts
    assert not transport.updates and not transport.create_statuses
    assert not s.dispatch.calls
    assert journal.read(request_id) == a
    sys.stdout.write(json.dumps(dict(state="ADMITTED", recognized_worker=a.record.control.worker.as_dict(),
        restarted=restarted.status.value, remote=result.status.value, forbidden_counts=counts,
        journal_mutations=len(transport.updates), dispatches=len(s.dispatch.calls))))


def main():
    if sys.platform == "linux":
        from tests.issue70_rwp03_linux_cold_isolation import install_filter, require_no_socket_descriptors
        require_no_socket_descriptors(); install_filter()
    observe(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
