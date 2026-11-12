"""Original-instance local integrity scope, never a lease, writer or effect permit."""
from .journal_record_v3 import encode_journal_v2


class WorkerLocalPhaseV3:
    def __new__(cls, *args, **kwargs):
        raise ValueError('WORKER_PHASE_ISSUER_REQUIRED')

    def __init_subclass__(cls, **kwargs):
        raise TypeError('WORKER_PHASE_SUBCLASS_FORBIDDEN')

    def __copy__(self):
        raise ValueError('WORKER_PHASE_COPY_FORBIDDEN')

    def __deepcopy__(self, memo):
        raise ValueError('WORKER_PHASE_COPY_FORBIDDEN')

    def __reduce__(self):
        raise ValueError('WORKER_PHASE_SERIALIZATION_FORBIDDEN')

    def local(self):
        a = self._authority
        if (getattr(a, '_local_phase', None) is not self
                or a.journal is not self._journal or a.expected != self._expected
                or a.boundary is not self._boundary or a.boundary_id != self._boundary_id
                or a.dispatch_authority is not self._dispatch or a.principal != self._principal
                or self._snapshot.journal_bytes != self._bytes
                or encode_journal_v2(self._snapshot.record) != self._bytes):
            raise ValueError('ORIGINAL_WORKER_PHASE_REQUIRED')
        a.authenticate_context(self._context)
        self._decision_guard()

    def require_verification(self, verification):
        self.local()
        if (verification.journal is not self._journal
                or verification.snapshot is not self._snapshot
                or verification.expected != self._expected):
            raise ValueError('WORKER_PHASE_VERIFICATION_MISMATCH')

    def __call__(self):
        """External boundary: fresh mutable ref/run/job checks, no TTL."""
        self.local()
        self._authority.require_current(self._context, self._snapshot, self._state)
        self.local()


def issue_local_phase_v3(authority, context, snapshot, state, decision_guard):
    """Only the authority's original issuance call may register this local scope."""
    if getattr(authority, '_phase_issuing', None) is not context:
        raise ValueError('WORKER_PHASE_ISSUER_REQUIRED')
    authority.require_current(context, snapshot, state)
    phase = object.__new__(WorkerLocalPhaseV3)
    phase._authority, phase._context, phase._snapshot = authority, context, snapshot
    phase._state, phase._decision_guard = state, decision_guard
    phase._journal, phase._expected = authority.journal, authority.expected
    phase._boundary, phase._boundary_id = authority.boundary, authority.boundary_id
    phase._dispatch, phase._principal = authority.dispatch_authority, authority.principal
    phase._bytes = bytes(snapshot.journal_bytes)
    authority._local_phase = phase
    phase.local()
    return phase
