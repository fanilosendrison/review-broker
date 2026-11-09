---
okf_version: '1.0'
adr_profile_version: 0.1.0
kind: KnowledgeAsset
asset_type: architecture-decision-record
domain: independent-review
severity: strict
name: Separate execution and result-storage provenance
id: ADR-005
status: proposed
date: '2026-11-09'
decision_body_sha256: 8a6d3a0910f79c3786e47f60ab6601017f1dcfb2c8ac28731bd14ed224786293
relation_completeness: complete
relations:
  clarifies: []
  amends: []
  supersedes: []
  confirms: []
governs:
- result-recovery-storage-provenance
participants:
  decision_makers:
  - Product owner
extensions:
  document_version: 0.1.0
  adoption_packet: RB91_JCH_GOVERNED_NORMATIVE_ADOPTION
  qualified_source: b7316e5e8cadc718872ea56dfecfb61709c636ce
---

# ADR-005 — Separate execution and result-storage provenance

## Context

A later upload must not pretend to be the original execution run, nor alter result truth.

## Decision

Keep immutable execution, authenticated actual storage and exact faithful result content distinct; verify storage-purpose workload/context/archives before one publication reservation.

## Alternatives considered

- Original-run-only retention was rejected by the owner; declarations or signatures alone do not prove result fidelity.

## Consequences

### Benefits

- Correct downstream recovery remains possible without inference or duplicate posting.

### Costs and obligations

- Source/job/policy custody, full metadata consistency/chronology, exact receipt attribution and real end-to-end qualification remain required.

## References

- Owner conditional direction: https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973
- Qualified candidate PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- RFC8785, JSON Schema Draft2020-12 and GitHub GraphQL updateRefs expected-old contract.
- Accepted specification, OIDC/result/evidence/execution/recovery contracts.
