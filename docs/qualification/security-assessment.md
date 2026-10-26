---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Reviewer Credential-Isolation Assessment"
version: "0.1.1"
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

The revised profile does not overwrite an installed historical profile with
different bytes. Migration and independent examination of the exact runtime
profile are prerequisites for authenticated execution. The security-qualification
repository variable must remain unset; no producer receipt here constitutes an
independent GO.
