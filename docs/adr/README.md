---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "generated-index"
domain: "independent-review"
severity: "guideline"
name: "Review Broker ADR Index"
version: "0.1.0"
adoption_status: "accepted"
---

# Review Broker ADRs

Generated from canonical outgoing metadata. Profile status: accepted.
Validation/rendering performs no acceptance transition or runtime admission.
Accepted metadata on the integration branch is a proposal until the
owner-authorized merge into dev. It grants no operational admission.

After acceptance, identity/date/relations/governs and Context-through-EOF bytes
are immutable. Only declared lifecycle transitions may change status. Retain
all allocated records; never reuse IDs. Reverse relations below are derived.

| ID | Status | Decision | Date | Incoming |
| -- | ------ | -------- | ---- | -------- |
| ADR-001 | accepted | [Ordinary trusted authority boundary](adr-001-ordinary-trusted-authority-boundary.md) | 2026-11-09 | None |
| ADR-002 | accepted | [J-CH durable consumption authority](adr-002-jch-durable-consumption-authority.md) | 2026-11-09 | None |
| ADR-003 | accepted | [Claim-time protocol isolation and cutover](adr-003-claim-time-protocol-isolation.md) | 2026-11-09 | None |
| ADR-004 | accepted | [V2 quiescence before terminal recovery](adr-004-quiescent-terminal-recovery.md) | 2026-11-09 | None |
| ADR-005 | accepted | [Separate execution and result-storage provenance](adr-005-recovery-storage-provenance.md) | 2026-11-09 | None |
