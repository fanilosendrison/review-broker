---
okf_version: '1.0'
adr_profile_version: 0.1.0
kind: KnowledgeAsset
asset_type: architecture-decision-record
domain: independent-review
severity: strict
name: J-CH durable consumption authority
id: ADR-002
status: accepted
date: '2026-11-09'
decision_body_sha256: 9a096763465325de69bb5ed8e781b43cae336ccb5885f530ff93574f7ad02920
relation_completeness: complete
relations:
  clarifies: []
  amends: []
  supersedes: []
  confirms: []
governs:
- durable-attempt-consumption
participants:
  decision_makers:
  - Product owner
extensions:
  document_version: 0.1.0
  adoption_packet: RB91_JCH_GOVERNED_NORMATIVE_ADOPTION
  qualified_source: b7316e5e8cadc718872ea56dfecfb61709c636ce
---

# ADR-002 — J-CH durable consumption authority

## Context

Ephemeral Codespace state cannot supply the required lifetime of consumed authority.

## Decision

Use one GitHub AtomicArm binding the original passive launcher challenge and count1, followed only by the original acknowledged controller and one protected continuation.

## Alternatives considered

- J2-A exposes writer custody remotely; J2-B adds a final CAS; B is unqualified backing; E adds custody without a required guarantee.

## Consequences

### Benefits

- Durability is independent of executor lifetime with explicit irreversible linearization.

### Costs and obligations

- Exact expected-old/parent/child validation, UNKNOWN forfeiture, workload binding and one-shot qualification are required.

## References

- Owner conditional direction: https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973
- Qualified candidate PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- RFC8785, JSON Schema Draft2020-12 and GitHub GraphQL updateRefs expected-old contract.
- Accepted specification, OIDC/result/evidence/execution/recovery contracts.
