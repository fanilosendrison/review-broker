---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "RB-PILOT-02 Historical Synthetic Pilot Record"
version: "0.2.2"
---

# RB-PILOT-02: consumed and permanently closed

Authority: Review Broker specification, issue #26, and the risk-proportionate
security decision in issue #27. This procedure is a historical record. It does
not authorize or expose an executable pilot identity.

```text
RB_PILOT_01=CONSUMED
RB_PILOT_02=CONSUMED
RB_PILOT_03_AT_RB_PILOT_02_CLOSURE=NOT_CREATED
NEW_AUTHENTICATED_INFERENCE_AUTHORIZED=NO
```

Both historical Python and CLI entry points remain present only to return their
stable consumed-identity errors before argument validation, environment
inspection, runtime preflight, fixture construction, directory creation,
credential consultation, claim writes, or model invocation. Deleting a remote
`/tmp` directory cannot reopen either identity.

The historical fixtures remain available for deterministic offline verification.
Their request, attempt, source, mission, packet, model, and policy identities
must not be interpreted as future authorization.

## Historical outcome

RB-PILOT-02 produced one confirmed Codex process dispatch and failed with the
bounded classification `CODEX_APPLICATION_ERROR`. The private failure receipt
contained two parsed failure events but no recognized category, code, or HTTP
status. The supported cause remains:

```text
HISTORICAL_PILOT_02_CAUSE=APPLICATION_ERROR_UNCLASSIFIED
HISTORICAL_RAW_ARTIFACTS_AVAILABLE=NO
```

The remote raw diagnostics were lost after Codespace Shutdown because only the
sanitized receipts had been recovered. This correction does not reconstruct
those bytes and does not weaken the historical uncertainty.

## Three distinct controls

### Permanent historical closure

The Review Broker package rejects RB-PILOT-01 and RB-PILOT-02 unconditionally.
This is a code-level historical boundary, independent of remote filesystem
state. It does not create another identity.

### Persistent controller reservation

The independent controller stores future authorized request reservations under
`~/.local/state/review-broker/pilots/`. A reservation is keyed by the canonical
SHA-256 of the supplied request identity and binds pilot, request, attempt, and
source identities. It is written exclusively with private permissions and
file/directory durability barriers, including the parent of every newly created
managed directory, before any model-capable command.

A valid or ambiguous existing reservation blocks reuse. A preexisting empty
reservation is never completed automatically. Reservations are never
automatically removed after success, failure, timeout, lost SSH, transfer
failure, process restart, remote cleanup, or Codespace restart. This guarantee
covers the designated controller and its persistent storage. It is not
consensus between controllers and does not resist deliberate deletion by a
privileged administrator.

At RB-PILOT-02 closure, no RB-PILOT-03 request or attempt identity existed.
That historical statement is superseded by the separately authorized and
prepared RB-PILOT-03 implementation. The reservation module itself still does
not generate identities or authorize an invocation; the new controller binds
its deterministic identity and separate execution authorization before using
the existing durable reservation boundary.

### Private diagnostic retention

Before Shutdown, the controller first retains sanitized receipt copies and
validates their canonical structure, controller binding, packet identity, and
outcome coherence as one set. A failed outcome requires its coherent failure
receipt; a successful outcome forbids one. Raw Codex events, stderr, final
output, and exit state are eligible only when that single validation decision
passes, its summary establishes `credential_screen=PASS_NO_MATCH`, remote
observation is regular and coherent, known-pattern screening passes, and
explicit size limits hold. A coherent `CODEX_APPLICATION_ERROR` failure remains
eligible for diagnostic retention.

Eligible files are copied through a fixed literal-path boundary without remote
expansion. The controller rechecks type, size, digest, and credential patterns
before atomically publishing private mode-0600 files. A private retention
manifest records absence, refusal, failure, or verified retention without
turning diagnostic bytes into a causal claim.

Known-pattern screening is bounded risk reduction, not proof of universal
confidentiality. Raw diagnostics remain private: they must not enter Git,
Issues, Actions artifacts, logs, agent output, or LLM context.

## Required future controller order

Before a separately authorized invocation, the controller must:

1. Verify the exact software and authorization identities.
2. Verify persistent controller storage and absence of an existing reservation.
3. Complete required offline and runtime preflights.
4. Durably write the controller claim.
5. Emit at most one model-capable command.

After that command, regardless of outcome, the controller must:

1. Preserve the observed result or uncertainty without retry.
2. Verify and recover sanitized receipts.
3. Admit raw diagnostics only after the sanitary credential gate.
4. Verify remote/local digests and write the retention manifest durably.
5. Attempt Codespace stop even if retention fails.
6. Independently observe `Shutdown`.
7. Publish only bounded sanitary status.

Partial retention remains partial. Missing files remain absent. A successful
Shutdown does not manufacture successful retention, and retention failure does
not authorize another inference. Manifest timestamp replay conflicts and the
primary exception when retention and Shutdown both fail remain deferred
nonblocking limitations.

## Current qualification boundary

```text
PILOT_SECURITY_QUALIFIED=NO
PRODUCTION_SECURITY_QUALIFIED=NO
CONTROLLER_RETENTION_FOR_HISTORICAL_RB_PILOT_02=SANITIZED_RECEIPTS_ONLY
PR14_MERGED=NO
ISSUE26_CLOSED=NO
```

The production workflow and risk-proportionate decision #27 remain unchanged.
