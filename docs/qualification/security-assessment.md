---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Reviewer Credential-Isolation Assessment"
version: "0.1.4"
---

# Reviewer Credential-Isolation Assessment

## Discovery

### Statement

The Codex CLI `:read-only` permission profile used by the original PR #14
candidate permitted model-controlled subprocesses to read the runtime user's
home directory, including the ChatGPT credential path.

### Source and evidence

The subject was candidate
`114ff4bd25d43c5aeaca1cf3f60deb80fc63f0ba` with Codex CLI `0.164.0` in the
dedicated Codespace. A direct `codex sandbox -P :read-only` probe read a
non-secret canary adjacent to the credential file and reported that the
credential path was readable. It could not write the packet or connect directly
to the network.

The exact upstream source at OpenAI Codex tag `rust-v0.164.0`, commit
`6aaac694803004a63c6f393d153c96d22521a6b9`, defines the built-in read-only
filesystem policy as read access to `/`. File mode `0600` therefore did not
isolate a same-user sandbox subprocess.

Credential contents were never read, copied, printed, hashed, or transferred.

### Existing authority

`docs/security/reviewer-independence.md` requires model-controlled tools to be
unable to read ChatGPT credential material. `docs/security/threat-model.md`
explicitly states that a read-only flag is insufficient. The observed behavior
contradicted the candidate implementation, not the accepted security contract.

### Semantic disposition

`derived-from-existing-authority`

### Affected layers

- `verification-or-qualification-evidence`
- `architecture-or-implementation`
- `integration-or-conformance`
- `repository-governance-or-documentation`

### Related discoveries or consequences

No live model invocation, construction review, or consumer review is admissible
until the correction receives independent security review. ChatGPT
authentication itself remains valid and separate.

### Required authority

No new product decision is required. The existing security contract uniquely
requires correction. Independent review remains required to accept the
qualification evidence.

### Next action

Use Codex's maintained named permission profiles to deny the complete runtime
home and trusted workspace, disable network and writes, prevent login shells,
and replace inherited model-tool environment variables with a fixed minimal
set. Verify the exact profile before every invocation and run a controlled
non-secret probe after installation.

## Corrected producer observation

The corrected `review-broker` profile produced the receipt in
`receipts/reviewer-isolation-probe-v1.json`:

- packet canary readable;
- runtime home and adjacent auth canary unreadable;
- auth path not readable;
- trusted broker workspace unreadable;
- packet directory not writable;
- direct network connection denied;
- sensitive and process canary environment variables absent;
- two processes visible in the sandbox namespace.

This historical producer probe passed the specified canaries but did not test
access outside the two denied trees. It does not independently qualify the
boundary. The repository security gate remains closed.

## External NO-GO and non-secret falsification

The historical external static review record is
`external-review-pr14-3cf97bb.md`. The reviewer reported
`SECURITY_REVIEW=NO_GO` and `CONSTRUCTION_REVIEW=NO_GO` for exact commit
`3cf97bb1958470f7e0c10244ddd4558cc5d59858`, with no independently
executed tests or effective runtime qualification.

A subsequent **remediation-agent** direct-sandbox probe on Codex CLI `0.164.0`
read a controlled non-secret canary outside the home and workspace while the
reviewed root-readable profile was active. Its bounded observation is retained
in `receipts/external-nonsecret-isolation-3cf97bb.json`. A separate direct probe
with a **temporary** minimal-system-plus-exact-packet profile denied that canary
while preserving packet reads, and is retained in
`receipts/minimal-read-nonsecret-probe-v1.json`. Neither ran a model or accessed
credential contents. The hard-link test did not create a usable link; readable
parent-process environment access remained observable without examining its
contents. Model-tool equivalence, output-channel risks, and effective process
isolation remain unverified.

The original single-name profile fails the second valid attempt with
`PROFILE_MISMATCH`. An attempt-bound immutable profile name now allows two
separate packet directories without replacing either profile. The Codespace's
`.codex` directory was owner-owned but group-writable (`0775`); only its
directory mode was hardened to `0700` after an exact metadata check. No
credential file was opened or modified.

The exact producer direct-sandbox observations from Codex `0.164.0` are in
`receipts/attempt-bound-direct-sandbox-v1.json`. The tested hard link was
actually constructed and readable, unlike the earlier inconclusive link
attempt. An allowed packet alias can therefore bypass the profile's outside
read boundary. The separate pre-invocation packet-tree guard rejects hard
links, but the combined model-tool path remains unqualified. Parent `/proc`
environment access was reported while the controlled parent canary was not
readable; no real credential content was accessed. The profile probe fails
closed on the readable hard link, so workflow invocation cannot be treated as
qualified. This finding is `no-normative-impact` in qualification evidence and
implementation: the accepted credential-isolation contract already forbids
exposing outside material. Independent adjudication is still required.

The historical installed profile was not replaced. The security-qualification
repository variable must remain unset; no producer receipt here constitutes an
independent GO.

## Bounded v1 shell-tool correction

The v1 product decision excludes model-controlled shell execution because the
broker already supplies the verified source images, diffs and instructions
through stdin. The candidate adds `-c features.shell_tool=false` to the
one-shot Codex command without removing the existing reasoning-effort override
or changing its attempt-bound profile and evidence. On the installed Codex CLI
`0.164.0` in the dedicated Codespace, non-inference `codex features list`
with an empty temporary `CODEX_HOME` reported `shell_tool` enabled by default,
disabled by this override, and enabled by a positive-control override. Tagged
source `rust-v0.164.0` returns before `exec_command`/`write_stdin` registration
when that feature is disabled. No effective **model** tool inventory was
observed. The Codespace returned to observed `Shutdown` without accessing
OAuth material or invoking an authenticated model.

The conditional inventory in [`reviewer-tool-surface.md`](reviewer-tool-surface.md)
records other independently registered tools: `apply_patch`, MCP, subagents,
code mode, web, extension and image tools. Their effective exposure and
privilege behavior remain unqualified. The previously established readable
hard-link counterexample remains valid for direct sandbox path permissions;
disabling shell does not establish global credential isolation. Independent
security and construction review of the exact published delta are still
required.

## Trusted-runtime attestation delta

### Official release identity

Registry metadata establishes root package `@openai/codex@0.164.0` and Linux
x64 alias `@openai/codex-linux-x64`, mapped to published artifact
`@openai/codex@0.164.0-linux-x64`. Both archives matched their npm
`dist.integrity`; extracted launcher and native identities matched the installed
Codespace bytes. The broker now rejects alternate PATH identities, changed
package metadata, launcher or native bytes, unsupported platforms and missing
or ambiguous installations. It repeats verification at invocation and executes
a root-owned non-writable package-layout copy by absolute path. This establishes
bounded `OFFICIAL_NPM_ARTIFACT_IDENTITY`; it does not establish
`UPSTREAM_SOURCE_EQUIVALENCE` or independent acceptance.

### Managed configuration counterexamples

Isolated non-authenticated diagnostics with synthetic managed requirements
produced four counterexamples under pinned `0.164.0`:

- managed `features.shell_tool=true` replaced the requested false value;
- a disallowed attempt profile fell back to managed `:read-only` after warning;
- approval `never` fell back to managed `on-request` after warning;
- a managed fallback profile enabled network despite the requested prohibition.

These findings are `derived-from-existing-authority`: the accepted independence
contract already requires the exact effective policy. They affect
`verification-or-qualification-evidence`, `architecture-or-implementation` and
`integration-or-conformance`; no new product decision is introduced.

### Attestation blocker

Supported startup configuration prints requirements rather than final selected
policy. Feature and doctor diagnostics run in separate processes. The exec JSONL
adapter reduces `SessionConfigured` to `thread_id`, while human summary is
emitted only after thread start and omits shell state, active profile identity
and complete policy. There is no supported same-process broker pause before the
turn. Modifying upstream Codex or adopting another execution backend is outside
this task.

Therefore `OBL01_STATUS=IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`,
`OBL02_ATTESTATION_INTERFACE=UNAVAILABLE`, and `OBL02_STATUS=BLOCKED`. The
security gate remains closed, and no authenticated model invocation is
permitted.

## Security-assurance policy change and pilot exception (2026-10-26)

RB-PI-SEC-01 (#27) explicitly retires maximum assurance of Codex internals as
a blanket launch prerequisite for low-sensitivity v1. This decision does not
refute or erase any earlier probe or independent NO-GO. OBL-02/03/04 remain
UNDETERMINED for complete qualification; the product accepts these disclosed
residual risks only for the fixed, non-secret RB-PILOT-01 (#26) experiment.
The ordinary production workflow and security gate remain closed. Pilot JSON
and event checks establish only local synthetic functional behavior, not
production recovery or security qualification. No live pilot has been
observed by this documentation change.
