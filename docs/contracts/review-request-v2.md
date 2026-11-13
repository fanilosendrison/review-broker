---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "ReviewRequest v2 Contract"
version: "0.1.2"
adoption_status: "accepted"
---

# ReviewRequest v2 Contract

## Publication and implementation status

This document is the accepted normative contract for ReviewRequest v2. Version
0.4.17 implements the schema, parsing, identity, admission, predecessor,
execution, recovery, publication, and retrieval integration described here.
Operational v2 admission remains explicitly default-disabled and requires
separate authorization. ReviewRequest v1 remains supported unchanged.

The [ED04 status reconciliation](../adoption/jch-normative-adoption.md#ed04--governed-status-reconciliation)
corrects stale implementation-status prose in the primary specification and
execution contract without changing these request semantics or wire bytes.
Request2 is independent of journal2/J-CH, whose normative effect begins upon
integration into dev; neither implementation status nor document publication
activates its execution.

## Stable Review Intent

A Review Intent identifies review purpose independently of execution and pull
request revisions. Its canonical object consists exactly of:

```json
{
  "mission": "<the complete ReviewRequest mission object>",
  "policy": "<the complete ReviewRequest policy object>",
  "reviewer": "<the complete ReviewRequest reviewer object>",
  "subject": {
    "kind": "github_pr",
    "pull_request": 57,
    "repository": "owner/repository"
  }
}
```

The example strings denote complete objects; they are not literal wire values.
The intent subject is the logical GitHub pull-request identity and contains no
commit. Canonical bytes use RFC 8785 JSON Canonicalization Scheme, encoded as
UTF-8 with no byte-order mark or trailing newline. Its identity is:

```text
review-intent:sha256:<SHA-256 of canonical Review Intent bytes>
```

An intent is not executable, is not a request, attempt, result, claim, or
verdict, and cannot authorize model execution or consumer action.

## Canonical v2 request

A v2 request preserves the v1 top-level `subject`, `mission`, `policy`, and
`reviewer` objects, sets `schema_version` to `2`, and adds the required
`review_operation` object. The `subject` adds required
`expected_head_commit`, which is exactly 40 lowercase hexadecimal characters.
The complete request permits no unknown fields. The implemented executable
contract is a JSON Schema Draft 2020-12 resource at
`schemas/review-request-v2.schema.json`. It must preserve the exact v1 schemas
for `mission`, `policy`, and `reviewer`; require exactly `kind`, `repository`,
`pull_request`, and `expected_head_commit` in `subject`; and encode
`review_operation` as the closed discriminated union below. It must not modify
or replace `schemas/review-request-v1.schema.json`.

Canonical request bytes use the same RFC 8785 encoding as v1. Identity remains:

```text
request:sha256:<SHA-256 of canonical complete request bytes>
```

The Review Intent is derived from the complete `mission`, `policy`, and
`reviewer` objects and the logical subject after removing only
`expected_head_commit`. Implementations must compute and retain the derived
`review-intent:sha256:` identity; the request does not carry a caller-supplied
intent identity.

The implemented GitHub envelope uses exactly one v2 marker pair:

```text
<!-- review-broker-request:v2 -->
<one RFC 8785 JSON object>
<!-- /review-broker-request:v2 -->
```

Text outside the markers has no request semantics. A v1 marker never carries a
v2 request, and a v2 marker never changes the interpretation of a v1 request.

## Review operation discriminated union

`review_operation` is one of these exact closed objects:

```json
{"kind":"initial"}
```

```json
{
  "kind": "changed_head",
  "previous_request_id": "request:sha256:<64 lowercase hexadecimal characters>"
}
```

```json
{
  "authorization_nonce": "<32 lowercase hexadecimal characters>",
  "kind": "repeat_same_head",
  "previous_request_id": "request:sha256:<64 lowercase hexadecimal characters>"
}
```

The nonce represents a cryptographically generated 128-bit value and creates a
distinct canonical request identity. It is not proof of authorization.
Contradictory metadata is invalid: `initial` permits neither predecessor nor
nonce; `changed_head` requires one predecessor and forbids a nonce; and
`repeat_same_head` requires both one predecessor and one nonce.

## Admission invariants

Admission must authenticate and authorize the requester under applicable broker
policy before accepting any operation. Operational admission for real model
execution remains a separate explicit requirement.

For every operation, admission must resolve the pull request and require its
head to equal `subject.expected_head_commit` before creating an execution claim.
A mismatch fails closed. For predecessor-bearing operations, trustworthy
historical evidence must identify the predecessor request, its Review Intent,
and its exact expected head. Unavailable, malformed, conflicting, or
incompletely bound history fails closed. A v2 predecessor uses its immutable
journal-bound admission record, including its exact expected and resolved head.
A historical v1 predecessor never gains an `expected_head_commit` field. Its
head is the observed `resolved_request.subject.head_commit` from the existing
receipt-authenticated published result, and its Review Intent is derived from
its unchanged v1 request fields.

`initial` has no predecessor. `changed_head` requires the predecessor to have
the same Review Intent and a different verified expected head.
`repeat_same_head` requires the predecessor to have the same Review Intent and
the same verified expected head, plus a fresh nonce and explicit repeat
authorization. No operation implies automatic review or re-review.

## Attempt allocation and duplicate delivery

Every distinct admitted v2 request permits exactly one attempt, with ordinal
`1`. Its identity remains the existing computation:

```text
attempt_identity(request_id, 1)
```

V2 never allocates an ordinal greater than `1`. A completed, failed, or
indeterminate attempt is never reset, reused, or incremented to obtain another
model invocation.

Identical canonical v2 bytes produce the same request identity and deterministic
claim. Repeated GitHub events, workflow deliveries, reconciliation passes,
transport retries, or multiple GitHub Issues carrying those same bytes reuse
that claim. They cannot allocate another attempt or invoke Codex again.

## Re-review and historical immutability

A changed pull-request head requires a newly authorized `changed_head` request.
A repeat on the same head requires a newly authorized `repeat_same_head`
request. Each is a distinct request with its own deterministic claim and
ordinal-1 attempt.

No later request resets or mutates a predecessor request, attempt, source,
packet, artifact, journal, publication intent, publication receipt, or result.
A later result does not automatically override an earlier result or authorize
consumer action. A prior invalid result does not become valid because a later
review succeeds.

A model-capable indeterminate attempt is never retried automatically. Duplicate
delivery, reconciliation, workflow replay, timeout, lost response, or
infrastructure recovery cannot create a second model-capable invocation under
the request. A subsequent same-head review requires a distinct
`repeat_same_head` request and distinct authorization. This is not a claim of
provider-level exactly-once inference.

## V1 compatibility

ReviewRequest v1 remains byte-for-byte and semantically unchanged. V2-only
fields never appear in a v1 request, and historical v1 canonical bytes are never
reinterpreted as v2. Existing v1 request identities, ordinal-1 attempt
identities, claims, artifacts, journals, publication receipts, and CLI result
retrieval remain valid. ReviewResult's independent execution, evidence, verdict,
and applicability dimensions remain unchanged.
