---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-05 Implementation and Stage 1 Evidence"
version: "0.1.2"
---

# Issue 70 RWP-05 — Implementation and Stage 1 evidence

## Authority and subject

This is an experimental offline implementation under the owner RWP-05 mandate,
not adoption of the PR #55 proposal or a public v3 contract. Product authority
remains the specification, versioned public schemas and accepted documents in
AGENTS.md order. Issue #70 and parent #67 select work and remain open.

Base PR #89 is OPEN/DRAFT/unmerged at SHA
`a7a4bcc2a21c3fa3961c7095e0c59b1bf1ecfd8e`, tree
`4fd57168bbb656a97c97340795094920f2097b19`. Its 1019-test Ubuntu PASS and
independent GO qualify that base only. Historical RWP-04 failed local runs and
NO_GO reviews are neither erased nor applied to a different candidate.

The successor targets #89's head branch, not dev. This report describes evidence
known before its commit. Final published SHA/tree, complete base-to-candidate
diff digest, exact tested checkout/tree, CI logs and independent review are
bound by the final successor-PR comment. A future identity is not predicted in
this document and its own commit does not qualify itself.

Related records:

- [Candidate architecture](../architecture/issue70-rwp05-failure-handling-candidate.md).
- [PM01–PM35 matrix](issue70-pre-model-pm-matrix.md), including exact E01–E21 test names.
- [RWP-04 implementation](issue70-rwp04-implementation.md), retained unchanged.

## Implemented responsibilities

The original attributed ADMITTED continuation issues one original-process
`ActivePreModelDecisionV3`. The capability is identity-bound, noncopyable and
nonserializable; genuine handoff consumption transfers it to RWP-04. A real
mutex arbitrates local failure/PREPARED selection and an exclusive handler lease
prevents two handlers from conserving evidence twice. Selected consumed state
permits only the chosen operation, not a second entry or a fallback.

Closed observations and a pure classifier cover exactly six experimental
reasons. Real Issue HTTP, clone/fetch, artifact upload/metadata/download and
completed remote verification boundaries preserve facts before diagnostic
reduction. Injected independent authorities confront actual requests and plans;
a valid payload, put or hash alone does not create provenance.

Original canonical observation bytes are recognized, retained outside the
Worker, read exactly and recognized again before one BLOCKED CAS. Lost retention
ACK permits readback only. The existing journal transition/CAS and the shared
internal guarded writer are reused; there is no second CAS algorithm. Strict
BLOCKED validation is separate from unchanged permanent-receipt validation.

The historical reader authenticates real B and direct parent A by SHA/origin,
applies the actual pure transition and compares complete canonical bytes, then
reconstructs the original observation/receipt. It never issues a ticket or a new
observation. Journal commitment, cause availability and active permission remain
separate. Failed control also fences existing journal-bound preparation helpers
before Git/file I/O; read-only historical reconstruction remains separate.

## Validation observed before publication

Environment: Python 3.11.9, macOS 10.13.6 x86_64, isolated editable installation
loading this worktree's src, jsonschema 4.26.0 and rfc8785 0.1.4. Dependency
installation and pip check succeeded. No Docker, Homebrew or shared-runtime
modification was used.

Commands executed from the private task worktree:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src
```

The full local run completed **1086 tests in 4261.819 seconds**: 1074 executed,
12 Linux-only skips, no failures. Log SHA-256:
`36b17d3d3f93a9300b8617ce12a6f4bb4e8823209219e5967d3b8755abf0f3e0`.
This is not a no-skip Linux PASS. The twelve unchanged RWP-03 network-isolation
witnesses require normal Ubuntu CI on the published final tree, as do the cold
RWP-04/RWP-05 cases under the effective Linux filter.

The final preparation-fence/Git/journal targeted run passed 14 tests in 120.531
seconds. A subsequent phase-cut measurement extension explicitly records
remaining authority and whether the journal still points to A: three tests
passed in 341.966 seconds. Its log SHA-256 is
`afedf34aadd4d48135df64d91b980cb2fe5a1eb380d23a1b3657644e509675c0`.
Unused newly introduced imports were subsequently removed. After the independent
R1 finding and correction below, a new full local run passed **1090 tests in
3743.354 seconds**, with 1078 executed, twelve Linux-only skips and no failures.
Its log SHA-256 is
`b982440eebd85b39bd87cc264a17a2795998c3d8d67c39be01af933d620a30d2`.
The corrected reconciliation/Git/journal targeted run passed 55 tests in 149.132
seconds; its complete four-test R1 module then passed in 36.074 seconds. Final
CI must cover the corrected published tree, not inherit earlier-tree acceptance.

Compilation, parsing every JSON file under schemas/profiles/programs, and
`git diff --check` passed. All changed handwritten Python modules/tests are at
most 399 physical lines. Public schemas, adopted contracts and operational
workflows were not changed. Final size/diff checks remain publication gates.

Initial normal Ubuntu 24.04/Python 3.11 CI passed on source candidate
`5f4ee4f307db7d91339c8b4c338a9f44755ef48e`, tree
`caace23b837721c3366ff47f851141df5f901417`:
[run 42229015539](https://github.com/fanilosendrison/review-broker/actions/runs/42229015539),
job `127929779929`, attempt 1. The logged checkout was
`b53cfc7a0aeb8642fc0ac4500d92968567b3b813`; its authenticated Git tree exactly
matches the candidate. All **1086 tests passed in 1199.081 seconds, zero skips**,
including all twelve Linux isolation witnesses and required cold RWP-04/RWP-05
cases. Install, compileall and JSON validation also passed. Log SHA-256:
`314acf3810f729a2e17d10e11cee083f54dcba8b19aaa4bc85feab41ea4285b6`.

This is a prior-commit result. Independent Pi review is NOT_RUN, and this evidence
update changes the tree. Fresh final-tree CI and GO are still required; global
RWP-05 and Stage 1 qualification remain NOT_QUALIFIED until the final PR receipt
establishes both. No prior-tree acceptance is silently transferred.

## F01–F23 evidence map

E references resolve to exact test names in the PM matrix, including E21's
corrected thrown-read reconciliation witnesses. Tests execute real
candidate canonicalizers, decoders, transition functions, readers, verifier,
continuations and journal code. Fixtures simulate external services and their
trust, not a replacement broker state machine. Service-side proposals, HTTP
payloads, mutations, upload/retention counts and exact journal bytes provide
oracles beyond reason strings.

| Obligation | Evidence | Demonstrated scope |
| ---------- | -------- | ------------------ |
| F01 | E06 | Six reasons, every fact/check/status variant, closed fields, strict numeric/null/time grammar, canonical LF identities and independent permanent golden bytes/ID. |
| F02 | E06 E07 E08 E09 E10 | No generic error/status/hash/put authority; real recognized ambiguity does not imply absence; upload priority spans complete reconstruction. |
| F03 | E07 | Rehashed identity/target/phase/packet/artifact forgeries and final-receipt tampering refuse before Git creation. |
| F04 | E08 | Missing/corrupt/unrecognized original proof blocks CAS; lost put ACK with exact readback succeeds with one put. |
| F05 | E02 E03 E05 E07 E08 E16 | Original attributable A required; copied/forged results, stale context and restarted ADMITTED producers cannot mint usable permission. |
| F06 | E08 E13 E14 | Direct/copy/subclass refusal, two-handler lease, both local choice orders, replay and interruption after selection permit one entry only. |
| F07 | E08 E09 E10 | Genuine reference 503, clone/fetch timeout with confirmed process-group termination, metadata 503 and precise metadata/storage timeouts commit exact TRANSIENT/BLOCKED. |
| F08 | E08 E10 | Real comment 404, composed unknown upload and four completed remote divergence checks commit UNKNOWN/BLOCKED, not packet success. |
| F09 | E01 E02 E03 | Claim/reservation/dispatch/ACK/binding/admission cuts and lost responses preserve original outcomes, without a new pre-A failure writer. |
| F10 | E04 E10 E14 | One upload; absent/unique/ambiguous reconciliation, metadata/download faults and divergences respect precedence; only full original-packet verification resolves UNKNOWN. |
| F11 | E04 E16 | Irreversible PREPARED entry; uncertain/applied/no-attribution and attributed/later-loss outcomes never cause failure repair. |
| F12 | E11 | Concrete GitHubTransportLiveV3/FakeGitHubApi POST blob/tree/commit; after movement, no following GET/POST or CAS. Positive selected-consumed operation completes. |
| F13 | E11 | Movement after last identity observation fences actual GraphQL emission; emitted HTTP 200 permission errors remain indeterminate, not source permanence or local success. |
| F14 | E12 | Actual simulated acquisition process, reference response and first persistence write may finish, but no next effect/upload/PREPARED follows a competing attributed refusal. |
| F15 | E13 | Actual pure BLOCKED/permanent and PREPARED successors race the same expected-old in both winning orders; no loser retry. |
| F16 | E13 | Equal/different failure proposals, known/lost ACK, equal-content ambiguity and post-B replay produce one disposition and one event. |
| F17 | E13 E21 | Before/after application cuts, lost ACK, GraphQL errors and unavailable readback retain pending; reconciliation does not mutate. |
| F18 | E13 E21 | Equal B without origin remains UNRESOLVED; delayed recognized write can reconcile COMMITTED; recognized expected-old rejection remains REJECTED; old A is not non-application proof. |
| F19 | E15 | Separate interpreter after full Worker-root deletion recovers original IDs/time from independent service stores; forbidden counters zero. |
| F20 | E08 E15 | Lost/corrupt/rejected cause preserves authenticated historical BLOCKED with UNAVAILABLE/REJECTED cause status, never reopens RESERVED. |
| F21 | E13 E15 | Bad parent/origin, canonical/control/history corruption, version loss and coherently rehashed observation/receipt/history forgery are rejected by real decoding and SHA history reads. |
| F22 | E16 | BLOCKED/permanent rediscovery, old/new Worker, generation 2, copied failure result and future operations have no new effects; old preparation helpers reject failed control before I/O. |
| F23 | E17 E13 | 26 before/after phase cuts plus post-choice cuts record proof/ticket/remaining-authority/outcome/disposition/counters; outside-catalog faults never manufacture BLOCKED. |

The F15/F16 journal-component races provide canonical transition and CAS
premises explicitly; they do not claim to mint active authority from those
premises. E08/E14 separately qualify genuine original active-ticket orchestration.
Likewise an excluded positive terminal/recovery scenario receives no PASS from
these negative future-operation witnesses.

## Construction discoveries and corrections

### Failed-control preparation fence

- **Statement:** Newly decodable ADMITTED/BLOCKED passed older state-only
  preparation checks and could perform new preparation I/O after failure.
- **Source and evidence:** The real-source failure scenario first committed B.
  A test then exercised the actual authorized builder and legacy retention,
  preparation-receipt and retained-authority helpers against current B. The
  preserved RED log showed 14 Git reads, new retention/receipt files and 46
  authority file reads; the legacy authority returned true. Positive component
  controls used the actual current A before the failure CAS, never a fake head.
- **Existing authority:** Owner mandate sections 4.1 and F22 require no new
  acquisition/preparation after failure. The candidate remains experimental;
  no adopted public semantics are changed.
- **Semantic disposition:** no-normative-impact; this is an implementation and
  evidence correction for the already-selected experimental behavior.
- **Affected layers:** architecture-or-implementation,
  verification-or-qualification-evidence, repository-governance-or-documentation.
- **Related consequences:** Original-process guards alone were insufficient for
  newly supported failed control passed to older journal-bound helper APIs.
- **Required authority:** Existing mandate authorization; no new product decision.
- **Impacts:** Shared pure open-control validation now guards those helpers;
  active policy verification checks its eligible domain before its first I/O.
  Historical observer verification is unchanged and does not obtain active rights.
- **Next action:** Preserve the RED/GREEN witness and subject the correction to
  final Ubuntu regression and the prescribed exact-tree independent review.

The reusable regression is
`test_F22_failed_control_is_rejected_before_authorized_git_or_legacy_packet_writes`.
The bounded fix rejects failed control rather than changing legacy receipt bytes,
introducing a new policy or requiring maximal internal model attestation.

### Other retained construction evidence

The first fixture accidentally replaced inherited integer commit_calls with a
list. Its trace was retained and the new measurement list became proposal_calls.
This was a fixture defect, not evidence of a product CAS failure.

The first two-handler test observed two external retention puts. An exclusive
failure-handler lease on the genuine ticket fixed that race; the regression
now proves one put and one journal entry. Original failing and corrected logs
remain separate evidence.

Removing the existing concrete HTTP before_effect guard temporarily made F12's
blob/tree/commit subcases and F13 fail (four failures across two tests), including
four following GET requests after commit. Restoring the source byte-for-byte
returned the tests to PASS. The negative sensitivity log is retained; no mutant
source is published. These intentional RED runs are not mislabeled full-suite
failures or removed from the evidence archive.

### Independent R1 — pending evidence lost on thrown reconciliation reads

- **Statement:** A thrown immediate post-CAS read discarded the enriched pending
  operation from the failure result, despite its consumed ticket.
- **Source and evidence:** The [independent NO_GO](https://github.com/fanilosendrison/review-broker/pull/90#issuecomment-6687752384)
  is bound to SHA `6cae20fefc577a17ada95085ff07f0f35f80b73b`, tree
  `50e214de5678eb252e3816e1108d0ee006abc187`. Its 1086-test CI remains a PASS
  only on that tree; it did not cover thrown concrete ref/matching-ref reads.
  The new original-ticket tests reproduced pending loss at both HTTP edges,
  with acknowledged/lost CAS responses, plus origin/authority-read exceptions.
- **Existing authority:** Mandate sections 6.3, F17/F18 and PM12/20/35 already
  require preservation of pending and read-only reconciliation after uncertainty.
- **Semantic disposition:** no-normative-impact; implementation/qualification fix.
- **Affected layers:** architecture-or-implementation,
  verification-or-qualification-evidence, repository-governance-or-documentation.
- **Related consequences:** The old PM12/20/35 evidence did not cover this case;
  E21 and the corrected full regression are now required. No historical verdict
  is rewritten into GO.
- **Required authority:** Existing owner mandate, no new protocol decision.
- **Impacts:** A coherent read-only reconciliation module now owns the existing
  algorithm. The shared transition retains each recognized pending enrichment
  before later verification; thrown observations return UNRESOLVED, never a
  retry permit. Invalid external pending authority remains fail-closed.
- **Next action:** Fresh corrected-tree Ubuntu CI and independent review.

E21 also proves recognized expected-old rejection evidence survives a thrown
readback, then reconciles REJECTED. A known writer can later reconcile COMMITTED;
without its ACK even authenticated equal B remains UNRESOLVED. All cases retain
exact intended/predecessor identities, a consumed ticket, four HTTP mutations
(blob/tree/commit/CAS), one logical failure CAS and unchanged counters during
reconciliation. The first reproduction fixture incorrectly lost ADMITTED's ACK;
that output is retained separately, and the corrected RED applies loss only to
the post-A failure CAS. Corrected RED/GREEN evidence is preserved privately.

## Historical 21-case prototype confrontation

Both owner-announced inputs were present and matched their announced hashes:

- Prototype Python SHA-256:
  `376b60b82f02b365741fe8bb4ed1bfd9d05d89a30ef0391c9bf04fd4753580ad`.
- Prototype report SHA-256:
  `fba732bd9f570e1886ae3527fc95c3a1e693ea5ce0b2b3adc78964441aa331c9`.

An unmodified reproduction passed 21/21. Its log SHA-256 is
`f3f81db0b94ab3dfbcfa028631d5c034ff9fc7979f170b24a5cf77f48ccdb8fc`.
That is prototype-only evidence: its simplified JSON/packet model is not the
production canonicalizer, renderer or verifier. The following integration map
qualifies boundaries with actual candidate code, not by transferring 21 verdicts.

| Prototype case | Integrated witness |
| -------------- | ------------------ |
| 01 fresh process | E05 and E18 destroy the actual Worker root and reproduce original manifest, inventory and remote receipt. |
| 02 deletion | E04 loss/expiry preserves PREPARED while readback is unavailable. |
| 03 wrong name | RWP-04 observation artifact-filter test and E10 post-ACK absent rejection. |
| 04 duplicate name | RWP-04 observation/receipt pagination cases and E10 ambiguity. |
| 05 replacement ID, same bytes | E19 test_proto05_same_name_new_id_serves_identical_bytes_but_not_original_receipt routes and downloads the replacement before receipt mismatch. |
| 06 changed ZIP, matching digest | E19 test_proto06_changed_zip_and_matching_authenticated_digest_still_changes_commitment. |
| 07 changed bytes, old digest | RWP-04 test_Q09_exact_remote_zip_digest_truncation_extra_bytes and E10 archive comparison. |
| 08 repository identity | RWP-04 test_Q06_Q08_artifact_filter_repository_run_digest_size_dates. |
| 09 run attempt | RWP-04 test_Q08_each_run_attempt_workflow_sha_and_job_binding. |
| 10 run head | Same RWP-04 exact workflow/run/job identity witness. |
| 11 changed future expiration | E19 test_proto11_future_expiration_metadata_change_is_not_silently_recommitted. |
| 12 expiry | E04 preserves commitment and reports UNAVAILABLE; E10 does not invent a catalog cause after ACK. |
| 13 wrong predecessor | RWP-04 test_Q17_changed_parent_unrecognized_writer_admission_or_binding and exact-SHA Git reader. |
| 14 different Worker | RWP-04 exact attempt/job binding and E07 original-packet/plan forgeries. |
| 15 altered source, matching digest | E19 test_proto15_proto16_remote_source_or_missing_member_with_matching_digest_refuses. |
| 16 missing member | Same E19 test, separate missing-member branch. |
| 17 receipt mismatch | E19 reconstructs an otherwise valid original packet but rejects changed remote receipt commitment. |
| 18 later loss keeps PREPARED | E04 and E16 distinguish immutable commitment from availability. |
| 19 incomplete pagination | RWP-04 test_Q07_incomplete_duplicate_cycle_scope_count_and_bad_ids. |
| 20 missing complete enumeration | RWP-04 R2 future-last and terminal-drift regressions. |
| 21 wrong attempt endpoint | RWP-04 exact attempt-specific Actions identity and pagination checks. |

Preserved RWP-04 R1/R2/R3 tests still check validate-before-directed-read,
complete coherent pagination and original genuine-handoff packet identity before
upload. Additional source/reference/policy/prompt/inventory/path/ZIP-budget
falsifications remain in the full suite. No historical model or feasibility
result asserts a live backend, token scope, deployed uploader or production GO.

## Stage 1 bounded assessment and remaining gates

Observed integrated witnesses cover actual common Controller, one reservation,
one injected dispatch, ACK, one bound Worker, original attributed A, authorized
policy/source/reference packet, one simulated upload, original-packet remote
verification, PREPARED and a fresh cold reader. Four-reference and empty-reference
variants preserve exact original manifest, inventory, offline and remote receipts.

Recognized catalog failures after A, all outside-catalog cuts, pre-A ambiguity,
post-choice irreversibility, local and Git races, original packet integrity,
independent original-proof retention and restart-only observation are demonstrated
within the simulated-service configuration. No actual reviewed repository code
is executed. Cold Linux isolation passed on the initial CI tree and remains a
required final-tree regression.

At this revision:

```text
RWP05_OFFLINE_FAILURE_HANDLING_AND_QUALIFICATION=NOT_QUALIFIED
REAL_WORKFLOW_PREPARATION=NOT_QUALIFIED
READY_FOR_BOUNDED_LIVE_PLAN=NO
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
EFFECTIVE_CODEX_POLICY=NOT_ATTESTED
```

The remaining construction gates are fresh final-tree Ubuntu CI with no required
skips, substantive Pi GO on that same tree/diff, final evidence publication and
verified handoff. Initial exact-tree Linux regression closes PM17.A. The matrix
now has 35 witnessed PASS, zero FAIL/BLOCKED and 30 OUT_OF_SCOPE subcases, with
prior-commit CI identities and corrected E21 local evidence explicitly separated. Excluded positives remain excluded after
construction acceptance; final-tree gates remain common to every required row.

Even after bounded Stage 1 qualification, a live plan needs separate owner
mandate and explicit treatment of:

1. Operational uploader and original-observation archive implementations,
   immutability, retention, exact readback and bounded transport budgets.
2. Independent live source/plan/observation, Actions, writer/origin and executable
   authorities, exact credentials and least-privilege permissions.
3. Protected exact-revision trigger/controller/Worker wiring, deployment inventory
   and exclusion of stale execution paths; no unqualified universal gate claim.
4. Exact admitted source, operator configuration, concurrency/at-most-once budgets,
   uncertainty disposition and private evidence handling.
5. Separate Codespace/lifecycle/non-acquisition/terminal and model-invocation
   admission/qualification; none is established by this pre-model tranche.

The task makes zero real Worker dispatches, prepared/observation uploads,
operational journal mutations, consumer source acquisitions, Codespace effects
and Review Broker model invocations. Publisher and independent construction
review model calls are distinct construction effects. Generation 2, specialized
STOPPED, ARMED, result publication, normative adoption and activation are not
implemented. No merge, dev integration, Issue closure, Project mutation or #83
change is included. Issue #70 remains absent from Project 17; no item was added.
