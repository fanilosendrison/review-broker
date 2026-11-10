"""Original journal admission without pretending its absent byte snapshots are present."""
from dataclasses import dataclass
import json

from .admission_evidence_v3 import validate_journal_admission_v3
from .identity import canonical_bytes


@dataclass(frozen=True)
class OriginalAdmissionEnvelopeV3:
    """Observer data only. Cannot claim, build a packet, or issue an active decision.

    The original continuation may hydrate the complete PreclaimAdmissionV3 only
    after its own attributed ADMITTED, with its genuine current-effect guard.
    """
    admission_bytes: bytes
    origin_body_bytes: bytes

    def __post_init__(self):
        value=validate_journal_admission_v3(json.loads(self.admission_bytes),self.origin_body_bytes)
        if canonical_bytes(value)!=self.admission_bytes:
            raise ValueError("ORIGINAL_ADMISSION_ENVELOPE_NONCANONICAL")

    def journal_admission(self): return json.loads(self.admission_bytes)
    @property
    def request(self): return self.journal_admission()["canonical_request"]
    @property
    def canonical_request_bytes(self): return canonical_bytes(self.request)
    @property
    def request_id(self): return self.journal_admission()["request_id"]
    @property
    def admission_evidence_id(self): return self.journal_admission()["admission_evidence_id"]
