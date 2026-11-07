---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "J-CH Versioned Journal and AtomicArm Contract Proposal"
version: "0.1.1"
---

# J-CH Versioned Journal and AtomicArm Contract — Proposal v0.1.1

**DRAFT / NON-NORMATIVE / NOT IMPLEMENTED / CORE SLICE TESTED — FULL CONTRACT NOT QUALIFIED**  
**Design issue:** [#91](https://github.com/fanilosendrison/review-broker/issues/91). **Companion candidate:** [J-CH ARM-bound Challenge proposal](arm-challenge-authority-proposal.md) (v0.1.2).  
This document proposes *journal* semantics only. It does **not** amend accepted OIDC ARM v1, ReviewRequest v1/v2, any executable schema, or the production journal. Requirements prefixed `J01`–`J23` are **candidate contract requirements**, not authorization to execute or merge.

## 1. Evidence, threat boundary, and nonclaims

- [Q1](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6698134952) observed ten unprotected `review-claims/*` refs, and an incomplete authorized-writer inventory.
- [Owner's explicit trust-boundary decision](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6706691402) accepts GitHub, approved authoritative writers/controllers and their credential custody as **trusted dependencies** for ordinary risk-proportionate reviews. It does **not** waive the requirement to reject bad input, broken transitions, credential exposure or ambiguous outcomes. The decision is already recorded in #91; this draft does not re-decide it.
- [Q2](https://github.com/fanilosendrison/review-broker/issues/95#issuecomment-6706224409) qualified *synthetic one-session SSH* in a disposable Codespace; it did **not** qualify journal authority or real OIDC.
- [Q3](https://github.com/fanilosendrison/review-broker/issues/96#issuecomment-6706990153) exercised GraphQL `updateRefs(beforeOid)` with the real scoped GitHub Actions `GITHUB_TOKEN`: one accepted head update in A/B and A/A competitions, lost ACK simulated by client-side response discard, and cleanup. Failed/stale calls produced **generic GitHub internal errors**, not typed compare-and-swap conflicts. This is bounded empirical evidence, not a complete linearizability proof.

**Guarantee domain:** at most one *broker-authorized Codex process start* per exact attempt, under trust of GitHub, approved writer code/credentials and privileged launcher within their declared responsibilities. No claim of provider-side exactly-once inference, protection against a malicious/compromised GitHub administrator or arbitrary snapshot duplication of an authorized launcher.

**Important impossibility boundary:** an authorized writer that **accidentally** deletes a consumed ref or writes a semantically regressive descendant can erase authoritative evidence just as a malicious writer can. Code-level monotonic validation and narrow writer custody reduce such defects but **cannot guarantee detection after all authoritative history has been removed**. An uncontrolled privileged write is an incident outside the protocol-correct-writer invariant; it is not silently considered safe because the writer was initially trusted.

## 2. Record format and version dispatch

**J01 — Separate version domains.** Journal `schema_version` is **not** ReviewRequest version or OIDC envelope version. New J-CH records use `schema_version: 2` and `protocol_id: "j-ch-v1"` from their **first claim**, not added by ARM to a v1 record. All older records retain exact bytes, identifiers and `schema_version: 1` semantics.

**J02 — Closed, lossless decoder.** A decoder must dispatch on the exact JSON integer `schema_version` (`type(v) is int`, not bool); reject missing, invalid, future or unsupported versions. For v2, require exactly the documented top-level field set and closed nested objects/validated references; no silent unknown-key dropping. A writer must preserve every field it is responsible for, with canonical RFC 8785-compatible bytes and the repository's accepted final newline convention. An unsupported record must not be rewritten, normalized, migrated or considered absent.

**J03 — v2 field domains.** A v2 record contains these required top-level keys: `schema_version`, `protocol_id`, `request_id`, `attempt_id`, `state`, `invocation_count`, `history`, `evidence_ids`, `arm_binding`, `evidence_locator_plan`, `evidence_locator`, `publication_intent`, `publication_receipt`. It may contain `admission` and `input_capacity` only in their established, closed domain-specific shapes, with their current identity checks. All other keys are invalid until an expressly accepted newer version. Optional legacy-compatible metadata fields are **not silently introduced or removed** by v2 updates; any accepted extension needs a revised schema and version.

**J04 — Identity stability.** Validate `request_id` domain, canonical attempt ordinal-1 identity derivation, deterministic claim-ref mapping, exact repository numeric identity and evidence/policy bindings. The request/attempt identities, protocol marker, initial admission, subject/packet identity, once-established capacity receipt and evidence provenance are never substituted by an ARM or later writer. A changed subject requires a distinct authorized ReviewRequest operation, never a new incarnation of an old attempt.

**J05 — Binding presence.** The required `arm_binding` is **JSON null** throughout `REQUESTED/ADMITTED/PREPARED` **and any `INDETERMINATE/STOPPED` state reached before AtomicArm**. The **only** transition allowed to set it non-null is the single atomic `PREPARED/count=0 -> ARMED/count=1` commit. From then on, `arm_binding` must exist, match the original canonical bytes and remain **byte-for-byte immutable** in every descendant record, including post-ARM `INDETERMINATE`, `REPORTED`, `STOPPED`. The exact persisted history, not the terminal enum by itself, distinguishes pre-ARM from post-ARM. Null/absent/conflicting bindings on an armed record are invalid, not grounds for reauthorization.

**J06 — Closed `arm_binding`.** The proposed exact object must bind: `binding_version` (fixed `1`), original `prepared_parent_sha` (40 hex), `challenge` (64 lowercase hex, generated only by live L), `request_id`, `attempt_id`, `packet_id`, `input_sha256`, exact capacity-receipt ID/digest, expected subject and reviewer policy/executable identities, `broker_repository_id`, trusted workflow ref/SHA, `controller_run_id`, `controller_run_attempt`, `codespace_name`, `codespace_id`, verified launcher program identity, and recipient/preflight observation digest. The record must reject unrecognized/missing/duplicate fields; all IDs cross-check their existing authoritative records and trusted observed context. This list is a **candidate wire field set**, not an approved final JSON Schema.

**J07 — No self-hashing commit field.** The committed binding **may include P**, its observed PREPARED parent SHA, but **must not include the new commit SHA A inside its own bytes**: that would make the commit identifier recursively self-referential. Construct A as a unique *direct child* of P; only **after** GitHub has accepted and C has positively observed A may the OIDC envelope bind both P and A, the binding digest and the original live challenge. The J-CH envelope remains separate and versioned; legacy v1 OIDC tokens cannot be accepted under J-CH.

Illustrative fragment only — **NOT** executable schema or real credentials:

```json
{
  "schema_version": 2,
  "protocol_id": "j-ch-v1",
  "state": "ARMED",
  "invocation_count": 1,
  "arm_binding": {
    "binding_version": 1,
    "prepared_parent_sha": "<exact 40-character SHA P>",
    "challenge": "<fresh launcher-generated 64-character hex N>",
    "attempt_id": "<same canonical attempt identity>",
    "controller_run_id": "<original Actions run ID>",
    "codespace_id": "<verified numeric recipient ID>",
    "...": "illustration only; all J06 fields required in executable contract"
  }
}
```

No key named `"..."` is permitted in an actual object. The full outer record retains all J03 required fields.

## 3. Legal transitions, counts, and monotonicity

**J08 — Consumption state invariant.** For v2: `invocation_count` is a strict JSON integer in `{0,1}`; it is `0` in `REQUESTED/ADMITTED/PREPARED`, **exactly `1` in `ARMED` and every state that descends from AtomicArm**. `INDETERMINATE` and `STOPPED` additionally admit **pre-ARM `count=0/arm_binding=null` histories** reached without any `ATOMIC_ARM_CONSUMED` event; the same state names admit post-ARM `count=1/arm_binding=original` histories only when that event is present. Thus neither `INDETERMINATE` nor `STOPPED` can determine consumption from the enum alone. `ARMED/count=0`, `PREPARED/count=1`, `ARMED` without binding and any count decrement are invalid. `count=1` is **durable authorization consumption**, **not observed Codex start or provider inference**.

**J09 — AtomicArm is the only entry into ARMED.** A single versioned `arm_once_challenge_bound` journal operation accepts only an authenticated, canonical, capacity-PASS `PREPARED/count=0/arm_binding=null` snapshot, with its exact parent SHA P and original controller-owned live launcher challenge. It creates *one* A with `state=ARMED`, `invocation_count=1`, fixed `arm_binding` and one new, canonically encoded `ATOMIC_ARM_CONSUMED` history event. Generic `transition(..., ARMED)` and `record_invocation()` are **not** legal v2 operations, including for `ARMED/count=0`; they remain available only under their accepted legacy contract.

**J10 — Post-arm and pre-arm stop states.** Preserve existing legal transitions and specialized evidence gates: `ARMED -> TERMINAL_CAPTURED -> VALIDATED -> REPORTED -> STOPPED`; alternatives to `INDETERMINATE`, then `STOPPED` under the existing accepted evidence/Shutdown requirements. **Pre-arm** `REQUESTED/ADMITTED/PREPARED -> INDETERMINATE -> STOPPED` also exists: it retains `count=0` and a null binding, and never carries a model grant. Post-arm transitions never reduce count, delete binding, change request/attempt/packet/recipient or create another launch authorization. `INDETERMINATE` reports uncertainty, **not retroactive revocation** of a proof already in the original trusted launcher.

**J11 — Pre-arm work.** Existing `REQUESTED -> ADMITTED -> PREPARED` and separately authorized evidence/retention/capacity metadata operations may continue only with count zero and null binding. A rejected input-capacity receipt is terminal for model-capable admission on that attempt. No legacy migration from a previously claimed v1 PREPARED record is inferred; a separately accepted migration would require an explicit historical non-replay plan.

**J12 — History, not just state string.** The candidate v2 `history` starts at claim, remains prefix-preserving and appends exactly one validated event per permitted mutating operation. `evidence_ids` are append-only (or unchanged for explicitly idempotent reads); new `ATOMIC_ARM_CONSUMED` entry records the protocol marker, count-one event, binding digest and exact relevant evidence IDs. Later states preserve that event. A trusted writer validates **the observed parent record and proposed child record together**, not only the child enum and Git ancestry. Descendant commits with semantically earlier or contradictory records are refused even if GitHub would accept a fast-forward.

**J13 — End-state immutability and no-op.** No invocation is ever permitted from `INDETERMINATE`, `STOPPED` or any previously consumed v1/v2 record. Exact idempotent reads may return existing data but **must not** create a new grant or commit; write attempts with `beforeOid == afterOid`, identical payload under a new grant, terminal state reversal, duplicated arm event or rebind are invalid. Post-result evidence recovery and publication remain separate authority, not permission to start Codex.

## 4. Exact GitHub observation and AtomicArm protocol

**J14 — Three distinct read outcomes.** For `GET` of a claim ref or its content:
- `PRESENT_VERIFIED`: authenticated success, exact ref and 40-hex SHA, fetched commit/tree/record identity match, canonical v1/v2 decoding and trusted repository identity.
- `ABSENT_AUTHENTICATED`: definitive, appropriately scoped `404` with no transport ambiguity and verified repository/credential capability. It is admissible only in the *new request claim* phase, never as authority to recreate a previously ARMED/consumed attempt. **404 cannot prove that a privileged actor never deleted an older ref.**
- `UNKNOWN`: timeout, malformed HTTP/JSON, 401/403, 408/409/422, 429, 5xx, inaccessible repo, missing/mismatched contents, ambiguity, rate limit, conflicting API observations or any other unclassified error. Every `UNKNOWN` refuses claim/re-arm/mint; it is never coerced to absence.

**J15 — Explicit expected-old, including for post-ARM writes.** The v2 writer computes exactly one new direct-child commit A of observed parent P, validates `(P_record,A_record)` before submission and invokes **GraphQL `updateRefs` (plural)** with `repositoryId`, the exact ref `name`, `beforeOid=P`, `afterOid=A`, `force:false`. No unconditional REST `PATCH` fallback, no `updateRef` (singular), no force and no mutation of the parent SHA after composing the call. Every v2 post-arm write must likewise use a checked expected-old transition and preserve J08–J13. The [bounded live Q3](https://github.com/fanilosendrison/review-broker/issues/96#issuecomment-6706990153) is evidence for this primitive, **not** for unrestricted future writers.

**J16 — Commit construction and success checks.** C must validate the exact prepared state, run/recipient/packet/preflight evidence and unique live challenge **before** composing A. Require a successful GitHub GraphQL response with no `errors`, correct `data.updateRefs` shape, no ambiguous transport/CLI failure, then an **independent fresh exact** ref and record observation of A (matching the proposed canonical content and direct-parent P). Only the original still-running C that prepared/sent this mutation and retains its original SSH launcher process may request OIDC. `clientMutationId` is correlation data, not proof of success, a lease or a grant.

**J17 — Irreversible ambiguous outcome.** If HTTP, CLI, GraphQL parsing, GraphQL `errors`, no response, timeout, wrong head, readback error or any other acknowledgement is uncertain **at or after the first attempted AtomicArm submission**, never retry a ref update, never mint OIDC and never reconnect/rebind for execution. Readback may classify and reconcile history **for evidence only**; even if A is later seen, it does **not** restore the interrupted controller's launch permission. This deliberately sacrifices availability. In Q3, stale/losing writes returned a generic "Something went wrong while executing your query" error; it is **not** a typed conflict and must not be reinterpreted as one.

**J18 — OIDC and post-mint check.** Only after the positive J16 path may C request the new versioned OIDC audience binding exact A, P, arm-binding digest, N, workflow/run, packet/capacity and recipient. Recheck authoritative state under accepted concurrency/lifecycle semantics before delivering proof; a missing, changed or ambiguous state refuses delivery. No second OIDC mint, grant reconstruction by a different controller, or new Codespace incarnation. An OIDC signature alone proves issuer/job/audience, not that a GitHub journal update succeeded; actual issuance ordering depends on trusted C.

**J19 — Atomicity limits.** `updateRefs(beforeOid)` enforces an exact ref-head predicate under its documented semantics and bounded Q3 observations. It does **not** validate business transitions, enforce no deletion, protect against out-of-band privileged writers, or guarantee the model provider saw exactly one request. The guarantee depends on trusted, protocol-conformant writers and the one-use original launcher boundary; none may be silently inferred from Git alone.

## 5. Compatibility and deployment gates

**J20 — Reject-before-publish upgrade order.** BEFORE the **first** new schema-v2 claim is admitted: deploy and independently qualify strict `schema_version` dispatch to **all** active trusted journal readers/writers (request processing, recovery/reconciler, evidence/publication commands, manually runnable tools and any still-running pinned old workflow SHA). Incompatible code **must refuse v2 without mutation**. Drain/disable older workflow executions or prove they cannot encounter the new records. Verify all listed writer paths, their versions and their effective permissions; no assertion that a new v2 field safely survives the old v1 `as_dict()` implementation. If such isolation cannot be established, STOP activation or explicitly design a disjoint ref namespace, with its own discovery/recovery invariants and migration decision. Merely publishing new decoder source on `dev` is not enough if old workflows remain runnable.

**J21 — Legacy coexistence.** Current v1 records and the original two-commit OIDC-v1 local consumption path remain byte-identical and callable only under their accepted scoped admission. No `schema_version=1 -> 2` in-place upgrade, no v1 JWT under J-CH, no retroactive new attempt identity, no re-ARM of historical #82, no reset of any previous count-one. A future migration of never-ARMED records needs separate owner acceptance and exact historical evidence; the default is **NO_MIGRATION**.

**J22 — Authoritative writer custody.** Under the owner-confirmed proportional trust model, approved writer/admin credentials remain trusted, but all operational writers must obey strict version, state and expected-old guards; untrusted reviewer/source material has no writer credentials. Observed credential exposure or unexpected privileged ability blocks the affected path. Admin/writer compromise, direct GitHub ref deletion/recreation and arbitrary privileged semantic rollback remain explicitly *unprotected residual risks*, not allegedly solved by GraphQL, a Git hash or signature. An accidental privileged destructive write is also an incident with no guaranteed recovery from the sole ref.

**J23 — Qualification and acceptance boundary.** Candidate acceptance requires executable tests for strict decoding, unknown-field preservation/refusal, v1/v2 isolation, all legal/illegal state pairs, one-time bound ARM, identical-target and divergent-target races, capacity rejection, partial GraphQL errors, response/readback ambiguity, 404-vs-unknown, stale readers, concurrent reconciler/terminal evidence, v1 historical non-replay and migration cutover. Offline models and Q3 are *partial evidence only*. Independent hostile review on exact candidate bytes, comparative J/E/B architecture and **separate owner normative adoption** precede implementation/prod admission. No new J-CH schema or Model-capable execution is authorized by this document.

## 6. Falsifiable examples: expected judgments

| Test vector | Proposed decoder / transition judgment | Why |
| --- | --- | --- |
| Exact v1 historical STOPPED/count1 | Read under v1 only, no J-CH write/mint | Preserve history |
| v1 PREPARED without protocol marker | **NO_IMPLICIT_MIGRATION** | Claim-time versioning |
| v2 `schema_version=true` or missing/future version | REJECT / UNKNOWN | Strict integer dispatch |
| v2 unknown top-level or unknown binding field | REJECT, never reserialize | No lossy writer |
| v2 ARMED/count0 or null binding | REJECT | Invalid intermediate state |
| v2 PREPARED/count1 or nonnull binding | REJECT | Inconsistent consumption |
| v2 ARMED/count1 with unchanged binding -> INDETERMINATE/count1 | PERMIT under evidence gate | Truthful uncertainty |
| v2 PREPARED/count0 with null binding -> INDETERMINATE/count0 -> STOPPED/count0 | PERMIT under evidence/Shutdown gates | Pre-arm interruption never consumed an invocation |
| v2 post-ARM INDETERMINATE/count1 without binding or ARM history event | REJECT | Historical consumption cannot be forgotten |
| v2 INDETERMINATE/count1 -> PREPARED/count0 | REJECT | No re-arm |
| v2 later commit preserves Git ancestry but drops ARM event | REJECT | Semantic monotonicity |
| Two C submit same P and different A/B | At most one ref update under expected-old | Exclusive authorization decision |
| Two C submit same P and same A | At most one ref update under expected-old | No accidental same-target success |
| Generic GraphQL error then ref observed at A | **NO_MINT / NO_RETRY**, evidence-only read | Ambiguous ACK |
| GitHub 403/429/5xx read or malformed record | UNKNOWN, stop | Never interpret as absent |
| Correctly authenticated 404 for a brand-new unclaimed request | Claim may proceed if all J14 conditions hold | Not equivalent to deleted history proof |
| A contains its own full SHA in canonical binding | REJECT contract design | Self-reference impossible |
| Old reader encounters schema v2 | REJECT and no mutation | Cutover requirement |

## 7. Core qualification findings (2026-11-07; bounded, non-normative)

An executable [candidate core-only schema](qualification/rb91-jch-journal-v2-core.schema.json) and [qualification tests](../../tests/test_rb91_jch_contract_qualification.py) were added to the same **Draft PR #94** for falsification. This is **not** a deployable schema or journal adapter: the slice deliberately refuses embedded `admission`, publication and artifact-locator payloads rather than accepting their nested shapes as arbitrary objects. These domains remain **unqualified**; so do the final `J06` wire-field naming decision, real commit-ancestry observation, full historical writer inventory, runtime OIDC/SSH binding and operational error transport.

- The core suite exercises exact version and field rejection, canonical/duplicate JSON, binding and capacity links, one atomic event, no-op/rebind/rollback refusal, pre/post-ARM INDETERMINATE/STOPPED histories, permission/404 vs UNKNOWN, and no mint/retry on ambiguous GraphQL outcomes.
- A real-code regression test on current `AttemptRecord.from_dict()` shows it **accepts v2 and `as_dict()` strips the protocol and arm binding**. The required `v2 -> reject without mutation` check is an **expected failure**, not a resolved gate. This blocks publishing any v2 journal. Only a future separate accepted, tested writer upgrade can close that gate.
- A fixture-only model does not prove every accepted v1 evidence state and publication domain was exercised; it must never be used as a replacement for the operational journal or imply independent hostile review.

## 7. Open work (honest acceptance status)

1. Complete J01–J23 as a **separately approved full** JSON Schema, state-transition adapter and tests with the exact domains for embedded admission/evidence/publication objects; the current core-only candidate is intentionally insufficient. Nothing here is executable wire approval.
2. Audit every actual writer and running workflow SHA; qualify fail-closed upgrade before any v2 record exists, or choose an explicitly accepted alternate ref namespace.
3. Resolve exact read/rate-limit/error transport and positive GraphQL response shape with code-level mocks and, if necessary, additional scoped **non-inference** experiments. No live J-CH ARM attempt is authorized.
4. Qualify same-process original launcher one-use, SSH failure/abrupt disconnect, reconciler interleavings and OIDC binding separately. Q2 is only nominal synthetic transport; Q3 only ref-CAS evidence.
5. Complete J/E/B cost/trust comparison, independent hostile technical review and explicit owner architecture/contract acceptance. PR #94 remains Draft.

```text
CONTRACT_PROPOSAL=RB91_JCH_JOURNAL_ATOMIC_ARM
PROPOSAL_VERSION=0.1.1
STATUS=DRAFT_NON_NORMATIVE
ACCEPTED_JOURNAL_SCHEMA=V1_UNCHANGED
CANDIDATE_JOURNAL_SCHEMA=V2_CORE_OFFLINE_QUALIFICATION_ONLY
SCHEMA_SCOPE=ATOM_ARM_CORE_NO_ADMISSION_OR_POST_RESULT_PAYLOADS
OLD_WRITER_REJECT_V2=BLOCKED_KNOWN_ACCEPTS_AND_STRIPS
GRAPHQL_UPDATEREFS_Q3=BOUNDED_REAL_PASS_WITH_GENERIC_ERRORS
OWNER_TRUST_BOUNDARY=ACCEPTED_FOR_ORDINARY_USE
OLD_WRITERS_STRICT_UPGRADE=NOT_IMPLEMENTED
SCHEMA_CUTOVER=NOT_AUTHORIZED
JCH_ARCHITECTURE_ADOPTED=NO
OIDC_V1_CONTRACT=UNCHANGED
HISTORICAL_REQUEST82=IMMUTABLE_CONSUMED
PRODUCTION_ARM_AUTHORITY_QUALIFIED=NO
REAL_MODEL_INVOCATIONS=0
```