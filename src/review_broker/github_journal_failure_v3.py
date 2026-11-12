"""Closed active failure entry into the existing journal transition/CAS primitive."""
from .pre_model_control_v3 import block_pre_model as transition_block_pre_model


def block_pre_model(self, current, failure_receipt_id, receipt, reservation_id,
                    generation, worker, authority):
    from .github_journal_v3 import GitHubJournalV3Error
    from .pre_model_failure_continuation_v3 import ActiveFailureAuthorityV3
    if type(authority) is not ActiveFailureAuthorityV3:
        raise GitHubJournalV3Error("ACTIVE_FAILURE_AUTHORITY_REQUIRED")
    authority.claim_entry()
    if not authority.permits(snapshot=current, failure_receipt_id=failure_receipt_id,
            receipt=receipt, reservation_id=reservation_id, generation=generation, worker=worker):
        raise GitHubJournalV3Error("FAILURE_AUTHORITY_UNTRUSTED")
    return self._transition(current, lambda record: transition_block_pre_model(
        record, failure_receipt_id, receipt, reservation_id, generation, worker),
        before_effect=authority.before_effect)
