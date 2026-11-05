"""Closed read-only policy boundary rooted in authenticated original A/P history."""
from __future__ import annotations

from dataclasses import dataclass

from .packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from .prepared_journal_history_v3 import PreparedJournalHistoryV3
from .pre_model_policy_source_v3 import PolicySourceAuthorityV3
from .pre_model_policy_selection_v3 import PolicySelectionAuthorityV3


@dataclass(frozen=True)
class HistoricalAuthorizedPolicyVerificationV3:
    """No inheritance, synthetic journal, new selection or packet-construction API.

    The shared verifier operations are reused verbatim, with A as their actual
    snapshot and the real journal object. Historical origin replaces active-head
    freshness only for these explicitly accepted read-only operations.
    """

    history: PreparedJournalHistoryV3
    source_authority: PolicySourceAuthorityV3
    selection_authority: PolicySelectionAuthorityV3

    def __post_init__(self) -> None:
        if type(self.history) is not PreparedJournalHistoryV3:
            raise ValueError("HISTORICAL_POLICY_CONTEXT_REQUIRED")
        self.history.verify()

    @property
    def snapshot(self):
        return self.history.admitted

    @property
    def journal(self):
        return self.history.journal

    @property
    def expected(self):
        return self.history.expected

    def before_effect(self) -> None:
        self.history.verify()

    require_admission = AuthorizedPolicyVerificationV3.require_admission
    require_profile = AuthorizedPolicyVerificationV3.require_profile
    require_references = AuthorizedPolicyVerificationV3.require_references
    selection_context = AuthorizedPolicyVerificationV3.selection_context
    verify = AuthorizedPolicyVerificationV3.verify
