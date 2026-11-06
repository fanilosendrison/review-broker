---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Live Preparation Operational Adapter Candidate"
version: "0.1.1"
---

# Issue 70 — Live preparation operational adapter candidate

## Status and boundaries

This is a **partial construction candidate**, not a deployable live preparation
workflow. The immutable base is draft PR #90, SHA
`4f715fc6bd52fc5dac87a2f660ba8d2bf535e811`, tree
`016b2b91b1f42eb7d78280634c15e499ae295d2a`. Its offline qualifications and
historical NO_GO results remain attached to their original subjects.

Product specification, public schemas and accepted architecture retain their
AGENTS.md precedence. No normative ReviewRequest v3, Packet v2 or ReviewResult
v2 adoption is made. No live execution, activation, merge or dev mutation is
permitted by this candidate. No new active workflow or internal live entrypoint
is installed. The existing disarmed Worker workflow remains byte-identical.

## Independent implemented responsibilities

- `actions_artifact_child_v3.py` owns verification and one synchronous invocation
  of the pinned official uploader from its Python parent. It supplies a private
  single file and allowlisted child environment, not a second broker process.
- `actions_artifact_http_v3.py` owns bounded live HTTP readers with mandatory
  guards, independent API/storage openers and no redirect following.
- `actions_artifact_readback_v3.py` owns the shared authenticated named-artifact
  metadata checks and exact raw-byte download. It is extracted from RWP-04, not a
  second implementation of its pagination, metadata or byte-identity rules.
- `github_prepared_artifact_v3.py` retains the existing PREPARED interfaces and
  delegates shared reads. PREPARED still validates its distinct remote receipt.
- `github_actions_failure_archive_v3.py` implements the separate RWP-05 archive
  protocol. Retention does not recognize observation origin or grant BLOCKED.
- `github_journal_transition_authority_v3.py` owns deterministic target-continuity
  authority over an injected authenticated-reader protocol. The guarded concrete
  specialization is colocated at the existing transport import boundary.
  `github_journal_commit_writer_v3.py` owns the mechanically extracted immutable
  Git commit assembly. The journal/CAS/reconciliation algorithms are unchanged.

These components are not an assembled live Controller or Worker. Injected guards
remain explicit obligations of the future original-process composition. Existing
original-ticket and observer-only restart boundaries are neither bypassed nor
claimed newly qualified by an unimplemented entrypoint.

## Discovery LP-01 — Admission ordering prevents the selected composition

### Statement

The existing four-reference admission cannot be constructed by the specified
Controller without source access before the claim and before the sole Worker mint.

### Source and evidence

At the exact base, `admission_v3.admit_initial_inline_v3()` authorizes the source,
requires a finalized PR observation, and unconditionally invokes
`acquire_git_file_admissions_v3()` and
`acquire_issue_reference_admissions_v3()` for the request's remote references
before returning `PreclaimAdmissionV3`. These readers require the concrete
same-token `GitHubSourceAuthorityV3` and `AUTHENTICATED_READ_ONLY` observations.
`PreModelControllerV3.run()` requires this complete admission before claim.

`GitHubPullRequestObservationReaderV3.observe()` returns only `_final`;
`finalize()` derives exact source feasibility from a `SubjectCaptureV2`.
Scope observation alone supplies no finalized admission observation.

The two executable witnesses in
`tests/test_issue70_live_prep_admission_boundary.py` exercise these actual modules.
The first records git-file, Issue-body and comment reads while the transport has
zero claim refs and reproduces the exact complete admission. The second proves
scope-only PR observation remains absent and a distinct control-token double
cannot substitute for the source token. All credentials/transports are fake.

### Existing authority

The owner mandate fixes Controller claim/reservation before Worker dispatch,
forbids Controller source acquisition and source-App mint, puts the sole source
mint inside the later Worker, and requires reuse of the existing RWP admission
and source authorities. It explicitly requires a bounded stop on an impossible
combination rather than an architectural substitution.

### Semantic disposition

`no-normative-impact`: this records a realization conflict among selected
experimental mechanisms, not a new product obligation or contract amendment.

### Affected layers

Architecture-or-implementation, integration-or-conformance,
verification-or-qualification-evidence, repository-governance-or-documentation.

### Related discoveries or consequences

Controller composition, exact active workflows and the new complete integrated
live-form simulation are stopped. The new concrete Controller authority and
Worker dispatch/ACK adapter are not claimed implemented. Independent adapter and
inert-registration work continues. LP-02 is independent.

### Required authority

A separate owner decision must reconcile the admission/credential ordering.
Neither changing the admission contract, pre-minting a token, using control
credentials for subject/reference reads, replaying #69 evidence as current
admission nor creating a provisional claim is selected here.

### Next action

Resolve LP-01 explicitly before implementing active orchestration. Then qualify
new exact-tree CI and original-process end-to-end execution with all mandated
negative cases. No live effect follows this partial candidate.

## Pinned Artifact operational adaptation

The official provider is `actions/upload-artifact` v7.0.2 at commit
`cf430e030ddbb5b0abf93d22962f4752f3646cd9`, with executable blob
`7b3f92ae681d6eeca5f5e5e4cf892ad0dfb254ea` for `dist/upload/index.js`.
Construction verified the exact Git HEAD, tree entry and actual file blob.
No helper upload was executed; no npm install is needed at live time.

The official bundled direct path assigns `name = basename(files[0])`, creates
one raw-file stream, and computes final size and digest from that stream.
The new child plan supplies `archive=false`, `overwrite=false`, retention 30,
exactly one file named after the deterministic artifact, and no added extension.
The directory is created 0700 and the file 0600. ZIP and observation JSON bytes
are not recompressed or wrapped. No overwrite or delete interface is exposed.

One instance consumes its opportunity before validation and cannot respawn,
including after refusal, timeout, signal or exception. Only local plan refusal
before spawn is REFUSED. After launch, every nonzero/exception/timeout is UNKNOWN.
The guard runs immediately before launch and after the opaque provider effect.
Guard loss may leave an orphan but grants no next journal effect.

Provider-internal retries are allowed **inside the one pinned child only**.
This is an explicit operational adaptation, not retroactive reinterpretation of
RWP-04's injected-boundary proofs. No per-provider-request broker atomicity or
cancellation is claimed. Child success is not Artifact metadata authority.
Independent complete REST observation, exact-attempt/job checks, authenticated
redirect resolution, credential-free storage download and original packet
reconstruction remain mandatory before the existing PREPARED CAS.

The child environment excludes GITHUB_TOKEN, GH_TOKEN, source token, private key,
owner approval variables, NODE_OPTIONS, PATH, proxies and Actions file-command
paths. Only Artifact runner variables, minimal locale/private HOME/TMPDIR and
exact INPUT values are passed. The official bundle reads ACTIONS_RUNTIME_TOKEN
and ACTIONS_RESULTS_URL; GITHUB_REPOSITORY/RUN_ID/SERVER_URL form output context.
No credential enters argv. Output is captured privately with a finite byte/time
budget, never interpreted as authority or copied to Issues/PRs.

## Discovery LP-02 — Runner environment bridge

- **Statement:** A normal shell run step does not receive the Artifact runtime
  environment that the Node action handler injects.
- **Source and evidence:** actions/runner commit
  `cf65f3ec8100ee0046d735ac5d647e00f4b8e817`,
  `src/Runner.Worker/Handlers/NodeScriptActionHandler.cs` versus
  `ScriptHandler.cs`; the former injects runtime token/results URL, the latter
  does not. The official upload bundle requires those values.
- **Existing authority:** The original Python Worker must be the helper's parent;
  no prepare/upload/continue split may manufacture continuation authority.
- **Semantic disposition:** `no-normative-impact`.
- **Affected layers:** architecture-or-implementation, integration-or-conformance.
- **Related consequences:** Future workflow wiring needs an explicitly verified
  runner-to-original-Python bridge, not assumed shell environment availability.
- **Required authority:** Existing construction mandate permits a launcher-only
  bridge; no new product semantics are needed. LP-01 still blocks composition.
- **Next action:** After LP-01 resolution, confront a minimal local pinned Node
  launcher that starts the single original Python Worker with runtime variables.
  No launcher or active workflow is installed in this partial candidate.

## Transition target identity, not actor attribution

The exact seven-field target basis is schema_version 1, evidence_type
`github-v3-journal-transition-target`, repository, repository_node_id, claim_ref,
predecessor_sha and successor_sha. Identity is the existing artifact identity of
canonical bytes followed by LF. Commit identity already binds tree/journal bytes.

Only a recognized 201 create-ref response or recognized 200/no-errors updateRefs
response associates this evidence with that operation. Lost/malformed/error
responses carry none. Historical predecessor authority independently rereads the
exact Git snapshot and recomputes the same target identity. This authenticates
Git target continuity, **not** a GitHub signature of the Worker/actor.

Current Actions authorization and journal guards remain separate. In particular,
lost mutation ACK plus authenticated equal target remains UNRESOLVED: historical
continuity never fills pending.writer_evidence_id. The unchanged RWP-05 pending
preservation tests remain required. No new rejection evidence is invented from
opaque GraphQL errors.

## Failure retention

Failure artifacts use `rb-v3-failure-observation-<64-hex>` and contain exactly
`FailureObservationV3.canonical_bytes`. The backend observes exact run/job/repo/
SHA, one matching name, positive Artifact ID, raw digest/size and dates. Within
an instance it pins the full first observed storage identity and rejects drift.
It then downloads raw bytes and compares the observation identity and links.
Remote observations additionally require the original packet ID supplied by the
independent original handoff, never copied from the observation being checked.

The backend is not original-observation provenance. Active RWP-05 still requires
recognized real-boundary origin, the original decision ticket, current Worker,
retention/readback and its sole CAS. Historical origin unavailability cannot be
replaced by Artifact existence. The stopped live composition supplies no new
operational failure-origin authority.
