---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Versioned Successor Review Contracts — Design Draft"
version: "0.1.0"
---

# Versioned Successor Review Contracts — Design Draft

**DRAFT ONLY — NON-NORMATIVE — NOT IMPLEMENTED — NOT ACCEPTED — MERGE BLOCKED**

## 0. Authority, dependency, and smallest useful release

This is a **draft successor contract design** for #51 PI-REQ-03, composed with
the accepted but non-normative #44 D1–D9 mission direction. It is derived
from the non-normative requester-reference proposal in **PR #52 at
`6118954dd29c330bc5e21c742934e2a39821eb42`**. That PR has passed
documentary product-owner adjudication but is **not merged**, and its current
head has **no independent review**. This draft may be discussed, but is
**not** authority to merge #52, change schemas, or enable inference.

The current accepted v1/v2 request/result/packet/identity/attempt evidence
remains immutable. The current implementation remains the authority for
what is actually operationally supported; the proposal must never be
mistaken for live functionality.

The initial candidate release is **PR subject + text-only references**:
inline, Git files at exact revisions, GitHub Issue bodies and individually
identified comments in the same authorized repository. Other product-required
reference kinds (GitHub PR components, requester-uploaded files, remote URLs,
HTML/PDF) are **deferred**; they are not silently accepted as optional omissions.
PR-independent subjects remain a separate PI-REQ-02 contract track.

The design deliberately does **not** create a general file-ingestion service,
RAG system, semantic document taxonomy, new durable attempt state machine or
automatic authority discovery.

### Proposed minimum version family

| Surface | Proposed candidate version | Why versioning is necessary |
| --- | --- | --- |
| ReviewRequest | `schema_version: 3` | v2 is closed; #44 removes mandatory semantic profiles; #51 introduces atomicity and reference declarations |
| Reviewer packet/manifest | `schema_version: 2` | packet v1 and `changes.validate_change_scope` have Git-specific sources and cannot add arbitrary context without changing historical semantics |
| ReviewResult | `schema_version: 2` | v1 requires the historically semantic `policy_id`, whose meaning cannot be silently repurposed for broker-owned execution controls |

These version numbers are **candidates**, not yet adopted schemas. One
coordinated successor is preferred over independently incompatible #44/#51
migrations. The first acceptance gate must verify whether a result-version
change can be made smaller without misrepresenting historical `policy_id`.

## 1. Proposed ReviewRequest v3 wire object

The complete candidate object has **exactly** these top-level properties:

| Field | Required | Proposed contract |
| --- | --- | --- |
| `schema_version` | Yes | Integer `3` |
| `subject` | Yes | Existing exact GitHub PR subject with `expected_head_commit` |
| `mission` | Yes | Existing v2 structure: `id`, `objective`, `instructions`, `criteria` only |
| `reviewer` | Yes | Existing v2 requested backend/model/effort shape until separately changed |
| `atomicity` | Yes | JSON boolean `true` / `false` only |
| `references` | No | Ordered array; absent and empty both mean no *declared* references, not substantive completeness |
| `review_operation` | Yes | Existing `initial`, `changed_head`, `repeat_same_head` discriminated union |

**No top-level `policy` field** is carried forward as a requester-selected
semantic category. Runtime tools, credentials, effective permissions and
technical policy remain broker-owned and are independently bound to packets
and published evidence. The requester cannot weaken them through `mission`
or `atomicity=false`.

All objects are closed to unknown properties in the eventual Draft 2020-12
schema. No implicit defaults, type coercion, hidden source discovery or
unrecognized `source.kind` values are permitted. Strings and integers use
JSON native types, never inferred from prose.

### Illustrative complete candidate request

The following is a **concrete v3 shape proposal**, not a currently valid
ReviewRequest or authorization to create one:

```json
{
  "schema_version": 3,
  "subject": {
    "kind": "github_pr",
    "repository": "fanilosendrison/review-broker",
    "pull_request": 52,
    "expected_head_commit": "6118954dd29c330bc5e21c742934e2a39821eb42"
  },
  "mission": {
    "id": "reference-contract-review",
    "objective": "Falsify the proposed contract against its declared references.",
    "instructions": "Report evidence gaps and cite only packet-bound sources.",
    "criteria": [
      "Are required reference contents actually available?",
      "Is exact PR change scope preserved?"
    ]
  },
  "reviewer": {
    "backend": "codex-cli",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "xhigh"
  },
  "atomicity": false,
  "references": [
    {
      "id": "requirement",
      "required": true,
      "source": {
        "kind": "github_issue_body",
        "repository": "fanilosendrison/review-broker",
        "issue": 43
      }
    },
    {
      "id": "contract",
      "required": true,
      "source": {
        "kind": "git_file",
        "repository": "fanilosendrison/review-broker",
        "path": "docs/contracts/review-request-v2.md",
        "commit": "ff83e486c6771c286f99a28e0813d151da3a2b91"
      }
    },
    {
      "id": "note",
      "required": false,
      "source": {
        "kind": "inline",
        "text": "Try to find a recoverable acquisition inconsistency."
      }
    }
  ],
  "review_operation": {
    "kind": "initial"
  }
}
```

This example is non-executable and illustrative; existing historical intent
may already have been reviewed, so an actual request would still have to
pass all predecessor, admission, ownership and one-shot gates.

### V3 field constraints (first candidate)

- `subject`: `kind=github_pr`, exact `owner/repository`, positive PR number,
  lowercase 40-character expected HEAD; no PR-free subject.
- `mission`: preserve v2's closed `id/objective/instructions/criteria` grammar,
  size limits and requester ownership. There is no `review_type` or hidden
  mission-template selector.
- `reviewer`: preserve v2's requested `codex-cli`, `gpt-5.6-sol`,
  `xhigh` contract for this first design, without claiming effective-model
  attestation not supplied by the runtime.
- `atomicity`: required true JSON boolean. No implicit `false` default.
  Changing its value changes both the complete request and Review Intent.
- `references`: ordered; order affects exact request and intent identity.
  Reject duplicate `id` values, unsupported kinds, malformed selectors and
  over-limit request/packet sizes. No separate `acquisition_mode` or
  semantic `document_class`.
- Each `references[]` entry has exactly `id`, `required` and `source`.
  `id` follows the established mission-ID lowercase-hyphen grammar,
  unique in the request. `required` is a mandatory JSON boolean.
  `source` is a closed discriminated source selector.

The first executable schema must derive finite request, per-source, total
packet and source-count limits from the already implemented constraints,
instead of silently assuming that arbitrary binary payloads fit in prompt
transport. Existing hard bounds include 2,000,000 original bytes per source,
8,000,000 rendered prompt bytes and at most 999 text-citation source IDs.

## 2. Initial admitted reference selectors

The first supported source discriminators and their complete candidate fields
are:

| Kind | Required selector fields | Optional selector fields |
| --- | --- | --- |
| `inline` | `kind`, `text` (string) | None |
| `git_file` | `kind`, `repository`, `path`, `commit` | `expected_sha256` |
| `github_issue_body` | `kind`, `repository`, `issue` (positive integer) | `expected_sha256` |
| `github_issue_comment` | `kind`, `repository`, `comment_id` (positive integer) | `expected_sha256` |

Only repositories already authorized for this requester and read scope are
admissible; the initial GitHub subset is the **same explicitly authorized
repository as the PR subject**. A GitHub numeric identifier must resolve to
the expected object and repository; the broker must not trust an ID in an
unauthenticated request to prove scope.

A pinned `git_file` must preserve exact blob bytes at the exact selected
commit, and independently verify its Git blob OID. Git file paths must pass
the existing safe bounded path grammar and forbid traversal, symlink
substitution or implicit branch-name resolution. The first selector commits
are full lowercase 40-character SHAs, matching the current Git boundary.

A GitHub body/comment source is an **observed mutable API value**, not a
stable version. The broker must record stable object ID, authenticated read
authority, observation time, actual returned `body` content and content hash.
A missing, null or non-string body cannot be silently converted to text.
No claim that GitHub supplies an immutable source-body version is permitted.

The exact byte domain of an optional `source.expected_sha256` is:

| Kind | SHA-256 input |
| --- | --- |
| `git_file` | Original Git blob bytes, not Git metadata or a text rendering |
| `github_issue_body` | Strict UTF-8 bytes encoding the decoded API `body` string |
| `github_issue_comment` | Strict UTF-8 bytes encoding the decoded API `body` string |

`expected_sha256` must be 64 lowercase hex characters. No silent NFC/NFD,
line-ending, BOM, Markdown or JSON-envelope transformation is allowed.
The optional expectation is an exact-version constraint, **not** a separate
logical reference selector. Its mismatch rejects preparation even for
`required=false`. If absent, remote mutable content is late-bound and
captured at actual preparation; its first stable byte identity is the
durably committed packet snapshot.

An inline text source is strict UTF-8 encoding of its request `text` field.
It has no independent source-provenance guarantee or `expected_sha256`
because its exact text is already part of the canonical request. An inline
fact in `mission.instructions` is instead **only requester-authored prose**,
not an independently acquired, technically corroborated reference; the
reviewer must not promote mission claims to verifiable source citations.

**Deferred kinds:** `github_pr` as reference, `upload` and `web_url` (including
HTML/PDF) are recorded in PI-REQ-03, but cannot be admitted by this first
candidate unless an explicitly accepted subsequent source contract, format,
version/capability binding and qualification supports them. Not-yet-qualified
optional kinds **fail admission**, rather than being reported as `omitted`.

## 3. Request-wide atomicity (exact semantic scope)

`atomicity=false` means the broker guarantees each source's exact original
bytes, selector, authorized provenance to the extent observable, and declared
capture/omission completeness **without claiming a coherent global cut**
across independently changing mutable sources. The reviewer receives
explicit individual observation bounds.

`atomicity=true` demands a **qualified source-backed coherent capture**
of the subject and *all captured references*. The broker must have a
supported way to prove the required common logical snapshot; timestamps,
sequential fetches and pagination completeness alone are insufficient. If
this cannot be established, the request **fails before `PREPARED`** with
no inference, including if the failure occurs after the journal claim.

Optional references that are legitimately omitted are **not counted as
captured** for the atomicity claim. An omitted optional reference remains
explicit; any missing required reference independently blocks preparation.

The agent owns the value; the broker validates it mechanically. No exhaustive
semantic analysis of mission instructions is claimed. `false` never waives
subject change-scope integrity, credential isolation, authorization, or
at-most-once execution. For the first implementation, conservative rejection
of nontrivial `true` combinations is allowed until a mechanism is qualified.

## 4. Admission, requiredness and source material

Before any packet can be successfully recorded as `PREPARED`:

1. Authenticate and authorize the requester and the exact PR subject.
2. Validate the closed source selector grammar, supported/qualified source kind,
   allowed repository, credential scope and requested byte limits.
3. Capture each required source, verify its expected hash when present, and
   verify all mandatory scope and identity properties.
4. Capture optional sources, or record `omitted` **only** for a specifically
   proven and permitted absence on an authorized, qualified acquisition path.
5. Establish `atomicity=true` coherent-capture evidence if requested.
6. Construct and verify the role-separated immutable packet, then durably
   bind its identity to the journal's `PREPARED` transition.

A successfully `PREPARED` packet has `captured` for every required reference.
Every optional reference has `captured` or a permitted `omitted` outcome
with a precise non-sensitive reason. Hard failure of a required source,
unqualified kind, authorization, ambiguous 404, unsafe destination or an
explicit expected hash **cannot** be converted into optional omission.
A failed request can retain `REQUESTED`/`ADMITTED` journal evidence; it
does **not** create a semantically "prepared but unarmable" packet.

A reference's declared normative authority remains a requester/source claim.
Receiving the exact bytes or verifying a citation proves technical integrity,
not the truth of the contents. Missing evidence that the reviewer **recognizes**
must be reported; no broker promise of discovering every implicit source in
natural-language mission text is made.

## 5. Canonical identities and predecessor rules

For proposed v3, use the established RFC 8785 canonical JSON bytes and
domain-prefixed SHA-256 identities, **but never reuse historical canonical
bases under new meanings**.

### Exact request identity

`request_id = "request:sha256:" + SHA256(RFC8785(complete_v3_request))`.

The complete request includes `schema_version=3`, every declaration and
its order, `atomicity`, inline content, remote expectations, subject HEAD
and `review_operation`. Duplicate canonical bytes share one request ID and
one claim/attempt, regardless of newly changing remote content.

### Logical Review Intent identity

Define an exact **version-distinguished** intent basis:

```json
{
  "intent_schema_version": 3,
  "subject": {
    "kind": "github_pr",
    "repository": "fanilosendrison/review-broker",
    "pull_request": 52
  },
  "mission": {
    "id": "reference-contract-review",
    "objective": "Falsify the proposed contract against its declared references.",
    "instructions": "Report evidence gaps and cite only packet-bound sources.",
    "criteria": [
      "Are required reference contents actually available?",
      "Is exact PR change scope preserved?"
    ]
  },
  "reviewer": {
    "backend": "codex-cli",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "xhigh"
  },
  "atomicity": false,
  "references": [
    {
      "id": "requirement",
      "required": true,
      "source": {
        "kind": "github_issue_body",
        "repository": "fanilosendrison/review-broker",
        "issue": 43
      }
    },
    {
      "id": "contract",
      "required": true,
      "source": {
        "kind": "git_file",
        "repository": "fanilosendrison/review-broker",
        "path": "docs/contracts/review-request-v2.md"
      }
    },
    {
      "id": "note",
      "required": false,
      "source": {
        "kind": "inline"
      }
    }
  ]
}
```

The corresponding `review_intent_id` is the existing
`review-intent:sha256:` domain plus SHA-256 of this **explicitly versioned**
intent basis. In this basis:

- Drop only `subject.expected_head_commit` from the logical subject.
- Drop `git_file.commit` and any `expected_sha256` as exact version pins.
- For `inline`, retain `kind` and reference `id`, **exclude `text`** as
  changing content in a stable logical slot.
- Keep each reference's order, `id`, `required`, kind and exact **logical
  source selector** (repository/path or GitHub object ID).
- Keep the exact complete mission, requested reviewer and `atomicity`.

Consequently, two inline values with the same logical reference slot can
share an intent but **never** an exact request or packet identity. Changing
`atomicity`, requiredness, mission, reviewer or logical selector changes
intent. Intent equality is not evidence equivalence.

A successor `initial` requires no earlier distinct request with the same
versioned intent; `changed_head` requires same intent and changed exact
subject HEAD; `repeat_same_head` requires same intent, unchanged HEAD and a
fresh 128-bit nonce. Each operation requires explicit authorized admission;
the same request never starts a second model invocation. Reject unsupported
cross-version predecessor equivalence rather than assuming it.

## 6. Versioned packet/manifest boundary

The successor packet needs the existing GitHub PR change coverage and an
**independent reference source collection**, without allowing reference
objects to satisfy subject image coverage. Do **not** relax
`changes.validate_change_scope`'s exact PR change-image invariant.

The candidate packet-v2 identity basis must bind at least:

- Version discriminator, exact request/subject/intent identities.
- Ordered subject before/after image source entries, exact diff hash,
  merge base and subject HEAD; no fabricated reference images in change scope.
- Ordered reference declarations and `captured/omitted` outcomes; actual
  reference source entries with original byte hashes, byte length, immutable
  snapshots, observation metadata, source kind and verified provenance.
- Declared `atomicity` and any **qualified** coherent-capture evidence when
  true, with explicit omitted material outside that guarantee.
- Broker-owned effective technical permission policy name/version/digest,
  reviewer program identity, renderer/version and original-vs-derived source
  transformations.
- Exact source citation mappings (`S001` etc.) where text/physical lines
  can actually be reconstructed.

`packet_id` hashes the canonical **versioned packet basis**, not the
manifest including `packet_id` itself. The persisted manifest additionally
records the packet ID and rendered prompt hash. Verification must re-read
the exact original snapshot bytes, validate roles and all recorded bounds,
rebuild renderable sources/prompt and compare identities; a prompt-hash-only
check is insufficient. The packet's own prompt must not create a circular
hash definition.

The current immutable packet-v1 representation and historical packet
receipts remain unchanged. Source and packet file/line citations retain
their supported mechanical meaning, not substantive-truth authority.
Unsupported binary/PDF anchors have no invented source-line semantics.

## 7. Durable lifecycle and material drift

The existing lifecycle is retained:
`REQUESTED → ADMITTED → PREPARED → ARMED → TERMINAL_CAPTURED →
VALIDATED → REPORTED → STOPPED` (plus valid indeterminate paths).

A remote mutable source with no content pin may change **before** its
snapshot is durably bound to `PREPARED`; the request's identity does not
claim otherwise. After `PREPARED`, recovery must reproduce the **same exact
packet bytes** or fail closed. Re-fetching different material cannot
replace a journal-bound prepared snapshot.

`ARMED` and `invocation_count=1` must be recorded durably **before**
Codex transport under the existing execution contract. `PREPARED` is the
packet-binding boundary, not a substitute for this invocation boundary.
No automatic model retry after arming; no provider-level exactly-once
inference guarantee is invented. Never create a new logical request
solely because a source or PR HEAD has drifted; explicit re-review
authorization is required.

## 8. Result publication and applicability

ReviewResult v1 cannot silently receive a new meaning for `policy_id` when
#44 removes requester semantic profile selection. The proposed successor
result therefore requires **separately versioned technical-policy
provenance**. A minimal result-v2 candidate preserves existing
independent `execution_status`, `evidence_status`, `review_verdict` and
PR-HEAD `applicability`, packet/request/attempt identities and verified
source/line findings. It must reference the **broker-owned effective
technical policy identity** without calling it the historical semantic
`policy_id`. The exact result-v2 JSON shape and backward-compatible
retrieval rules remain an explicit normative-contract gate.

The result's `packet_id` binds captured and omitted references via
the verified packet manifest. `sources_examined` is still a reviewer
statement, not a broker proof that every source was intellectually
examined. The consumer must be able to inspect the bounded reference
coverage via the existing receipt/artifact mechanism, or obtain an
explicit unavailable/expired status; do not promise permanent source
availability after Actions artifact retention expiry.

`applicability=CURRENT` continues to refer to the reviewed subject HEAD
only. It does **not** establish that remotely mutable references remain
current. The first successor makes **no post-review reference freshness
claim**. A future authenticated, packet-linked reference-freshness
observation is separate, requires its own accepted contract and must never
rewrite historical ReviewResult bytes or launch inference.

Result publication, claim receipt, authenticated actor binding,
indeterminate conditions and verified retrieval retain their
non-waivable broker-controlled semantics. Reviewer verdict never
authorizes code merge or product-owner contract acceptance.

## 9. Auth/transport and first qualification

The existing private source App is limited to Contents, Pull requests and
Metadata read on its specifically authorized repository. Reading private
Issue bodies/comments requires separately authorized **Issues: read**,
new owner configuration, non-inference source-acquisition qualification
and a verified absence of source credentials in the model runtime.
Requester's GitHub Issue/token, publication and Codespace-control
credentials cannot substitute for source read authority.

The first candidate must qualify **without model invocation**:

1. Closed v3 request validation including required atomicity, unknown kinds,
   duplicate IDs, contradictory types and invalid expectation digests.
2. Exact request/intent/packet identity collisions, changes of order,
   source selectors, byte content and version pins; v1/v2 fixtures unchanged.
3. Required-source failure before `PREPARED`; optional permitted omission
   only under an approved proven-absence condition, never on ambiguous 404.
4. True atomicity rejection for unsupported mutable combinations; false
   atomicity preserving exact independently timed source observations.
5. Missing, oversized, modified, unauthorized, unqualified optional source,
   GitHub object outside authorized repository, and tampered snapshot cases.
6. Subject change images/diff cannot be satisfied by references; packet
   reconstruction fails on role/source/hash/omission/prompt changes.
7. Pre-`PREPARED` mutable reacquisition is openly late-bound, post-`PREPARED`
   replacement fails, and post-`ARMED` inference is not repeated.
8. Reviewer assertions in mission text do not become verified `Sxxx` source
   citations; citation validation rejects unsupported/missing anchors.
9. The historical #50 F003 motivating case is a **controlled fixture**
   using authentic historical snapshots if available, otherwise explicitly
   labeled synthetic—not today's mutable #43/#44 pretending to be past.
10. Historical v1/v2 request/attempt/packet/result/publishing evidence
    remains interpretable without recomputing or reinterpreting old identities.

Only after the versioned contract, source permission model, and exact offline
tests are accepted may any implementation or live operation be separately
authorized. Do not reopen generalized exhaustive Codex-internal attestation
from the abandoned high-assurance track as a default prerequisite.

## 10. Outstanding exact-contract decisions

The following are **not silently resolved** by publishing this draft:

- Final closed Draft 2020-12 executable schemas and precise size/selection
  thresholds for the first supported reference kinds.
- Justified placement and deterministic derivation of effective technical
  `policy/program` provenance in packet/result; no reinterpretation of
  historical `policy_id` or `program_id`.
- Exact result-v2 field names, verified packet-manifest retrieval and
  historical evidence availability/retention behavior.
- Qualifiable `atomicity=true` coherent snapshot mechanisms for a given
  source combination; unsupported cases must reject.
- Exact permission administration and authenticated GitHub Issue/comment
  acquisition; no unauthorized App permission expansion.
- GitHub PR reference component collections, upload receipts, remote URL
  redirects and HTML/PDF extraction (later stages with separately accepted
  byte-domain rules).
- Pre-existing status drift: the governing v1 specification still asserts
  v1 is the only implemented request while the accepted v2 contract,
  executable code and real v2 review results establish bounded v2
  implementation. Reconcile separately before normative successor adoption.

**These are versioned-contract acceptance gates, not permission to create a
general ingestion platform.** The accepted non-normative direction in #51
is not itself a substitute for these technical decisions.

## 11. Publication, review and authorization gate

This document is intentionally a **draft PR dependent on PR #52**:

- Do not merge this draft until PR #52's outstanding independent/publication
  gate is explicitly disposed and accepted as a non-normative design baseline.
- Review this exact candidate against #43 PI-REQ-03, #44 D1–D9, #51's
  disposition, accepted v1/v2 contracts, packet/result schemas, implementation
  and exact-SHA historical evidence; do not rely on an older v2 packet as
  full cross-document verification.
- Independent reviewers should seek counterexamples to identity bases,
  mutable-source recovery, atomicity scope, permission boundaries, mission
  evidence authority, result provenance, required/optional admission and
  minimum possible representation.
- A favorable review is **not** automatic adoption as normative contract,
  approval to change executable schemas, expansion of GitHub permissions,
  launch of a Codespace or inference, or downstream merge authorization.
- No implementation sub-issues or consumer-repository modifications are
  authorized by this draft.

`DOCUMENT_STATUS=UNACCEPTED_NON_NORMATIVE_VERSIONED_CONTRACT_DRAFT`
`REVIEW_REQUEST_V3_IMPLEMENTED=NO`
`PACKET_V2_IMPLEMENTED=NO`
`REVIEW_RESULT_V2_IMPLEMENTED=NO`
`PARENT_DESIGN_PR52_MERGED=NO`
`NORMS_AND_SCHEMAS_UNCHANGED=YES`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
