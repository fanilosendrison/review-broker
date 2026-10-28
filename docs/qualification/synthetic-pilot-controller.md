---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "Synthetic Pilot Controller Persistence and Retention"
version: "0.1.2"
---

# Synthetic pilot controller persistence and retention

This procedure defines controller-side preparation for RB-PILOT-03, whose technical preparation was product-authorized on 2026-10-28. It creates no pilot identity, integrates no real controller, and grants no authenticated inference authority.

## Persistent request reservation

Store controller state under:

```text
~/.local/state/review-broker/pilots/
```

The request reservation directory is named by the SHA-256 of the canonical
request identity string. Its `controller-claim.json` binds the supplied pilot,
request, attempt, and source identities in state `ARMED`.

Write the claim after all non-model preflights and before any model-capable
command. Synchronize each parent directory after creating a managed child,
including the controller root after creating the request reservation. Treat
every valid, malformed, partial, inaccessible, aliased, or otherwise ambiguous
existing reservation as consumed. Never complete, replace, or automatically
delete it.

The controller storage guarantee applies to one designated controller and its
persistent filesystem. It does not implement distributed consensus and does
not protect against deliberate privileged deletion.

## Private retention layout

Verified data is retained under the same request directory:

```text
<request-digest>/
  controller-claim.json
  receipts/
    pilot-claim.json
    pilot-armed.json
    pilot-summary.json
    pilot-failure.json
  diagnostics/
    codex-events.jsonl
    codex-stderr.txt
    codex-final.json
    codex-exit-code.txt
  retention-manifest.json
```

Absent optional artifacts remain absent. The controller records each remote
observation and transfer outcome separately.

## Diagnostic admission

Validate the retained claim, armed receipt, summary, and outcome-dependent
failure receipt once as one canonical, identity-coherent set. Report sanitized
receipt retention as `PASS` only for a valid set. Retain raw diagnostics only
when that same validation decision passes and the validated summary states
`credential_screen=PASS_NO_MATCH`. A valid failed pilot remains eligible when
its summary and failure receipt agree. Also require each remote file to be
regular, non-aliased, singly linked, coherently observed, within its explicit
size bound, and negative under known-pattern credential screening.

Apply these limits:

```text
codex-events.jsonl   64 MiB
codex-stderr.txt     16 MiB
codex-final.json      1 MiB
codex-exit-code.txt  64 bytes
```

Copy only fixed literal paths. Do not use remote expansion. Revalidate local
file identity, size, SHA-256, and credential patterns before publishing it into
the private destination. Existing identical bytes may be recognized
idempotently; different bytes are an integrity failure.

Raw diagnostic retention and sanitized receipt retention are independent. A
negative known-pattern screen is not universal confidentiality assurance and
does not qualify sensitive workloads.

## Failure and Shutdown

Record truthful `PASS`, `PARTIAL`, refusal, absence, transfer, hash, and local
validation outcomes in the private manifest. Never report a successful copy
without remote/local digest equality.

After controller responsibility begins, attempt Shutdown in a `finally`
boundary. Retention failure, contamination, missing artifacts, or integrity
failure must not leave the Codespace running and must not authorize a retry.

Publish only sanitary statuses. Never publish raw diagnostics or their hashes.

Manifest replay remains fail-closed when a newly generated retention timestamp
conflicts with an existing manifest. If retention and Shutdown both fail, the
Shutdown exception remains primary and the retention exception remains its
context. These deferred nonblocking limitations do not weaken receipt admission
or authorize a retry.

## Future integration boundary

A future pilot implementation must bind authorization and command emission to a
successful durable controller claim. This package currently provides the
reservation and retention mechanisms only.

```text
RB_PILOT_01=CONSUMED
RB_PILOT_02=CONSUMED
RB_PILOT_03_PREPARATION_AUTHORIZED=YES
RB_PILOT_03_IMPLEMENTED=NO
RB_PILOT_03_EXECUTION_AUTHORIZED=NO
CONTROLLER_REAL_CLAIM_ARMED=NO
AUTHENTICATED_INFERENCE=0
PRODUCTION_SECURITY_QUALIFIED=NO
```
