---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "evidence-disposition"
domain: "independent-review"
severity: "draft"
name: "RB91 Current Evidence Disposition"
version: "0.1.1"
---

# RB91 — Current disposition, 2026-11-09

## Immutable historical observations and exact present source

This dated addendum does not edit historical Q4, verdicts or Issue comments.
At initial dossier SHA85149a17c6eda3e8f7cbc5f0f00c280f1b5ecdf9 the five
historical documents/schema/model files were byte-identical to PR94
`eb1e2772159ba7faa4ae5f57cb24b3bf40d9d6ce`. F1 removes the two trailing-space
pairs from lines13–14 of the copied journal proposal; that copy is no longer
byte-identical. Four other historical files and PR94 itself remain unchanged.
Their contemporary failure labels remain correct for the source they examined,
not the present integrated binary.

Fresh fetch and GitHub PR reads observed:

- dev `3057192a6ad4e80663b3b8168cbaa52657c3db27`.
- PR94 OPEN/DRAFT, head `eb1e2772159ba7faa4ae5f57cb24b3bf40d9d6ce`.
- PR100 MERGED, head `e5faa6f4d24f5ad168b754dbd501d3b544768c03`, merge
  `671ae588f25464b6ac80bddb44af83b8ca6b9af8`.
- PR106 MERGED, head `b54171e734f6ea457584fe276d01b9d593f91963`, merge
  `3057192a6ad4e80663b3b8168cbaa52657c3db27`.
- PR106 merge parents are prior dev and approved head, in that order; its tree
  equals approved head `5efdd01402647e5fea486c50f2f5cb52e5dbcdc2`.
  Both R1/R2 approved heads are ancestors of current dev.
- #97/#102 CLOSED/completed; #91/#83/#107 OPEN. #95/#96 bounded experiments
  completed, not production acceptance. Project17's standard fields/view match
  AGENTS; #91 moved Todo→In Progress with fresh readback; no Done/closure claim.

## Qualification inventory

| Evidence | Exact reference | Current bounded disposition |
| -------- | --------------- | --------------------------- |
| Q1 | #91 comment6698134952 | Ten unprotected claims, zero protected branches in 61-branch snapshot, incomplete privilege census. Historical observation, not updated into an anti-admin guarantee |
| Owner trust | #91 comment6706691402 | 2026-11-07 accepted ordinary-profile GitHub/approved-writer trust; not J-CH adoption |
| Phase2/3/4 | #91 comments6697694942/6699304864/6699837657 | Actual finite model results retained with original bounds/hashes; not unbounded/runtime proof; research bundles were outside GitHub |
| Phase5 | #91 comment6705109389 | Mark-first late-first-start counterexample; shared Actions scheduler, possible orphan remains separate |
| Phase6/7 | #91 comments6705233912/6705364596/6705374578 | Local synthetic process/framing results, fork counterexample, 16KiB fixture insufficient as production PROOF bound |
| Q2 | #95 comment6706224409 | PASS_BOUNDED_REAL_SSH: one process observed across nominal HELLO/pause/PROOF; primary four cases plus preserved first series/supplement, 9 sessions/5 fake starts; no real OIDC/AtomicArm; abrupt orphan lifecycle UNKNOWN |
| Q3 | #96 comment6706990153 | PASS_BOUNDED_WITH_UNTYPED_ERRORS: A/B and A/A unique accepted updates, generic errors; ACK loss client-injected, not network qualification; 9 disposable refs cleaned |
| Q4 | PR94 report and #91 comment6707983349 | Historical PARTIAL_CORE_PASS_FULL_CUTOVER_NO_GO, 643 tests/1 expected failure; core only, not complete ABI |
| R2 old NO_GO | PR100 comment6708992062 at d88fa0e8b24e41ac2cd095f0c881b2b65d5aecfa | Original7 rejection remains a real old-SHA defect, never rewritten |
| R2 GO | PR100 comment6710805675 at e5faa6f4d24f5ad168b754dbd501d3b544768c03 | Source repair, 633-test suite and independent extra controls; original7/extended11 retained |
| R2 integration | PR100 comment6711375749; CI42400935760 | Exact ordinary merge and post-merge633 PASS; new source only, not old executable revocation |
| R1 old NO_GO | PR106 comment6729001852 at 9f7326563ef496c4a62d9b235f8afbbb45fef987 | Explicit shared-tree/path contradiction: 3 genuine REDs; separate earlier refusals/NO_GOs remain historical |
| R1 GO | PR106 comment6729959024 at b54171e734f6ea457584fe276d01b9d593f91963 | Exact independent GO, unchanged69/fresh11 and full701 PASS; bounded scope/identity/UNKNOWN refusal, not full remote-graph or malicious-service attestation |
| R1 integration | PR106 comment6730245043; CI42546569358 | Merge3057192, exact runner checkout/full701 PASS; scoped live Actions capability still separate |
| #83 B | comment6668614720 | Conditional target only; nine persistent-type candidates not qualified allocations; FEASIBILITY_UNDETERMINED and historical45→46→45 unchanged |
| #107 | open issue107 | Pre-existing umask077 unsafe-root test-fixture defect remains OPEN/unfixed, independent of current design tests; normal022 suite used, no production guard weakened |

Canonical URLs are `https://github.com/fanilosendrison/review-broker/issues/N#issuecomment-ID`
or `/pull/N#issuecomment-ID` as identified above. Exact run receipts are at
`https://github.com/fanilosendrison/review-broker/actions/runs/ID`.

## JQ finding-by-finding current disposition

- **JQ-001/R2:** source FIXED/INTEGRATED. New executable legacy tests now assert
  v2 and hybrid refusal and original/extended v1 preservation. Historical Q4
  expected failure is not rerun as a false current expected failure.
- **JQ-002:** pre/post-ARM history distinction retained, no reinterpretation.
- **JQ-003:** complete candidate schema and typed nested metadata/reference
  contract now supplied. Candidate tests PASS; production ABI implementation
  and operational qualification remain NOT DONE.
- **JQ-004/R1:** source FIXED/INTEGRATED; new adapter no longer treats every
  failed read as absence. Old executables retain their original behavior.
  New GraphQL adapter and actual intended token capability remain unqualified.
- **JQ-005:** D05/D06 candidate boundary/fence now specified and additional
  finite falsification executed. Real integrated journal/OIDC/launcher still open.
- **JQ-006/J20:** updated source/API/run inventory supplied; no old writer drain,
  permission change, workflow disabling, remote installation census or activation.

## Atomic discovery records

### ED01 — Current source no longer has the old R1/R2 behavior

Statement: Q4 present-tense source-defect labels are stale for3057192, not false
historically. Evidence: exact merge ancestry, independent GO/integration receipts
and new current tests. Existing authority: accepted historical preservation and
strict failure boundaries. Disposition: `no-normative-impact`. Layers:
verification-or-qualification-evidence; repository-governance-or-documentation.
Consequences: old binaries/J20 remain separate. Required authority: reporting
only. Next action: retain old evidence and publish this dated disposition.

### ED02 — Mark-first cannot establish the stronger terminal no-start fence

Statement: an already delivered proof can reach a first start after R marks
INDETERMINATE. Evidence: phase5 and new bounded traces. Existing authority:
accepted v1 INDETERMINATE is uncertainty, STOPPED requires actual Shutdown;
no accepted instantaneous revocation promise. Disposition: `decision-required`.
Layers: normative-contract; decision-history; formal-model-or-analysis;
verification-or-qualification-evidence; architecture-or-implementation.
Consequence: candidate v2 S2 ordering differs from v1. Required authority:
product owner. Next action: adjudicate proposed quiescence-before-terminal
ordering with architecture adoption, not change v1 recovery in this task.

### ED03 — Full journal ABI can reference exact versioned result bytes

Statement: a closed typed content/location reference can avoid embedding an
open ReviewResult payload into the closed journal. Evidence: candidate schema,
identity/byte/refusal tests. Existing authority: accepted result/artifact identity
and publication separation; PR94 candidate J03, not accepted ABI. Disposition:
`decision-required`. Layers: normative-contract; architecture-or-implementation;
verification-or-qualification-evidence. Consequence: additional private validated
result retention/retrieval before intent, no v1 result/schema rewrite. Required
authority: owner. Next action: include exact candidate choice in adoption packet.

### ED04 — Request implementation-status prose diverges

Statement: product specification and execution contract describe request2 as
unimplemented while accepted review-request-v2 contract and current source
report/implement it. Evidence: pinned documents' versioned-boundary/status
sections and actual parser/admission/source. Existing authority order places
product intent above implementation; no safety invariant conflict is resolved by
source. Disposition: `authority-conflict-or-uncertain`. Layers:
repository-governance-or-documentation; integration-or-conformance.
Consequences: no inference of active request2 operational admission; journal2 is
independent. Required authority: future owner-governed authority reconciliation.
Next action: preserve accepted docs untouched; this dossier uses their common
stable identities/no-retry/disabled-admission requirements and explicitly does
not promote source into normative execution authority. This status-prose issue
is not a new prerequisite for choosing the durable authority concept.

## F1 owner disposition and revision — 2026-11-09

The [owner](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973)
conditionally selected J-CH and resolved ED03's design direction: do NOT accept
permanent publication blockage solely because a valid terminal execution's
original run ended before result retention. Keep execution immutable and permit
separately authenticated recovery storage. S2 and the protected-host boundary
are confirmed; B/E remain nonpreferred alternatives. These decisions are not
reopened and do not perform formal normative adoption.

The prior independent GO and F1 counterexample on85149a17… remain immutable.
The new [F1 candidate](../rb91-f1-storage-provenance.md) replaces RESULT_RUN with
distinct execution, storage/job/actor, issuer, evidence and content predicates.
A NEW exact-SHA review for normative-adoption readiness is required; no old GO
qualifies amended bytes. Historical Q4 and R1/R2 outcomes are unchanged.
