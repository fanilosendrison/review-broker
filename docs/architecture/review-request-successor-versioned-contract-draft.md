---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Versioned Successor Review Contracts — Design Draft"
version: "0.1.6"
---

# Versioned Successor Review Contracts — Design Draft

**DRAFT ONLY — NON-NORMATIVE — NOT IMPLEMENTED — NOT ACCEPTED — MERGE BLOCKED**

## 0. Authority, dependency, and smallest useful release

This is a **draft successor contract design** for #51 PI-REQ-03, composed with
the accepted but non-normative #44 D1–D9 mission direction. It is derived
from the **published non-normative** requester-reference proposal in
**PR #52 at `6118954dd29c330bc5e21c742934e2a39821eb42`**, merged
into `dev` as commit `f9e902ee577d3a22330c3bf2fb04dcae28ed3034`
after the owner explicitly accepted the **design direction with bounds**.
The exact-head independent [ReviewRequest #56](https://github.com/fanilosendrison/review-broker/issues/56#issuecomment-6511613848)
remains `COMPLETED / VALID / CURRENT / NO_GO` with seven findings and five
uncertainties; earlier #53/#54 `NO_GO` results remain immutable. Product-owner
publication **does not** promote a model verdict to `GO` or establish
normative/executable successor guarantees. This draft is not authority to
change schemas or enable inference.

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
| `subject` | Yes | Exact GitHub PR subject with requested `repository`, stable numeric `repository_id`, `pull_request` and `expected_head_commit` |
| `mission` | Yes | Existing v2 structure: `id`, `objective`, `instructions`, `criteria` only |
| `reviewer` | Yes | Existing v2 requested backend/model/effort shape until separately changed |
| `atomicity` | Yes | JSON boolean `true` / `false` only |
| `references` | **Yes** | Explicit ordered array, possibly `[]`; missing/null is invalid, not a synonym for empty |
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
    "repository_id": 1433701208,
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

- `subject`: `kind=github_pr`, exact requested `owner/repository`,
  **required positive integer `repository_id`**, positive PR number and
  lowercase 40-character expected HEAD. The numeric ID identifies the
  intended repository; the name is a mutable requested selector.
  No PR-independent subject is introduced.
- `mission`: preserve v2's closed `id/objective/instructions/criteria` grammar,
  size limits and requester ownership. There is no `review_type` or hidden
  mission-template selector.
- `reviewer`: preserve v2's requested `codex-cli`, `gpt-5.6-sol`,
  `xhigh` contract for this first design, without claiming effective-model
  attestation not supplied by the runtime.
- `atomicity`: required true JSON boolean. No implicit `false` default.
  Changing its value changes both the complete request and Review Intent.
- `references`: **required, ordered and possibly `[]`**; order affects
  exact request and intent identity. Missing/null `references` is invalid;
  do not normalize absent into empty. Reject duplicate `id`, unknown
  kinds, malformed selectors and resource-limit violations. No new
  `acquisition_mode` or semantic `document_class`.
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

Only authorized sources in the **same immutable numeric GitHub repository
ID as `subject.repository_id`** are in scope. Reference
`source.repository` strings must match the requested canonical name,
but name equality never replaces repository-identity verification.

**First-claim identity gate (candidate):** authenticated GitHub metadata
must match both exact `full_name` and requested numeric `id` before
creating a claim. Renames, transfers, redirected aliases, reused names,
and identity mismatches fail closed; do not silently retarget. Resolve
the PR object/HEAD and the object IDs/parent Issue membership for
existing Issue/comment references under this same repo **before claim**,
and bind the verified IDs, requester and read-authority scope to the
durable resolved admission. A provably absent optional source gets a
verified absence record, not a fabricated object identity. Ambiguous
permission-vs-absence is a refusal, not an optional omission.

**Recovery identity gate:** reverify the exact canonical requested name,
numeric repository ID, PR ID and admitted reference object IDs before
reacquisition. A changed object identity is a hard target mismatch;
only unpinned `body` bytes from the **same immutable object** may drift
before `PREPARED`. Persist verified IDs and source principal/installation
scope in packet provenance, without exposing credential material.
This is a proposed v3 rule, not an existing operational capability.

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

## 3. Request-wide atomicity: Git revision consistency

`atomicity=false` keeps per-source exact bytes, authorization, provenance,
PR change scope and truthful omission guarantees, **without** promising
a coherent common instant across independently mutable sources.

`atomicity=true` requires a **verifiable common immutable Git revision
basis** covering the PR change basis and every captured reference.
The first **proposed, not implemented** acceptance matrix is:

| Material covered | Candidate `atomicity=true` behavior |
| --- | --- |
| Exact GitHub PR at expected HEAD H with `references: []` | Eligible after offline qualification |
| PR + bounded `inline` UTF-8 references | Eligible: inline bytes are immutable by canonical request |
| PR + inline and `git_file` references at **H in the exact same authenticated `repository_id`** | Eligible: all reference blobs are verified in the same immutable HEAD tree |
| Git file at another commit H2 != H (even if its bytes match) | Reject in the first atomicity profile |
| GitHub Issue/comment bodies or mutable PR conversations/reviews | Reject under `true`: no qualified common Git version basis |
| Unqualified `upload`, `web_url`, HTML/PDF or composite kinds | Reject these source kinds under either boolean |

**Consistency definition:** Let H be `subject.expected_head_commit`
and B the PR's verified merge-base. The subject's postimages and all
`atomicity=true` eligible Git reference files must come from **the
same tree of H** and the same authenticated immutable repository ID.
The subject's B-preimages and exact B→H diff are inherent comparison
material; they are not external references required to reside in H.
Inline bytes are fixed by the canonical request and do not provide
external historical-time evidence or semantic truth.

**Proof bound to the packet:** authenticated repository ID, H/B
commit/tree/blob identities, exact Git source bytes/digests, pre-/post-
image and diff coverage, inline request bytes, source roles, verified
renderer/prompt identity and declared `atomicity` value. Resolve H
exactly at admission and reject changed or unverifiable identity
during qualified preparation. Separate API timestamps, hashes and
pagination do **not** establish an atomic multi-object GitHub snapshot.

**Counterexamples:** source at H2, different repository ID, substituted
blob, changed inline text in the prompt, absent PR preimage or incorrect
B→H diff, mutable Issue/comment body, and changed PR HEAD mid-prepare.
Every case must fail `atomicity=true` before `PREPARED`.
Permitted optional omissions stay visible and outside the claim;
all required sources still must be captured.

This is **Git-version coherence**, not general real-time simultaneity
across services. The bool remains requester-owned but cannot waive
technical broker controls. The matrix is a **qualification target**,
not a live supported capability.

## 4. Admission, requiredness and source material

Before first **claim** creation, validate the complete closed request,
authenticate the requester, compare the stable numeric repository ID and
canonical name, resolve the PR object and expected HEAD, verify any
existing reference-object IDs and their authorized repository membership,
and reject determinate invalid/unqualified/unauthorized sources.

Before any packet can be successfully recorded as `PREPARED`:

1. Revalidate the authenticated admission, immutable GitHub targets and exact
   PR HEAD, not a repository name alone.
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

The complete request includes `schema_version=3`, both the requested
repository name and its stable `subject.repository_id`, **required
`references` (including `[]`)**, order, `atomicity`, inline values,
remote expectations, subject HEAD and `review_operation`. Missing
`references` is invalid rather than canonically equivalent to `[]`.
Duplicate canonical bytes still share exactly one request/claim/attempt.

### Logical Review Intent identity

Define an exact **version-distinguished** intent basis:

```json
{
  "intent_schema_version": 3,
  "subject": {
    "kind": "github_pr",
    "repository": "fanilosendrison/review-broker",
    "repository_id": 1433701208,
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

- Drop only `subject.expected_head_commit`; retain the canonical requested
  name and `subject.repository_id` to bind logical target continuity.
- Retain the **mandatory ordered `references` array**, even when `[]`.
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

- Version discriminator, exact request/subject/intent identities,
  including authenticated stable repository/PR object IDs.
- Ordered subject before/after image source entries, exact diff hash,
  merge base and subject HEAD; no fabricated reference images in change scope.
- Ordered reference declarations and `captured/omitted` outcomes; actual
  reference source entries with exact bytes/hashes, observation metadata,
  immutable snapshots, authenticated repository/reference object IDs,
  verified source principal/installation scope and technical provenance.
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

## 7. Durable lifecycle and bounded pre-model failure protocol

The exact proposed journal wire, failure receipts, dispatch transaction
and crash/competing-worker cases are specified in the
**[pre-model preparation protocol annex](pre-model-preparation-failure-protocol-draft.md)**.
This non-normative v3 design is not implemented. [Draft test PR #57](https://github.com/fanilosendrison/review-broker/pull/57)
at `4ef45da3e0de2fe852d2a4a88df0644acbc67d46`
([CI PASS, 501 tests](https://github.com/fanilosendrison/review-broker/actions/runs/41042188166))
has directly reproduced **three current-code gaps**: repeated
`ADMITTED` dispatch, absence of a specialized receipt-backed
`REQUESTED/ADMITTED → STOPPED` transition, and a current
journal parser that would silently discard a future
`pre_model_control` object by reserializing it as v1.

**Keep the existing AttemptState family.** A v3-only versioned
preparation-control subrecord lives in the same Git-ref journal claim,
never in a separate cross-ref ledger. It binds current reservation
generation/worker, durable failure classification and evidence IDs.
**Mandatory before any v3 enablement:** strict journal v1/v2
wire-version decoding; current `AttemptRecord.from_dict` ignores
`schema_version` and silently drops unrecognized `pre_model_control`
fields on round-trip. Older deployed workers must not touch v3
claims. Historical v1/v2 journal serialization and semantics are
preserved, not rewritten.

**Initial automatic dispatch limit is exactly one.** The v3
controller CAS-reserves generation 1 before external GitHub workflow
dispatch. The `issues:opened` event and reconciler are **discovery
paths to the same controller**, never independent v3 model-capable
workers. A worker CAS-binds its exact run ID, and generation,
reservation, worker and disposition must be checked **within the
same claim CAS that commits `PREPARED` and `ARMED`**.
A separate read/recheck is insufficient against intervening
recovery/refusal commits. Lost dispatch acknowledgement is
**ambiguous**, not permission to dispatch again. No unbounded
hourly reconciler redispatch.

**Failure classification is bounded:** verified permanent
source/identity/digest/unsupported-atomicity violations cause a
durable `REFUSED_PERMANENT` CAS disposition before cleanup.
A proven transient error or indeterminate observation leads to
`BLOCKED` with a typed `TRANSIENT` or `UNKNOWN` receipt. An
ambiguous 404 or failed GitHub dispatch response is not silently
called a permitted omission. A new generation on the same unarmed
attempt requires **one fresh authenticated recovery authorization
per dispatch**, a previous-run/quiescence check and exact
stable-source-identity revalidation. A new generation is forbidden
from `PREPARED` or any later state; an ambiguously delivered old
worker remains fenced even after a manual retry. There are zero
automatic redeliveries after the initial reservation: **no timeout
heuristic** is needed to enforce this bound.

**Terminal permanent refusal:** once the refusal CAS suppresses
every future preparation/armament path, **prove that the shared
Codespace is not currently owned by another active request**
before issuing any stop command. The existing shared GitHub Actions
concurrency group is a candidate source of exclusivity, not by
itself a durable cross-request ownership certificate. If ownership
is unproven, block cleanup rather than stop another attempt.
Then validate independently observed `Shutdown` for that owner.
A narrowly specialized v3-only receipt-validation operation may
transition `REQUESTED → STOPPED` or `ADMITTED → STOPPED`
when it proves the same request/attempt, permanent failure,
zero invocations, no `ARMED` history and actual Shutdown.
Never accept generic STOPPED or create a fake ReviewResult.
An unverified shutdown leaves the refusal durably blocked;
reconciler performs cleanup only. A competing or stale worker
cannot arm after its reservation is no longer current.

**Keep packet and inference boundaries separate.** Before durable
`PREPARED`, a permitted mutable source may be reacquired only
under the same verified repository/object identity. After
`PREPARED`, reconstruct exact recorded packet bytes or fail.
The original durable `ARMED` and `invocation_count=1` guards
remain before any model-capable transport; provider exactly-
once is not claimed. No new general attempt state or service
is justified by this proposal.

The revised annex lists **PM01–PM25 future executable fault
injections**, including journal-version downgrades, cross-request
Codespace conflicts, duplicate entry points and atomic worker
fencing. **None** is asserted to have passed on v3. PR #57's
**16 tests against real current modules** (14 ordinary PASS and two
expected future-contract failures; full CI 501 tests) cover v1/v2
code, not these v3 changes.

**Follow-up minimal-journal and external-authority experiments:**
[test-only PR #58](https://github.com/fanilosendrison/review-broker/pull/58)
has now qualified **offline** a smaller journal-v2 candidate that
retains exactly the serialized v1 AttemptRecord fields/history plus
versioned `pre_model_control`, with no duplicated top-level
`packet_evidence_id`. Its 12 migration tests call the actual
v1 serializer/decoder/transition logic; 15 further tests check
**injected** GitHub dispatch/run metadata and demonstrate that
Codespace name/state and Actions concurrency do **not** establish
an exclusive cross-request owner. CI for that isolated branch
reports 546 PASS, but real v3 GitHub-ref CAS, effective principal
authority, owner lease and safe rollout remain **unqualified**.
The [protocol annex](pre-model-preparation-failure-protocol-draft.md)
records the precise GitHub Actions 200/204 dispatch distinction and
why a lost response never permits automatic redelivery.

## 8. Result publication and applicability

ReviewResult v1 cannot silently acquire a new meaning for its historical
requester-semantic `policy_id` when #44 removes mandatory semantic profiles.
The proposed successor therefore needs **versioned technical permission
profile identity**, distinct from a claim of effectively attested Codex
enforcement. Its smallest candidate representation is specified in the
[separate minimal result-v2 proposal](review-result-v2-technical-policy-proposal.md):
replace v1 `policy_id` with `technical_policy_id`, require
`reference_coverage` and exact `resolved_request`, preserve independent
execution/evidence/verdict/applicability and historical v1 result bytes.

The `technical_policy_id` candidate hashes precisely the canonical
verified installed **permission-profile name and original profile-byte
SHA-256**, with an identity-version discriminator. It is checked against
packet/attempt/preflight evidence; it is **not** a proof of the provider's
effective policy enforcement. The result's `reference_coverage` records
each declared reference exactly once as packet-bound `captured` with
`Sxxx` source ID, or permitted optional `omitted` with
`AUTHORIZED_ABSENT`. Captured does **not** mean examined, and
subject-role `Sxxx` sources remain separately examinable.
The exact accepted JSON schema, publisher receipt and retrieval behavior
remain a normative and offline-qualification gate.

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

A producer-authored [offline falsification experiment](review-request-successor-offline-qualification.md)
has exercised **55 synthetic cases (55 PASS)**, including real local Git
B/H/H2 objects, mocked admission/journal recovery and an illustrative
closed result-v2 subset. The experimental runner and JSON report were
generated separately from this repository. This is **not a qualification
of the unimplemented successor, real GitHub permissions, full RFC 8785,
production crash/replay semantics, or an independent model review**.

The first executable candidate must still independently qualify
**without model invocation**, including the annex's **PM01–PM25**
dispatch, refusal, CAS race, journal-version and shared-Codespace
ownership scenarios. Those proposed test cases have not been
executed on any v3 implementation:

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
11. Missing `references` is invalid while explicit `references: []`
    has one exact canonical request/intent identity; changing array order
    or any ID changes the corresponding canonical basis.
12. Wrong `subject.repository_id`, transferred/renamed/reused repository
    name, wrong PR/Issue/comment stable object ID, or insufficient source-App
    installation scope fails claim/recovery.
13. `atomicity=true` PR B/H + frozen inline + same-H/same-repository Git
    references passes only with full Git object/diff identity proof; H2,
    another repository, changed inline source, missing preimage or mutable
    Issue/comment source fails before `PREPARED`.
14. A permanent post-claim source refusal binds typed reason and genuine
    Shutdown observation before specialized terminal `STOPPED`; no
    `PREPARED`, `ARMED` or inference occurs.
15. A transient source failure keeps the same claim blocked for explicit
    recovery; repeated reconciler passes cannot loop automatically. Inject
    crashes between claim, blocked-disposition commit, prepared snapshot
    commitment, and shutdown receipt.

Only after the versioned contract, source permission model, and exact offline
tests are accepted may any implementation or live operation be separately
authorized. Do not reopen generalized exhaustive Codex-internal attestation
from the abandoned high-assurance track as a default prerequisite.

## 10. Outstanding exact-contract decisions

The following are **not silently resolved** by publishing this draft:

- Final closed Draft 2020-12 executable schemas and precise size/selection
  thresholds for the first supported reference kinds. Proposed `references`
  cardinality begins at zero, with an explicit mandatory field.
- Stable repository and reference-object identity fixtures must include
  both pre-claim target resolution and crash/recovery revalidation, not
  just post-acquisition byte hashing.
- Qualify the **proposed** installed technical permission-profile
  identity and new result-v2 `technical_policy_id` against the actual
  packet/attempt/preflight evidence. It does not mean effective-policy
  attestation, and no historical `policy_id` or `program_id` changes.
- Independently test the companion **minimal result-v2 wire proposal**,
  `reference_coverage`, verified packet-manifest retrieval and
  historical evidence availability/retention behavior; its field choices
  are not yet normative or implemented.
- Offline qualification of the newly proposed **Git-HEAD consistency
  profile** for `atomicity=true`: exact PR B/H + frozen inline + same-H
  Git references in the same immutable repository ID. Unsupported
  heterogeneous mutable GitHub sources still reject.
- Qualification of the required `references: []` schema, stable numeric
  `subject.repository_id` and authenticated reference-object binding.
- Qualify the [pre-model protocol annex](pre-model-preparation-failure-protocol-draft.md):
  **strict versioned journal parser/serializer** (the minimal v1-compatible candidate passed offline shape tests, but older deployed
  workers must not downgrade a new claim), one automatic dispatch
  via a unified discovery/controller entry point, **atomic**
  current-generation/worker fencing at `PREPARED` and `ARMED`,
  shared Codespace ownership before stopping, failure receipts,
  specialized `STOPPED`, manual recovery authorization and
  **PM01–PM25** fault-injection matrix. These v3 paths remain
  **unimplemented**.
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

## 10a. Focused falsification gates inherited from ReviewRequest #56

[ReviewRequest #56](https://github.com/fanilosendrison/review-broker/issues/56#issuecomment-6511613848)
independently reviewed the **parent** design proposal, not this versioned draft.
Its seven findings are **not automatically resolved** by this PR. Before
normative adoption, explicitly resolve the following contract questions and
bind each answer to an executable counterexample fixture:

1. **Pre-commit drift vs authorized re-review (#56 F001).** Distinguish a
   pre-`PREPARED` reacquisition under the *same* unarmed claim, where no
   snapshot has been committed, from a new `repeat_same_head` review of
   updated remote material. A committed `PREPARED` snapshot must never be
   refreshed under the same claim. Document the persisted evidence that
   makes the boundary observable on crash/recovery, including a failed
   or incomplete pre-commit acquisition.
2. **Immutable GitHub identity (#56 F002).** An `owner/repository` name can
   be renamed, transferred or reused and is **not** an immutable identity.
   The admitted resolved request and packet must bind GitHub's authenticated
   stable repository ID, object identity and authorized installation, not
   merely a name and the captured content digest. If a name resolves to a
   different repository ID on recovery, **fail closed**. Decide whether the
   canonical v3 selector requires a requester-supplied expected repository
   ID or obtains and durably binds one before claiming a new identity.
   **Proposed answer:** require numeric `subject.repository_id` in the
   v3 request, verify canonical name+ID before claim, and durably bind
   the authenticated object IDs. Test rename/transfer/reuse.
3. **Inline/upload logical slot continuity (#56 F003).** Reusing the same
   requester-selected reference ID can express continuity of a question,
   **not** substantive evidence equivalence. A different content value
   produces a distinct exact request/packet, and a same-intent successor
   cannot bypass explicit re-review permission and trusted predecessor
   evidence. Do not add an automatic semantic-equivalence classifier.
4. **Canonical basis and historical compatibility (#56 F004).** Qualify the
   exact v3 closed schema, RFC 8785 canonical basis, version-separated
   identity domain, source selectors and predecessor rules using offline
   request/intent/packet fixtures, including a changed logical GitHub
   repository identity. Historical v1/v2 identities must remain immutable.
5. **Permanent versus recoverable pre-model failure (#56 F005).** An
   unsupported selector, unauthorized access, disallowed repository,
   failed expected digest or unestablished required atomicity must not
   accidentally become a recoverable `REQUESTED/ADMITTED` retry loop.
   **Proposed answer:** the [focused protocol annex](pre-model-preparation-failure-protocol-draft.md)
   fixes a single automatic dispatch CAS reservation, journal-bound
   permanent/blocked dispositions, one fresh owner authorization per
   subsequent dispatch, worker-generation fencing, and a versioned
   specialized `REQUESTED/ADMITTED → STOPPED` path after actual Shutdown.
   None is implemented; **PM01–PM25** must be fault-tested before
   adoption, including the observed journal-version downgrade
   and cross-request Codespace conflict.
   The runbook currently supports bounded same-attempt pre-model recovery;
   it does **not** authorize a later re-review after `ARMED`.
6. **Testable atomicity contract (#56 F006).** `atomicity=true` is an
   obligation, not a claim of general cross-provider snapshot isolation.
   **Proposed answer:** qualify immutable PR B/H comparison, frozen inline
   values and same-repository/same-H Git blobs as the first profile for
   `atomicity=true`. Reject other commits and independently mutable API
   bodies under `true`. Prove both pass and counterexample failures using
   verified Git objects and byte-exact packet construction.
7. **Source-complete independent qualification (#56 F007).** The v2 broker
   packet examines only PR-changed material. A later independent review
   claiming conformity to #43/#44/#51 and governing contracts must **actually
   include their exact contents**, or state the limitation and use a
   separate read-only reviewer with explicitly verified inputs and
   independent execution provenance. Never call PR-only evidence a
   cross-document review.

No unresolved item above is a license to re-open exhaustive internal Codex
security attestation, expand source permissions, or add a generic ingestion
layer. There is no authority in this draft to update normative schemas or
run a model.

## 11. Publication, review and authorization gate

This document is intentionally a **draft PR dependent on the now-published
non-normative design of PR #52**:

- Parent PR #52 publication is complete; **that prerequisite is satisfied**,
  but the three historical independent `NO_GO` results remain valid evidence
  of the bounded design's unsettled technical details.
- Review this exact candidate against #43 PI-REQ-03, #44 D1–D9, #51's
  disposition, accepted v1/v2 contracts, packet/result schemas, implementation
  and exact-SHA historical evidence; do not rely on a v2 PR-change-only packet
  as full cross-document verification. Publication of #52 is not publication
  approval for this draft.
- Independent reviewers should seek counterexamples to identity bases,
  mutable-source recovery, atomicity scope, permission boundaries, mission
  evidence authority, result provenance, required/optional admission and
  minimum possible representation. They must include all **three**
  companion annexes, especially the pre-model protocol and PM01–PM20,
  and source-check both the 55-case synthetic report and 15-case
  current-module test evidence rather than misrepresenting either
  as v3 qualification.
- A favorable review is **not** automatic adoption as normative contract,
  approval to change executable schemas, expansion of GitHub permissions,
  launch of a Codespace or inference, or downstream merge authorization.
- No implementation sub-issues or consumer-repository modifications are
  authorized by this draft.

`DOCUMENT_STATUS=UNACCEPTED_NON_NORMATIVE_VERSIONED_CONTRACT_DRAFT`
`REVIEW_REQUEST_V3_IMPLEMENTED=NO`
`PACKET_V2_IMPLEMENTED=NO`
`REVIEW_RESULT_V2_IMPLEMENTED=NO`
`PARENT_DESIGN_PR52_MERGED=YES`
`NORMS_AND_SCHEMAS_UNCHANGED=YES`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
