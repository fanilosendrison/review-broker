"""One-shot original-Worker remote retention and existing PREPARED CAS composition."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from .github_journal_transport_v3 import GraphQLRefUpdateV3, OutcomeStatusV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import encode_journal_v2
from .packet_preparation_authority_v3 import offline_packet_receipt_v3, retained_inventory_v3
from .packet_retention_v3 import load_packet_evidence_v3, packet_retention_locator_v3
from .packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from .pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
from .pre_model_control_v3 import transition_state
from .prepared_journal_history_v3 import require_snapshot_origin_v3
from .prepared_packet_archive_v3 import (
    archive_packet_v3, extract_prepared_packet_v3, inventory_identity_v3,
)
from .remote_prepared_receipt_v3 import (
    RemotePreparedReceiptV3, api_decimal_v3, prepared_artifact_name_v3,
)
from .github_prepared_artifact_v3 import PreparedUploadPlanV3, UploadStatusV3
from .queue import AttemptState
from .pre_model_active_decision_v3 import ActivePreModelDecisionV3, PreModelDecisionStateV3
from .pre_model_failure_boundaries_v3 import PreModelFailureCollectorV3
from .pre_model_failure_continuation_v3 import PreModelFailureContinuationV3
from .pre_model_failure_evidence_v3 import PreModelFailureEvidenceV3


from .github_journal_guarded_writer_v3 import GuardedPreModelWriterV3 as _GuardedPreparedWriter


class RemoteRetainedPacketAuthorityV3:
    """Reconstruct verified remote-root bindings again at the existing prepare boundary."""
    def __init__(self, *, verification: AuthorizedPolicyVerificationV3, remote_root: Path,
                 receipt: RemotePreparedReceiptV3, job_id: str, decision=None, owner=None):
        if type(verification) is not AuthorizedPolicyVerificationV3:
            raise ValueError("ACTIVE_REMOTE_PREPARATION_AUTHORITY_REQUIRED")
        self.verification, self.root = verification, remote_root
        if type(decision) is not ActivePreModelDecisionV3:
            raise ValueError("ORIGINAL_REMOTE_PREPARATION_DECISION_REQUIRED")
        self.receipt, self.job_id, self.decision, self.owner = receipt, job_id, decision, owner

    def permits(self, *, snapshot, packet_evidence_id, reservation_id, generation, worker):
        self.decision.enter_once(self.owner, "PREPARED", self, self.receipt.evidence_id)
        v = self.verification
        v.require_current_effect()
        if (snapshot != v.snapshot or type(generation) is not int or generation != 1
                or reservation_id != snapshot.record.control.reservation_id
                or worker != snapshot.record.control.worker
                or packet_evidence_id != self.receipt.evidence_id):
            return False
        _, _, _, manifest = load_packet_evidence_v3(
            self.root, snapshot.record.attempt.admission, policy_verification=v)
        inventory = retained_inventory_v3(self.root, before_effect=v.before_effect)
        offline = offline_packet_receipt_v3(snapshot, manifest, inventory_identity_v3(inventory))
        self.receipt.require_links(offline, v.expected, self.job_id, snapshot.claim_ref)
        v.require_current_effect()
        return True


@dataclass(frozen=True)
class RemoteRetentionResultV3:
    status: OutcomeStatusV3
    state: str
    remote_reconstruction: str
    reason: str
    journal_outcome: object | None = field(default=None, repr=False)  # Existing journal outcome, never synthesized.
    remote_receipt: RemotePreparedReceiptV3 | None = None
    archive_bytes: bytes | None = field(default=None, repr=False)


class PreModelRemoteRetentionV3:
    def __init__(self, *, producer: PreModelPacketContinuationV3,
                 retention_base: Path, verification: AuthorizedPolicyVerificationV3,
                 uploader, adapter, remote_verification_root: Path,
                 failure_evidence: PreModelFailureEvidenceV3 | None = None):
        if (type(producer) is not PreModelPacketContinuationV3
                or type(verification) is not AuthorizedPolicyVerificationV3
                or verification.journal is not producer.journal
                or verification.expected != producer.authority.expected
                or adapter.worker_history.expected != verification.expected):
            raise ValueError("ACTIVE_ORIGINAL_REMOTE_CONTINUATION_REQUIRED")
        self.producer, self.base, self.verification = producer, retention_base, verification
        self.uploader, self.adapter, self.remote_root = uploader, adapter, remote_verification_root
        self.failure_evidence = failure_evidence if failure_evidence is not None else producer.failure_evidence
        if self.failure_evidence is not None and type(self.failure_evidence) is not PreModelFailureEvidenceV3:
            raise ValueError("CLOSED_FAILURE_EVIDENCE_BOUNDARY_REQUIRED")
        self._lock, self._attempted = Lock(), False

    def run(self, context, handoff):
        with self._lock:
            if self._attempted:
                return RemoteRetentionResultV3(OutcomeStatusV3.UNRESOLVED, "UNCONFIRMED",
                                               "UNAVAILABLE", "OBSERVER_ONLY_NO_RETRY")
            self._attempted = True
        effect_started, outcome, receipt, raw = False, None, None, None
        decision, collector, selected_operation = None, None, None
        a, journal, v = self.verification.snapshot, self.producer.journal, self.verification
        try:
            decision = self.producer.claim_remote_continuation(context, handoff, remote_owner=self)
            if decision.snapshot != a:
                raise ValueError("REMOTE_ORIGINAL_DECISION_SNAPSHOT_MISMATCH")
            self.producer.authority.require_current(context, a, AttemptState.ADMITTED)
            require_snapshot_origin_v3(journal, a)
            previous = handoff.journal_outcome
            if (handoff.status is not OutcomeStatusV3.COMMITTED or previous is None
                    or previous.status is not OutcomeStatusV3.COMMITTED
                    or previous.pending is not None or previous.snapshot != a
                    or journal.mutation_authority.permits(GraphQLRefUpdateV3(
                        a.repository_node_id, a.claim_ref, a.parent_sha, a.commit_sha, False),
                        a.writer_evidence_id) is not True):
                raise ValueError("RWP03_HANDOFF_NOT_ATTRIBUTED")
            def decision_guard():
                if selected_operation is None: decision.require_active(self)
                else: decision.require_selected(self, "PREPARED", selected_operation)
            guard = self.producer.authority.phase_guard(context, a, AttemptState.ADMITTED, decision_guard)
            v = AuthorizedPolicyVerificationV3(journal, a, v.expected,
                                               v.source_authority, v.selection_authority, guard)
            root = packet_retention_locator_v3(self.base, a.claim_ref)
            # Neither caller-supplied retained_root nor packet_id grants an effect.
            _, _, _, manifest = load_packet_evidence_v3(
                root, a.record.attempt.admission, policy_verification=v)
            # After authenticating this original process's handoff, its ID is an
            # integrity anchor, never permission to upload or bypass verification.
            if manifest["packet_id"] != handoff.packet_id:
                raise ValueError("RWP03_ORIGINAL_PACKET_ID_MISMATCH")
            adapter = self.adapter
            if self.failure_evidence is not None:
                collector = PreModelFailureCollectorV3(decision=decision, owner=self,
                    evidence=self.failure_evidence, before_effect=v.require_current_effect,
                    original_packet_id=handoff.packet_id, budget=adapter.budget)
                adapter = collector.bind_artifact_adapter(adapter)
            inventory = retained_inventory_v3(root, before_effect=v.before_effect)
            offline = offline_packet_receipt_v3(a, manifest, inventory_identity_v3(inventory))
            archive = archive_packet_v3(root, inventory, adapter.budget, v.before_effect)
            plan = PreparedUploadPlanV3(prepared_artifact_name_v3(
                a.claim_ref, a.record.control.worker.run_id, 1), canonical_bytes(inventory) + b"\n", context)
            v.require_current_effect()
            effect_started = True
            upload = (self.uploader.upload_once(plan, archive, before_effect=v.require_current_effect) if collector is None
                      else self.uploader.upload_once(plan, archive, before_effect=v.require_current_effect, failure_observer=collector))
            v.require_current_effect()
            if upload.status is UploadStatusV3.REFUSED:
                return RemoteRetentionResultV3(OutcomeStatusV3.REJECTED, "ADMITTED",
                                               "UNAVAILABLE", "UPLOAD_ESTABLISHED_REFUSAL")
            # A lost ACK permits only bounded observation, never a second upload.
            storage = adapter.observe(a, v.require_current_effect, active_context=context)
            v.require_current_effect()
            if collector is not None: collector.established_artifact(storage)
            raw = adapter.download(storage, v.require_current_effect)
            v.require_current_effect()
            extraction = {} if collector is None else {"failure_observer": collector}
            extract_prepared_packet_v3(raw, self.remote_root, adapter.budget,
                                       v.before_effect, expected_inventory=inventory, **extraction)
            _, _, _, remote_manifest = load_packet_evidence_v3(
                self.remote_root, a.record.attempt.admission, policy_verification=v, **extraction)
            if canonical_bytes(remote_manifest) != canonical_bytes(manifest):
                if collector is not None:
                    collector.verification_failed("MANIFEST", artifact_identity(canonical_bytes(manifest) + b"\n"),
                        artifact_identity(canonical_bytes(remote_manifest) + b"\n"), PreModelRemoteRetentionV3.run,
                        (self.remote_root, manifest, remote_manifest))
                raise ValueError("REMOTE_PACKET_MANIFEST_CHANGED")
            if collector is not None: collector.remote_reconstruction_complete()
            receipt = RemotePreparedReceiptV3.build(offline, storage)
            job_id = api_decimal_v3(context.job_id)
            receipt.require_links(offline, v.expected, job_id, a.claim_ref)
            authority = RemoteRetainedPacketAuthorityV3(
                verification=v, remote_root=self.remote_root, receipt=receipt, job_id=job_id,
                decision=decision, owner=self)
            v.require_current_effect()
            decision.choose(self, "PREPARED", authority, receipt.evidence_id)
            selected_operation = authority
            writer = copy.copy(journal)
            writer.transport = _GuardedPreparedWriter(journal.transport, v.require_current_effect, capture_unknown_updates=True)
            outcome = writer.prepare(a, receipt.evidence_id, a.record.control.reservation_id,
                                     1, a.record.control.worker, authority,
                                     before_effect=v.require_current_effect)
            if outcome.status is not OutcomeStatusV3.COMMITTED:
                return RemoteRetentionResultV3(outcome.status, "UNCONFIRMED", "VERIFIED",
                    "PREPARED_CAS_NOT_ATTRIBUTED_NO_RETRY", outcome, receipt, raw)
            p = outcome.snapshot
            expected = transition_state(a.record, AttemptState.PREPARED, receipt.evidence_id,
                                         a.record.control.reservation_id, 1, a.record.control.worker)
            if (p is None or outcome.pending is not None or p.parent_sha != a.commit_sha
                    or p.journal_bytes != encode_journal_v2(expected)
                    or journal.mutation_authority.permits(GraphQLRefUpdateV3(
                        a.repository_node_id, a.claim_ref, a.commit_sha, p.commit_sha, False),
                        p.writer_evidence_id) is not True):
                raise ValueError("PREPARED_CAS_ATTRIBUTION_UNCONFIRMED")
            try:
                if journal.read(context.inputs.request_id) != p:
                    raise ValueError("PREPARED_LATER_READBACK_CHANGED")
            except Exception:
                return RemoteRetentionResultV3(OutcomeStatusV3.COMMITTED, "PREPARED", "UNAVAILABLE",
                    "PREPARED_COMMITTED_LATER_READBACK_UNAVAILABLE", outcome, receipt, raw)
            return RemoteRetentionResultV3(OutcomeStatusV3.COMMITTED, "PREPARED", "VERIFIED",
                "PREPARED_COMMITTED_INDEPENDENT_READBACK_REQUIRED", outcome, receipt, raw)
        except Exception as exc:
            if collector is not None and decision.state is PreModelDecisionStateV3.ACTIVE:
                failure = PreModelFailureContinuationV3(collector).run()
                if failure is not None: return failure
            return RemoteRetentionResultV3(
                OutcomeStatusV3.UNRESOLVED if effect_started else OutcomeStatusV3.REJECTED,
                "UNCONFIRMED", "UNAVAILABLE", f"REMOTE_CONTINUATION_UNCONFIRMED:{type(exc).__name__}",
                outcome, receipt, raw)
        finally:
            if decision is not None: decision.close(self, operation=selected_operation)
