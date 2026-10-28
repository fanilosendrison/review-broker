---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Bootstrap Record"
version: "0.1.0"
---

# Review Broker Bootstrap Record

## Repository

The local root was empty and was not a Git repository. No user material was
deleted or overwritten. `fanilosendrison/review-broker` did not exist and was
created directly with `PRIVATE` visibility. Fresh GitHub readback confirmed the
visibility and default branch `dev`.

The first bounded bootstrap commit established the repository before detached
worktree authoring. Subsequent construction occurs on
`feat/full-bootstrap-delivery` through a detached linked worktree and a pull
request. Branch protections and required checks must not be bypassed.

## GitHub governance

Private user Project #17 is `Review Broker — Implementation`. Issue #1 is the
native roadmap parent. Issues #2 through #13 are native sub-issues RB-01 through
RB-12. Four repository milestones represent M0 through M3. Native blocked-by
relationships encode the approved dependency graph.

The Project's live standard fields and single table view are documented in
`AGENTS.md`. Issue closure is not evidence that technical qualification passed.

## Historical reference

The implementation inspected, without modification, commit
`e9f9234730b8d7cab7d2c0ef295bec7856fdbf17` from
`fanilosendrison/turnlock-review-lab`, including:

- `tools/codex_oauth_review.py`;
- `tools/review_sources.py`;
- `tests/test_codex_oauth_review.py`;
- `programs/issue78-pr80-m7-codex-oauth-pilot-v1.json`.

The broker retains one-shot invocation, Git and SHA-256 identities,
line-addressed packets, immutable prompts, JSONL evidence, citation anchoring,
failure preservation, and no fallback. It replaces the historical carriage
return rejection with byte-preserving physical-line mapping.

## Dedicated runtime

Exactly one new Codespace was created for the broker on the lowest available
machine. Codex CLI `0.164.0` was installed from a pinned npm package and its CLI
flags were inspected. The runtime is stopped. No historical ChatGPT credential
was copied.
