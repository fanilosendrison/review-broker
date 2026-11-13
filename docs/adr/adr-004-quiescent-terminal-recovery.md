---
okf_version: '1.0'
adr_profile_version: 0.1.0
kind: KnowledgeAsset
asset_type: architecture-decision-record
domain: independent-review
severity: strict
name: V2 quiescence before terminal recovery
id: ADR-004
status: accepted
date: '2026-11-09'
decision_body_sha256: ad6213f461029bf14ecbf220490a797dc3f20fabbdfc734a30d84a5690289374
relation_completeness: complete
relations:
  clarifies: []
  amends: []
  supersedes: []
  confirms: []
governs:
- v2-terminal-fencing
participants:
  decision_makers:
  - Product owner
extensions:
  document_version: 0.1.0
  adoption_packet: RB91_JCH_GOVERNED_NORMATIVE_ADOPTION
  qualified_source: b7316e5e8cadc718872ea56dfecfb61709c636ce
---

# ADR-004 — V2 quiescence before terminal recovery

## Context

An already delivered proof may start after mark-first recovery records uncertainty.

## Decision

For v2 use verified quiescence and held lifecycle custody before an incompatible terminal expected-old CAS; preserve v1 ordering.

## Alternatives considered

- Cancellation transit, fresh head reads and SSH loss are not fences.

## Consequences

### Benefits

- No late first start after an incompatible terminal decision within the qualified custody boundary.

### Costs and obligations

- Real Shutdown/child-tree proof, all-mutator custody and terminal-evidence races need implementation and operational qualification.

## References

- Owner conditional direction: https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973
- Qualified candidate PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- RFC8785, JSON Schema Draft2020-12 and GitHub GraphQL updateRefs expected-old contract.
- Accepted specification, OIDC/result/evidence/execution/recovery contracts.
