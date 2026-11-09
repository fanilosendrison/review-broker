---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "RB91 Durable Authority Decision Dossier"
version: "0.1.0"
---

# RB91 — Durable authority decision dossier

**2026-11-09 · NON-NORMATIVE · OWNER DECISION REQUIRED · NO ACTIVATION**

## Executive recommendation

**RECOMMEND_J_CH**, conditionally, for the ordinary trusted-GitHub profile.
GitHub remains the sole durable consumption authority; a protected live
launcher supplies an ephemeral, non-transferable-in-protocol continuation.
Neither a second database nor a persistent Codespace volume is necessary for
the required safety property under the accepted dependency assumptions.

The recommendation depends on ALL of the following candidate obligations:

1. One claim-time journal v2, strict decoding, immutable ordinal-1 identity,
   monotone parent/child validation, and one AtomicArm expected-old update.
2. Only the original controller with a clean ACK, exact readback and its
   original live SSH launcher may mint and deliver one bound OIDC proof.
3. The protected launcher generates its own challenge, never restores it,
   never forks/copies authorized state, atomically consumes one continuation,
   and exposes no alternate model-start entry point to the reviewer.
4. V2 reconciliation establishes quiescence before committing an incompatible
   terminal decision. A stop request, SSH disconnect, lease expiry or journal
   reread is NOT a quiescence fence.
5. J20 proves reject-before-publish for every effective old writer, or stops
   activation. No separate ref namespace is implicitly selected.

These are implementation acceptance conditions, not claims that the current
runtime satisfies them. The conceptual argument is sufficient to propose an
architecture without first operating production. If ordinary process copying,
reentry, bypass or ineffective Shutdown remains possible in a proposed
implementation, that implementation cannot qualify under this recommendation.
A nonce or PID is not evidence to waive this gate.

## Reading map and authority

- [Guarantees](rb91-guarantee-matrix.md): all twelve obligations and evidence bounds.
- [D01–D08 and launch protocol](rb91-launcher-decision-ledger.md).
- [Complete candidate journal contract](rb91-journal-v2-candidate.md).
- [Architecture comparison](rb91-architecture-comparison.md).
- [Evidence reconciliation](qualification/rb91-current-evidence-disposition.md).
- [J20 and future qualification](qualification/rb91-j20-preparation.md).
- [Offline experiment results](qualification/rb91-decision-experiments.md).

Product specification, public schemas and accepted contracts retain authority.
All new rules here are proposals. Issues, PRs, models and reviewer verdicts are
inputs to a decision, not normative authority. Existing OIDC ARM v1, its local
consumption store, legal recovery order and historical attempts remain unchanged.
The request-schema version, journal-schema version and OIDC protocol version
are different domains.

## Exact provenance and publication strategy

Freshly fetched `dev`: `3057192a6ad4e80663b3b8168cbaa52657c3db27`.
Original Draft [PR94](https://github.com/fanilosendrison/review-broker/pull/94):
`eb1e2772159ba7faa4ae5f57cb24b3bf40d9d6ce`, based on
`64ee8062c5016cdc5a862b49b8acea18eec0aab4`.
This dossier starts from current `dev`, copies PR94's six design/test files,
and changes only its still-executable obsolete legacy-decoder assertions.
The original proposal, journal proposal, Q4 report and core schema are retained
byte-for-byte. Their historical present-tense labels are NOT current status.
The dated disposition is authoritative only as a report of new evidence.

A new Draft avoids force-updating or merging into PR94's research branch.
PR94 remains open/Draft; it is not closed or declared an accepted replacement.
No source in `src/`, accepted document, public schema, operational workflow,
credential grant or admission variable is changed.

Preflight inventoried the persistent `dev` checkout and 35 existing linked
worktrees, including R1 implementation/review and earlier qualification trees.
Only the new task-owned linked worktree is used for edits and validation.
No sibling state is stashed, switched, cleaned, rewritten or removed.
Exact branch/worktree inventories and raw API snapshots remain private.

## Safety argument and limits

Suppose two broker-authorized starts occur for the same attempt. Under strict
monotonicity and trusted GitHub expected-old semantics, at most one AtomicArm
can consume that attempt. Both starts must therefore redeem the same binding.
Distinct conforming launcher incarnations have independent unpredictable
256-bit challenges and cannot import a recorded challenge or acquire another
controller's session. The only eligible original incarnation has one atomic
WAITING-to-CLAIMED continuation and one child-start call. Two starts therefore
require a challenge collision, copied privileged state, a bypass/reentrant
launcher, a nonconforming writer/controller or broken provider/OS semantics.
Those are explicit boundaries or qualification failures, not properties proved
by GitHub CAS. Random collision probability is negligible, not mathematically
zero (birthday bound approximately n(n−1)/2^257 for n independent challenges).

No provider-level exactly-once inference, execution liveness, instantaneous
revocation, arbitrary privileged-host cloning resistance or compromised-GitHub
anti-rollback is claimed. Consumed but never started is an intentional outcome.
Quiescence fencing additionally excludes late first starts AFTER an incompatible
terminal decision; it cannot retract a start that already occurred.

## Decisions and handoff

Already decided: the owner's 2026-11-07 ordinary-profile trust of GitHub and
explicitly authorized writers; decision27's proportionate assurance boundary;
immutable historical consumed attempts and no automatic post-ARM retry.

Derived, not new product choices: UNKNOWN never creates permission; lost ARM
ACK never mints; old executable bytes are not repaired by merging new source;
STOPPED requires actual observed Shutdown; v1 histories cannot become v2.

Still for the owner, as one explicit adoption packet:

- Select J-CH rather than J2-A/J2-B/E/B for the ordinary profile.
- Accept claim-time journal v2 and a disjoint `j-ch-v1` OIDC envelope, AtomicArm
  consumption semantics and the complete candidate ABI (including referenced,
  rather than embedded, publication result bytes).
- Accept the proposed v2 quiescence-before-terminal recovery ordering; v1 stays
  mark-first. Select S2 for incompatible terminal decisions, not instantaneous
  revocation on cancellation request.
- Confirm the stated protected-host boundary excludes arbitrary privileged
  memory cloning, while ordinary fork/reentry/relaunch bugs remain testable
  implementation defects and cannot be waived as host trust.
- Later, separately authorize construction, bounded live non-inference
  qualification, J20 rollout and operational admission on exact configurations.

No additional owner decision about a database, permanent VM, persistent volume,
GitHub plan upgrade or namespace is required by current evidence. If J20 cannot
establish writer isolation, a separate namespace proposal or alternative custody
requires a NEW explicit decision, not an automatic fallback.

Deferred until after conceptual adoption: real v2 journal adapter; issuer and
same-session launcher integration; protected deployment and bypass/credential
qualification; abrupt disconnect/crash/reentry tests with independently retained
start witnesses; all-writer J20 and effective Actions credential capability;
end-to-end cleanup/evidence/publication qualification. These are not accomplished.

Issue91 remains OPEN. Its formal owner-adoption and eventual closure criteria
are not satisfied merely by this dossier or an independent design GO.
Production ARM and J-CH v2 admission remain disabled.
