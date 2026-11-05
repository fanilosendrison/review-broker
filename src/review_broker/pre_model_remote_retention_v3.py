"""One-shot original-Worker remote retention and existing PREPARED CAS composition."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from .github_journal_transport_v3 import GraphQLRefUpdateV3, OutcomeStatusV3
from .identity import canonical_bytes
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


class _GuardedPreparedWriter:
    """Guard effect-producing calls internally; read-only reconciliation stays readable."""
    def __init__(self, transport, guard):
        self.original, self.guard = transport, guard
        self.writer = copy.copy(transport)
        # Concrete live HTTP transport guards each internal HTTP boundary. Injected
        # transports must provide the equivalent callback for internal external I/O.
        self.writer.before_effect = guard

    def create_journal_commit(self, *args):
        self.guard()
        return self.writer.create_journal_commit(*args)

    def update_ref(self, update):
        self.guard()
        return self.writer.update_ref(update)

    def read_claim(self, ref):
        return self.original.read_claim(ref)


class RemoteRetainedPacketAuthorityV3:
    """Reconstruct verified remote-root bindings again at the existing prepare boundary."""
    def __init__(self, *, verification: AuthorizedPolicyVerificationV3, remote_root: Path,
                 receipt: RemotePreparedReceiptV3, job_id: str):
        if type(verification) is not AuthorizedPolicyVerificationV3:
            raise ValueError("ACTIVE_REMOTE_PREPARATION_AUTHORITY_REQUIRED")
        self.verification, self.root = verification, remote_root
        self.receipt, self.job_id = receipt, job_id

    def permits(self, *, snapshot, packet_evidence_id, reservation_id, generation, worker):
        v = self.verification
        v.before_effect()
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
        v.before_effect()
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
                 uploader, adapter, remote_verification_root: Path):
        if (type(producer) is not PreModelPacketContinuationV3
                or type(verification) is not AuthorizedPolicyVerificationV3
                or verification.journal is not producer.journal
                or verification.expected != producer.authority.expected
                or adapter.worker_history.expected != verification.expected):
            raise ValueError("ACTIVE_ORIGINAL_REMOTE_CONTINUATION_REQUIRED")
        self.producer, self.base, self.verification = producer, retention_base, verification
        self.uploader, self.adapter, self.remote_root = uploader, adapter, remote_verification_root
        self._lock, self._attempted = Lock(), False

    def run(self, context, handoff):
        with self._lock:
            if self._attempted:
                return RemoteRetentionResultV3(OutcomeStatusV3.UNRESOLVED, "UNCONFIRMED",
                                               "UNAVAILABLE", "OBSERVER_ONLY_NO_RETRY")
            self._attempted = True
        effect_started, outcome, receipt, raw = False, None, None, None
        a, journal, v = self.verification.snapshot, self.producer.journal, self.verification
        try:
            self.producer.claim_remote_continuation(context, handoff)
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
            def guard():
                self.producer.authority.require_current(context, a, AttemptState.ADMITTED)
            v = AuthorizedPolicyVerificationV3(journal, a, v.expected,
                                               v.source_authority, v.selection_authority, guard)
            root = packet_retention_locator_v3(self.base, a.claim_ref)
            # Neither caller-supplied retained_root nor packet_id grants an effect.
            _, _, _, manifest = load_packet_evidence_v3(
                root, a.record.attempt.admission, policy_verification=v)
            inventory = retained_inventory_v3(root, before_effect=v.before_effect)
            offline = offline_packet_receipt_v3(a, manifest, inventory_identity_v3(inventory))
            archive = archive_packet_v3(root, inventory, self.adapter.budget, v.before_effect)
            plan = PreparedUploadPlanV3(prepared_artifact_name_v3(
                a.claim_ref, a.record.control.worker.run_id, 1), canonical_bytes(inventory) + b"\n", context)
            v.before_effect()
            effect_started = True
            upload = self.uploader.upload_once(plan, archive, before_effect=v.before_effect)
            if upload.status is UploadStatusV3.REFUSED:
                return RemoteRetentionResultV3(OutcomeStatusV3.REJECTED, "ADMITTED",
                                               "UNAVAILABLE", "UPLOAD_ESTABLISHED_REFUSAL")
            # A lost ACK permits only bounded observation, never a second upload.
            storage = self.adapter.observe(a, v.before_effect, active_context=context)
            raw = self.adapter.download(storage, v.before_effect)
            extract_prepared_packet_v3(raw, self.remote_root, self.adapter.budget,
                                       v.before_effect, expected_inventory=inventory)
            _, _, _, remote_manifest = load_packet_evidence_v3(
                self.remote_root, a.record.attempt.admission, policy_verification=v)
            if canonical_bytes(remote_manifest) != canonical_bytes(manifest):
                raise ValueError("REMOTE_PACKET_MANIFEST_CHANGED")
            receipt = RemotePreparedReceiptV3.build(offline, storage)
            job_id = api_decimal_v3(context.job_id)
            receipt.require_links(offline, v.expected, job_id, a.claim_ref)
            authority = RemoteRetainedPacketAuthorityV3(
                verification=v, remote_root=self.remote_root, receipt=receipt, job_id=job_id)
            v.before_effect()
            writer = copy.copy(journal)
            writer.transport = _GuardedPreparedWriter(journal.transport, v.before_effect)
            outcome = writer.prepare(a, receipt.evidence_id, a.record.control.reservation_id,
                                     1, a.record.control.worker, authority,
                                     before_effect=v.before_effect)
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
            return RemoteRetentionResultV3(
                OutcomeStatusV3.UNRESOLVED if effect_started else OutcomeStatusV3.REJECTED,
                "UNCONFIRMED", "UNAVAILABLE", f"REMOTE_CONTINUATION_UNCONFIRMED:{type(exc).__name__}",
                outcome, receipt, raw)
