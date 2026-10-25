---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Consumer Integration"
version: "0.1.0"
---

# Review Broker Consumer Integration

## Approved endpoint

Create request Issues only in the private repository
`fanilosendrison/review-broker`. Do not create a consumer-specific execution
workflow or reviewer environment.

## CLI interface

Provide a mission object in `mission.json`:

```json
{
  "id": "publication",
  "objective": "Independently review documentary publication",
  "instructions": "Challenge the documentary candidate under the specified criteria.",
  "criteria": [
    "Preserve exact source identity",
    "Challenge unsupported publication claims",
    "Identify material uncertainty"
  ]
}
```

Then invoke:

```bash
reviewctl request \
  --repo fanilosendrison/proto-scope \
  --pr 57 \
  --profile publication \
  --mission-file mission.json
```

The command creates the canonical ReviewRequest v1 and one GitHub Issue. It does
not require Codex, the Codespace credential, or ChatGPT authentication.

## ChatGPT GitHub connector interface

Create an Issue in the same approved endpoint. Place exactly one RFC 8785
ReviewRequest object between:

```text
<!-- review-broker-request:v1 -->
<canonical ReviewRequest v1 JSON>
<!-- /review-broker-request:v1 -->
```

Do not introduce connector-specific fields or another protocol. The Issue
author must be authorized and the subject repository must be allowlisted.

Some GitHub token or App event sources may not trigger `issues.opened`. The
service does not assume delivery: the reconciler can discover admitted durable
work. Actual connector event behavior remains unqualified until a connected App
creates a test request after the workflow is present on `dev`.

## Agent entry point

The following instruction is provisional until final service qualification:

> For independent review, do not construct an ad hoc reviewer environment or
> independently select an execution mechanism.
>
> Use the Review Broker ReviewRequest contract.
>
> The requester owns the mission. The broker owns execution and evidence. The
> consumer owns admission of the result.

Consumers should reference this instruction rather than copy broker internals.
A `GO` remains subject to the consumer's own admission and publication policy.
