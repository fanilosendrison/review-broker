---
okf_version: '1.0'
adr_profile_version: 0.1.0
kind: KnowledgeAsset
asset_type: architecture-decision-record
domain: independent-review
severity: strict
name: Claim-time protocol isolation and cutover
id: ADR-003
status: accepted
date: '2026-11-09'
decision_body_sha256: 2edf07dddd80fa5098b21df5927b1abe681762a7f45ad92f139670d81eb0ca1b
relation_completeness: complete
relations:
  clarifies: []
  amends: []
  supersedes: []
  confirms: []
governs:
- journal-protocol-coexistence
participants:
  decision_makers:
  - Product owner
extensions:
  document_version: 0.1.0
  adoption_packet: RB91_JCH_GOVERNED_NORMATIVE_ADOPTION
  qualified_source: b7316e5e8cadc718872ea56dfecfb61709c636ce
---

# ADR-003 — Claim-time protocol isolation and cutover

## Context

Old executables must not strip authority they do not understand.

## Decision

Select strict journal2/j-ch-v1 at initial claim; preserve original7/extended11 v1 bytes and semantics; require J20 reject-before-publish for all effective writers.

## Alternatives considered

- Implicit migration or a mere ref prefix cannot establish isolation.

## Consequences

### Benefits

- No historical attempt is rehabilitated by schema evolution.

### Costs and obligations

- Inventory/drain/deny/isolation and actual scoped credentials remain unqualified operational gates.

## References

- Owner conditional direction: https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973
- Qualified candidate PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- RFC8785, JSON Schema Draft2020-12 and GitHub GraphQL updateRefs expected-old contract.
- Accepted specification, OIDC/result/evidence/execution/recovery contracts.
