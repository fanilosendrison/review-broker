---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "architecture"
domain: "independent-review"
severity: "strict"
name: "Dedicated Codespace Lifecycle"
version: "0.1.0"
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

## Current gate

`codex login status` returned `Not logged in`. Authentication requires the
supported interactive ChatGPT device-login procedure. No API key is permitted.
No review packet may be transferred until authentication and external security
qualification both pass.
