---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Minimal ReviewResult v2 Technical Policy and Reference Coverage Proposal"
version: "0.1.0"
---

# Minimal ReviewResult v2 — Technical Policy and Reference Coverage

**UNACCEPTED NON-NORMATIVE CANDIDATE. NOT AN EXECUTABLE SCHEMA. NO IMPLEMENTATION OR INFERENCE AUTHORIZED.**

## 1. Source problem and minimum versioned delta

This document is an annex to draft PR #55, derived from the accepted **non-normative**
PR #52 direction and #44 D1–D9. It is a standalone producer/consumer design
analysis, **not an independent reviewer verdict**. The current v1 result is
defined by `schemas/review-result-v1.schema.json` and
`docs/contracts/review-result.md`. It contains `policy_id` derived from
requester-selected semantic `policy.profile`, which #44 removes from the
proposed successor. That identifier must not silently become an identity
for the broker's technical runtime permissions.

The **minimal proposed ReviewResult v2** changes the result-v1 field set:

1. `schema_version` becomes the required integer `2`.
2. Replace `policy_id` with required `technical_policy_id`, with the
   separate, explicitly versioned identity basis in section 2.
3. Add required `reference_coverage`, an ordered, source-bound coverage
   summary in section 3; it is `[]` for requests with `references: []`.
4. Require the already-used `resolved_request` field, carrying the authenticated
   exact v3 request and resolved source/subject identities.
5. Preserve v1 `request_id`, `subject_id`, `packet_id`, `attempt_id`,
   `execution_status`, `evidence_status`, `review_verdict`, `reviewer`,
   `sources_examined`, `findings`, `remaining_uncertainties`, `validation`
   and `applicability` with their separate meanings and accepted evidence checks.

No historical v1 result bytes, receipt, marker, result ID or identity formula
are modified. All v1-only fields and unknown fields are rejected in the eventual
closed v2 schema. This design does not yet prove that a separate result schema
is the *only possible* minimal migration; it is an explicit candidate whose
necessity follows from non-reinterpretation of historic `policy_id`.

## 2. Exact proposed technical-policy identity

The identifier is:

`technical_policy_id = "technical-policy:sha256:" + lowercase_hex(SHA256(RFC8785(basis)))`

where the complete canonical basis is exactly:

```json
{
  "identity_schema_version": 1,
  "permission_profile_name": "review-broker-<attempt-bound-profile-name>",
  "permission_profile_sha256": "<64 lowercase hexadecimal characters>"
}
```

The real `permission_profile_name` is the **verified installed Codex
permission-profile name**, not literal example text. The hash covers the
**original actual installed profile bytes**, not the semantic profile name
`code/architecture/publication/scientific/custom` and not a claimed
effective-model identity.

The proposal requires agreement across the verified successor packet,
the trusted attempt artifact and the bounded preflight receipt:

- Same installed profile name, SHA-256 and exact attempt/packet binding.
- The profile bytes are verified and credential isolation/source-token
  separation is enforced by the applicable existing controls.
- A missing, contradictory or unverified profile fails the relevant
  evidence gate before result publication.
- Runtime executable/wheel identities and admission/assurance mode remain
  **separate** evidence attributes, not silently added to the policy basis.
- An attempt-specific profile name may yield a different identity for
  essentially similar permissions; the ID proves **exact profile identity**,
  not semantic equivalence across differently instantiated configurations.

**Critical limit:** verifying installed file bytes is **not** an
independent attestation of Codex's effective enforcement. Existing
`validation.assurance_scope`, requested model/effort and
`effective_model_identity_verified` /
`effective_reasoning_effort_verified` retain their own unaltered evidence
status. Do not resurrect comprehensive internal Codex attestation by
renaming a verified producer receipt into an effective-policy proof.

## 3. Exact first-stage reference coverage union

`reference_coverage` is a **required ordered array** corresponding
one-to-one, in the same order, to every entry of the canonical
v3 request's mandatory `references` array. Its first-stage entries
are closed discriminated objects, not freeform labels.

```json
{
  "reference_coverage": [
    {
      "id": "requirement",
      "status": "captured",
      "source_id": "S003"
    },
    {
      "id": "optional-context",
      "status": "omitted",
      "reason": "AUTHORIZED_ABSENT"
    }
  ]
}
```

Rules for the first **single-content text** kinds:

- Exactly `id`, `status=captured` and one actual `S001`–`S999`
  `source_id` for a captured reference. The ID must refer to a
  **reference-role** source in the exact packet manifest.
- Exactly `id`, `status=omitted` and the bounded reason
  `AUTHORIZED_ABSENT` for an omitted optional reference.
- Omission is allowed only when the broker has **affirmatively proved
  permissible absence via authorized source authority**. An ambiguous
  404, permission uncertainty, transient read error, unqualified
  source kind, unsafe destination or expected-digest mismatch is **not**
  omitted. Such failures reject admission/preparation as appropriate.
- Every required reference is `captured` for a prepared packet;
  no omitted reference can become `sources_examined` or support citations.
- `sources_examined` may include **subject-source IDs** and/or captured
  reference-source IDs; not all examined sources must be references.
  Conversely, a captured source does not prove actual substantive
  examination by a reviewer.
- Missing, duplicated, reordered, invented or contradictory reference
  outcomes fail result validation against the packet. A future
  multi-component reference needs a separate versioned coverage shape.

This is a **minimal durable metadata summary**, not a second source
archive. The full original bytes/hashes and source roles remain tied to
`packet_id` and its authenticated manifest/receipt. No private source
content is copied into a published result. If a source artifact expires
and cannot be retrieved, the consumer must report the limitation;
the summary is not proof that the underlying bytes remain available.

## 4. Proposed first-stage result-v2 object shape

The following JSON is an **illustrative synthetic object** showing the
complete set of candidate top-level keys, not an executable result,
reviewer response, or signed publication receipt:

```json
{
  "schema_version": 2,
  "request_id": "request:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "subject_id": "subject:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "technical_policy_id": "technical-policy:sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "packet_id": "packet:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "attempt_id": "attempt:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "execution_status": "COMPLETED",
  "evidence_status": "VALID",
  "review_verdict": "NO_GO",
  "resolved_request": {
    "schema_version": 3,
    "request": {
      "schema_version": 3,
      "references": []
    }
  },
  "reviewer": {
    "backend": "codex-cli",
    "model_requested": "gpt-5.6-sol",
    "reasoning_effort_requested": "xhigh",
    "effective_model_identity_verified": false,
    "effective_reasoning_effort_verified": false
  },
  "sources_examined": ["S001"],
  "findings": [],
  "remaining_uncertainties": [],
  "validation": {
    "assurance_scope": "BOUNDED_PRIVATE_V1",
    "effective_policy_attestation": "UNAVAILABLE"
  },
  "applicability": {
    "status": "CURRENT",
    "checked_head_commit": "1111111111111111111111111111111111111111"
  },
  "reference_coverage": []
}
```

The result above deliberately uses *dummy identities*, and the abbreviated
`resolved_request` is **not** a complete valid v3 request. The real
`technical_policy_id` must be recomputed from the genuine installed
profile and tied to the signed packet/attempt evidence. No favorable
verdict, policy attestation or claim of live support is implied.

## 5. Publication, retrieval and applicability

- Retain the current independent v1 execution/evidence/verdict/applicability
  dimensions. `COMPLETED` and `VALID` never imply `GO`, and a
  structurally valid citation never establishes substantive correctness.
- A v3 permanent **pre-model** refusal produces an authenticated refusal
  receipt and terminal claim disposition, **not** a fabricated
  `ReviewResult` with a fake inference outcome.
- `applicability=CURRENT` refers only to the reviewed PR HEAD as
  independently checked at publication; it never implies that any
  mutable Issue/comment/web reference remains current.
- Do not add `reference_currentness` to result-v2. A future freshness
  observation requires a separately approved bound contract, without
  mutating an immutable historic result or invoking a new model.
- The result-v2 canonical identity, versioned marker/envelope, publication
  intent and receipt, publisher actor authentication, complete comment
  pagination, and `reviewctl result` retrieval **must be separately
  versioned and acceptance-tested**. They are not implemented here.

## 6. Falsification checklist and disposition

Require executable **offline** contract fixtures before acceptance:

1. `policy_id` from v1 is rejected by closed result-v2 schema.
2. Same actual profile bytes/name give same technical-policy ID; changing
   name or installed bytes changes it and fails attempt/packet mismatch.
3. No effective-policy/model attestation may be inferred from profile hash.
4. Empty v3 references produce exactly `reference_coverage: []`.
5. Every declared reference has exactly one corresponding outcome and
   none is omitted if required.
6. A captured reference names an actual reference-role `Sxxx` source,
   whereas a subject-role `Sxxx` is allowed in `sources_examined`.
7. Omitted references cannot appear examined or cited; 404 uncertainty
   cannot be misrepresented as authorized absence.
8. Published metadata must match the exact immutable packet manifest.
9. Result currentness cannot become reference currentness.
10. Historic v1 canonical bytes, identities, markers, comments and
    result retrieval remain independently interpretable.

**Current status:** This is a proposal; a small standalone experimental
counterexample model is documented in the companion offline qualification
note, but it is **not a test of the real successor implementation**.
Independent reviewer qualification with exact governing source access
and an accepted versioned schema remain required.

`RESULT_V2_DESIGN=PROPOSED_NOT_ACCEPTED`
`TECHNICAL_POLICY_IDENTITY=PROPOSED_NOT_ATTESTED_EFFECTIVE`
`REFERENCE_COVERAGE_SHAPE=PROPOSED_NOT_IMPLEMENTED`
`V1_RESULTS_MUTATED=NO`
`NORMATIVE_SCHEMA_ACCEPTED=NO`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
