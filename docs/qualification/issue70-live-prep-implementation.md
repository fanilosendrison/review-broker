---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Partial Live Preparation Implementation"
version: "0.2.1"
---

# Issue 70 — Partial live preparation implementation

The sections preceding **Owner-resolved completion candidate** preserve the
historical PARTIAL report at 5041cc2 and its old NO_GO. They are not claims about
the resumed implementation or its later CI/review. The owner decision resolves
the old conflict without rewriting that history.

## Historical exact construction scope

Base PR #90 remains draft/unmerged at
`4f715fc6bd52fc5dac87a2f660ba8d2bf535e811`, tree
`016b2b91b1f42eb7d78280634c15e499ae295d2a`. Observed dev is
`64ee8062c5016cdc5a862b49b8acea18eec0aab4`, tree
`93655e2dc29f0860a79abaacd782d449de23660a`; both workflow registration paths were
absent there. No dev mutation or persistent-checkout synchronization is allowed.

The [architecture candidate](../architecture/issue70-live-prep-operational-adapters-candidate.md)
records the exact independent adapters and LP-01/LP-02 discoveries. LP-01 stops
the active Controller/Worker composition, not the independent components. This
report does not declare the owner mandate complete or request a live-effect GO.
No historical qualification report, public schema, accepted contract or old test
assertion was modified to accommodate this partial result.

## Implemented and stopped boundaries

Implemented construction subjects are the pinned synchronous direct-upload
boundary, live REST/storage executors, shared exact-byte Artifact reader,
separate failure-observation Artifact archive and deterministic Git transition
authority. The latter specializes rather than changes the legacy live transport;
legacy transports still provide no writer evidence. Pending reconciliation is
unchanged, including equal-target lost-ACK UNRESOLVED behavior.

No active workflows, Node runtime bridge, live Controller authority, concrete
initial dispatch/ACK adapter or internal Controller/Worker CLI entrypoint is
installed. The existing Worker remains disarmed. Consequently the new complete
live-form Controller-to-PREPARED simulation and C01–C15/W01–W15/deployed WF active
gates are **not qualified**. Existing RWP-01 through RWP-05 simulations remain
regressions, not substitutes for that missing composition.

The separate registration branch changes only:

- `.github/workflows/v3-pre-model-controller.yml`
- `.github/workflows/v3-pre-model-worker.yml`

Both are workflow_dispatch-only with exact mandated inputs, empty permissions,
one correctly named/keyed job, ubuntu-24.04, job-level false and one inaccessible
colon command. They contain no action, checkout, secret, variable, upload or
write permission. Schema equality to a new active workflow is not claimed:
those active workflows are stopped. The schemas match the exact owner mandate.

## Executed offline witnesses

The initial 14 focused tests passed in 0.271 seconds. The two new integrated
Artifact tests passed in 100.874 seconds. The combined final focused set passed
**20 tests in 103.651 seconds**, zero failures/skips, using Python 3.11.9 in an
isolated editable environment on macOS. No live source token, provider upload or
operational dispatch was used.

- `test_issue70_live_prep_admission_boundary.py`: actual admission records all
  three remote-reference reads while zero claims exist; qualified PR scope alone
  cannot provide final source feasibility; control-token substitution refuses.
- `test_issue70_live_prep_artifact_child.py`: pinned constants and negative Git/
  actual-blob verification; one-file direct plan, basename, overwrite false,
  retention 30, environment allowlist and private creation modes; one call only;
  nonzero/signal/timeout/exception UNKNOWN; no respawn; post-effect authority
  withdrawal leaves only an orphan; bounded private output and actual local
  harmless child timeout. The official upload code is never executed in tests.
- `test_issue70_live_prep_artifact_integration.py`: actual RWP-04 packet and
  archive through the new child boundary with provider-only doubles, independent
  REST metadata/storage and PREPARED CAS, including lost child ACK with exact
  read-only reconciliation. ZIP bytes and digest remain identical. A genuine
  RWP-05 catalog observation passes the new separate direct JSON archive/readback
  and metadata substitution refusal; this does not qualify a new live failure
  origin or an operational BLOCKED composition.
- `test_issue70_live_prep_http.py`: concrete opener receives authenticated 302
  without following it; storage uses a separate opener and header-free request;
  size limits and credential-bearing storage requests refuse before I/O.
- `test_issue70_live_prep_journal.py`: independent closed identity oracle;
  recognized 201/200 evidence only; malformed, error and lost responses provide
  none; equal target retains pending with absent writer evidence; wrong direct
  parent and force refuse; historical exact bytes are independently reread;
  deterministic target identity never bypasses a denied actor guard.

These are finite component witnesses. They do not claim every A/J/C/W/WF live
case has been qualified. In particular, full new active-journal movement and
stale-expected-old integration remain future composition gates; legacy RWP-05
regressions preserve their original scope.

## External source confrontation

Construction acquired the public official upload repository in private ignored
storage at the exact mandated commit. `verify_upload_helper_v3()` verified Git
HEAD, exact tree blob and actual file bytes successfully. The official direct
implementation uses the single file's basename, raw stream, hash and length.
Bundled runtime configuration requires ACTIONS_RUNTIME_TOKEN/RESULTS_URL; it does
not require the control/source tokens. Provider retries stay inside that one
pinned child. This construction observation is not a live provider run and does
not establish runner-to-Python wiring; LP-02 records that remaining boundary.

The first full local suite remains under private supervision on its initial
source and contains the known isolation failure below; it cannot qualify the
corrected source. Exact final local results, corrected normal Ubuntu CI and
independent review must be supplied by a later exact-SHA PR receipt. They are
not predicted by this document's own commit. Compilation and initial whitespace
checks passed. Full-suite, JSON/YAML, size, secret, diff and source-pin checks
remain qualification requirements.

## First exact-tree CI failure and bounded correction

The first draft #93 source was `8784a461601b57a23c3dde965d91c304b190714d`,
tree `3bcb9038c94a2d70136f8cf97d4b17901c3ce922`.
[CI run 42271271901](https://github.com/fanilosendrison/review-broker/actions/runs/42271271901),
job `128076155621`, completed **FAILURE**: 1110 tests in 1723.539 seconds,
one assertion failure. Compilation/JSON steps were skipped, not passed.
The failure and complete logs are retained, never relabeled PASS.

- **Statement:** The added authority imported the concrete transport outside its
  repository-reserved import boundary, violating the unchanged isolation oracle.
- **Source and evidence:** The actual CI failure and focused local RED both name
  `test_v1_v2_modules_do_not_import_live_v3_transport`. This is task-attributable,
  not an unrelated failure or a defect in the test.
- **Existing authority:** The existing import-isolation regression and mandatory
  v1/v2 preservation apply; test relaxation or hidden/dynamic import is forbidden.
- **Semantic disposition:** `no-normative-impact`.
- **Affected layers:** architecture-or-implementation,
  verification-or-qualification-evidence, repository-governance-or-documentation.
- **Related consequences:** Prior source is not qualified; no independent GO
  exists for it. The new component regression assertions remain unchanged.
- **Required authority:** Existing in-scope correction authority; no product or
  repository-governance rule change.
- **Impacts and correction:** Colocate the guarded concrete specialization at the
  existing concrete transport boundary. Keep target authority protocol-injected,
  with no concrete transport import. Extract immutable Git commit assembly into
  one coherent responsibility using the existing method-delegation pattern;
  source path ownership remains single-source. The original transport remains
  evidence-free. No journal/CAS/reconciliation algorithm is replaced. No import
  spelling is hidden or concatenated, and no historical oracle is changed.
- **Verification:** The unchanged three-test isolation module and complete
  44-test legacy concrete transport corpus pass after correction. Full new
  component tests, existing guarded HTTP/RWP-05 tests and corrected exact-tree
  CI remain required. The existing isolation test is the regression witness;
  a duplicate would add no new coverage. The global bug registry is outside
  this task's worktrees and is not modified.
- **Next action:** Publish the correction through the governed publisher, run
  new complete exact-tree CI and obtain the prescribed independent review.

Separately, the observed 1723.539-second full corpus leaves little margin inside
its previous thirty-minute CI job budget. The corrected candidate raises only
that finite budget to forty-five minutes. This is a no-normative-impact
qualification-capacity adjustment, not a claim that the first failure was a
timeout: it was the isolation assertion above. Runner, action pins, permissions,
commands, test count and every assertion remain unchanged. No test is skipped
or weakened. No operational workflow receives an enlarged effect budget.

The failure-archive component is also tightened to require an independently
supplied original packet ID for remote observations. A coherently rehashed
observation cannot supply that expected ID to itself. The integrated witness
checks mismatch refusal before spawn, followed by exact positive raw readback.

## Independent registration publication

Draft stub PR [#92](https://github.com/fanilosendrison/review-broker/pull/92)
was published only through governed publisher run
`01M6S1GMD7F5Z8HCPRAPKBK4G7`, using conditional absent-ref creation based on exact
dev. No manual commit/push, bootstrap ref, force update or default-branch change
was used. Stub HEAD is `294b6b88e5b5d0d131a690dc6196495549065b3e`, tree
`49b856732daf5e4b1a004b0ff3c6052d6953476f`.

Normal Ubuntu CI [run 42270110612](https://github.com/fanilosendrison/review-broker/actions/runs/42270110612),
job `128072165301`, concluded SUCCESS. Its logged synthetic merge checkout
`049f0ea14598effd06afef2e9250d32361e2a8a5` has that exact stub tree, verified
through authenticated Git-object readback. Independent review remains pending.
The registration PR remains draft/unmerged; passing CI does not install it.

## Remaining disposition

```text
LIVE_PREP_OPERATIONAL_ADAPTERS=PARTIAL_CONSTRUCTION_CANDIDATE
PRIMARY_LIVE_PREP_IMPLEMENTATION=NOT_QUALIFIED
LIVE_EFFECTS=0
READY_FOR_OWNER_LIVE_EFFECT_MANDATE=NO
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
EFFECTIVE_CODEX_POLICY=NOT_ATTESTED
V3_PRODUCTION_ACTIVATION=NO
```

The owner must resolve LP-01 before resumption of the active orchestration
subset. No alternative credential/admission architecture has been silently
selected. The future [specimen plan](issue70-live-prepared-specimen-plan.md) and
[effect budget](issue70-live-effect-budget.md) remain plan-only and blocked.

No ReviewRequest/subject/reference fixture, qualification secret/variable,
source-App permission/install, source token mint, Controller/Worker dispatch,
Artifact upload, journal/claim mutation, Codespace, ARMED or Review Broker model
invocation occurred. Construction review/publisher model calls are distinct.
No merge, Issue closure, Project mutation, generation 2 or next live task follows.
Useful worktrees and private evidence must be retained on this PARTIAL outcome.

## Owner-resolved completion candidate

The resumption task is
ISSUE70_LIVE_PREP_LP01_LP02_RESOLUTION_AND_COMPLETION, based exactly on
5041cc267612035a9dc7883fcb2a6f337751acfe / tree
e8a513cc6cddc0b6e8a3b86caf121e6d998e81a6. The same worktree/private evidence and
existing PR #93 branch are reused; PR #92 files, branch, title and body are frozen.
Its exact registration-only GO stays separate from the new primary gate.

The [architecture resumption](../architecture/issue70-live-prep-operational-adapters-candidate.md)
records the dual-phase owner decision and Node24 bridge. The implementation uses
real source/admission/Controller/transition/ACK/Worker/packet/receipt/decision/
retention/cold-reader code. Only external HTTP, credential issuer and Artifact
process/network boundaries are doubled in the new composed witnesses.

### Responsibilities and fences

- github_live_runtime_v3 and github_actions_controller_authority_v3 authenticate
  protected source/context/owner/input/Issue gates. A source-produced original
  admission moment is required; pure canonical bytes do not recreate it.
- github_actions_initial_dispatch_v3 consumes the existing Controller's original
  attributed reservation opportunity once. Its exact 200 details are candidates,
  never Worker identity. No timeout/204/malformed response causes redispatch.
- github_actions_dispatch_ack_v3 reconstructs closed immutable observations from
  GitHub Actions plus the journal, deriving the actual principal. Correlated
  Controller run/workflow/job IDs bind original successful outcome for ACK11.
- live_source_admission_v3 and github_initial_history_v3 construct actual complete
  preclaim admission with A and complete twice-confronted history before claim.
  Worker B proves the same logical scope but uses a separate concrete secret.
- pre_model_ack_start_gate_v3 waits read-only before source mint/binding. The
  Controller start gate is also read-only and precedes mint, with no provisional
  claim. Both actual entrypoints repeat their own context checks.
- The local Node24 action validates three literal dispatch inputs, passes an
  environment allowlist and starts one original Python, with no provider/domain
  logic, npm dependency, runtime download, pre/post or respawn.
- live_pre_model_worker_v3 composes the existing RWP chain, not a YAML replacement
  state machine. OriginalAdmissionEnvelopeV3 has no byte-completeness or permit
  claim; only original attributed A hydrates the exact complete admission through
  the shared retained-byte restorer. B freshly captures the subject; mutable
  reference comparisons and immutable Git semantics remain unchanged.
- github_policy_authority_v3 recognizes the broker-owned pinned definition and
  original selection against actual journal/Actions context. Source content is
  not approval; selection requires the genuine original decision. Historical
  policy observers cannot select. Effective Codex policy stays NOT_ATTESTED.
- cold_packet_observer_v3 uses an independently API-verified private corpus outside
  the packet. It has no effect-capable transport or credentials. The qualified
  Linux seccomp primitives are shared without changing their existing oracle,
  syscall list or denial requirements. A fresh observer can recollect proof after
  original Worker/subject roots disappear; it never renews sources or a ticket.

The concrete Git Database implementation has one canonical shared provider and a
historical compatibility facade, not hidden imports or duplicate algorithms.
Existing v1/v2 routes lazily avoid v3 operational providers. Journal operation
hooks establish fresh expected-old/missing-ref scope at each actual write; the
existing transition/CAS/reconciliation algorithms and lost-ACK distinctions stay
intact. Immutable observed Git and completed dispatch DATA are reused without
caching a mutable Worker/ref permission. Conditional GETs require fresh server
304 validation; errors/POSTs/redirects/Link responses never become cached success.

### Executable qualification register

- LP01-01–05/16: test_live_prep_dual_source, actual Controller/admission/claim/
  reservation/dispatch/ACK; provider counters assert claim absence throughout
  source admission and zero source-after-first-write or wrong-credential use.
  Token strings differ, logical scope/authorization IDs match, and each
  permits_token accepts only its own secret.
- LP01-06–10: wrong App/install/scope/permissions refuse; issuer policy refuses A
  reuse as B. This is not a claim that stable logical IDs prove secret inequality.
- LP01-11–15: complete composition and worker_fail_closed cover fresh exact B
  capture, HEAD/PR-object drift and changed expected-digest body/comment before
  any packet/upload. No Controller subject snapshot is reused.
- D01–D13: dispatch_authorities uses genuine Controller results and externally
  observed runs, exact URLs/payload, one POST, malformed/lost/204 ambiguity,
  identity faults, actual-principal derivation and cold recognition. Bare
  transport calls and a new authority with copied admission bytes refuse.
- ACK01–ACK12: ack_start_gate covers visibility lag, Controller terminal success,
  bounded expiry, wrong inputs/run/ref/SHA/origin, one emitted POST after loss,
  genuinely applied ACK CAS with lost response and zero gate mutation/source.
- LP02-01–12/14: real Node launcher tests and maintained YAML parser oracles cover
  metadata, exact one Python, allowlists, private-key refusal, execPath, exit and
  no respawn; active YAML has no split continuation or post-launch mutation.
- LP02-13/15: real harmless child reports original Python parent PID; metadata
  Git also receives no source/control credential. The restarted ADMITTED probe
  starts a distinct interpreter with genuine provider data but zero source,
  helper, ticket or journal effect. Historical reconstruction survives deletion
  of Worker, Controller capture and both subject roots without new acquisition.
- Full live-form four-reference and empty-reference witnesses preserve original
  packet/remote receipt into PREPARED and independent historical reconstruction,
  zero invocations and STOP_BEFORE_ARMED. Failure HTTP503 is actually retained/
  read back before the unique original BLOCKED CAS; unavailable retention emits
  no BLOCKED. Baseline RWP-01–05, permanent goldens and pending evidence remain
  unchanged regression oracles.

The first complete witness exposed a cold corpus admission-permits argument
mismatch after real PREPARED. The failing output is retained; correction uses the
same original admission/request binding. A full replay passes. An early new test
also expected ValueError where the existing Actions validator raises its typed
RuntimeError; only the new test expectation was corrected, preserving rejection.
No historical assertion was edited.

The initial genuine nominal composition measured 185,923 simulated HTTP calls,
not live traffic. Duplicate context observations were removed; immutable object
and historical dispatch data plus standard HTTP validators reduce read cost
without cached mutation rights. Read-reuse tests require fresh ref observation,
changed target detection, credential partitioning, no stale-on-403 and no POST
cache. This is no-normative-impact realization/conformance evidence, not live
quota/latency qualification. Actual public helper pin verification runs without
upload. CI provisions that exact public build dependency and Node24; tests use
no real credential. PyYAML is an exact test-only extra, not a live dependency.

### Qualification status and publication

Focused runs, full local results, exact new normal Ubuntu CI (all twelve Linux
witnesses without skip), final source/tree/diff and a fresh read-only
openai-codex-1 / gpt-6.1-sol / high review must be bound by the later PR receipt.
This document does not predict its own final commit or declare that pending
review GO exists. Earlier component GO, failed CI, PARTIAL/NO_GO and source trees
remain separate historical facts. The 45-minute CI budget is unchanged.

No real Controller/Worker dispatch, A/B source mint, fixture/request Issue/PR,
Artifact upload, operational claim/journal write, Codespace, ARMED, model or
result effect is authorized or performed. No owner variable/secret, App
permission/install, default branch, dev, Issue lifecycle or Project field changes.
The future specimen/budget remain plan-only. READY_FOR_OWNER_LIVE_EFFECT_MANDATE,
if later jointly established, means a separate bounded owner mandate may be
considered, never that live PREPARED, production or model readiness is qualified.

### New independent NO_GO and original-instance correction

The first completion candidate was SHA
1ddc5dfa70631a94099c6d29bd216a1a02866e41, tree
4088398af9478ffaf7c4c2af5a330d7b770603ca. Its exact normal Ubuntu CI
[42326963685](https://github.com/fanilosendrison/review-broker/actions/runs/42326963685),
job128264378342, passed1149 tests in1369.913 seconds without skips, including all
twelve Linux witnesses and Node24.22.2. Synthetic checkout d2f489ddf2086fcee844fa14f95140d8ea10f280
has that exact tree. This PASS did not qualify the two subsequent copy-replay
counterexamples. The [fresh independent NO_GO](https://github.com/fanilosendrison/review-broker/pull/93#issuecomment-6701105210)
is preserved unmodified on that source; old5041cc2 history also remains unchanged.

Both discoveries are no-normative-impact implementation/verification corrections
under the existing owner mandate, affecting original-instance provenance and
at-most-one effects, not a new protocol or product decision. Their controlling
requirements are source-production provenance, single original reservation
opportunity and no permission recreation through copies. Required authority is
this task's explicit in-scope correction/requalification mandate.

- R1: a shallow-copied bound transport shared its lock but not its attempted/
  permit booleans. During a genuine dispatch HTTP observation, the copy bound the
  still-active Controller issuance and emitted a second POST. The real-source
  RED observed two POSTs, not merely a source hypothesis. Correction rejects
  copy/deepcopy/serialization, checks original transport and Controller identity
  at binding and consumption, and consumes shared original-Controller state under
  its mutex. A copied per-transport boolean is never the consumption authority.
- R2: a source-session copy retained closed=false plus the genuine issuer/result
  after the original closed. A fresh receiver accepted that expired registration.
  The real-source RED observed that acceptance and an incorrect receiver inside
  the genuine source-production moment. Correction rejects copying/serialization,
  binds exact producing session and exact receiving authority, and atomically
  consumes/clears the issuer/result/receiver once under the source mutex. Closing
  also invalidates every registration field. No credential/fingerprint is stored.

The two original regression oracles in
`test_live_prep_original_instance_replay.py` produced two expected RED failures
before correction and passed with the original positive Controller flow intact.
Those oracles were preserved and additional copy/serialization checks were added.
They observe genuine source and attributable reservation moments; instrumentation
calls the actual original methods and doubles only external provider observations.
Copy, deepcopy, serialization, wrong receiver, post-close reuse and total POST
count are explicit oracles. A focused correction run passed31 tests, including
RWP01 and concrete source/dispatch invariants. No historical test was relaxed.
The owning repository report preserves the validated lesson; the global bug
registry is outside this task's authorized worktree and is not modified.

The first local full run remains diagnostic if edits overlapped it; its source
manifest decides exactness. Fresh corrected-source full validation, CI and a new
independent review are required. No GO is transferred from the earlier tree.
