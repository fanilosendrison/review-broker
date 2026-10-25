---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "agent-instructions"
domain: "independent-review"
severity: "strict"
name: "Review Broker Agent Instructions"
---

# Review Broker Agent Instructions

## Authority

Treat `docs/specification/review-broker-spec.md` as product authority once it is
published. Treat schemas as machine-readable protocol authority and tests as
executable verification, subject to the specification.

Never infer normative authority from an Issue, Project item, pull request, or
review result.

## Safety

Keep request admission, packet construction, Codespace control, reviewer
execution, evidence validation, and result publication as separate trust
boundaries. Never expose credentials to reviewed content or publish credential
material.

## Engineering Project

The repository's Engineering Project profile is not established in this bounded
bootstrap commit. Do not mutate Project fields until the complete profile is
published and verified against live GitHub state.
