"""Original-process, locally exclusive final pre-model decision capability."""
from __future__ import annotations

from enum import Enum
from threading import RLock

from .github_journal_transport_v3 import OutcomeStatusV3
from .pre_model_failure_domain_v3 import require_failure_predecessor_v3


class PreModelDecisionStateV3(str, Enum):
    ACTIVE = "ACTIVE"
    CONSUMED_FOR_BLOCKED = "CONSUMED_FOR_BLOCKED"
    CONSUMED_FOR_PREPARED = "CONSUMED_FOR_PREPARED"
    CLOSED = "CLOSED"


class ActivePreModelDecisionV3:
    """Not serializable, constructible, copyable or authorized by its Python type."""
    def __new__(cls, *args, **kwargs):
        raise ValueError("ORIGINAL_CONTINUATION_ISSUER_REQUIRED")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("PRE_MODEL_DECISION_SUBCLASS_FORBIDDEN")

    def __copy__(self):
        raise ValueError("PRE_MODEL_DECISION_COPY_FORBIDDEN")

    def __deepcopy__(self, memo):
        raise ValueError("PRE_MODEL_DECISION_COPY_FORBIDDEN")

    def __reduce__(self):
        raise ValueError("PRE_MODEL_DECISION_SERIALIZATION_FORBIDDEN")

    def _provenance(self):
        if (type(self) is not ActivePreModelDecisionV3
                or getattr(self, "_producer", None) is None
                or getattr(self._producer, "_decision", None) is not self):
            raise ValueError("PRE_MODEL_DECISION_PROVENANCE_INVALID")

    @property
    def snapshot(self):
        self._provenance()
        return self._snapshot

    @property
    def context(self):
        self._provenance()
        return self._context

    @property
    def state(self):
        self._provenance()
        with self._lock:
            return self._state

    def require_active(self, owner):
        self._provenance()
        with self._lock:
            if self._owner is not owner or self._closed or self._state is not PreModelDecisionStateV3.ACTIVE:
                raise ValueError("PRE_MODEL_DECISION_NOT_ACTIVE_FOR_OWNER")

    def _transfer_after_handoff(self, producer, remote, context, handoff):
        self._provenance()
        from .pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
        with self._lock:
            self.require_active(producer)
            retained = producer._remote_handoff
            if (producer is not self._producer or type(remote) is not PreModelRemoteRetentionV3
                    or context is not self._context or retained is None
                    or retained[0] is not context or retained[1] is not handoff):
                raise ValueError("ORIGINAL_REMOTE_HANDOFF_REQUIRED")
            self._owner = remote

    def _publish_handoff(self, producer, context, result):
        self._provenance()
        with producer._lock:
            with self._lock:
                self.require_active(producer)
                if (producer is not self._producer or context is not self._context
                        or result.journal_outcome is not producer._decision_admitted_outcome):
                    raise ValueError("ORIGINAL_PACKET_HANDOFF_PUBLICATION_REQUIRED")
                producer._remote_handoff = (context, result)

    def begin_failure_handler(self, owner, handler):
        self._provenance()
        with self._lock:
            self.require_active(owner)
            if self._failure_handler is not None:
                raise ValueError("ORIGINAL_FAILURE_HANDLER_ALREADY_ENTERED")
            self._failure_handler = handler

    def choose(self, owner, choice: str, operation, identity: str):
        """Irreversible local choice BEFORE any journal-operation validation or Git write."""
        self._provenance()
        with self._lock:
            self.require_active(owner)
            if choice not in {"BLOCKED", "PREPARED"} or operation is None or not identity:
                raise ValueError("PRE_MODEL_DECISION_CHOICE_INVALID")
            if choice == "BLOCKED":
                from .pre_model_failure_continuation_v3 import ActiveFailureAuthorityV3
                if (type(operation) is not ActiveFailureAuthorityV3
                        or operation.ticket is not self or operation.owner is not owner
                        or self._failure_handler is not operation.handler):
                    raise ValueError("ORIGINAL_BLOCKED_OPERATION_REQUIRED")
            else:
                from .pre_model_remote_retention_v3 import PreModelRemoteRetentionV3, RemoteRetainedPacketAuthorityV3
                if (type(owner) is not PreModelRemoteRetentionV3
                        or type(operation) is not RemoteRetainedPacketAuthorityV3
                        or operation.decision is not self or operation.owner is not owner):
                    raise ValueError("ORIGINAL_PREPARED_OPERATION_REQUIRED")
            self._state = PreModelDecisionStateV3("CONSUMED_FOR_" + choice)
            self._operation, self._identity = operation, identity

    def require_selected(self, owner, choice, operation, identity=None):
        self._provenance()
        with self._lock:
            if (self._closed or self._owner is not owner or self._operation is not operation
                    or self._state is not PreModelDecisionStateV3("CONSUMED_FOR_" + choice)
                    or identity is not None and identity != self._identity):
                raise ValueError("PRE_MODEL_DECISION_SELECTED_OPERATION_REQUIRED")

    def enter_once(self, owner, choice, operation, identity):
        self._provenance()
        with self._lock:
            self.require_selected(owner, choice, operation, identity)
            if self._entered:
                raise ValueError("PRE_MODEL_DECISION_MUTATION_ALREADY_ENTERED")
            self._entered = True

    def close(self, owner, *, operation=None):
        self._provenance()
        with self._lock:
            if self._owner is not owner:
                return  # Original-run cleanup cannot revoke an authentic transfer.
            if self._state is not PreModelDecisionStateV3.ACTIVE and self._operation is not operation:
                return  # A losing handler cannot close the winner's selected operation.
            self._closed = True
            if self._state is PreModelDecisionStateV3.ACTIVE:
                self._state = PreModelDecisionStateV3.CLOSED


def _issue_active_decision_v3(producer, context, outcome, issuer):
    """Only the original run's private, momentary issuance gate accepts this call."""
    from .pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
    if type(producer) is not PreModelPacketContinuationV3:
        raise ValueError("ORIGINAL_CONTINUATION_ISSUER_REQUIRED")
    with producer._lock:
        if (issuer is None or producer._decision_issue_gate is not issuer
                or producer._decision is not None or not producer._attempted
                or outcome is not producer._decision_admitted_outcome
                or outcome.status is not OutcomeStatusV3.COMMITTED
                or outcome.pending is not None or outcome.snapshot is None):
            raise ValueError("ORIGINAL_ATTRIBUTED_ADMISSION_ISSUER_REQUIRED")
        require_failure_predecessor_v3(outcome.snapshot.record)
        ticket = object.__new__(ActivePreModelDecisionV3)
        ticket._producer, ticket._owner = producer, producer
        ticket._snapshot, ticket._context = outcome.snapshot, context
        ticket._state, ticket._lock = PreModelDecisionStateV3.ACTIVE, RLock()
        ticket._operation, ticket._identity, ticket._entered, ticket._closed = None, None, False, False
        ticket._failure_handler = None
        producer._decision = ticket
        producer._decision_issue_gate = None
        return ticket
