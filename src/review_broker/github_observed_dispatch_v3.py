"""Capabilityless immutable dispatch provenance observed afresh for this Worker process."""
from .github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
from .identity import canonical_bytes
from .pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3


class GitHubObservedDispatchV3:
    """Data, not a cached current-Worker permission or Controller-private archive.

    Completed Controller attempt identity and original dispatch bindings do not
    change. Current authority independently rechecks the live Worker and ref at
    every effect. A restarted observer must reconstruct this data through the
    concrete GitHub authority again. principal_id always performs fresh API reads.
    No dispatch/ACK-writing/binding/ticket creation interface is provided here.
    """
    def __init__(self,source,receipt):
        if type(source) is not GitHubActionsDispatchAcknowledgmentAuthorityV3:
            raise ValueError('CONCRETE_DISPATCH_OBSERVATION_REQUIRED')
        self._source=source
        self._principal=source.principal_id(receipt)
        self._receipt=canonical_bytes(receipt.as_dict())

    def authenticates(self,receipt,*,dispatch_principal_id):
        return (type(receipt) is DispatchAcknowledgmentV3 and type(dispatch_principal_id) is int
            and dispatch_principal_id==self._principal and canonical_bytes(receipt.as_dict())==self._receipt)

    def principal_id(self,receipt):
        return self._source.principal_id(receipt)
