---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-03 Authorized Packet Preparation Candidate"
version: "0.1.0"
---

# Issue 70 RWP-03 — Authorized Packet Preparation Candidate

**PRODUCT-OWNER SELECTED DESIGN DIRECTION — NON-NORMATIVE; NOT IMPLEMENTED; NOT QUALIFIED.**

## 1. Status, source, and scope

This proposal records the bounded architectural decisions selected for
RWP-03 of Issue #70 (parent #67). It is a design input for a separately
mandated implementation, not an accepted contract or an implementation
authorization. Neither publication of this file nor an independent
construction-review GO grants permission for live GitHub effects.

The exact experimental source is draft, unmerged PR #84 at
`2c062df9cea70888fd367f008f67c4215638ed7c`, tree
`0890147dd1b284dd613cfb33ffd93e6bb25aeceb`, based on PR #81 at
`2f32e78f8b00ba4598dc7b030e2e5fd43afd2add`. Its prior evidence is
`RWP01_OFFLINE_INITIAL_CONTROLLER=PASS` and
`RWP02_OFFLINE_WORKER_BINDING=PASS`; the latter includes exact-source CI
(868 tests) and an independent read-only GO. Those are separate, bounded
historical results, not qualifications of RWP-03. PRs #71, #72, #77, #81,
and #84 remain experimental and are not to be merged by this proposal.

The intended RWP-03 offline exit is
`RWP03_OFFLINE_AUTHORIZED_PACKET=PASS`: the current generation-1 Worker
continues from an attributed `PRE_MODEL_WORKER_BOUND` to a separately
attributed `ADMITTED`, an authorized expected technical-policy selection,
a locally captured and verified four-reference Reviewer Packet v2, and
independent cold reconstruction of its bytes and authority. Stop there.

`REMOTE_PACKET_RETENTION=NOT_QUALIFIED`,
`EFFECTIVE_CODEX_POLICY=NOT_ATTESTED`, and
`LIVE_PREMODEL_PREPARED=NOT_QUALIFIED` remain unchanged. No `PREPARED`,
`ARMED`, Codespace lifecycle, model inference, ReviewResult, production
activation, generation-2 recovery, or normative adoption is in scope.

## 2. Existing implementation facts and the identified gap

The experimental `packet_v2.py` currently defines
`TechnicalProfileSnapshotV2` with a synthetic verification default.
Its `_technical_policy()` requires `SYNTHETIC_OFFLINE_VERIFIED`, verifies
`expected_name == actual_name` and the digest of `original_bytes`, and
emits `qualification=SYNTHETIC_OFFLINE_ONLY`. The candidate
`packet-v2.candidate.schema.json` accepts precisely that qualification.
`packet_retention_v3.load_packet_evidence_v3()` reconstructs that synthetic
profile unconditionally from retained `technical-profile.bin`. Those
mechanisms correctly qualify the historical offline packet, not an
independently approved technical-policy selection.

Separately, `reviewer_profile.py` constructs an eventual Codex permission
configuration from absolute paths of the real reviewer home, trusted
workspace, and packet directory. Such installed-profile bytes cannot be
claimed before the later execution environment exists. The semantic
review profiles under `profiles/` are distinct from the technical Codex
permission profile; see the accepted mission-ownership direction D6 in
`docs/architecture/requester-owned-mission-decision-proposal.md`.

`pre_model_worker_v3.py` deliberately stops after an attributed Worker CAS.
`GitHubActionsWorkerAuthorityV3` authorizes the initial binding; it is not
a reusable authorization for every later effect. A distinct continuation
must establish current authority at each subsequent boundary.

The implemented `GitHubJournalV3.record_admission()` records the original
admission evidence and performs a state transition; it does not, by itself,
attest to newly captured sources or technical-policy authorization. Preserve
that distinction instead of silently redefining `ADMITTED`.

## 3. Decision A — Broker-owned expected technical policy

The broker, not the requester or reviewed repository, owns technical
execution-policy selection. RWP-03 binds an **expected policy definition**
without asserting installation or effective enforcement by Codex.

The first candidate should use a single broker-owned, immutable,
versioned policy definition selected from the executing Review Broker's
approved source revision. The policy definition must be independent of
runtime-allocated absolute paths, a Codespace instance, an installed
Codex profile, and any requester-controlled field. The eventual concrete
profile is instantiated and independently checked in a later execution
qualification; its absence at RWP-03 is not a synthetic success.

The expected definition should describe, using a closed versioned data
format, the reviewer backend and requested model/effort, the required
read-only packet boundary, the ban on executing reviewed source, the
noninteractive approval requirement, environment/credential isolation,
and the intended network restriction. These are **required configuration
intent**, not effective capability measurements. Any policy materialization
must later prove the exact authorized relationship to the expected
constraints; identity equality alone cannot establish effective sandbox
behavior.

For the successor implementation, the proposed dedicated broker-owned
source is `src/review_broker/profiles/pre-model-v3-expected-policy.json`.
This path and its format are **prospective**: the file does not exist or
become authoritative through this proposal. The implementation must pin
its exact broker repository ID, Git commit, Git blob/file bytes, policy
name, and content digest; ambiguous or mutable source selection fails
closed. A consumer repository file or a request reference may never
replace this authority.

The requester retains control of substantive `mission` and the declared
ordered `references`, not of Codex permissions, credentials, or runtime
policy. Requester instructions cannot weaken the broker's technical
constraints.

## 4. Decision B — Separate content identity and authorization provenance

RWP-03 uses two distinct identities, never collapsed:

1. **Policy content identity** identifies the exact expected policy
   definition, including format/version, broker-owned policy name,
   and original-byte SHA-256. It is independent of a particular
   requester or Worker.
2. **Selection authorization identity** identifies the separate broker
   decision admitting that exact policy for one request, attempt,
   generation, reservation, Worker, and expected executable SHA.

The policy source must be read and checked against a pinned broker-owned
Git object or another independently accepted trusted source. Its byte
identity is evidence of integrity, not evidence of approval.

The narrow experimental selection decision is produced by an injected
broker-policy authority **independent from the request, consumer source,
packet producer, and Worker inputs**. The authority must verify the exact
approved policy content and provenance before authorizing its use.
An injected test authority qualifies only its bounded offline contract;
its presence cannot be relabeled as a deployed credential, signature,
GitHub App, or effective runtime attestation.

The proposed closed selection receipt (descriptive field names; final wire
schema belongs to the separate RWP-03 implementation mandate) binds:

- a schema version and a distinct receipt type;
- the broker repository and numeric ID, exact broker executable SHA;
- the policy source location, exact source commit, and original byte hash;
- the policy name/version and policy content identity;
- the separately observed policy-source evidence identity;
- the exact Request ID, Review Intent ID, Attempt ID, claim ref;
- generation 1, Reservation ID, bound Worker run ID and attempt;
- the journal predecessor commit and the decision-authority evidence;
- the selected policy authorization identity derived from canonical bytes.

Use existing `canonical_bytes()` and domain-separated artifact-identity
conventions. The receipt's own identity is computed from its complete
canonical basis and is not embedded in that basis. No receipt may refer
to its future packet ID or an as-yet-uncommitted future journal commit,
preventing circularity. Do not mint an authority by computing a digest of
caller-controlled receipt fields; the independent authority must accept
the exact decision and provenance.

An authorization for the same content but another request, attempt,
Worker, reservation, executable SHA, or policy source must not be reusable.
Absent, contradictory, expired-if-applicable, stale, untrusted, or
otherwise unverifiable authority fails closed.

## 5. Decision C — Closed candidate packet variant, preserving history

Introduce a second **experimental** technical-policy qualification,
`PREMODEL_POLICY_SOURCE_VERIFIED_ONLY`, alongside the existing
`SYNTHETIC_OFFLINE_ONLY`. Do not reinterpret or rename the existing
variant, recompute historical packet identities, or change accepted
ReviewRequest v1/v2 or ReviewResult contracts.

The new variant represents an expected policy with verified broker-owned
source bytes and a separately admitted selection. It is **not** a
production-security certification, a claim that a Codex profile has been
installed, or proof that Codex enforces the requested restrictions.

The successor candidate manifest's `technical_policy` should retain
its existing policy-content identity, original-byte evidence, and
qualification, and add versioned source-provenance and selection-decision
evidence for the **new variant only**. Use a closed discriminated schema,
not permissive optional fields that would allow mixing synthetic and
authorized modes. The original `SYNTHETIC_OFFLINE_ONLY` branch retains
its exact old allowed fields and canonical values.

The new variant's complete `technical_policy` value participates in the
existing `_packet_basis()` and therefore in the new `packet_id`. A changed
selection decision must change the packet identity even if the policy
content bytes are unchanged. The policy-content ID may remain identical
across two decisions; that is expected and must not imply equal packet
or preparation authority. The program may still reference the content
ID separately; it must not lose the authorization linkage held by the
packet. Do not alter the identity derivations for old variants.

The proposed retained evidence inventory for the new variant includes
exact original expected-policy bytes, a canonical policy-source
observation, and a canonical selection receipt under a private evidence
root. The existing `technical-profile.bin` path may be retained as a
historical compatibility location, but the new variant must not silently
claim those expectation bytes are the final installed Codex profile.
The implementation mandate must specify an unambiguous on-disk naming
and typed loader for the new kind. Local atomic writes, private file
permissions, complete inventory checks, and symlink rejection remain
mandatory.

Cold reconstruction must use only the journal's authenticated claim data,
the exact retained bytes, and **independent verifier authority** supplied
to the new process. It must rebuild the canonical source observation,
policy-content ID, selection receipt ID, packet manifest, source inventory,
prompt, and packet ID. The verifier may not obtain an approval by merely
re-hashing retained data, accepting a producer-supplied `authorized=true`,
or recursively trusting an assertion stored inside the packet.

The new cold path must explicitly refuse a missing or unrecognized
independent source/selection authority. A test-only injected verifier
can hold an external trusted fixture decision; that fixture is not
production authority. A fresh process with only mutable producer-owned
packet bytes must **not** be able to manufacture acceptance.

## 6. Decision D — Worker continuation after the RWP-02 boundary

Build a **new RWP-03 continuation component**. Do not change
`PreModelWorkerV3.run()` into a source-acquisition entry point and do not
reuse the initial-binding `GitHubActionsWorkerAuthorityV3` as a perpetual
effect permit. RWP-02's successful `PRE_MODEL_WORKER_BOUND` is a
prerequisite, not a blanket authorization for future operations.

The continuation must re-read the current journal, validate the original
Request v3 and admission, confirm the exact accepted dispatch ACK and
Worker-binding history, and independently authenticate current runtime,
reservation and generation-1 Worker identity. A fresh, narrowly scoped
current-worker authority must check journal freshness before each external
read or filesystem mutation. A matching historical Worker ID or locally
cached `COMMITTED` outcome alone is insufficient.

The nominal offline sequence is:

```text
RWP-02 acknowledged run and attributed PRE_MODEL_WORKER_BOUND
  -> reauthenticate current bound Worker / current journal
  -> GitHubJournalV3.record_admission() with original admission_evidence_id
  -> attribute the resulting ADMITTED CAS to the current operation
  -> exact authorized subject and four-reference capture (injected transports)
  -> independently authorize and capture expected broker technical policy
  -> build and independently verify Reviewer Packet v2 new candidate variant
  -> private local retained-evidence persistence and cold reconstruction
  -> STOP; no PREPARED or externally retained artifact
```

`ADMITTED` means the original request/admission was durably recorded; it
does not certify that subsequent capture has succeeded. Capture and policy
receipt identities are separate evidence, checked later. A failed or
unattributed `ADMITTED` operation authorizes no acquisition. A competing,
stale, missing, or rerun Worker cannot claim continuation rights from a
readback showing a matching state. No auto retry follows an unresolved CAS.

Source capture must reuse the qualified candidate source readers,
preclaim admission constraints, subject provenance, original-byte/Git
object identities, physical line rendering, and declared reference order.
The four supported kinds remain `inline`, `git_file`,
`github_issue_body`, and `github_issue_comment`. `atomicity=true`
must not be claimed unless the applicable coherent-cut evidence exists;
independent captures under `atomicity=false` do not imply coherence.
Requester-supplied content remains untrusted data, never authority to
select policy or execute reviewed code. No live API request, token mint,
checkout of consumer code for execution, or reviewer invocation is
permitted in RWP-03 offline qualification.

An attributed `ADMITTED` CAS must be verified before packet preparation.
The candidate local packet must be complete and independently verifiable,
but RWP-03 must not call `GitHubJournalV3.prepare`, record the historical
offline PREPARED receipt, upload an Actions artifact, or claim remote
durability. RWP-04 owns private remote artifact retention, its exact
storage metadata, remote receipt, PREPARED CAS, and cold remote readback.

## 7. Falsification and qualification gates

The separate RWP-03 execution mandate must produce independent nominal
and adversarial tests over real candidate admission/journal/packet code
with **injected external authorities and transports**. At minimum,
exercise the following counterexamples:

1. Policy bytes with a correct hash but no independent authorization.
2. Correct policy content selected for the wrong request, attempt, Worker,
   reservation, claim, executable SHA, broker repository, or source commit.
3. An attempt to replace policy bytes with requester-provided text,
   consumer-repository content, or a declared reference.
4. A policy source read that is missing, ambiguous, mutated, unpinned,
   or inconsistent with the authorized original bytes.
5. Policy name/version mismatch, malformed closed schema, unknown
   qualification, or an unauthorized synthetic-to-verified promotion.
6. A changed selection receipt with unchanged content bytes: the new
   packet identity must change.
7. An old synthetic packet or retained evidence must round-trip with
   byte-identical historical identity and unchanged qualification.
8. Cold loading with missing source observation, missing selection
   receipt, or substituted source/decision evidence must fail closed.
9. A cold loader with correct retained bytes but no **independent**
   verifier authority must reject the new variant.
10. Worker context, run attempt, ACK, binding, generation, or reservation
    not current or mismatched must prevent admission and source reads.
11. An `ADMITTED` CAS that is rejected or unresolved must prevent all
    subsequent capture/packet actions, including a losing identical-target
    CAS after readback.
12. Changed PR HEAD, incorrect diff or merge base, substituted Git blobs,
    mutable Issue/Comment reference change, missing required source,
    incomplete pagination, unauthorized source scope or broken original
    reference order must fail closed.
13. Captured reference/source bytes that change before packet verification
    must invalidate the candidate packet; no silent reacquisition.
14. Unknown storage members, non-private modes, symlinks, altered
    inventory, altered policy bytes, incorrect prompt, or changed packet
    manifest must fail independent cold verification.
15. Attempts to enter `PREPARED`, dispatch, mint live credentials, acquire
    live sources, launch Codex, start Codespaces, or activate workflows
    must be absent from the experimental interfaces and produce zero effects.

Test a separate fresh interpreter after destroying ephemeral Worker
memory; preserve only an explicit private test-fixture trust root, the
simulated journal and retained local bytes. Network access must be
forbidden during cold verification. Tests must not mistake a mock
provider response for a real authority or synthetic file permissions for
remote retention. Run the complete repository regression suite, exact-SHA
CI and independent read-only construction review; preserve the existing
RWP-01/RWP-02 GO as historical evidence rather than reissuing them.

### Acceptance classification

`RWP03_OFFLINE_AUTHORIZED_PACKET=PASS` requires, jointly, exact Worker
continuation, attributed `ADMITTED`, authorized expected-policy source,
new closed packet variant and canonical identity binding, exact four-kind
capture, private local retention, genuine packet verification, cold
reconstruction with independent authority, negative-case coverage,
full regression PASS, exact-source CI PASS, and fresh independent GO.

Even then, `EFFECTIVE_CODEX_POLICY=NOT_ATTESTED`,
`REMOTE_PACKET_RETENTION=NOT_QUALIFIED`, and
`LIVE_PREMODEL_PREPARED=NOT_QUALIFIED` remain explicit.

## 8. Historical compatibility, future work, and open implementation details

This design does not amend the accepted repository specification, schemas,
`docs/contracts/`, normative architecture, Request v1/v2, ReviewResult,
existing Reviewer Packet v2 identities, historical qualification reports,
PR #55, or previously qualified workflows. Any new policy variant and
its receipt are **candidate-only**, with strict version/qualification
discrimination; do not retrofit previous records.

This document selects the design direction but does not itself define
an executable JSON Schema, new Python API signature, authoritative
source file bytes, real credential provenance, or an actual production
attestation. Those must be supplied as an exact implementation specification
in the separately authorized RWP-03 mandate and validated against the
current source before code changes. If an implementation discovers a
material conflict with accepted authority or historical guarantees, stop
and seek an explicit decision; do not weaken a validator or invent a
production qualifier.

Follow-on RWP-04 addresses authenticated private remote retention and
commit/readback of `PREPARED`. RWP-05 addresses the bounded pre-model
failure/reconciliation classification. The separate issue #43 Product
Intent and #51 reference-contract work remain independent.

The reviewer’s final runtime policy enforcement, effective model identity,
network/filesystem/tool restrictions, Codespace lifecycle and independent
inference are later boundaries and cannot be inferred from an approved
pre-model packet.

## 9. Documentary publication gate

Publish this document through an isolated detached-HEAD task worktree
based on the exact PR #84 source, using the repository's mandated
publication orchestrator; create one **draft** documentation-only
successor PR targeting the PR #84 branch. No source, schema, workflow,
test, credential, permission, rule, Project state, or historical report
may be modified by that PR. Validate OKF frontmatter, Markdown,
`git diff --check`, exact files and identities, then perform the normal
exact-SHA CI and independent read-only review applicable to its scope.

Only after the draft PR exists and its identities have been read back,
add a non-normative documentary link to Issue #70, preserving its body,
state, parent links, and Project state. A proposed architecture is not
`RWP03_OFFLINE_AUTHORIZED_PACKET=PASS`; RWP-03 implementation remains
separately authorized.
