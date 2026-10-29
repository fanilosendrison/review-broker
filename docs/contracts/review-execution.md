---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "Review Execution v1 Contract"
version: "0.2.0"
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

Generic journal transitions cannot create `TERMINAL_CAPTURED`, `REPORTED`, or
`STOPPED`. Those states require their specialized evidence-validating
operations. `REPORTED` additionally requires a precommitted publication intent
and an independently observed exact GitHub comment receipt. A failed
or ambiguous shutdown observation records an infrastructure incident and does
not create `STOPPED`.

## Atomic claim and idempotence

The claim ref is deterministic from the request SHA-256. GitHub ref creation is
atomic: one concurrent creator wins and all others read that winner. Journal
updates create a child commit and update without force; a competing child is
non-fast-forward and fails. A journal reader obtains the ref once and retrieves
state from that exact immutable commit SHA, so ref movement cannot mix content
from a newer commit with an older compare-and-swap parent. Issue comments are
not execution claims.

Actions concurrency serializes scheduling for the single Codespace but is not
the authoritative journal.

## At-most-once boundary

The journal records `ARMED` and `invocation_count = 1` before Codex transport.
The adapter refuses a packet containing any prior attempt artifact. No retry is
allowed after `ARMED` without conclusive terminal evidence. A lost response is
`INDETERMINATE`.

Each v1 request retains its existing ordinal-1 attempt. Every future v2 request
also permits exactly one attempt, with ordinal `1` and the existing
`attempt_identity(request_id, 1)` computation. V2 never allocates a greater
ordinal. Completed, failed, and indeterminate attempts are never reset, reused,
or incremented for another model invocation.

This contract limits broker CLI invocations to one per attempt. It does not
claim that provider transport implements exactly-once inference.

## Versioned duplicate and re-review execution

Canonical byte-identical requests share one deterministic request identity and
claim even when delivered through repeated events, workflows, reconciliation,
transport retries, or multiple Issues. Duplicate delivery cannot allocate an
attempt or invoke Codex again.

A v2 `changed_head` request creates a distinct claim only after admission
verifies its exact expected head, stable Review Intent, and trustworthy
predecessor with a different head. A v2 `repeat_same_head` request creates a
distinct claim only after admission verifies the same expected head and intent,
trustworthy predecessor, fresh nonce, authenticated requester authorization,
and separately authorized operational admission. Contradictory, unavailable,
or incomplete evidence fails before claim creation.

No head change, reconciliation, workflow replay, timeout, lost response, or
infrastructure recovery automatically creates a review. Recovery preserves the
existing request and attempt. A later same-head review after any model-capable
indeterminate attempt requires a separately authorized `repeat_same_head`
request. Every predecessor request, attempt, journal, artifact, publication
record, and result remains immutable.

These v2 rules are normative but unimplemented. Existing executable journal and
recovery behavior remains v1-only until separately implemented and qualified.

## Recovery

Pre-model states can resume the same attempt. Captured evidence can be validated
without inference. Validated evidence can be published without inference.
`ARMED` without terminal evidence is marked indeterminate and stopped.

The reconciler reads authenticated open request Issues as well as durable claim
refs. A lost Issue event creates or reuses the deterministic claim before a
pre-model dispatch. Exact terminal artifacts can be downloaded, independently
verified, validated, and published without another model invocation. Artifact
expiry, absence, ambiguity, incompleteness, identity mismatch, publication
ambiguity, incomplete scans, and failed cleanup remain explicit non-passing
outcomes; none is converted into a later durable state.
