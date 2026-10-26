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
model-capable operation. `TERMINAL_CAPTURED` validation and `VALIDATED`
publication are explicitly `BLOCKED_EVIDENCE_LOCATION`: the current journal
does not record the durable Actions artifact locator required to recover exact
bytes. That conformance obligation is recorded under RB-08 rather than
fabricated.

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

## Remaining gates

Independent technical and security review must examine the corrected exact PR
head. `REVIEW_BROKER_SECURITY_QUALIFIED` remains unset. No Codex inference,
Proto-Scope review, or consumer admission occurred during these corrections.
