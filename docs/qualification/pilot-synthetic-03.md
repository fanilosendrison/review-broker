---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "RB-PILOT-03 Operational Preparation"
version: "0.1.5"
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
3. Transfer the exact authorized wheel into the fixed private bootstrap root.
4. Build a dedicated Python environment without resolving packages from the
   network, then verify the remote wheel hash, package version, imports,
   dependencies, exact entry point, Codex runtime, and non-inference login
   status.
5. Create and synchronize the persistent controller reservation only after all
   preflights pass.
6. Emit at most one fixed remote command through the verified environment.
7. Capture either the command return code or a sanitary transport exception.
8. Attempt bounded private retention even after an ambiguous emission.
9. Validate receipts, admit clean diagnostics, and derive functional status
   only from the validated receipt set.
10. Request Shutdown and independently observe its state.
11. Produce a sanitary acceptance decision with independent functional,
    execution, retention, and Shutdown dimensions.

An existing, partial, malformed, inaccessible, or ambiguous reservation blocks
emission. A failed or undetermined remote bootstrap blocks reservation. No
post-emission failure authorizes an automatic retry.

## Codespace identity and OpenSSH alias

Review Broker 0.4.2 separates the GitHub Codespace identity from the controlled
OpenSSH `Host` alias. GitHub lifecycle operations and literal copies continue
to use the Codespace identity. Remote preparation, preflight, reviewer emission,
and sanitary artifact observation use an operator-supplied literal alias that
must exist exactly once in the private controlled configuration and whose
GitHub CLI proxy command must bind the expected Codespace identity.

Alias syntax, literal stanza uniqueness, private configuration metadata, and
proxy binding are validated locally when the transport is constructed, before
Codespace startup or controller reservation. Wildcards, multi-pattern aliases,
external includes, ambiguous stanzas, implicit aliases, and mismatched
Codespace bindings fail closed. Raw configuration lines are not reported.

The first authorized v0.4.1 operation emitted no model-capable command and
created no controller claim because its SSH target used the Codespace identity
rather than the distinct configured alias. A subsequent read-only diagnostic
proved this mismatch and observed Shutdown. That operation did not consume
RB-PILOT-03.

Independent review of v0.4.2 established that its partial `ProxyCommand`
validation accepted a valid Codespaces command followed by shell content. In
v0.4.3 the complete literal value must match exactly `gh`, either `cs` or
`codespace`, `ssh`, either `-c` or `--codespace`, the expected Codespace
identity, and `--stdio`, separated only by spaces or horizontal tabs. Shell
suffixes, substitutions, redirections, prefixes, quoting, escaping, and all
additional options or arguments are refused rather than normalized.

Review Broker 0.4.4 additionally supports the bounded native configuration
emitted by GitHub CLI 2.37.0: an absolute executable path ending in `gh`, the
exact `cs ssh -c` Codespace binding, `--stdio -- -i`, and an absolute identity
path textually equal to the block's single literal `IdentityFile`. The
executable path, Codespace identity, and identity-file path remain distinct
values. Paths containing spaces, control characters, or shell syntax are not
accepted; neither are missing or duplicate identity directives, alternate
keys, extra arguments, or shell suffixes. Validation never reads the key or
executes the proxy command.

The 0.4.4 correction changes the candidate source and wheel identities, so all
prior execution authorizations remain inapplicable. No new inference occurred,
RB-PILOT-03 remains unconsumed, and any real execution requires a new
product-owner decision bound to the new exact SHA and wheel.

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
Reviewer failure does not imply retention failure. The retention manifest
exposes functional and execution values only when the canonical receipt-set
validator accepts the complete retained set. Missing, partial, malformed, or
identity-incoherent receipts leave the functional result `UNDETERMINED`.

## Shutdown and interpretation

Shutdown is attempted after controller responsibility begins, including after
preflight, emission, validation, retention, contamination, or local failures.
A successful stop request and an observed `Shutdown` state are distinct facts.
Shutdown does not establish functional success. Retention does not establish
model acceptance. Process creation does not establish authenticated provider
inference. A remote exit code is only a process observation. Global pilot
acceptance requires validated functional success, complete required retention,
coherent execution observations, and observed Shutdown. The controller CLI
returns success only for that complete acceptance state.

A timeout, SSH loss, or other transport exception after emission records
execution as `INDETERMINATE`, preserves the consumed claim, attempts private
retention once, never retries emission, and still crosses the Shutdown
boundary.

## Offline acceptance

Offline tests use simulated runners, lifecycle controls, artifact sources, and
execution authorization fixtures. Acceptance requires deterministic identities,
claim-before-emission ordering, replay refusal, one maximum emission, no
automatic retry, bounded sanitary observation, coherent failure-diagnostic
retention, local hash verification, and observed simulated Shutdown. Historical
F-01 through F-07 tests must remain green.

The simulation does not qualify real Codespaces transport, production security,
or an authenticated inference.

## Consumed outcome and successor preparation

RB-PILOT-03 was subsequently authorized and consumed. Its controller emitted
one model-capable command, retained a valid coherent failure receipt and all
eligible diagnostics, and observed Shutdown. The validated result was
functional `FAIL` with `CODEX_APPLICATION_ERROR`; no retry is permitted.

A later direct, separate `gpt-5.6-terra` smoke diagnostic completed successfully
at medium reasoning effort. That diagnostic established bounded provider access
only and did not validate Review Broker's packet, output, citation, receipt,
retention, or controller protocol.

Review Broker 0.4.5 prepares RB-PILOT-04 with the unchanged fixture and mission,
a distinct deterministic identity and paths, and an explicit immutable
Terra/medium policy. The residual-risk decision in Issue #27 remains in force,
ordinary v1 production admission remains unchanged and unqualified, and no
RB-PILOT-04 execution is authorized by preparation, CI, or review.

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
