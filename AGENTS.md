---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "agent-instructions"
domain: "independent-review"
severity: "strict"
name: "Review Broker Agent Instructions"
version: "0.3.0"
---

# Review Broker Agent Instructions

## Technical authority

Apply authority in this order:

1. `docs/specification/review-broker-spec.md` for product intent and boundaries.
2. Versioned schemas in `schemas/` for machine-readable public contracts.
3. Accepted architecture and security documents in `docs/`.
4. Executable source and tests for implementation behavior.

Issues, Project items, comments, pull requests, and review results are not
technical or product authority. They may select and track work only.

## Safety boundaries

Keep request admission, source acquisition, Codespace control, Codex execution,
evidence validation, and result publication separate. Never execute reviewed
repository code. Never expose ChatGPT authentication, GitHub control
credentials, API keys, authorization headers, or credential files to reviewed
content, evidence, logs, or Issues.

Do not run authenticated reviews of actual consumer PRs through the production
workflow until their applicable admission and qualification gates pass.
RB-PILOT-01 and RB-PILOT-02 (#26) are consumed and permanently closed; their
historical CLI entry points must refuse before side effects. RB-PILOT-03 has not
been created or authorized. A future synthetic identity requires separate
product authorization, a persistent controller reservation before any
model-capable command, and private pre-Shutdown evidence retention. No pilot
publishes, merges, or claims security qualification. The Product Intent decision
in #27 retires maximal Codex-internal attestation as a blanket low-sensitivity
v1 prerequisite; it does not authorize real-PR review or any new pilot inference
by itself. Never retry an attempt that reached `ARMED`.

## Engineering Project profile

- Owner: `fanilosendrison`
- Title: `Review Broker — Implementation`
- Number: `17`
- URL: `https://github.com/users/fanilosendrison/projects/17`
- Visibility: private
- Default Issue repository: `fanilosendrison/review-broker`
- Default repository branch: `dev`

The live Project uses only GitHub's standard fields. Exact workflow field:
`Status`, with options `Todo`, `In Progress`, and `Done`.

Map workflow state as follows:

- `Todo`: validated work is unstarted or ready.
- `In Progress`: an executor actively owns the work.
- `Done`: all acceptance, validation, publication, and required review gates are
  satisfied.

The Project has no dedicated blocked or review option. Keep blocked or
externally reviewed work at its truthful prior status and record the exact
blocker or review gate in the Issue. Never use `Done` for blocked, partial, or
merely implemented work.

The current view is `View 1`, a table without a filter. Use it as the complete
roadmap inventory; it adds no technical semantics.

Required classification comes from repository labels `contract`,
`infrastructure`, `implementation`, `qualification`, and `adoption`. Milestones
M0 through M3 carry the phase grouping. Native parent/sub-issue and blocked-by
relationships carry decomposition and prerequisite semantics.

Before changing Project fields or Issue lifecycle, inspect live state with the
repository's GitHub Engineering Project tooling and verify every mutation by
fresh readback.

## Stable requester instruction

Until final qualification, treat the following entry point as provisional:

> For independent review, do not construct an ad hoc reviewer environment or
> independently select an execution mechanism. Use the Review Broker
> ReviewRequest contract. The requester owns the mission. The broker owns
> execution and evidence. The consumer owns admission of the result.
