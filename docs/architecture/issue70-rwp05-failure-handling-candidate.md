---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-05 Failure Handling Candidate"
version: "0.1.1"
---

# Issue 70 RWP-05 — Failure handling candidate

## Status and authority

This owner-selected experimental implementation starts at draft PR #89, SHA
`a7a4bcc2a21c3fa3961c7095e0c59b1bf1ecfd8e`, tree
`4fd57168bbb656a97c97340795094920f2097b19`. The accepted RWP-04 result is
1019 tests without skips and independent GO on that tree. Older failures and
NO_GO results remain facts on their own trees. No normative v3 adoption,
operational permission, activation or public-schema change follows here.

The product specification and accepted public contracts retain their authority.
The PR #55 pre-model annex at `d827df21b1ccd179408f0624709cc2446795e134`
is documentary candidate input. This mandate selects a narrower ADMITTED+
realization, not its generation-zero writers, recovery or terminal extensions.

## Responsibilities

- `pre_model_failure_observation_v3.py`: closed observation schema, strict
  canonicalization, pure classification and exact links; no I/O or approval.
- `pre_model_failure_evidence_v3.py`: explicit bounded injected retention and
  independent provenance interfaces; no implicit backend or network fallback.
- `pre_model_failure_continuation_v3.py`: original decision provenance,
  one-shot failure orchestration and active failure authority.
- `pre_model_failure_readback_v3.py`: authenticated historical A/B relation and
  observer-only original-observation reconstruction.

Narrow coherent extractions may own the local capability, real-boundary fact
collection and shared guarded Git writer. Existing transition, identity,
canonicalization, inventory, Packet v2 verification and expected-old CAS rules
remain single-source implementations. Existing callers without observation
hooks retain their diagnostics and behavior. Permanent receipts keep their
original fields, accepted combinations, bytes and identities.

## Eligible domain and original decision

A is the original continuation's attributable, exactly read-back ADMITTED
snapshot. B is its failure successor; P is its PREPARED successor. The active
failure domain is generation 1, RESERVED, original bound Worker/run_attempt=1,
recognized admission/ACK/executable, no failure ID, no PREPARED/ARMED history and
zero invocations. An ADMITTED state merely visible after an unattributed write
creates no permission. Nothing before binding or before confirmed A receives a
new failure writer.

`ActivePreModelDecisionV3` is an internal object capability emitted only inside
the original packet continuation after confirmation of A. Its provenance binds
the actual producer, execution-context object, A, claim, reservation and Worker.
A constructor, snapshot, boolean, digest, copied result, copied capability,
subclass or restarted process cannot mint it. Real local mutual exclusion
arbitrates concurrent handlers; Git CAS remains the distributed arbitration.

The active capability permits observations and exactly one final path. The
identity-checked RWP-04 handoff transfers it to the genuine remote continuation;
reading ADMITTED cannot transfer it. Before entering either journal operation,
it irreversibly becomes CONSUMED_FOR_BLOCKED or CONSUMED_FOR_PREPARED, bound to
that operation and owner. Internal guards accept only this selected consumed
operation, not a second entry. Validation failure does not restore ACTIVE.
After return its active path is closed. There is no BLOCKED fallback after
PREPARED selection, nor PREPARED fallback or second failure after BLOCKED
selection. Definitive exits without a qualified mutation also close it.

## Phase matrix

| Phase | Permitted behavior |
| ----- | ------------------ |
| Before confirmed A | Existing refusal/uncertainty/read-only reconciliation; no new failure CAS. |
| A, active original ticket, recognized retained observation, current authority | One BLOCKED entry may be selected. |
| Capture/reference/policy/build/persistence interruption without catalog evidence | Existing refusal/UNRESOLVED; no invented observation. |
| Unknown upload response | Existing bounded RWP-04 reconciliation, never another upload. |
| Unknown upload remains unresolved through complete verification | Recognized composed upload observation may authorize UNKNOWN/BLOCKED. |
| Entry into BLOCKED or PREPARED | Irreversible selection; further reconciliation is read-only. |
| Attributed PREPARED followed by archive/read failure | COMMITTED/PREPARED; availability UNAVAILABLE. |
| Attributed BLOCKED followed by original-proof loss | Historical ADMITTED/BLOCKED remains; cause verification UNAVAILABLE. |
| Restart, even with valid A/context | Observation only; no ticket emission. |

Guard failures and local deadlines are not evidence that another effect failed
or never occurred. A previously launched effect may finish after journal
movement, but grants no next effect or advancement. No cross-service atomicity
or retroactive cancellation is asserted.

## Closed observation

The observation contains exactly these fields:

```text
schema_version=1
 evidence_type=pre-model-preparation-failure-observation
 repository, repository_node_id, claim_ref, admitted_commit_sha
 request_id, attempt_id, admission_evidence_id
 generation=1, reservation_id, workflow_run_id, workflow_run_attempt=1
 phase, operation, reference_id, packet_id, artifact_name, artifact_id
 fact, observed_at
```

Numeric values are strict integers, never booleans or floats. Git and artifact
identities have their canonical lowercase hexadecimal grammar. Artifact IDs are
positive canonical decimal strings, without signs, whitespace or float
conversion. Timestamps preserve the original UTC `YYYY-MM-DDTHH:MM:SSZ` bytes
and valid calendar value; readers never renew them.

REFERENCE_READ binds an admitted reference ID; other phases have reference_id
null. SOURCE_ACQUISITION and REFERENCE_READ have packet_id/artifact_name null.
REMOTE_* phases bind the genuine handoff's original packet and deterministic
RWP-04 artifact name. Artifact ID is null until independently established;
remote verification requires the exact recognized non-null artifact ID.

Allowed phase/operation pairs:

- SOURCE_ACQUISITION: GIT_CLONE or GIT_FETCH.
- REFERENCE_READ: GITHUB_ISSUE_GET or GITHUB_ISSUE_COMMENT_GET.
- REMOTE_UPLOAD: ACTIONS_ARTIFACT_UPLOAD.
- REMOTE_READ: ACTIONS_ARTIFACT_METADATA_GET or ACTIONS_ARTIFACT_DOWNLOAD.
- REMOTE_RECONSTRUCTION: VERIFY_ARCHIVE_BYTES, VERIFY_ARCHIVE_INVENTORY,
  VERIFY_REMOTE_MANIFEST or VERIFY_REMOTE_PACKET.

The fact union is closed, with exactly the listed fields:

```text
HTTP_STATUS: kind, status
TRANSFER_TIMEOUT: kind, process_terminated=true
UPLOAD_OUTCOME_UNKNOWN: kind, emitted=true, reconciliation=UNCONFIRMED
READ_TIMEOUT: kind
VERIFICATION_FAILED: kind, check, expected_id, observed_id,
                     expected_size, observed_size
```

ARCHIVE_BYTES pairs with VERIFY_ARCHIVE_BYTES, actual completed ZIP-byte
artifact IDs, nonnegative exact sizes within explicit transport budgets, and a
difference of identity or size. INVENTORY and MANIFEST use existing canonical
inventory IDs and exact canonical-manifest-byte artifact IDs respectively;
PACKET_ID uses the original/calculated packet IDs. Their sizes are null and IDs
must differ. Unsafe extraction, incomplete parser/schema checks and budget
stops do not manufacture a completed verification fact. No control is relaxed
to obtain an observed identity.

Observation identity is `artifact_identity(canonical_bytes(observation) + LF)`.
No classification or reason is caller-controlled in this object. There is no
free text, signed URL, header, command, Git output, HTTP body, source content,
secret, traceback or requester prose. A valid hash identifies bytes, not origin.

## Six-reason classification and precedence

| Reason | Classification | Required original fact |
| ------ | -------------- | ---------------------- |
| SOURCE_API_UNAVAILABLE | TRANSIENT | Admitted-reference reader actually observes HTTP 429/502/503/504. |
| SOURCE_ACCESS_AMBIGUOUS | UNKNOWN | That authenticated reader actually observes HTTP 403/404. |
| SOURCE_TRANSFER_INTERRUPTED | TRANSIENT | Admitted clone/fetch started, timed out and its process termination was confirmed. |
| ARTIFACT_UPLOAD_UNCONFIRMED | UNKNOWN | Upload actually emitted with unknown outcome; complete bounded reconciliation did not establish the exact object. |
| ARTIFACT_READ_UNAVAILABLE | TRANSIENT | Recognized-plan metadata/download HTTP 429/502/503/504 or precisely observed read timeout. |
| REMOTE_RECONSTRUCTION_UNCONFIRMED | UNKNOWN | A concrete completed bound archive/inventory/manifest/packet identity comparison differs. |

Authority/ticket failure or indeterminate journal result always forbids a new
failure CAS. UNKNOWN upload first receives the existing bounded reconciliation.
It remains unresolved until metadata, actual ZIP download, extraction/inventory
and original-packet verification all succeed. During that uncertainty the
composed upload reason takes precedence over a read error or divergent check.
After full success, only subsequent independently observed failures apply.
After recognized ACK, eligible read and concrete verification failures retain
their own catalog reason. TRANSIENT is a category, not a retry promise.

A generic exception/message/status/hash is never promoted automatically.
Post-ACK absent/expired/ambiguous artifact, budget, redirect/path refusal,
schema error and other outside-catalog faults retain existing results.
Recognized 403/404 means neither absence, omission nor permanence.

## Real-boundary evidence and independent retention

Facts are collected after a successful guard and an actual emitted operation,
before existing readers reduce them to public diagnostics. Narrow hooks cover
the Issue reader, subject clone/fetch, uploader, metadata/download and concrete
remote checks. Their transient execution references are not serialized into
the observation. Independent authority must confront the actual executed
request, repository/object/endpoint or artifact plan, not just payload IDs.

An explicit bounded injected store retains immutable original canonical bytes
outside the Worker. It is test construction infrastructure, not an operational
database, second journal or qualified live backend. Trust corpus and archive
are distinct from untrusted inputs and from each other. A put never creates
provenance recognition. Before choosing BLOCKED, recognition, one retention
attempt, exact readback/identity, renewed recognition and current Worker
authority must all pass. A lost put ACK permits only bounded exact readback,
not another write. Indeterminate retention/provenance means no failure CAS.
Nothing is added to the packet, its inventory, ZIP or RWP-04 remote receipt.

## Receipt, transition and historical observer

The failure receipt preserves the existing exact fourteen-field shape:

```text
schema_version, evidence_type, request_id, attempt_id, admission_evidence_id
 generation, reservation_id, workflow_run_id, workflow_run_attempt
 classification, reason_code, reference_id, observation_evidence_id, observed_at
```

Version is integer 1 and type is pre-model-preparation-failure. Bindings are
those of A and its original observation; classification/reason come only from
the recognized catalog. The observation ID is recalculated from retained exact
bytes. The timestamp is copied unchanged. Receipt identity is
`artifact_identity(canonical_bytes(receipt) + LF)`, with no self-ID or future
B SHA. Permanent validation remains distinct and byte-compatible.

The pure A-to-B transition preserves ADMITTED, admission, Worker, generation,
reservation, all previous history and other identities. Only disposition and
failure ID change, plus one final PRE_MODEL_FAILURE event with the full receipt
and its evidence ID. Decoder/history jointly require ADMITTED/BLOCKED/generation
1/bound initial Worker, exactly one final failure, zero invocations and no
PREPARED/ARMED or reopened history. BLOCKED is not an AttemptState.

The journal operation reuses the existing transition transport and CAS, expected
old A.commit_sha and force=false. Original-choice guards reach observation
reads/writes and each internal blob/tree/commit and GraphQL request. After
entry, pending reconciliation is read-only. HTTP 200 errors, an old A or
unattributed equal B bytes do not establish success or non-application.
`github_journal_reconciliation_v3.py` owns that single bounded read-only path.
Thrown ref/origin reads retain the exact pending operation as UNRESOLVED; the
shared transition also preserves its last independently recognized writer or
rejection evidence if subsequent result verification/reconciliation throws.
Invalid caller-supplied pending authority is still rejected before transport I/O.

Results separate journal outcome, authenticated state/disposition, observation
verification status and diagnostic reason. A committed failure is not a packet
handoff. Confirmed journal commitment survives later evidence unavailability.

The historical reader authenticates B and its actual parent A by SHA and origin,
requires the exact domains, validates the full receipt, applies the real pure
transition to A and compares all B bytes. It then rereads original observation,
origin, links, timestamp and classification without new source/upload activity.
Unverifiable journal origin prevents claiming authenticated BLOCKED. With
trusted A/B but missing/rejected cause evidence, retain the commitment and
report observation UNAVAILABLE/REJECTED as actually established. No ticket,
new observation, capture, builder, selection, persistence or mutation is issued.
Cold verification is a separate interpreter after Worker-root deletion, retaining
the existing effective Linux boundary and external fixture trust.

The shared pure failure-domain module owns open-control eligibility. Active
policy verification rejects failed/ineligible ADMITTED snapshots before its
first I/O. Existing journal-bound retention, preparation-receipt and retained
packet-authority helpers also reject failed control before any Git/file reads
or writes. This closes newly decodable BLOCKED state at older preparation
interfaces without changing their open-A receipt bytes or admitting historical
observers into active preparation.

## Qualification and Stage 1 limits

F01–F23 cover closed schema/legacy compatibility, proof and exact links,
retention before CAS, original eligibility, local exclusive decisions,
TRANSIENT/UNKNOWN, all pre-A and post-A interruptions, upload priorities,
PREPARED barrier, concrete Git/GraphQL guards, concurrent failures and
PREPARED/permanent-refusal races, ambiguity/attribution, genuine cold observer,
proof loss, falsified history and future/restart refusal. Service counters and
positive controls are mandatory, including effects applied with lost responses.

The integrated nominal witness traverses actual admission, common Controller,
reservation/dispatch simulation, ACK, Worker, attributed A, four-reference or
empty-reference original packet, upload, reconstruction, PREPARED and cold read.
PM01–PM35 have explicit per-subcase scope and test evidence in the separate
matrix; excluded terminal/recovery/Codespace positives receive no transferred
PASS from negative boundary tests. PM11 before A preserves existing ambiguity
without creating a writer, as the candidate annex's reservation/crash clauses
require. Historical prototype 21-case feasibility stays distinct from integrated
qualification; original input hashes must match before any reuse claim.

Final Stage 1 PASS requires all declared bounded guarantees, full exact-tree
normal Ubuntu CI, unchanged twelve Linux tests and required cold cases without
skips, and fresh read-only Pi GO fixed to openai-codex-1/gpt-6.1-sol/high.
READY_FOR_BOUNDED_LIVE_PLAN means only that a live plan may be written. Actual
uploader wiring, real failure-proof retention, deployed credentials/authorities,
triggers, permissions, rollout exclusion and exact live-effect budgets remain
separate prerequisites.

No real dispatch, consumer acquisition, artifact/failure-proof upload, operational
journal mutation, Codespace or broker inference is authorized. Generation 2,
recovery, specialized STOPPED/non-acquisition, ARMED, ReviewResult, activation,
normative adoption, dev integration, #83 changes, merges, Issue closures and
Project changes are excluded. Construction model calls remain separate effects.
