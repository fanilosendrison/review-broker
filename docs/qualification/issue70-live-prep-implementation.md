---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Partial Live Preparation Implementation"
version: "0.1.0"
---

# Issue 70 — Partial live preparation implementation

## Exact construction scope

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

The full local suite is running under private supervision. Exact final local
results, normal Ubuntu CI and independent review must be supplied by a later
exact-SHA PR receipt. They are not predicted by this document's own commit.
Compilation and initial whitespace checks passed. Final full-suite, JSON/YAML,
size, secret, diff and source-pin checks remain publication requirements.

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
