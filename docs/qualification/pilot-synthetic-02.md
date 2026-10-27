---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "RB-PILOT-02 Prepared Synthetic Pilot Procedure"
version: "0.1.1"
---

# RB-PILOT-02: prepared, unauthorized synthetic review

Authority: Review Broker specification, issue #26, and the risk-proportionate
security decision in issue #27. This procedure prepares a future operation; it
does not authorize or record an inference.

```text
RB-PILOT-01=CONSUMED
RB-PILOT-02=PREPARED
RB-PILOT-02_INFERENCE_AUTHORIZED=NO
```

The executable entry point does not grant authority to use it. Do not reinterpret
the historical RB-PILOT-01 authorization as applying to RB-PILOT-02. Require a
separate future mandate for one invocation after independent review of the
installed candidate and the operating conditions.

## Fixed identity and boundary

RB-PILOT-02 uses the exact RB-PILOT-01 source bytes, mission, subject identity,
source records, Codex distribution `@openai/codex`, version `0.164.0`, model
`gpt-5.6-sol`, reasoning effort `xhigh`, disabled shell feature, and forbidden
API-key fallback. Its request identity uses kind `RB-PILOT-02`, fixture ordinal
`1`, and the unchanged fixture SHA-256. Its attempt identity uses ordinal `1`
under that new request identity. Both identities differ from RB-PILOT-01.

The command accepts no repository, pull request, source, mission, model,
identity, or run-directory selection. It uses the fixed directory
`/tmp/review-broker-pilot-26-rb02` and a separate durable claim at
`/tmp/review-broker-pilot-26-rb02.claim.json`. An existing, unreadable,
non-regular, malformed, or ambiguous claim blocks execution. An `ARMED` claim
is never removed automatically after success, failure, timeout, or cleanup.
This prevents ordinary replay; it does not protect against a privileged
controller deliberately deleting both persistent traces.

The pilot has no GitHub publication capability and does not use the production
workflow. No automatic retry is permitted. A local success does not qualify
Codex security, controller retention, Codespace shutdown, or production use.

## Future operator preflight

Before any future invocation, the independent controller must:

1. Verify the exact independently reviewed candidate commit SHA.
2. Build the wheel from that SHA and independently verify its SHA-256.
3. Verify the transferred wheel against that digest.
4. Verify that the pinned Codex runtime and requested policy remain unchanged.
5. Check the existing ChatGPT/Codex authentication state without exposing a
   token. `codex login status` may be used only during that future operation.
6. Verify availability of the fixed run path and absence of the RB-PILOT-02
   claim.
7. Verify that the intended existing Codespace is being used.
8. Obtain explicit operator authorization for exactly one invocation.

A valid login status does not prove that the backend will accept
`gpt-5.6-sol`. Only an expressly authorized invocation can establish that
observation. If the session has expired, treat interactive renewal as a
separate operational decision. Do not install a new identity or use an API-key
fallback.

## Future one-shot execution

Only after the separate authorization, install the verified wheel and run:

```bash
reviewctl pilot-synthetic-02 \
  --broker-wheel-sha256 VERIFIED_WHEEL_SHA256 \
  --acknowledge-unqualified-pilot
```

The command must create the durable claim before its single model-capable
transport. Do not retry automatically after the claim reaches `ARMED`, including
a provider rejection, timeout, validation failure, or incomplete receipt.

## Private receipts and interpretation

The fixed run directory retains `pilot-armed.json`, `pilot-summary.json`, and,
on failure, `pilot-failure.json`. Receipts bind the RB-PILOT-02 request,
attempt, and packet identities; wheel digest; requested model and effort;
functional state; bounded failure classification when observable; factual
runner dispatch and process-start state; and credential-screening or quarantine
state. Raw provider messages are not receipt facts.

`runner_dispatches` records entry into the single subprocess runner.
`process_start_status=CONFIRMED` requires a returned process result or timeout;
an `OSError` or another exception without sufficient start evidence remains
`UNDETERMINED`. `inference_process_invocations` is derived from that observation,
not presumed from the Python call to `invoke_once()`. Process creation does not
prove provider acceptance or authenticated inference.

A structurally invalid result is not interpreted semantically. It produces a
sanitized local failure and receipt closure when local writes remain available.
An unexpected output-validation exception is reduced to
`PILOT_OUTPUT_VALIDATION_UNAVAILABLE`; exception text, tracebacks, and raw model
output are not copied into receipts.

A local PASS requires valid terminal events, the last agent message, matching
identities, schema-valid findings, and an exact `S001` line 3 citation containing
`return age > 18`. Interpret the outcome only as:

```text
PILOT_FUNCTIONAL=PASS|FAIL
PILOT_SECURITY_QUALIFIED=NO
PRODUCTION_SECURITY_QUALIFIED=NO
```

## Future recovery and shutdown

After either success or failure, the independent controller must:

1. Recover private receipt copies and verify regular JSON, expected identities,
   and SHA-256 against the remote files.
2. Keep raw events, model output, stderr, credentials, and secrets away from
   public Issues, pull requests, repositories, and artifacts.
3. Preserve an explicit failure or uncertainty status if receipt retention or
   verification fails.
4. Stop the Codespace and independently observe the actual `Shutdown` state.
5. Preserve shutdown uncertainty as an infrastructure incident rather than
   inferring success from a requested state.

These instructions are not evidence that retention or shutdown occurred.
`CONTROLLER_RETENTION=UNVERIFIED` remains true until the future controller
records the observations. PR #14 remains unmerged, issue #26 remains open, and
production security remains unqualified.
