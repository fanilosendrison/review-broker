---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "ReviewRequest v1 Contract"
version: "0.1.1"
---

# ReviewRequest v1 Contract

## Canonical representation

ReviewRequest v1 is the object defined by
`schemas/review-request-v1.schema.json`. Canonical bytes use RFC 8785 JSON
Canonicalization Scheme, encoded as UTF-8 with no byte-order mark or trailing
newline. The logical request identity is:

```text
request:sha256:<SHA-256 of canonical request bytes>
```

The schema permits exactly the v1 fields. A GitHub pull request is the only
implemented subject kind. The initial backend, model, and effort are
`codex-cli`, `gpt-5.6-sol`, and `xhigh`.

## Mission ownership

The `mission` object belongs to the requester. `objective`, `instructions`, and
at least one `criteria` entry are required. Admission rejects missing
information instead of creating domain premises. The requested profile adds
mandatory behavior and minimum evidence. Mission text can strengthen but cannot
disable the profile.

## Immutable resolution

Admission resolves and stores repository identity, pull-request number, exact
head and base commits, merge base, mission identity, policy identity, and source
manifest identity. A later head change does not mutate the prior resolution.

The following identity domains remain separate:

- `request:sha256:` for canonical logical requests.
- `subject:sha256:` for exact resolved subjects.
- `mission:sha256:` for requester mission content.
- `policy:sha256:` for selected policy identity.
- `attempt:sha256:` for an explicit request identity and ordinal.
- `packet:sha256:` for packet basis and source manifest.
- `artifact:sha256:` for exact evidence bytes.

## GitHub Issue envelope

The canonical JSON appears exactly once between these markers:

```text
<!-- review-broker-request:v1 -->
<one RFC 8785 JSON object>
<!-- /review-broker-request:v1 -->
```

A derived `Request-ID` may appear outside the markers. No other Issue text has
request semantics. Multiple envelopes, noncanonical JSON, unknown fields, and
unauthorized authors or repositories fail admission.

## Version compatibility and re-review boundary

The v1 fields do not distinguish duplicate delivery, a fresh request for a newly
resolved PR head, and explicit re-execution of an earlier attempt. V1 therefore
continues to preserve one deterministic logical claim and does not allocate a
new attempt after a subject change.

The accepted v2 semantics are defined separately in
`docs/contracts/review-request-v2.md`. They do not add fields to v1, reinterpret
historical v1 bytes, activate v2 support, or authorize execution. Existing v1
canonical bytes, identities, attempts, claims, artifacts, journals, publication
receipts, and result retrieval remain valid.
