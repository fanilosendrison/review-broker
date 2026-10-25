---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Recovery Runbook"
version: "0.1.0"
---

# Review Broker Recovery Runbook

## Evidence first

Read the deterministic claim ref, current attempt record, exact workflow run,
packet artifact, recovered evidence artifact, request Issue, and observed
Codespace state. Do not use an Issue comment or desired external state as
terminal execution truth.

## Safe recovery by state

- `REQUESTED`, `ADMITTED`, or `PREPARED`: resume the same attempt before the
  model boundary. Rebuild packets only from the same resolved commits and
  require the same packet identity.
- `ARMED`: if complete terminal evidence is absent, record `INDETERMINATE`, stop
  the Codespace, and do not invoke Codex again.
- `TERMINAL_CAPTURED`: validate recovered evidence without inference.
- `VALIDATED`: publish the existing result without inference.
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
evidence was recovered.

Validation and publication failures retain captured artifacts and resume only
the failed downstream operation. A failed stop remains an infrastructure
incident until `Shutdown` is observed.

## Reconciler

The hourly and manually dispatched reconciler reads
`refs/heads/review-claims/`, evaluates each journal state, observes the dedicated
Codespace, marks an inconclusive armed attempt indeterminate, and stops stranded
runtime state. It emits a reconciliation artifact. It never launches a second
model attempt.
