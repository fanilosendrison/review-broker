---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Requester-Declared Reference Contract Proposal"
version: "0.1.0"
---

# Requester-Declared Reference Contract Proposal

**DRAFT FOR INDEPENDENT CONTRACT REVIEW — NON-NORMATIVE; NOT ACCEPTED; IMPLEMENTATION NOT AUTHORIZED**

## 1. Status, motivation, and authority

This proposal addresses **Issue #51 (RB-CON-REF)** and the requester-owned
reference-material Product Intent **PI-REQ-03 in Issue #43**. It composes with
the **product-owner-accepted but non-normative** mission-design direction D1–D9
in `docs/architecture/requester-owned-mission-decision-proposal.md` (#44).

The motivating evidence is F003 from the historical ReviewRequest #50: the
reviewer of PR #45 could only see PR change material, not the cited Issues #43
and #44 or relevant governing sources. That review's `COMPLETED / VALID /
CURRENT / NO_GO` result is immutable. Source absence was a known packet scope
limitation, not evidence of a failed model invocation.

**Authority boundary:** This document is a proposed design, not a new accepted
ReviewRequest, ReviewResult, packet, source, or execution contract. Current v1/v2
schemas, identities, operating modes, GitHub permissions, and source-reader code
remain untouched. The supported subject for the first qualification remains a
GitHub PR. PR-independent subjects are separately tracked under #43 PI-REQ-02.

## 2. Minimal model and proposed decisions

### R1 — Three distinct roles

- **Subject:** exactly what is being examined (initially an identified GitHub PR,
  including its correctly bound change scope).
- **Mission:** requester-authored objective, instructions and criteria. Its
  semantic freedom follows the accepted #44 design direction; the broker does
  not insert mandatory domain review profiles.
- **References:** bounded material designated or directly supplied by the
  requester to inform examination of the subject.

A reference is neither an implicit change to the subject nor a verified
normative authority. Requester claims, content observed by the reviewer,
technical properties verified by the broker, reviewer findings, and downstream
consumer acceptance remain distinct.

### R2 — Minimal requester declaration

The proposed successor request has one optional, ordered `references` array.
An absent array or an empty array means **no requester-declared references**,
not that the mission's implicit evidence needs have been satisfied.

Each declaration has exactly three common properties:

| Property | Meaning |
| --- | --- |
| `id` | Unique stable requester-chosen identifier **within this request** |
| `required` | Explicit boolean; required and optional are never inferred |
| `source` | A discriminated source designation or requester-supplied content |

No `review_type`, `document_class`, `authority_level`, mandatory evidence
ontology, or independent `acquisition_mode` field is introduced. Acquisition is
entailed by the source kind. The example below is **a fragment, not executable
wire-schema approval**:

```json
{
  "references": [
    {
      "id": "intent",
      "required": true,
      "source": {
        "kind": "github_issue_body",
        "repository": "fanilosendrison/review-broker",
        "issue": 43
      }
    },
    {
      "id": "decision",
      "required": true,
      "source": {
        "kind": "github_issue_comment",
        "repository": "fanilosendrison/review-broker",
        "comment_id": 6506352077
      }
    },
    {
      "id": "spec",
      "required": true,
      "source": {
        "kind": "git_file",
        "repository": "fanilosendrison/review-broker",
        "path": "docs/contracts/review-request-v2.md",
        "commit": "ff83e486c6771c286f99a28e0813d151da3a2b91"
      }
    },
    {
      "id": "additional-context",
      "required": false,
      "source": {
        "kind": "inline",
        "text": "Check the unstated concurrency assumptions."
      }
    }
  ]
}
```

A remote mutable source may additionally specify a **content expectation**
(e.g., `expected_sha256`, explicitly scoped to the selected component or
complete returned object). If set, an observed mismatch is never silently
accepted. The exact wire placement and validation constraints of that optional
pin are successor-schema work, not settled by this example. Inline content is
already part of canonical request bytes. An uploaded file instead requires an
immutable, authenticated transfer receipt that identifies its received bytes
before it can be referenced by a request.

### R3 — Supported product forms without a universal ingestion platform

| Source kind | Acquisition | Declared selection |
| --- | --- | --- |
| `inline` | Requester inline | Explicit text |
| `git_file` | Remote Git | Repository, path, exact commit |
| `github_issue_body` | Remote GitHub | Repository and issue ID |
| `github_issue_comment` | Remote GitHub | Repository and individual comment ID |
| `github_pr` | Remote GitHub | Repository, PR ID and explicit component selector(s) |
| `upload` | Requester file transfer | An authenticated immutable upload receipt |
| `web_url` | Remote HTTP(S) | Exactly requested URL/resource, not linked resources |

These are **reference forms**, not new subject kinds. For `github_pr`, a
component selector may request the description, exact code change material,
conversation comments, review submissions and/or inline review comments.
A requested collection requires a complete, bounded component inventory;
all pages must be accounted for. Each mutable description or comment is
captured separately. The PR head alone does not identify those bodies.
Linked Issues, third-party documents and recursive URLs are never included
implicitly.

The first **implementation candidate** supports UTF-8 inline text and
same-authorized-repository Git files, GitHub Issue bodies, and individual Issue
comments, with the existing GitHub PR **subject**. GitHub PR **references**,
file uploads, and external web resources remain product requirements but may
be qualified in subsequent stages. No raw binary source gains a line-addressed
citation contract merely by being named.

### R4 — Captured snapshots are technical observations, not origin proofs

The broker records a distinct outcome for **every** declared reference:
`captured` or `omitted`, with a bounded reason for omission. A captured source
records the requester reference ID, its source designation and role, acquired
bytes and SHA-256, byte length, stable `Sxxx` source identifier(s) where
applicable, snapshot path, observation metadata, and technical source
provenance actually verified.

For Git, record repository identity, commit, path, Git blob OID, SHA-256 and
original bytes. For GitHub Issues/comments, record the identified GitHub
object, the actual body string received from the authenticated API, its exact
chosen UTF-8 encoding as packet bytes, content hash, and observation time.
That verifies **what the API returned**, not an immutable version history
of GitHub's mutable objects.

For inline/upload, record the authenticated submitting principal, actual
received bytes, and verified transport receipt when applicable. A submitted
filename, label, purported repository or asserted source URL is a **claim**,
not independently verified authorship. An externally retrieved URL is a
location, not immutable identity: record requested and final URL, bytes,
SHA-256, observation information and redirect provenance.

Do not introduce a stand-alone `ReferenceSetID` unless independent consumption
or lookup later proves it necessary. The versioned packet manifest already
carries the whole referenced set and its immutable identity.

### R5 — Required, optional and unauthorized are distinct

- A **required** source that is missing, unverifiable, unsupported, oversized,
  unauthorized, incompletely captured, or inconsistent with an expected digest
  prevents model-capable armament. No "complete review" may be reported.
- An **optional** source may be `omitted` only when the broker can reliably
  establish an allowed absence/unavailability under an authorized acquisition
  path. It is not transmitted, not cited and not counted as examined. The
  omission and reason remain bound to the immutable packet.
- Authorization failure, ambiguous permission/nonexistence, unsafe destinations,
  or a disallowed source class are **admission failures even when optional**;
  `required=false` is not a way to bypass the read boundary.
- References mentioned only in natural-language mission instructions do not
  become silently declared, and the broker does not claim to detect all
  implicit substantive evidence requirements.

No requester instruction can disable technical admission or citation
validation. The reviewer may independently report insufficient substantive
evidence without the broker making a domain-level sufficiency judgment.

### R6 — Packet integration without relaxing PR change scope

Use a successor **versioned packet shape** capable of distinguishing source
roles; do not reinterpret historical packet-v1 bytes or IDs.

- Keep all original PR preimages, postimages, changed-file statuses, and exact
  diff exclusively in the **subject change basis**.
- Validate exact changed-file coverage against **subject sources only**.
  `changes.validate_change_scope` must not be weakened to accept arbitrary
  reference files as changed images.
- Include a bounded reference record for **every declared reference** (including
  optional omissions) and separate captured source entries from change
  images, while using existing `S001`-style citation IDs for supported text.
- Bind both bases, ordered reference declarations/outcomes, source bytes and
  derived representations, mission/program instructions and renderer identity
  into the same new `packet_id` computation. Verify a prompt by reconstructing
  it from bound inputs, never by trusting the prompt's own digest alone.
- A captured source may be **available** to the reviewer without the broker
  proving it was substantively **examined**. `sources_examined` and citations
  are reviewer reports subject only to supported structural/anchor checks.
- Treat all reference text and embedded links/instructions as untrusted data:
  no execution, no elevation to broker protocol or normative authority.

For HTML or PDF, retain original source bytes. Any extracted/rendered text is
a separate identified derivative with pinned extraction method/version and
explicit coverage limitations. A text-only extract does not prove diagrams,
images or nontextual claims were examined.

### R7 — Versioned request and intent identities

Because `review-request-v2.schema.json` is closed, this feature **cannot be
silently inserted into v2**. A single versioned successor is the preferred
integration point for #44 mission semantics and #51 references. `v3` is a
working designation, **not yet an approved whole-request schema**.

Proposed successor identity rules:

1. `request_id` hashes the **complete canonical successor request**, including
   exact reference declarations, any version pins, inline bytes, immutable
   upload receipts, operation and explicit re-review authorization nonce.
   Identical canonical bytes yield the same claim: delivery duplication or
   source drift cannot authorize a second model invocation.
2. A **version-distinguished Review Intent** hashes the logical PR subject,
   requester mission, requested reviewer settings, and each reference's
   `id`, `required`, kind and **logical selector**. It excludes source-version
   expectations, observed snapshots, Git file commit when the repository/path
   remain the logical selector, mutable body hashes, inline content, and upload
   receipt bytes. Inline/upload use their reference ID as their logical slot;
   matching slots are not proof of semantically equivalent content.
3. A different reference logical target, component selection, required flag,
   mission or reviewer setting produces a different Review Intent. Merely
   observing a new version of the same logical remote target does not.
4. Version 3 identity bases must include an explicit identity-version
   discriminator. They must not collide semantically with or reinterpret v1/v2
   `review-intent`, `policy_id`, `program_id` or predecessor evidence.
5. Removing #44's **semantic** `policy.profile` must not erase broker-owned
   runtime permission and policy provenance. The successor must bind the
   actual approved technical reviewer configuration independently of requester
   semantic taxonomy.

Cross-version `v1/v2 ↔ successor` predecessor equivalence is **not presumed**.
Reject an unsupported cross-version predecessor rather than interpreting
older attempts under new identity rules. The exact new canonical basis and
predecessor proof obligation must be accepted before implementation.

### R8 — Re-review and durable capture boundary

Retain the useful v2 operation meanings for a successor design, subject to
explicit versioned validation:

| Event | Required treatment |
| --- | --- |
| Same request delivered twice | Same request ID, claim and at-most-once attempt |
| Same logical references, changed PR head | New authorized `changed_head` request |
| Same PR head, changed reference snapshot | New authorized `repeat_same_head` request with distinct nonce |
| Different logical reference selector or requiredness | New Review Intent; explicit new initial request |
| Crash before a reference snapshot is durably committed | Safe pre-model recovery may reacquire; no inference or earlier snapshot claim |
| Crash after a packet/snapshot identity is durably prepared | Resume must verify/reuse the **same exact bytes**; changed re-fetch cannot replace it |
| Interrupted/indeterminate model-capable attempt | Never silently retry or rearm the same request |

A source snapshot is committed when packet evidence is **durably linked to the
journal's prepared state**, not merely when a transient local file was fetched.
If a prepared packet cannot be reproduced byte-identically and authorized
artifacts cannot be recovered, fail closed; do not "refresh" under the old
claim. At-most-once Codex invocation remains a separate requirement; no
provider-level exactly-once inference is claimed.

This does **not** require acquisition before the journal claim for all sources:
the current `REQUESTED → ADMITTED → PREPARED` lifecycle can be preserved if
required-completeness is guaranteed before any model-capable armament and
recovery identity evidence is trustworthy.

### R9 — Distinct reference freshness, no historical result mutation

A `CURRENT` subject HEAD does not establish current references. Preserve
subject applicability and a **separately scoped, dated observation** of
reference freshness. For an observable mutable reference, possible check
outcomes are `CURRENT`, `SUPERSEDED`, `UNDETERMINED` or `NOT_CHECKED`. Immutable
or directly supplied snapshots need no later external-currentness assertion.

Results always identify **the exact reference snapshots examined**. Their
validity as historical evidence does not change when an upstream resource
changes. A subsequent freshness check is a distinct authenticated observation
and must never overwrite historical ReviewResult bytes or mint a new inference.
The future result representation or linked observation needs its own accepted
versioned contract: ReviewResult v1 cannot acquire new fields silently.

If no freshness recheck occurred, do not claim that the reference is current.
No automatic network refresh is required on every `reviewctl result` read.

### R10 — Least authority and bounded transport

Source authorization is independent from requester authentication, subject
authorization and runtime admission. A requester-supplied reference must not
leak another installation's/private repository's content. The initial GitHub
retrieval scope is **the same explicitly authorized repository**.

The existing private source App permits Contents/Pull requests/Metadata reads,
not private Issue bodies by implication. Any `Issues: read` grant or App
configuration change requires explicit owner approval and separate
qualification. Publication or Codespace-control credentials cannot substitute
for read authority. Reference credentials must not reach the reviewer.

For later uploads: authenticated sender, immutable received-object receipt,
byte/count/retention limits, hash validation, private storage and no local-path
assumption. For web resources: narrowly permitted HTTP(S) destinations (HTTPS
first), redirect and DNS revalidation, denial of private/loopback/metadata
targets, bounded size/content type, no browser script execution or recursive
crawl, and explicit handling of unauthenticated/private resources.

Existing limits (2 MB/source, 8 MB rendered prompt, S001–S999 citation IDs)
are **starting implementation constraints**, not a new universal promise.
Small, qualified limits may be stricter; oversized or unsupported material
fails truthfully. Security assurances should remain risk-proportionate and
not resurrect generalized exhaustive Codex-internal attestation.

## 3. Minimal staged implementation and qualification

No implementation Issues are authorized or created by this proposal.

- **A — Core references and inline:** successor request/packet representation,
  independent change/reference scope, exact bytes and omission handling, stable
  identities, recovery, citations and offline validation.
- **B — GitHub acquisition:** versioned Git files, Issue bodies, individual
  comments and explicit PR components; permission decisions and complete API
  pagination. Same authorized repository initially.
- **C — Upload:** transferable immutable file receipts and agent submission
  without forcing publication of local material.
- **D — Web:** selected URLs, text/HTML articles/documentation and PDF byte
  capture with qualified extraction and bounded network behavior.

A is the logical prerequisite. B, C and D may have independent implementations
and qualification. Reuse #48 for self-service GitHub App onboarding and #13
for agent-facing submission; do not duplicate those responsibilities. Support
for PR-independent **subjects** stays separate under #43 PI-REQ-02.

### Acceptance fixtures — no live inference required

1. **Historical F003 analogue:** the exact PR #45 historical head
   `d728086bd8faf082e5b2725a59c21cc6ab2b55ea` plus genuinely preserved
   reference snapshots if available; otherwise an **explicitly synthetic**
   replica. Never claim today's mutable #43/#44 bodies are historic originals.
2. **Changed-file independence:** a reference path not in the PR diff is
   available as reference but never added to changed-file coverage.
3. **Required failure:** missing, forbidden, digest-mismatched, oversized or
   incomplete required material cannot arm a reviewer.
4. **Optional failure:** provably missing authorized optional reference is
   packet-bound as omitted, with no invented source/citation.
5. **Authorization failure:** optional and required source access denied,
   ambiguous 404/permission, unauthorized repository and unsafe URL all fail
   as appropriate; no credential fallback.
6. **Mutable source drift:** issue/comment or URL changes after prepared
   snapshot; same request cannot silently refresh, retry or mutate the packet.
7. **Version invariants:** duplicate request, authorized same-head repeat and
   changed-head operation preserve attempt rules; cross-version predecessor
   claims do not gain automatic equivalence.
8. **Packet tampering:** changed bytes, source roles, omission flags,
   component inventory, extraction, rendered prompt or order fail verification.
9. **Composite GitHub PR:** requested description/review/diff components are
   complete or rejected, never conflated with PR head alone.
10. **Historical compatibility:** every original v1/v2 canonical request, ID,
    publication receipt and result remains byte-for-byte interpretable.

The acceptance target is **reference completeness, immutable provenance and
truthful limits**, not any manufactured reviewer `GO`.

## 4. Review focus and design-decision gate

A reviewer independent of the author should attempt to falsify the following
claims against the existing contracts/code and #44 D1–D9:

- **F1 — Identity:** Logical selectors versus version pins versus supplied bytes
  yield unambiguous successor request/intent/packet identities, especially for
  inline/upload and mutable remote sources.
- **F2 — Recovery:** The pre-/post-`PREPARED` boundary prevents a new reference
  snapshot from replacing committed evidence or triggering a second invocation.
- **F3 — Scope:** A packet containing references cannot falsely satisfy or
  weaken exact PR change-scope validation.
- **F4 — Composition with #44:** Mission freedom and removal of mandatory
  semantic profiles do not erase effective technical policy provenance or
  retrofit historical `policy_id`/`program_id` semantics.
- **F5 — Applicability:** Separate, dated reference-currentness claims neither
  mutate a result nor overclaim applicability when no recheck occurs.
- **F6 — Acquisition authority:** Required/optional semantics cannot launder
  unauthorized reads or false external/origin claims.
- **F7 — Minimality:** No separate reference service, RAG, general ingestion
  ontology or new state-machine operation is required without evidence.

A material contradiction should be documented as a concrete counterexample
with the smallest relevant source lines. The reviewer may return NO_GO or
uncertainties. A favorable design review is **not** a product-owner decision
to accept a normative contract, publish on `dev`, implement, grant permissions,
start Codespaces or invoke Codex.

## 5. Explicit non-goals and pending disposition

- No changes to current accepted specs, schemas, executable source, tests,
  runtime policies, source App grants, workflows, or historical receipts.
- No admission of arbitrary worktrees or non-PR subjects under this design.
- No automatic browsing, RAG, link-following, document authority taxonomy,
  universal binary extraction or guaranteed semantic correctness.
- No new ReviewRequest creation, live model invocation, Codespace launch or
  claimed independent review until explicitly performed and recorded.
- No acceptance of a fixed v3 wire schema, exact threshold schedule or
  provider-independent transport before separate contract review.

`DESIGN_STATUS=PROPOSED_FOR_INDEPENDENT_REVIEW`

`NORMATIVE_STATUS=NON_NORMATIVE`

`SUCCESSOR_SCHEMA_ACCEPTED=NO`

`IMPLEMENTATION_AUTHORIZED=NO`

`LIVE_INFERENCE_AUTHORIZED=NO`
