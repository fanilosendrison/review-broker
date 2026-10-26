---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "Review Execution v1 Contract"
version: "0.1.0"
---

# Review Execution v1 Contract

## Durable states

The journal permits this primary path:

```text
REQUESTED
→ ADMITTED
→ PREPARED
→ ARMED
→ TERMINAL_CAPTURED
→ VALIDATED
→ REPORTED
→ STOPPED
```

A state may enter `INDETERMINATE` only through the explicit legal transition
map in `queue.py`. Cleanup may move `INDETERMINATE` to `STOPPED`. Every
transition requires an evidence identity.

`REQUESTED` means an atomic deterministic claim exists. `ADMITTED` requires a
validated, authorized, immutable resolution. `PREPARED` requires a verified
packet. `ARMED` is durable before a model-capable call. `TERMINAL_CAPTURED`
requires a receipt binding the request, attempt, packet, complete terminal
artifact inventory, and one non-contradictory terminal event sequence.
`VALIDATED` requires independent validation. `REPORTED` requires observed
publication. `STOPPED` requires a receipt binding the request, attempt,
Codespace, workflow context, observation time, and actual `Shutdown` after
reporting or indeterminate cleanup.

Generic journal transitions cannot create `TERMINAL_CAPTURED` or `STOPPED`.
Those states require their specialized evidence-validating operations. A failed
or ambiguous shutdown observation records an infrastructure incident and does
not create `STOPPED`.

## Atomic claim and idempotence

The claim ref is deterministic from the request SHA-256. GitHub ref creation is
atomic: one concurrent creator wins and all others read that winner. Journal
updates create a child commit and update without force; a competing child is
non-fast-forward and fails. Issue comments are not execution claims.

Actions concurrency serializes scheduling for the single Codespace but is not
the authoritative journal.

## At-most-once boundary

The journal records `ARMED` and `invocation_count = 1` before Codex transport.
The adapter refuses a packet containing any prior attempt artifact. No retry is
allowed after `ARMED` without conclusive terminal evidence. A lost response is
`INDETERMINATE`.

This contract limits broker CLI invocations to one per attempt. It does not
claim that provider transport implements exactly-once inference.

## Recovery

Pre-model states can resume the same attempt. Captured evidence can be validated
without inference. Validated evidence can be published without inference.
`ARMED` without terminal evidence is marked indeterminate and stopped.

The reconciler reads authenticated open request Issues as well as durable claim
refs. A lost Issue event creates or reuses the deterministic claim before a
pre-model dispatch. It reports unsupported states, incomplete scans, missing
artifact locators, and failed cleanup explicitly; it never converts them into a
later durable state.
