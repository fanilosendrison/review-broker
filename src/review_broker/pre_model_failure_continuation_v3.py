"""Original-ticket failure orchestration; journal and proof outcomes stay independent."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from threading import Lock

from .github_journal_guarded_writer_v3 import GuardedPreModelWriterV3
from .github_journal_transport_v3 import GraphQLRefUpdateV3, JournalOutcomeV3, OutcomeStatusV3
from .identity import artifact_identity, canonical_bytes
from .journal_record_v3 import encode_journal_v2
from .pre_model_active_decision_v3 import ActivePreModelDecisionV3
from .pre_model_control_v3 import block_pre_model
from .pre_model_failure_evidence_v3 import FailureEvidenceRejectedV3
from .pre_model_failure_v3 import blocked_failure_receipt_v3
from .prepared_journal_history_v3 import require_snapshot_origin_v3
from .queue import AttemptState


@dataclass(frozen=True)
class PreModelFailureResultV3:
    status: OutcomeStatusV3
    state: str
    disposition: str
    observation_status: str
    reason: str
    journal_outcome: JournalOutcomeV3 | None = field(default=None, repr=False)
    failure_receipt_id: str | None = None
    observation_evidence_id: str | None = None


def _observed_control(journal, request_id, snapshot=None):
    try:
        value = snapshot if snapshot is not None else journal.read(request_id)
        require_snapshot_origin_v3(journal, value)
        return value.record.attempt.state.value, value.record.control.disposition
    except Exception:
        return "UNCONFIRMED", "UNCONFIRMED"


class ActiveFailureAuthorityV3:
    def __new__(cls, *args, **kwargs):
        raise ValueError("ORIGINAL_FAILURE_DECISION_AUTHORITY_REQUIRED")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("FAILURE_AUTHORITY_SUBCLASS_FORBIDDEN")

    def _require_choice(self):
        if type(self) is not ActiveFailureAuthorityV3:
            raise ValueError("CLOSED_FAILURE_AUTHORITY_REQUIRED")
        self.ticket.require_selected(self.owner, "BLOCKED", self, self.receipt_id)

    def claim_entry(self):
        self._require_choice()
        self.ticket.enter_once(self.owner, "BLOCKED", self, self.receipt_id)

    def before_effect(self):
        self._require_choice()
        self.ticket._producer.authority.require_current(self.ticket.context, self.ticket.snapshot,
                                                        AttemptState.ADMITTED)

    def permits(self, *, snapshot, failure_receipt_id, receipt, reservation_id, generation, worker):
        self.before_effect()
        a = self.ticket.snapshot
        if (snapshot != a or failure_receipt_id != self.receipt_id
                or canonical_bytes(receipt) + b"\n" != self.receipt_bytes
                or type(generation) is not int or generation != 1
                or reservation_id != a.record.control.reservation_id
                or worker != a.record.control.worker):
            return False
        restored = self.collector.evidence.read_original(self.observation_id, self.collector.binding,
                                                          self.before_effect)
        expected = blocked_failure_receipt_v3(a, restored)
        return canonical_bytes(expected) + b"\n" == self.receipt_bytes


def _failure_authority(collector, receipt, handler):
    ticket = collector.decision
    if type(ticket) is not ActivePreModelDecisionV3:
        raise ValueError("ORIGINAL_FAILURE_TICKET_REQUIRED")
    ticket.require_active(collector.owner)
    authority = object.__new__(ActiveFailureAuthorityV3)
    authority.collector, authority.ticket, authority.owner = collector, ticket, collector.owner
    authority.handler = handler
    authority.receipt_bytes = canonical_bytes(receipt) + b"\n"
    authority.receipt_id = artifact_identity(authority.receipt_bytes)
    authority.observation_id = receipt["observation_evidence_id"]
    return authority


class PreModelFailureContinuationV3:
    """One handler attempt; other handlers still arbitrate through the shared ticket/CAS."""
    def __init__(self, collector):
        self.collector, self._lock, self._attempted = collector, Lock(), False

    def run(self):
        with self._lock:
            if self._attempted:
                return PreModelFailureResultV3(OutcomeStatusV3.UNRESOLVED, "UNCONFIRMED", "UNCONFIRMED",
                                               "UNAVAILABLE", "FAILURE_OBSERVER_ONLY_NO_RETRY")
            self._attempted = True
        c, authority, outcome, observation, receipt_id = self.collector, None, None, None, None
        ticket, owner, handler_entered = c.decision, c.owner, False
        journal, a = ticket._producer.journal, ticket.snapshot
        try:
            ticket.begin_failure_handler(owner, self)
            handler_entered = True
            c.guard()
            observation = c.original_failure()
            if observation is None:
                return None  # Caller preserves the original outside-catalog result.
            observation = c.evidence.retain_original(observation, c.binding, c.guard)
            c.guard()
            receipt = blocked_failure_receipt_v3(a, observation)
            authority = _failure_authority(c, receipt, self)
            receipt_id = authority.receipt_id
            ticket.choose(owner, "BLOCKED", authority, receipt_id)
            writer = copy.copy(journal)
            writer.transport = GuardedPreModelWriterV3(journal.transport, authority.before_effect,
                                                       capture_unknown_updates=True)
            outcome = writer.block_pre_model(a, receipt_id, receipt, a.record.control.reservation_id,
                                            1, a.record.control.worker, authority)
            if outcome.status is OutcomeStatusV3.COMMITTED:
                b = outcome.snapshot
                expected = block_pre_model(a.record, receipt_id, receipt, a.record.control.reservation_id,
                                           1, a.record.control.worker)
                if (b is None or outcome.pending is not None or b.parent_sha != a.commit_sha
                        or b.journal_bytes != encode_journal_v2(expected)
                        or journal.mutation_authority.permits(GraphQLRefUpdateV3(a.repository_node_id,
                            a.claim_ref, a.commit_sha, b.commit_sha, False), b.writer_evidence_id) is not True):
                    raise ValueError("BLOCKED_CAS_ATTRIBUTION_UNCONFIRMED")
            state, disposition = (("ADMITTED", "BLOCKED") if outcome.status is OutcomeStatusV3.COMMITTED
                                  else _observed_control(journal, a.record.attempt.request_id, outcome.snapshot))
            proof = "UNAVAILABLE"
            try:
                # After CAS, finish only read-only proof verification. A is no longer
                # required to be head; the already selected operation remains bound.
                c.evidence.read_original(observation.evidence_id, c.binding, authority._require_choice)
                proof = "VERIFIED"
            except FailureEvidenceRejectedV3:
                proof = "REJECTED"
            except Exception:
                proof = "UNAVAILABLE"
            return PreModelFailureResultV3(outcome.status, state, disposition, proof,
                "BLOCKED_FAILURE_COMMITTED" if outcome.status is OutcomeStatusV3.COMMITTED
                else "BLOCKED_CAS_NOT_ATTRIBUTED_READ_ONLY", outcome, receipt_id, observation.evidence_id)
        except Exception as exc:
            state, disposition = _observed_control(journal, a.record.attempt.request_id)
            proof = "REJECTED" if isinstance(exc, FailureEvidenceRejectedV3) else "UNAVAILABLE"
            return PreModelFailureResultV3(OutcomeStatusV3.UNRESOLVED, state, disposition, proof,
                "FAILURE_UNCONFIRMED_NO_RETRY:" + type(exc).__name__, outcome, receipt_id,
                None if observation is None else observation.evidence_id)
        finally:
            if handler_entered: ticket.close(owner, operation=authority)
