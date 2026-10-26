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
No actual invocation is claimed by this procedure.

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

## Preparation (operator, not automated by the chat)

1. Verify the exact approved PR #14 candidate SHA and green CI.
2. Build the Review Broker wheel from that SHA in a separate trusted worktree,
   inspect the change and transfer the wheel to the existing Codespace. Verify
   the transferred SHA-256; install it without executing any reviewed subject
   code. Do not re-use unverified local packages.
3. Verify that the existing root-owned Codex runtime exists at
   /var/lib/review-broker/codex-0.164.0-linux-x64.
4. Launch using only a scrubbed non-secret process environment. Example
   (substitute a *fresh* run path, verified wheel SHA, and a minimal PATH that
   resolves exactly one trusted Codex npm launcher):

   env -i HOME="$HOME" CODEX_HOME="$HOME/.codex" \
     PATH="/usr/local/bin:/usr/bin:/bin" LANG=C.UTF-8 TZ=UTC \
     python3 -P -m review_broker.cli pilot-synthetic \
       --run-dir /tmp/review-broker-pilot-26-unique \
       --broker-wheel-sha256 VERIFIED_WHEEL_SHA256 \
       --acknowledge-unqualified-pilot

5. Never automatically rerun this command for the same run directory.
   The pilot-armed.json record is flushed before any model-capable invocation.

## Local evidence and interpretation

The pilot produces private local files under its run directory:
- evidence/input-manifest.json, source snapshot and input prompt.
- pilot-armed.json: durable one-shot marker.
- evidence/codex-events.jsonl, codex-final.json and exit state where available.
- pilot-summary.json: sanitized local output.

A local PASS requires a single completed Codex turn, a schema-valid JSON
message matching the final event, request/subject/packet identities and exact
physical source citation identifying the age-18 boundary defect. That local
PASS is **not** full security or production evidence qualification.

If credential-shaped material occurs, pilot evidence is quarantined locally.
If the first attempted transport fails, the run identity is consumed and
must not be retried automatically.

## Operator cleanup (outside the pilot process)

From an independently authenticated host, stop the existing Codespace with
the normal GitHub CLI and independently verify its final state is Shutdown.
Do not place lifecycle tokens in the pilot process. If Shutdown is not observed,
report an infrastructure incident. The pilot command itself cannot attest the
host's Codespace lifecycle.

Before reporting PILOT_FUNCTIONAL=PASS end-to-end, verify all three:
1. A single authenticated model turn with valid local output.
2. No GitHub publication/artifact upload.
3. Actual Codespace Shutdown observed from the control plane.

The production security variable REVIEW_BROKER_SECURITY_QUALIFIED remains
unset, and PR #14 remains unmerged until a separate decision.
