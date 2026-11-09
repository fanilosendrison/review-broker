---
okf_version: '1.0'
adr_profile_version: 0.1.0
kind: KnowledgeAsset
asset_type: architecture-decision-record
domain: independent-review
severity: strict
name: Ordinary trusted authority boundary
id: ADR-001
status: proposed
date: '2026-11-09'
decision_body_sha256: f7ebfe521c2fe4d2b2623939402de3818da989f2b49b39e55291e5c967007869
relation_completeness: complete
relations:
  clarifies: []
  amends: []
  supersedes: []
  confirms: []
governs:
- ordinary-risk-proportionate-authority
participants:
  decision_makers:
  - Product owner
extensions:
  document_version: 0.1.0
  adoption_packet: RB91_JCH_GOVERNED_NORMATIVE_ADOPTION
  qualified_source: b7316e5e8cadc718872ea56dfecfb61709c636ce
---

# ADR-001 — Ordinary trusted authority boundary

## Context

Consumption must survive executor loss without claiming safety after fully privileged GitHub/host compromise.

## Decision

Retain the owner-confirmed ordinary GitHub/writer/host dependency boundary; ordinary faults, leaks, fork/reentry and ineffective Shutdown remain defects.

## Alternatives considered

- Independent anti-admin custody is not required solely for the excluded administrator threat.

## Consequences

### Benefits

- Avoids inventing an external authority solely for an excluded adversary.

### Costs and obligations

- Qualified code, credential custody and specific observed-leak veto remain mandatory.

## References

- Owner conditional direction: https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973
- Qualified candidate PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- RFC8785, JSON Schema Draft2020-12 and GitHub GraphQL updateRefs expected-old contract.
- Accepted specification, OIDC/result/evidence/execution/recovery contracts.
