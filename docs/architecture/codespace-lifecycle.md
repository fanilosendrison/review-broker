---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "architecture"
domain: "independent-review"
severity: "strict"
name: "Dedicated Codespace Lifecycle"
version: "0.1.1"
---

# Dedicated Codespace Lifecycle

## Provisioned runtime

The dedicated Codespace is
`review-broker-reviewer-4q4v769jr65hjww9` for
`fanilosendrison/review-broker` on branch `dev`. The selected machine is
`basicLinux32gb`, the lowest available option: 2 cores, 8 GB RAM, and 32 GB
storage.

Observed runtime inventory:

- Linux kernel `6.8.0-1064-azure` on `x86_64`.
- Ubuntu `24.04`.
- GitHub CLI `2.100.0`.
- Python `3.14.2` in the runtime image.
- Codex CLI `0.164.0` from `@openai/codex@0.164.0`.
- npm integrity `sha512-TWj7UGyPRe3Pj/A3ddNAxs1te3a/W/xAd+J0LHrrFTmsSfahGMOLF/vn88D3QCIgAT3B1rm1y/Z3NYE0rx6cZQ==`.

The Codespace is independent of Proto-Scope and Turnlock Review Lab. Its current
observed state is `Shutdown`.

## Lifecycle protocol

A trusted workflow starts the existing Codespace through the authorized REST
endpoint and polls until `Available` with a fixed bound. It transfers only the
prepared packet, verifies packet identities inside the runtime, durably records
`ARMED`, and permits one Codex process.

The workflow recovers named evidence artifacts, validates them outside the
reviewer, publishes through a separate credential, requests stop, and polls
until `Shutdown`. `ShuttingDown` is not terminal proof.

Every post-start failure enters cleanup. A scheduled reconciler separately reads
durable claim refs and observed Codespace state, marks an inconclusive armed
attempt `INDETERMINATE`, and stops a stranded runtime. Cleanup does not infer
execution success.

## Qualified control transport

A dispatch-only trusted workflow at default-branch SHA
`21a944ac65404dfe2f1d17d51787d3a245ebb0f7` qualified the dedicated credential
in Actions run `40304872558`. Identity `fanilosendrison` demonstrated exact
Codespace visibility, REST start through `Available`, fixed-command SSH, upload,
remote byte and SHA-256 verification, download with exact byte equality, and
stop through `Shutdown`. Cleanup independently observed `Shutdown`.

The GitHub CLI's Codespace copy wrapper requires legacy SCP mode (`scp -O`) to
interpret its quoted remote path correctly. A fixed trusted download path also
requires `gh codespace cp --expand` so OpenSSH strict filename checking can
remain enabled. No broader credential permission is required by this transport
constraint.

## Current gate

`codex login status` returned `Logged in using ChatGPT` at the recorded
post-authentication observation. No API key is permitted. The corrected
historical named permission profile passed limited producer canaries but failed
a later controlled outside-tree canary. A temporary minimal-read direct probe
passed that outside-tree check; effective model-tool isolation is still
unqualified. The Codespace was returned to `Shutdown` after the controlled
probes.

The Codespaces-control transport gate passes. No review packet may reach a model
until independent security review accepts the exact candidate and evidence.
