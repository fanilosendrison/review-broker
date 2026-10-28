---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "RB-PILOT-04 Terra Functional Preparation"
version: "0.1.0"
---

# RB-PILOT-04 Terra functional preparation

## Scope

Review Broker 0.4.5 prepares one future non-production functional attempt using
the unchanged synthetic eligibility source, mission, reviewer schema and
expected defect. The request kind is `RB-PILOT-04`, with request ordinal 1 and
attempt ordinal 1. Request and attempt identities are derived by the existing
packet and identity machinery and are distinct from every consumed historical
pilot.

Preparation performs no Codespace access, controller reservation or model
invocation. RB-PILOT-04 execution requires a later product-owner authorization
bound to the exact source SHA, wheel SHA-256, deterministic request and attempt,
and Codespace identity.

## Explicit reviewer policy

RB-PILOT-04 uses the immutable policy:

```text
MODEL=gpt-5.6-terra
REASONING_EFFORT=medium
CODEX_VERSION=0.164.0
MAXIMUM_MODEL_CAPABLE_EMISSIONS=1
AUTOMATIC_RETRIES=0
```

The historical `CodexPolicy` defaults remain Sol/xhigh. The Terra policy is
passed explicitly through `invoke_once()` and supplies the values recorded in
attempt, summary and failure evidence. Runtime overrides, fallback models and
model negotiation are not admitted. Strict configuration, shell disabling,
the credential-isolated read-only profile, packet verification, structured
output schema and post-invocation packet checks remain mandatory.

## Isolation and shared machinery

RB-PILOT-04 has fixed, separate remote run, claim and bootstrap paths. It reuses
the closed controller, transport, preflight, artifact observation and private
retention implementations through an enumerated immutable runtime
configuration. Arbitrary pilot identifiers, paths, package versions and model
selectors are rejected. RB-PILOT-03 interfaces and deterministic identity are
preserved for historical verification.

The controller validates attempt-bound authorization before Codespace startup.
Authorization for RB-PILOT-03 cannot satisfy RB-PILOT-04. Remote preflight must
verify the exact 0.4.5 wheel, installed package, pinned dependencies, entrypoint,
Codex runtime and non-inference login status before the durable controller claim
is armed. After armament, one emission maximum is allowed and all outcomes are
consumed without retry.

## Acceptance boundaries

Functional `PASS` requires the validated retained receipt set to establish a
completed invocation, valid schema, coherent source citations and the expected
review outcome. Exit zero alone is insufficient. Missing, malformed,
contaminated, partial or identity-incoherent evidence cannot establish success.
Operational acceptance additionally requires complete mandatory retention,
coherent execution observations and independently observed Shutdown.

The direct Terra smoke result established only bounded authenticated provider
access. Issue #27's risk-proportionate decision remains unchanged. This
preparation does not qualify production security, ordinary real-PR admission or
RB-PILOT-04 execution.
