"""Shared concrete write-edge guards, with read-only journal reconciliation."""
import copy

from .github_journal_transport_v3 import GraphQLUpdateResultV3


class GuardedPreModelWriterV3:
    def __init__(self, transport, guard, *, capture_unknown_updates=False):
        self.original, self.guard = transport, guard
        self.writer = copy.copy(transport)
        self.writer.before_effect = guard
        self.capture_unknown_updates = capture_unknown_updates

    def create_journal_commit(self, *args):
        self.guard()
        return self.writer.create_journal_commit(*args)

    def update_ref(self, update):
        self.guard()
        if not self.capture_unknown_updates:
            return self.writer.update_ref(update)
        try:
            return self.writer.update_ref(update)
        except Exception:
            # Preserve the core's intended-SHA pending evidence; never repeat CAS.
            return GraphQLUpdateResultV3(None, ("PRE_MODEL_UPDATE_UNCONFIRMED",))

    def read_claim(self, ref):
        return self.original.read_claim(ref)
