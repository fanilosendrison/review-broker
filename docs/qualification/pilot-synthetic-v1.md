---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "One-shot Synthetic Pilot Procedure"
version: "0.1.0"
---

# RB-PILOT-01: explicit non-production synthetic review

Authority: specification, 2026-10-26 proportional security decision #27 and
pilot issue #26. This is not a production ReviewRequest.

The existing reviewed PR #14 remains unmerged; the code must be independently
inspected before it is installed in the credential-bearing Codespace.

RB-PILOT-01 binds its fixed request identity to fixture ordinal `1` and derives
its attempt identity with attempt ordinal `1`. That identity was armed and
consumed by the authorized #26 invocation on 2026-10-27. The public Python and
CLI entry points now fail with `PILOT_IDENTITY_ALREADY_CONSUMED` before runtime
preflight, run-directory creation or invocation. A fresh directory and explicit
acknowledgment cannot reopen it. Require a separately authorized pilot identity,
with a distinct request and attempt identity, before any future model-capable
attempt; this procedure does not create one.

## Boundaries

- Input is compiled into the pilot module: a harmless eligibility predicate.
  The bug at age 18 is intentionally detectable; source is never executed.
- No user-supplied PR, repository, mission or source argument exists.
- The pilot uses the existing official pinned Codex 0.164.0 native, model
  gpt-5.6-sol/xhigh, attempt-bound named profile and shell-disable flag.
- The pilot is executed **inside the existing dedicated Codespace**, not GitHub
  Actions, and only with the operator's explicit acknowledgment.
- No GitHub, API-key, Codespaces or App token may exist in the pilot parent
  process environment. The only intended runtime credential is Codex OAuth.
- Run directory must be an unused, absolute, private path outside the HOME and
  broker workspace, e.g. /tmp/review-broker-pilot-26-unique.
- No publication, issue comment, PR review, merge or automatic retry.
- Retain historical hard-link/proc findings and OBL-02/03/04 as unqualified.

## Closed identity

Do not prepare, install or launch RB-PILOT-01 again. Treat request ordinal `1`
and attempt ordinal `1` as consumed. Its entry point is retained only to return
the stable refusal before consulting runtime or credential state. A future
expressly authorized pilot must define a distinct request and attempt identity;
a fresh directory alone is not new invocation authority.

## Local evidence and interpretation

The pilot produces private local files under its run directory:

- `evidence/input-manifest.json`, source snapshot and input prompt.
- `pilot-armed.json`: durable one-shot marker.
- `evidence/codex-events.jsonl`, `codex-final.json` and exit state where
  available.
- `pilot-failure.json`: private sanitized failure receipt when the pilot fails.
- `pilot-summary.json`: sanitized local output.

Treat `CODEX_FAILURE_UNCLASSIFIED` and `CODEX_NONZERO_EXIT_UNCLASSIFIED` as
unknown causes. A negative direct-child return code establishes only
`CODEX_SIGNAL_TERMINATION` and its signal number, never a native crash. The
failure receipt may retain only bounded structured fields directly present in
recognized `error` or `turn.failed` envelopes, process outcome, identities and
artifact hashes. Free-form messages and stderr cannot establish a provider
cause. Do not retain raw provider messages or opaque event identifiers in that
receipt. Keep absent fields `UNDETERMINED` and let credential quarantine take
priority over diagnostic extraction.

A local PASS requires a single completed Codex turn, a schema-valid JSON
message matching the final event, request/subject/packet identities and exact
physical source citation identifying the age-18 boundary defect. That local
PASS is **not** full security or production evidence qualification.

## File-observation boundary

Accept a file observation only when two complete bounded-memory reads through
the same open descriptor have equal byte counts and SHA-256 digests, and a final
path check still identifies that descriptor's regular file. Treat an incomplete,
changed, substituted or unavailable observation as indeterminate rather than
retaining diagnostic facts, an old digest or a negative credential-screening
claim.

This check is not an exclusive lock, proof of future immutability or absolute
protection against adversarial concurrent ABA mutation. Do not infer those
stronger guarantees from an accepted observation.

If credential-shaped material occurs, pilot evidence is quarantined locally.
If the first attempted transport fails, the run identity is consumed and
must not be retried automatically.

## Operator cleanup (outside the pilot process)

This transfer remains operationally unverified:
`PILOT_SANITIZED_RECEIPT_RETENTION=UNVERIFIED`.

Before stopping the Codespace, use the independently authenticated controller
to recover private copies of `pilot-armed.json`, `pilot-summary.json` and, when
present, `pilot-failure.json`. Store them in a private controller directory,
verify that each copied file is regular JSON with the expected identities, and
verify its SHA-256 against the remote file. Perform this recovery after both
successful and failed inference.

Do not copy raw JSONL, model output, stderr or credential material into a GitHub
Issue, Actions artifact, repository path or other publication surface. Keep
sanitized-receipt recovery separate from the reviewer process. If recovery or
verification fails, report `PILOT_SANITIZED_RECEIPT_RETENTION=FAIL` and preserve
that uncertainty; do not delay or skip Codespace shutdown.

From the independently authenticated host, stop the existing Codespace with the
normal GitHub CLI and independently verify its final state is `Shutdown`. Do not
place lifecycle tokens in the pilot process. If `Shutdown` is not observed,
report an infrastructure incident. The pilot command itself cannot attest the
host's Codespace lifecycle.

Before reporting PILOT_FUNCTIONAL=PASS end-to-end, verify all three:
1. A single authenticated model turn with valid local output.
2. No GitHub publication/artifact upload.
3. Actual Codespace Shutdown observed from the control plane.

The production security variable REVIEW_BROKER_SECURITY_QUALIFIED remains
unset, and PR #14 remains unmerged until a separate decision.
