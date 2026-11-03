---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Recovery Runbook"
version: "0.2.0"
---

# Review Broker Recovery Runbook

## Evidence first

Read the deterministic claim ref, current attempt record, exact workflow run,
packet artifact, recovered evidence artifact, request Issue, and observed
Codespace state. Do not use an Issue comment or desired external state as
terminal execution truth.

## Safe recovery by state

- `PREPARED` with a rejected `input_capacity` receipt: preserve the packet,
  exact counts and claim, keep invocation count zero, and report
  `BLOCKED_INPUT_CAPACITY`. Do not arm, automatically dispatch, manufacture a
  model verdict or reset that receipt. A remedy requires separately authorized
  work under the [capacity contract](../contracts/added-source-rendering-capacity.md).
- `REQUESTED`, `ADMITTED`, or `PREPARED` without a capacity rejection: resume the same attempt before the
  model boundary. Re-admission must reproduce the recorded resolved-request
  evidence identity. A rebuilt prepared packet must reproduce the recorded
  packet evidence identity before execution can continue.
- `ARMED`: if complete terminal evidence is absent, record `INDETERMINATE`, stop
  the Codespace, and do not invoke Codex again.
- `TERMINAL_CAPTURED`: resolve or read the journal-bound Actions artifact
  locator, reject unavailable or mismatched evidence, download exact bytes, and
  validate without inference. Missing locators remain
  `BLOCKED_EVIDENCE_LOCATION`.
- `VALIDATED`: reconstruct the same validation from the exact terminal artifact
  and require its recorded evidence identity before publication. Missing or
  expired evidence remains blocked.
- `REPORTED`: stop and verify `Shutdown`.
- `INDETERMINATE`: preserve uncertainty and complete cleanup only.
- `STOPPED`: require actual Codespace `Shutdown`; a mismatch is an incident.

## Failure cases

Lost GitHub events are found by claim-ref and Issue reconciliation. Duplicate
requests resolve to the existing deterministic claim. Stale pre-model work can
resume; stale post-arm work cannot infer transport outcome.

Failed startup or transfer before `ARMED` can resume the same attempt after the
cause is corrected. SSH failure after `ARMED`, lost terminal response, or
workflow cancellation after arming is indeterminate unless complete terminal
evidence was recovered. Recovery records every attempted artifact transfer;
missing, truncated, malformed, or contradictory terminal streams cannot create
`TERMINAL_CAPTURED`.

Validation and publication failures retain captured artifacts and resume only
the failed downstream operation. Publication recovery first records a unique
intent. Only the reservation creator may post; all later executions observe the
exact nonce-bearing result comment and actor. No comment after an attempted post
is ambiguous and is never retried automatically. A failed stop remains an
infrastructure incident until `Shutdown` is observed.

## Reconciler

The hourly and manually dispatched reconciler completely paginates authorized
open request Issues and `refs/heads/review-claims/` within explicit bounds. It
authenticates and resolves request envelopes before creating or reusing a
canonical claim. Missing Issue delivery and pre-model states dispatch the
trusted default-branch workflow; concurrent or duplicate dispatches retain one
claim and cannot create a second attempt.

The reconciler marks an inconclusive armed attempt indeterminate, obtains a
bound shutdown observation, and records `STOPPED` only from that receipt. It
emits a reconciliation artifact, resolves planned artifacts when possible, and
never launches a second model attempt. Expired, unavailable, incomplete, or
identity-mismatched artifacts and ambiguous publication remain explicit blocked
outcomes.
