---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "PR 14 Technical Findings"
version: "0.1.0"
---

# PR 14 Technical Findings

## Scope

This record applies to corrections derived from direct examination of PR #14 at
baseline `6e017817e19fd4276451f34acdb0eb2993eb4fc6`. It is producer engineering
evidence, not independent construction or security acceptance.

## F1 — Stopped-state truth

Generic journal transitions can no longer create `STOPPED`. Cleanup obtains a
separate receipt that binds actual `Shutdown`, Codespace, request, attempt,
observation time, and workflow context. The durable transition validates that
receipt and is conditional on successful observation. Failure writes a shutdown
incident and leaves the journal in its prior recoverable or indeterminate state.

## F2 — Terminal-capture truth

Runtime recovery records every required transfer independently and preserves
partial artifacts. `TERMINAL_CAPTURED` requires a specialized receipt binding
the request, attempt, packet, complete artifact inventory, and one
non-contradictory started-plus-terminal event sequence. Missing, truncated,
malformed, contradictory, or identity-mismatched evidence cannot cross that
state boundary and is preserved as indeterminate.

## F3 — Recovery completeness

The reconciler now executes authorized pre-model dispatch, armed-to-indeterminate
handling, observed shutdown, and stopped-state recording. It never repeats a
model-capable operation. The remaining integrity correction adds a journaled
Actions artifact plan and finalized exact locator before validation. The
reconciler can retrieve those bytes, reproduce validation, and enter the
publication protocol without model inference. Historical attempts with no plan
or locator remain explicitly `BLOCKED_EVIDENCE_LOCATION`; unavailable, expired,
incomplete, or mismatched artifacts remain non-passing rather than fabricated.

## F4 — Lost Issue delivery

Reconciliation completely paginates open Issues and claim refs within explicit
bounds. It parses the canonical envelope, applies existing requester and
repository authorization, resolves the subject, creates or reuses the atomic
claim, and dispatches only the trusted default-branch workflow. Duplicate and
concurrent discovery retain one attempt. An incomplete scan fails before any
claim or dispatch.

## F5 — Re-review identity

Existing authority keeps logical request identity stable while resolved subject
identity changes. It does not define when changed subject state authorizes a new
attempt or how an ordinal is allocated. Issue #20 records the contract decision.
Automatic changed-subject re-review remains blocked.

## Additional established findings

Privileged workflows now reject non-default dispatch refs and check out the
exact event SHA. The remote broker is built from that SHA, transferred as an
exact wheel, SHA-256 verified, force-installed, invoked with unsafe Python import
paths disabled, and bound into attempt evidence. Packet preparation rechecks the
PR head after complete file enumeration and rejects source identity movement.

## F6 — Packet-to-prompt binding

The counterexample was reproduced at baseline
`6d9af04fcf6c85c813909cf77c5780ee0f92555c`: altered prompt bytes were accepted
when their mutable hash and length were updated while packet identity stayed
unchanged. Verification now recomputes program and source-manifest identities
and reconstructs the complete expected prompt from packet-bound mission, policy,
and exact source snapshots. Positive and negative CRLF coverage is retained.

## F7 — Coherent journal reads

The baseline reader was proven to return commit A together with branch content
from commit B. It now retrieves content using the one observed immutable commit
SHA and rejects incomplete ref, content, encoding, canonicalization, and request
identity responses. Deterministic tests cover ref movement, stale coherent
reads, competing compare-and-swap updates, and incomplete responses.

## Remaining gates

Independent technical and security review must examine the corrected exact PR
head. `REVIEW_BROKER_SECURITY_QUALIFIED` remains unset. No Codex inference,
Proto-Scope review, or consumer admission occurred during these corrections.
