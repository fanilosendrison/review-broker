---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Requester-Declared Reference Contract Proposal"
version: "0.1.2"
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

Two bounded independent Review Broker v2 reviews examined earlier heads of this
proposal. #53 at `3f721f00163263e1a31063d2cbb48e377eaa669f` returned
`COMPLETED / VALID / CURRENT / NO_GO` (F001–F008); #54 at
`e14af9c5764ce3d4d848b6449d2e0e8e44c90c42` returned
`COMPLETED / VALID / CURRENT / NO_GO` (F001–F005). Their results and
SHA-specific applicability remain immutable. Each v2 packet contained only
PR change material, not the governing Issues/contracts/code. This revision
addresses #54 but **has not itself received an independent review**. No
full cross-document qualification or normative acceptance is claimed.

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

### R1a — Request-wide atomicity guarantee

The successor request **requires one top-level `atomicity` JSON boolean**
covering the subject and all captured reference components:

| Value | Broker guarantee |
| --- | --- |
| `true` | The broker establishes a **coherent logical capture** covering the subject and every captured reference component. If a qualified common-cut/consistency mechanism cannot prove it, reject preparation **before `PREPARED`** and never arm the model. |
| `false` | Independently timed snapshots are allowed, but all source-local byte identity, authorization, integrity, scope, observation and completeness guarantees remain mandatory. No cross-material coherent-snapshot claim is made. |
| Missing or non-boolean | Invalid successor request; reject before admission. |

Pinned immutable versions are examined at their selected revisions. For mutable
components, separately valid hashes, timestamps, pagination or sequential
observations **do not prove** a common coherent cut. The first implementation
may reject nontrivial `atomicity=true` selections until a suitable mechanism
is qualified. This field does not manufacture snapshot atomicity.

The scope of `true` is the **actually captured material**: authorized
optional omissions must remain explicit and may not be represented as examined.
A required-source failure independently prevents `PREPARED`. The field is
a requester-selected **technical requirement**, not a review category or a
waiver of broker-owned security/runtime controls. It must not be inferred
from natural language. A mission that implicitly expects more than its
declared `atomicity=false` does not receive a hidden stronger guarantee;
a reviewer may notice the discrepancy, but semantic detection is not
guaranteed.

### R2 — Minimal requester declaration

The successor request has the **required** top-level `atomicity` boolean
from R1a and one optional, ordered `references` array. An absent or empty
array means **no requester-declared references**, not that the mission's
implicit evidence needs have been satisfied. The
packet/result must truthfully expose the **declared and actually available**
material boundary, including an empty declaration. Broker validation of that
boundary does not certify that the mission has all substantively necessary
evidence. Generic reviewer instructions require disclosure of **recognized**
missing evidence and remaining uncertainty; they cannot guarantee detection
of every implicit requirement in natural language. Content embedded in
`mission.objective`, `mission.instructions` or `mission.criteria` remains
requester-authored **instructions, context or claims**. It acquires no
independently verified source provenance, reference outcome or `Sxxx` anchor
merely by appearing in the mission. A reviewer may test such hypotheses,
but cannot cite them as independently corroborated reference evidence.
The broker does not attempt to semantically detect every embedded factual
claim; the consumer owns substantive evidence admission (#44 D1/D5).

Each declaration has exactly three common properties:

| Property | Meaning |
| --- | --- |
| `id` | Unique stable requester-chosen identifier **within this request** |
| `required` | Explicit boolean; required and optional are never inferred |
| `source` | A discriminated source designation or requester-supplied content |

No `review_type`, `document_class`, `authority_level`, mandatory evidence
ontology, or independent `acquisition_mode` field is introduced. Acquisition is
entailed by the source kind. The example below is **a fragment, not executable
wire-schema approval**. This example does not assert a coherent snapshot
across independently mutable GitHub sources:

```json
{
  "atomicity": false,
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

For supported **single-content remote** kinds, the optional
`source.expected_sha256` field is exactly 64 lowercase hexadecimal characters
and represents SHA-256 of the **original captured content bytes**. The first
qualifiable byte domains are:

| Source kind | Exact bytes hashed |
| --- | --- |
| `git_file` | Original Git blob bytes at the selected commit/path; its Git OID is independently validated |
| `github_issue_body` | Strict UTF-8 encoding of the decoded GitHub API `body` string for the selected Issue |
| `github_issue_comment` | Strict UTF-8 encoding of the decoded GitHub API `body` string for the identified comment |

Do not hash the surrounding GitHub API JSON, add a BOM, normalize Unicode or
line endings, render Markdown, or substitute a derived text representation.
A null/non-string `body` fails capture rather than becoming fabricated text.
The expectation is included in exact request identity and excluded from
Review Intent as a version pin. A mismatch fails admission/preparation
even if `required=false`.

`inline` already includes the exact text value in the canonical request; its
content bytes are its strict UTF-8 encoding. `upload` instead requires an
immutable authenticated receipt binding the original uploaded file bytes and
SHA-256, without assuming a local filename/path establishes provenance.
For composite PR and web URL/HTML/PDF references, define per-component or
response-byte hashing in the separately qualified support phase: there is
**no** accepted digest domain for a loosely designated whole PR or an
unspecified extraction. An unsupported source kind cannot become supported
by attaching a hash.

Without an expected content pin, a remote mutable source is **late-bound**:
the request selects its logical location, but its exact content is established
only by the packet snapshot durably committed during preparation. The
`request_id` alone does **not** identify the remote bytes that will be observed;
the bound `packet_id` does. A request cannot promise deterministic acquisition
across a crash **before** that commitment.

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
individually identified conversation comments, review submissions and/or inline
review comments. Each selected mutable component needs its own identity,
captured bytes, hash and observation metadata; the PR head identifies code,
**not** mutable description, review or comment bodies.

**Pagination completeness is not snapshot atomicity.** A changing GitHub PR
can yield a mixed-time set even when every returned page was fetched. For
the first PR-reference implementation, prefer explicit component identifiers.
An "all comments/reviews" selector is admissible only after a bounded
membership, pagination and concurrent-mutation consistency rule is qualified;
otherwise its required collection is unsupported. The broker may describe
distinct component observations with their separate observation times, but
must **not** claim one coherent point-in-time PR snapshot without evidence.
An explicit `atomicity=true` request fails before `PREPARED` if the
selected composite or cross-reference set lacks a qualified coherent capture.
With `atomicity=false`, observed mixed-time boundaries remain explicit.
No guarantee is claimed about detecting hidden natural-language atomicity
requirements. Linked Issues, third-party documents and recursive URLs are
never included implicitly.

The first **implementation candidate** supports UTF-8 inline text and
same-authorized-repository Git files, GitHub Issue bodies, and individual Issue
comments, with the existing GitHub PR **subject**. GitHub PR **references**,
file uploads, and external web resources remain product requirements but may
be qualified in subsequent stages. No raw binary source gains a line-addressed
citation contract merely by being named.

### R4 — Captured snapshots are technical observations, not origin proofs

A successfully `PREPARED` packet exists **only after all required references
have been captured and verified** and any explicit `atomicity=true`
requirement has been established. Every required reference is `captured`;
each optional reference is `captured` or a justified, qualified `omitted`.

Missing required material, inadmissible or unqualified kinds, failed digest
checks or unproved requested atomicity **fail before `PREPARED`**. They do
not produce a "PREPARED but unarmable" packet or a third source outcome.
If a durable `REQUESTED`/`ADMITTED` claim already exists, preserve the
truthful pre-model failure evidence without advancing to `PREPARED`;
recovery continues under the existing pre-model contract. A captured source records the requester
reference ID, its source designation and role, acquired bytes and SHA-256,
byte length, stable `Sxxx` source identifier(s) where applicable, snapshot
path, observation metadata, and technical source provenance actually verified.

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

- An authorized **required** source that is unavailable, too large, missing,
  unsupported, incompletely captured or digest-mismatched **fails before
  `PREPARED`**, not merely before arming a prepared packet.
- An **optional** source may be `omitted` only when its source kind and
  acquisition path are **implemented, qualified and authorized**, and a
  specifically permitted absence is reliably established. Omission is
  packet-bound, never cited and never counted as examined.
- An **unimplemented or unqualified** kind is invalid even when optional.
  Thus optional `web_url` or `upload` before its admitted stage fails
  admission/preparation; it is never a permitted `omitted` reference.
- Unauthorized access, ambiguous permission/nonexistence, unsafe locations,
  invalid version expectations, digest mismatches or unqualified selectors
  fail even when optional. `required=false` never bypasses integrity or
  access checks.
- References mentioned only in natural-language mission instructions do not
  become silently declared. The broker does not claim to detect all implicit
  substantive evidence requirements; the packet must disclose its actual
  source boundary rather than imply mission-level completeness.

No requester instruction can disable technical admission or citation
validation. Generic reviewer instructions require that **identified** missing
material and substantive uncertainty be reported. The reviewer, not the broker,
judges substantive adequacy; the consumer retains downstream admission.
Neither a structurally valid response nor an empty `references` array
establishes that the mission's implicit evidence needs were satisfied.

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
- Bind both bases, the explicit `atomicity` value and any evidence supporting
  `atomicity=true`, ordered reference declarations/outcomes, source bytes,
  derived representations, mission/program instructions and renderer identity
  into the same new `packet_id` computation. Verify a prompt by reconstructing
  it from bound inputs, never by trusting the prompt's own digest alone.
- A captured source may be **available** to the reviewer without the broker
  proving it was substantively **examined**. `sources_examined` and citations
  are reviewer reports subject only to supported structural/anchor checks.
- Treat all reference text and embedded links/instructions as untrusted data:
  no execution, no elevation to broker protocol or normative authority.
  Mission text remains explicitly labeled requester instructions/claims;
  embedded factual assertions do not become independently anchored sources.

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
   the required `atomicity` value, exact reference declarations, any version
   pins, inline bytes, immutable
   upload receipts identifying received bytes, operation and explicit
   re-review authorization nonce. Identical canonical bytes yield the same
   claim: delivery duplication or remote-source drift cannot authorize a
   second model invocation. Different inline/upload bytes have **different
   exact requests**, even if they occupy the same logical reference slot.
2. A **version-distinguished Review Intent** represents a continuing logical
   examination purpose; it hashes the logical PR subject, requester mission,
   requested reviewer settings, the declared `atomicity` requirement, and
   each reference's `id`, `required`, kind
   and **logical selector**. It deliberately excludes source-version pins,
   observed snapshots, Git file commit when repository/path remain the logical
   target, mutable body hashes, inline content and upload receipt bytes.
   For inline/upload the requester-chosen ID is the **logical slot**, not a
   proof of semantic equivalence between different supplied contents.
3. Reusing an inline/upload ID asserts **continuity of the question under
   changing input**, not sameness of evidence. Changed exact content requires
   a **new, explicitly authorized request**: use the successor's same-head
   repeat operation when the PR head is unchanged, not a second `initial`
   request under the same intent. A different reference logical target, ID,
   component selection, required flag, `atomicity` value, mission or reviewer
   setting creates a different Review Intent; merely observing a newer version of the same
   logical remote reference does not. Intent equality is never used as proof
   of identical material; packet identity carries the actual captured bytes.
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
| Same logical references, changed PR head | New explicitly authorized `changed_head` request |
| Same PR head, changed reference bytes (remote or supplied inline/upload) | New explicitly authorized `repeat_same_head` request with distinct nonce; no automatic refresh |
| Different logical reference selector or requiredness | New Review Intent; explicitly authorized `initial` under that new intent |
| Crash before a reference snapshot is durably committed | Safe pre-model recovery **may see different unpinned bytes** under the same unarmed request/claim; no earlier snapshot stability is asserted |
| Crash after a packet/snapshot identity is durably prepared | Resume must verify/reuse the **same exact bytes**; changed re-fetch cannot replace it |
| Interrupted/indeterminate model-capable attempt | Never silently retry or rearm the same request |

A source snapshot is committed when packet evidence is **durably linked to the
journal's prepared state**, not merely when transient files were fetched. Before
that point, an unpinned mutable source can change, including across pre-model
recovery, without changing the canonical request or claim. That is **not** an
immutable-snapshot guarantee; only the eventually committed packet identifies
the bytes that the reviewer is authorized to receive. A caller requiring an
exact prior version must supply a content expectation or an immutable selector.
If a prepared packet cannot be recovered or reproduced byte-identically, fail
closed; do not "refresh" under the old claim.

`PREPARED` is the snapshot-binding boundary, **not** the model invocation
uniqueness mechanism. The existing `docs/contracts/review-execution.md`
requires durable `ARMED` and `invocation_count = 1` **before** Codex
transport, with no automatic model retry after arming; the successor must
preserve that independent execution rule and the existing recovery contract.
No provider-level exactly-once inference is claimed.

This does **not** require acquisition before the journal claim for all sources:
the current `REQUESTED → ADMITTED → PREPARED` lifecycle can be preserved if
required-source completeness, source-kind qualification and requested
`atomicity=true` coherence are all established **before `PREPARED`**,
and recovery identity evidence is trustworthy. No new state machine is proposed.

### R9 — Distinct reference freshness, no historical result mutation

A `CURRENT` subject HEAD does **not** establish that independently mutable
references are current. The **initial successor scope** binds the exact
reference snapshots examined and identifies which sources are mutable; it
does **not** require a post-review reference freshness check or assert
`reference_currentness=CURRENT`. If no later check is performed, reference
freshness remains **not checked**, without adding an unapproved status field
to the current ReviewResult v1 contract. Directly supplied or immutable
snapshots need no external-currentness claim.

The reviewed snapshots remain historical evidence even if a source later
changes. An **optional, separately designed future** freshness observation
must be authenticated and bound to the exact historical request/packet
identity, component selector and captured digest, with an observation
timestamp, acquisition authority and explicit current/stale/unknown
semantics before any such claim can be qualified. No enum or wire
representation for this future observation is approved here. Any later check
must not alter an immutable ReviewResult or trigger another inference.

A result reader must not infer reference freshness from subject applicability
or silently refresh references. No external fetch is universally required on
`reviewctl result` retrieval.

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
9. **Composite GitHub PR:** exact named components are captured with distinct
   observation identities; pagination alone never establishes atomicity.
   A mutating "all comments" collection cannot pass as a coherent point-in-time
   snapshot without qualified membership/consistency evidence.
10. **Historical compatibility:** every original v1/v2 canonical request, ID,
    publication receipt and result remains byte-for-byte interpretable.
11. **Unpinned late binding:** a pre-`PREPARED` crash may observe new remote
    bytes, but a durably prepared packet cannot change, and `ARMED` remains
    an independent one-invocation boundary.
12. **Known missing evidence:** an empty declared reference set and authorized
    optional omission are visibly reported as source-coverage limits, never
    represented as proof of semantic mission completeness.
13. **Freshness not checked:** a subject-current result with mutable references
    makes no unsupported reference-currentness claim; no implicit network read
    or historical-result mutation occurs.
14. **Atomicity:** missing or malformed `atomicity` is rejected; unprovable
    `true` fails before `PREPARED`; `false` preserves source-local guarantees.
    Changing `atomicity` changes both successor request and intent identities.
15. **Unsupported optional kinds:** optional `web_url` or `upload` before its
    qualified stage is rejected, not silently `omitted`.
16. **Required failure:** a missing mandatory reference cannot produce a
    successfully `PREPARED` packet; pre-model journal records remain truthful.
17. **Digest scope:** hashes of Git blobs and strict UTF-8 API bodies are
    tested independently of JSON envelope or content normalization.
18. **Mission evidence:** unverified assertions embedded in requester instructions
    do not acquire broker-certified provenance or `Sxxx` source citations.

The acceptance target is **reference completeness, immutable provenance and
truthful limits**, not any manufactured reviewer `GO`.

## 4. Review focus and design-decision gate

A reviewer independent of the author should attempt to falsify the following
claims against the existing contracts/code and #44 D1–D9:

- **F1 — Identity:** Logical intent continuity versus byte-exact request and
  packet identity remains explicit even when inline/upload contents change
  under one reference ID or remote references are unpinned.
- **F2 — Recovery:** The pre-/post-`PREPARED` boundary binds immutable
  snapshots, while the **separate existing `ARMED` mechanism** enforces
  invocation uniqueness; neither substitutes for the other.
- **F3 — Scope:** A packet containing references cannot falsely satisfy or
  weaken exact PR change-scope validation.
- **F4 — Composition with #44:** Mission freedom and removal of mandatory
  semantic profiles do not erase effective technical policy provenance or
  retrofit historical `policy_id`/`program_id` semantics.
- **F5 — Applicability:** The first successor makes no unverified reference
  freshness claim; any later authenticated observation is separately
  versioned/bound and never alters historical results.
- **F6 — Acquisition authority:** Required/optional semantics cannot launder
  unauthorized reads or false external/origin claims.
- **F7 — Minimality:** A required top-level `atomicity` boolean does not
  add a semantic profile, generic ingestion service, RAG, ontology or new
  durable state-machine operation.
- **F8 — #54 response:** Inspect explicit atomicity (#54 F001), mission
  assertion authority (#54 F002), optional unqualified source types (#54 F003),
  required-reference failures before `PREPARED` (#54 F004), and concrete
  per-source digest domains (#54 F005).

A material contradiction should be documented as a concrete counterexample
with the smallest relevant source lines. The reviewer may return NO_GO or
uncertainties. A favorable design review is **not** a product-owner decision
to accept a normative contract, publish on `dev`, implement, grant permissions,
start Codespaces or invoke Codex.

**F008 evidence boundary:** Current ReviewRequest v2 packets contain only
PR change material; the historical #53 review did not include the governing
materials below and cannot independently validate external-authority claims.
Before product-owner contract-design acceptance, separately confront this
proposal with Issue #43 PI-REQ-03, Issues #44/#51, `docs/contracts/review-request-v2.md`,
`docs/contracts/review-execution.md`, `docs/contracts/review-evidence.md`,
`docs/contracts/review-result.md`, the closed v2 schema, `changes.py`,
`packets.py`, `identity.py`, `predecessor.py` and authenticated historical
#50/#53 evidence. Such corroboration must be labeled **separate from the
bounded reviewer packet**; source names or assertions alone are not proof.
No future source-access or implementation qualification is claimed by this
design document.

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
