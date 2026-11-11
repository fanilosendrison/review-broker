---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-02 Offline Authenticated Worker Binding"
version: "0.1.0"
---

# RWP-02 — offline authenticated Worker binding

## Scope and immutable base

This experimental implementation stops immediately after the first attributed
`PRE_MODEL_WORKER_BOUND`. It does not acquire sources, admit a packet, retain an
artifact, enter `PREPARED` or `ARMED`, invoke a model, or activate a workflow.
The Issue overlay selects experimental work; it is not normative authority.

```text
BASE_PR=81
BASE_SHA=2f32e78f8b00ba4598dc7b030e2e5fd43afd2add
BASE_TREE=ce178c442dcee0149f3e895a9d3b6a3d662d73e1
PR77_SHA=2c757eef954ff0c809adff331c31e28371f8624b
```

The preserved task worktree is detached at this exact base. The publication
head is `feat/issue70-v3-rwp02-worker-20261103`; its draft PR must target
`feat/issue70-v3-rwp01-controller-20261102`, never `dev`.
The corrected global naming convention permits Python importable modules.
No dotagents backup or historical worktree is modified by this task.

The preflight Project adapter reported that Issue #70 was absent from
Project #17. No Project membership or field was changed. That observation grants
no technical authority and does not alter the requested experimental scope.

## Components and permitted changes

Five existing modules change:

- `pre_model_controller_v3.py`: optionally request one ACK after the existing
  attributed reservation and sole dispatch; retain ambiguity without retry.
- `pre_model_control_v3.py`: append the ACK and retain existing transitions.
- `journal_record_v3.py`: recognize the strictly validated additive event.
- `github_journal_v3.py`: expose ACK CAS and enforce snapshot-bound authority
  when registering a Worker on an ACK-bearing claim.
- `github_actions_identity_v3.py`: opt-in initial Worker dispatch observation,
  without changing the default pull-request behavior.

New modules have distinct responsibilities:

- `pre_model_dispatch_ack_v3.py`: closed receipt and provenance-boundary protocol.
- `github_actions_workflow_dispatch_v3.py`: exact dispatch run/job checks.
- `github_actions_worker_authority_v3.py`: combine execution context, retained
  dispatch provenance, run/job observation and exact journal snapshot.
- `pre_model_worker_v3.py`: one binding operation and immediate stop.

Three mechanical extractions retain existing algorithms and public imports:

- `journal_history_v3.py`: strict history and transition-order validation.
- `github_journal_snapshot_v3.py`: authenticated snapshot decoding.
- `github_actions_jobs_v3.py`: complete run-attempt jobs pagination.

The additions also include the two RWP-02 test modules, this report and the
statically disabled Worker YAML. No historical test assertion is changed.
Public schemas, v1/v2 workflows, packet/retention/source modules and normative
contracts are unchanged. New and changed handwritten source files are at most
400 physical lines. The baseline's unrelated 404-line `admission_v3.py` remains
unchanged; this task neither fixes nor waives it.

## ACK contract and noncircular identities

`DispatchAcknowledgmentV3` has exactly these fields:

```text
schema_version = 1
evidence_type = v3-initial-dispatch-acknowledgment
broker_repository, broker_repository_id
request_id, attempt_id, claim_ref, reservation_id, generation = 1
reservation_commit_sha
worker_workflow_path, execution_ref, executable_sha
workflow_run_id, dispatch_response_evidence_id
```

The numeric identities must be strict positive integers; booleans are refused.
The Request/Attempt/claim/reservation relationship is reconstructed with the
existing identity functions. Unknown fields, unsupported versions, duplicate
ACKs and incorrect history ordering are rejected. There is no job ID or
invented run attempt in this receipt, and no credential or source payload.

The receipt ID is `artifact_identity(canonical_bytes(receipt) + b"\n")`.
The separate journal event ID binds event name, request, attempt, generation,
prior history count and the receipt itself. The receipt contains neither its
own ID nor the journal event ID. The response evidence identifies retained
transport observations; hashing them does not prove their origin.

The existing journal CAS writes the receipt into the same claim history:

```text
CLAIM -> PRE_MODEL_DISPATCH_RESERVED -> DISPATCH_ONCE
      -> PRE_MODEL_DISPATCH_ACKNOWLEDGED -> PRE_MODEL_WORKER_BOUND
```

The Controller's designated injected boundary must correlate the exact emitted
request, trusted transport, authorized Controller, observed response, positive
run ID and reservation. The journal then checks the exact reservation commit
and that boundary's authorization before using its existing transition CAS.
No new ref, business ledger, database or recovery generation is introduced.

## Three proofs, none interchangeable

1. **Dispatch provenance:** the authorized Controller won its reservation and
   the designated transport boundary observed its exact dispatch acceptance.
2. **Actions authentication:** an independently accepted execution boundary
   binds the entire context, inputs, boundary identity and job ID; the existing
   reader confronts authenticated run/job API observations.
3. **Worker authorization:** a verified ACK and reservation snapshot authorize
   one proposal; only its attributed `COMMITTED` CAS result confirms binding.

Dispatch principal identity comes from explicitly configured Controller trust,
not from the requester. Actor and triggering actor remain distinct observations;
both must match that principal for this initial-attempt path. `run_attempt=1`
is mandatory. Run ID, numeric repository/workflow IDs, workflow name/path,
observed head SHA, observed head branch, executable SHA, unique job identity and
complete job pagination must match. Caller-provided inputs or SHA values do not
replace these observations. `GET workflow run` alone does not attest inputs.

The new event requires explicit Worker opt-in. Ordinary runtime claims still
reject `workflow_dispatch`, preserving the previous non-Worker boundary test.
Only `pull_request` and this bounded Worker event are recognized.

The Worker authority binds the exact snapshot, ACK receipt ID, Actions evidence,
complete accepted context and dispatch principal. Its evidence cannot authorize
a different snapshot, reservation, generation or Worker. Synthetic legacy
Worker authorities cannot register a Worker on an ACK-bearing claim. Legacy
no-ACK journals remain decodable and usable only in their historical scope;
the new Worker refuses them before proposing CAS.

## Scenario matrix

All cases below passed offline. Test method names contain the exact case IDs.
The suite emits `artifacts/rwp02/scenario-measurements.json`, including each
variant's simulated dispatch/ACK/Worker attempt counts, committed mutations,
attributed winner, complete final journal, result classification and zero
source acquisitions/real GitHub effects. These are local test artifacts, not
remote execution receipts. Initial fixture construction is separately synthetic
admission setup; no source acquisition is part of the Controller/Worker path.

### Nominal cases

- N01: reservation, observed dispatch, ACK CAS and Worker CAS are attributed;
  one simulated dispatch, one ACK attempt, one Worker attempt, four mutations
  including claim creation; journal remains `REQUESTED`, Worker set.
- N02: a fresh interpreter reconstructs the identical ACK receipt ID solely
  from serialized journal bytes; cold retained provenance permits binding.
- N03: Worker starting inside dispatch observes no ACK; zero Worker mutation,
  zero Actions reads. Controller may subsequently confirm its original ACK.
- N04: two independent Workers propose from the same ACK; exactly one gets an
  attributed `COMMITTED`, the competing distinct-target CAS is rejected.
- N05: discovery after confirmed binding is observation only, not permission
  for another operation; no second Worker CAS occurs.
- N06: old synthetic journal round-trip bytes and independent reservation
  event digest remain unchanged. Existing compatibility suites also pass.

### Negative cases

- F01: another run ID, including a separately triggered matching run, refused.
- F02: same run ID with attempt 2 refused.
- F03: different Request ID refused.
- F04: different Reservation ID refused.
- F05: generation 0, 2, boolean or string refused.
- F06: wrong numeric repository identity refused.
- F07: wrong workflow ID, path or name refused.
- F08: run's observed executable SHA differs, refused despite matching claims.
- F09: wrong or missing observed execution branch refused.
- F10: missing/duplicate jobs, incomplete pagination, wrong job attempt or
  boundary job identity refused.
- F11: unauthenticated execution context refused without Actions reads.
- F12: requester substituted for actor or triggering actor refused.
- F13: HTTP 204 or absent observed run ID gives no positive ACK.
- F14: ambiguous dispatch gives no ACK and never causes redispatch.
- F15: applied ACK with lost acknowledgment stays `UNRESOLVED`; absent writer
  attribution cannot authorize Worker CAS or a repeated ACK mutation.
- F16: forged/unrecognized ACK refused; equal reconstructed Python requests
  or responses, wrong transport or wrong Controller cannot claim provenance.
- F17: duplicate, replaced or replayed ACK refused; unsupported fields and
  versions, boolean identities and added run attempt fail closed.
- F18: stale ACK snapshot cannot recover binding permission after another CAS.
- F19: byte-identical target commits still produce exactly one attributed
  winner; losing operation is `UNRESOLVED`, not authorized by readback equality.
- F20: interruption before ACK application, after application without response,
  or during Worker binding never causes automatic mutation repetition.
- F21: source-acquisition tripwires remain uncalled, including successful binding.
- F22: freely constructed environment-like context fields do not confer trust.
- F23: locally reproduced receipt hash without retained provenance is refused;
  no local digest is described as a signed GitHub attestation.
- F24: legacy no-ACK fixture refused by the new Worker; permissive historical
  Worker authority cannot bind an ACK-bearing claim.

## Race, restart and interruption interpretation

Only the synchronous operation's writer evidence permits a positive result.
An ACK-bearing snapshot still needs authenticated predecessor-writer evidence.
The test predecessor authority recognizes only acknowledged injected writes,
not arbitrary commit equality. Read-only observation cannot invent attribution
for a lost response. An uncertain operation remains uncertain without loops,
sleeps, timeout-based failure inference or automatic redispatch.

The same-target race uses a barrier solely to arrange the test interleaving;
its deadlock bound is not a production uncertainty timeout. Finite simulations
are not exhaustive GitHub concurrency or physical crash-durability proofs.
Cold receipt reconstruction does not qualify production response retention.

## Local verification and preserved historical evidence

Python 3.11 environments were created afresh in this task. The clean environment
installed only the project and its declared runtime dependencies; validation ran
with `PYTHONPATH` and `PYTHONHOME` unset. No pre-existing virtual environment is
a hidden prerequisite. The required focused suites, complete discovery,
compilation and whitespace checks completed successfully.

- RWP-02: 32 tests, including all 6 nominal and 24 negative case methods.
- RWP-01 regression: 20 tests.
- Actions identity: 13 tests; journal: 29 tests.
- Historical #70 composition: 13 tests.
- Historical #68 nominal/failure/recovery: 2/11/3 tests.
- Complete clean suite: **868 tests in 685.950 seconds, OK**.
- Two complete local suites passed; neither is substituted for exact-source CI.
- All 17 pertinent JSON/schema artifacts validate.
- Disabled YAML validates with maintained `js-yaml`; it has only
  `workflow_dispatch`, three inputs, empty permissions and one statically
  false job containing an inert `:` step. It never calls Python or a network.

The earlier 836-test RWP-01 result, CI run `41610589260`, independent GO and
`openai-codex-1 / gpt-5.6-sol / xhigh` receipt remain historical evidence from
PR #81. They are not recalculated or relabeled as RWP-02 evidence. Historical
Issue #68/#69/#70 fixture bytes and test assertions are unchanged. The two initially
failing construction checks are retained as RED evidence, not as validation
failures remaining in the final suite.

Clean full-suite log SHA-256:
`a676a7630a508e1c3d54eaf8331a663793492c3678800e2b759c81beeebcd21f`.

Clean RWP-02 log SHA-256:
`c0857c8f418fbca4d40954bd05f3cdf014e2a638d9d7f6770875af55497cdd32`.

## Qualification boundary and next gate

The implemented authorities are not production attestations. Synthetic dispatch
observations are owned by the injected test transport; its designated fixture
boundary preserves a trusted external observation archive. Synthetic execution
context acceptance is a separate pinned fixture boundary. Actions HTTP calls
use an injected API simulation; the new Worker refuses an implicit live reader.
The existing expected-old Git simulation arbitrates journal mutations. No real
GitHub journal mutation, dispatch, source token mint, source acquisition,
Codespace action or broker-model invocation occurs.

The offline scenario result is:

```text
RWP02_OFFLINE_WORKER_BINDING=PASS
REAL_WORKFLOW_PREPARATION=IN_PROGRESS
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
V3_PRODUCTION_ACTIVATION=NO
```

Overall task completion additionally requires exact published-source CI and a
fresh read-only independent GO on the final SHA/tree. This report does not
pre-assert those later receipts; they belong to the successor PR and qualified
Issue #70 handoff. Construction review is not a Review Broker invocation.

Before RWP-03, a separate mandate is required. Packet authority and technical
policy, remote retention, source acquisition and `PREPARED` remain outside
this tranche. Real execution boundaries, dispatch-response provenance retention,
provider permissions, operational admission and any bounded live effect require
their own later qualification and explicit owner authorization. The disabled
YAML on an experimental branch is not an operational workflow.
