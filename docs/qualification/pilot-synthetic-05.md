---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "synthetic-pilot"
name: "RB-PILOT-05 Sol/xhigh Functional Preparation"
---

# RB-PILOT-05 Sol/xhigh functional preparation

## Scope

Review Broker 0.4.8 prepares one deterministic synthetic identity using the
unchanged source fixture, mission and expected defect. RB-PILOT-05 has request
ordinal 1 and attempt ordinal 1. Its fixed policy requests `gpt-5.6-sol` with
`xhigh` reasoning effort through the corrected Codex wire schema.

This record qualifies preparation only. It does not authorize execution,
Codespace startup, a controller invocation or authenticated inference.

## Fixed identity and runtime

```text
PILOT_ID=RB-PILOT-05
REQUEST_ID=request:sha256:499b77e199fb18f45fe55ba863de36f3b370ab92310234a0c0131587ee94261a
ATTEMPT_ID=attempt:sha256:9f77e1f5a2f206394d6922b3db7d133af2ab84355a94aa72ba28ad27926b65cf
MODEL=gpt-5.6-sol
REASONING_EFFORT=xhigh
PACKAGE_VERSION=0.4.8
MAX_MODEL_CAPABLE_EMISSIONS=1
AUTOMATIC_RETRIES=0
RB_PILOT_05_EXECUTION_AUTHORIZED=NO
```

The remote run, claim and bootstrap paths are isolated under the fixed RB05
namespace. The 0.4.8 bootstrap is fixed at
`/tmp/review-broker-pilot-26-rb05-bootstrap-v048`; the earlier 0.4.7 bootstrap
is neither reused nor modified. The shared preflight binds every generated
script to the selected runtime singleton's bootstrap root, exact wheel path,
installed package version and basename asserted from `direct_url.json`.

The 0.4.7 generator left the historical 0.4.5 basename in that nested
provenance assertion and could therefore refuse before installation was
recognized. AST-based tests reproduce that static mismatch and inspect the
actual nested `python -c` program generated for every runtime. RB03 and RB04
retain their historical 0.4.5 runtime identities and byte-identical generated
preflight behavior. This correction does not establish that the static defect
was the exclusive remote cause of the earlier sanitary
`REMOTE_REVIEWCTL_MISSING` result.

## Acceptance boundary

Attempt-bound authorization must match RB05, its deterministic request and
attempt, the exact source SHA, wheel SHA-256 and Codespace identity before
startup. Preflight precedes durable controller armament. Armament permits at
most one model-capable command and no automatic retry. Functional PASS still
requires the full local schema, exact identities, source coverage, valid
citations and the expected `NO_GO` finding at `S001`, line 3. Operational PASS
also requires complete private retention and observed Shutdown.

The corrected wire schema hash remains
`ca4449b3b0e4431938d3d1ab0226c0031e8596fc4a21ca3106c6ae0d44f124ab`.
The bounded direct Sol/xhigh diagnostic passed provider, wire, full-schema and
exact-output checks, but did not independently attest effective model identity
or reasoning effort.

RB-PILOT-01 through RB-PILOT-04 remain consumed and unchanged. No RB05 claim
exists and no RB05 execution authorization has been issued. Codex remains
pinned to 0.164.0, and production security remains unqualified.
