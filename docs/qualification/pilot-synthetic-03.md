---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "RB-PILOT-03 Operational Preparation"
version: "0.1.0"
---

# RB-PILOT-03 operational preparation

## Scope and authority

The product owner authorized technical preparation of RB-PILOT-03 on
2026-10-28. The prepared implementation is non-production. It performs no
real Codespace access, authenticated inference, OAuth operation, or persistent
controller reservation during qualification. A separately sourced execution
authorization remains mandatory before any real controller activity.

The local authorization record binds the pilot, deterministic request and
attempt identities, Review Broker source SHA, candidate wheel SHA-256, and
Codespace identity. Validation of this record establishes applicability only.
It does not cryptographically authenticate product-owner provenance.

## Deterministic identity

RB-PILOT-03 uses request ordinal 1 and attempt ordinal 1. The request identity
is derived through `request_identity()` from the unchanged eligibility fixture,
the `RB-PILOT-03` kind, and ordinal 1. The attempt identity is derived through
`attempt_identity()`. Packet construction derives subject and packet identities
through the existing packet implementation. RB-PILOT-01 and RB-PILOT-02 remain
consumed and closed.

## Controller sequence

The controller applies these boundaries in order:

1. Validate attempt-bound execution authorization.
2. Validate source, wheel, and Codespace identities.
3. Prepare the Codespace and complete non-model preflights.
4. Create and synchronize the persistent controller reservation.
5. Emit at most one fixed remote command.
6. Observe sanitary artifact metadata.
7. Retain and validate receipts privately.
8. Admit clean diagnostics only after receipt and credential gates pass.
9. Request Shutdown and independently observe its state.
10. Produce a sanitary report with independent functional, execution,
    retention, and Shutdown dimensions.

An existing, partial, malformed, inaccessible, or ambiguous reservation blocks
emission. No post-emission failure authorizes an automatic retry.

## Remote observation and private retention

The observer accepts only the eight fixed RB-PILOT-03 artifact names. It emits
bounded metadata, never raw artifact bytes. Regular-file identity, link count,
size, SHA-256, and known-pattern credential screening are observed before a
literal copy. Malformed or incomplete observations remain undetermined.

The existing private-retention implementation validates the complete receipt
set before admitting diagnostics. A coherent `CODEX_APPLICATION_ERROR` remains
eligible when credential screening reports `PASS_NO_MATCH`. Every transferred
file is checked locally against its observed size and SHA-256. The private
manifest records retained, refused, failed, and absent artifacts independently.
Reviewer failure does not imply retention failure.

## Shutdown and interpretation

Shutdown is attempted after controller responsibility begins, including after
preflight, emission, validation, retention, contamination, or local failures.
A successful stop request and an observed `Shutdown` state are distinct facts.
Shutdown does not establish functional success. Retention does not establish
model acceptance. Process creation does not establish authenticated provider
inference.

## Offline acceptance

Offline tests use simulated runners, lifecycle controls, artifact sources, and
execution authorization fixtures. Acceptance requires deterministic identities,
claim-before-emission ordering, replay refusal, one maximum emission, no
automatic retry, bounded sanitary observation, coherent failure-diagnostic
retention, local hash verification, and observed simulated Shutdown. Historical
F-01 through F-07 tests must remain green.

The simulation does not qualify real Codespaces transport, production security,
or an authenticated inference.

```text
RB_PILOT_03_PREPARATION_AUTHORIZED=YES
RB_PILOT_03_IMPLEMENTED=YES
RB_PILOT_03_EXECUTION_AUTHORIZED=NO
RB_PILOT_03_AUTHENTICATED_INFERENCE=0
REMOTE_OBSERVER_IMPLEMENTED=YES
CONTROLLER_OPERATIONAL_INTEGRATION_IMPLEMENTED=YES
END_TO_END_REAL_CODESPACE_QUALIFICATION=NOT_EXECUTED
PRODUCTION_SECURITY_QUALIFIED=NO
```
