# Issue #51 — candidate v3 pre-model contracts (test-only)

**UNACCEPTED / NONNORMATIVE / NOT INSTALLED / NOT EXECUTABLE BY REVIEW BROKER.**

This fixture directory defines **five non-normative closed Draft 2020-12 schema candidates**: the original broad pre-model journal prototype, the smaller v1-compatible journal migration candidate, two existing receipt shapes and a new no-Codespace-access terminal evidence candidate.
They do **not** live under the root `schemas/` directory and are not loaded by
`reviewctl`, a running reconciler, a production workflow, or a Codespace.

- `journal-v2.candidate.schema.json`: version-separated journal with
  request/attempt state, evidence history, single dispatch generation,
  reservation, worker identity and terminal preparation disposition.
- `journal-v2.compat.candidate.schema.json`: **preferred minimum migration experiment**; the exact serialized v1 `AttemptRecord` field names and existing state/event `history[]` entries remain, plus only the new `pre_model_control` field and version discriminator. No extra `packet_evidence_id`.
- `failure-v1.candidate.schema.json`: bounded PERMANENT/TRANSIENT/UNKNOWN
  pre-model failure receipt with explicit reason, observation and generation.
- `recovery-v1.candidate.schema.json`: owner-recovery authorization *shape*
  with nonce, predecessor reservation, authenticated actor-ID claim and
  prior-run evidence pointer. The JSON contents alone never authenticate a user.
- `no-codespace-access-v1.candidate.schema.json`: **v3-only alternative to shutdown evidence** for permanent refusal before any Codespace access; binds exact worker/run/claim, trace and mandatory start-gate evidence references. The receipt shape alone cannot prove those external facts.

The isolated reference implementation is `tests/reference_pre_model_v3.py`;
the test suite `tests/test_pre_model_v3_reference.py` uses its model, **not**
production v3. It reuses production `review_broker.identity` for RFC 8785
canonicalization and attempt IDs, and production `evidence` validation for
the shutdown receipt. GitHub-ref persistence, distributed CAS, App permissions,
GitHub run identity, owner authentication and shared Codespace ownership are
**injected simulated trust boundaries**, not independently established facts.

**Observed prototype-to-production representation differences:** this candidate
journal adds an explicit `packet_evidence_id` and uses a uniform, experimental
`history[]` event shape. The present production v1 `AttemptRecord` has
neither this top-level packet field nor that exact history format. A real
v3 implementation would need a separately reviewed mapping or a smaller
representation that retains the original evidence-ID/history semantics.
The current fixture cannot be installed as a drop-in schema or serve as
a complete migration specification. The current legacy decoder also
accepts future-version records and drops unknown fields, as shown in PR #57.

## Follow-up: smaller migration and external-authority comparison

The preferred **minimal** v2 candidate is tested by
`tests/reference_v1_journal_migration.py` and
`tests/test_v1_journal_migration_reference.py` (12 new tests).
The test wrapper calls the *real production* `AttemptRecord.as_dict`,
`AttemptRecord.from_dict` and `queue.transition_record`, checks
canonical byte-roundtrip, preserves legacy publication/artifact fields
and history entries exactly, rejects unknown journal versions and
unknown fields, and tests competing in-memory CAS writes. A historical
`PREPARED` packet receipt is already retained in `history[]` and
`evidence_ids`: the extra prototype `packet_evidence_id` is not
required for this candidate.

**Important intermediate state:** current production transitions to
`ARMED` while `invocation_count=0` and then writes the invocation
count separately. The compatibility candidate accepts that intermediate
record. A separately accepted v3 implementation must either preserve
these transition/transport guarantees or explicitly combine the writes,
but must **never infer Codex transport occurred solely from ARMED**.

The companion `tests/test_v3_external_authority_inputs.py`
(15 tests) uses an injected GitHub metadata provider, not GitHub
network. It falsifies incorrect repository/workflow/run/head identities,
mismatched worker reservations and missing run observations. A positive
test only means the **supplied** metadata agrees; it is not proof the
real GitHub principal, App scope, worker or Codespace owner was
authenticated. This remains a real-world qualification gate.

**GitHub API fact:** Since February 2026, the Actions workflow dispatch
endpoint optionally accepts `return_run_details: true` and can return
`200` with `workflow_run_id`; without it, the documented response
is still `204` with no run details. Both a missing run ID and a lost
response are unresolved for exact worker correlation, **not authority
to redeliver**. Required readback must bind the returned run ID to
exact broker repository ID, workflow ID, head SHA and run attempt.

**Codespace authority gap:** a Codespace API name/repository/state
observation does **not by itself** supply a cross-request exclusive
workflow owner/lease. A GitHub Actions concurrency-group name is a
scheduling constraint on workflows, **not** a universal resource-lease
certificate covering out-of-band controllers. Stopping the shared
Codespace still needs independently qualified global ownership
evidence or must remain blocked. These tests intentionally refuse
to infer a lease from API metadata alone; an injected matching
lease flag is a conditional **model assumption**, not an
implemented ownership verifier.

For source evidence:
- GitHub workflow dispatch REST specification:
  https://docs.github.com/en/rest/actions/workflows
- GitHub Actions concurrency documentation:
  https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- GitHub Codespaces REST specification:
  https://docs.github.com/en/rest/codespaces/codespaces

**No real GitHub ref race, worker run correlation, external CAS, App
permission, crash or Codespace ownership is qualified here.** The
candidate is test-only and not a drop-in production journal parser.

## Follow-up: separate attempt finality from shared Codespace shutdown

The accepted *historical* Review Broker v1/v2 `STOPPED` rule requires
a genuine `Shutdown` observation. That rule must not silently change.
The v3 design now explores a **specialized terminal refusal** after
`REFUSED_PERMANENT` and strictly before `PREPARED`, if the attempt
**provably never acquired the shared Codespace**.

The current installed workflow calls `internal-prepare` before the
first Codespace `start` step; its post-run stop is gated on
`steps.start.outcome != 'skipped'`. Those facts support a
**possible** no-Codespace-access route, not a live v3 proof.
Pre-packet GitHub source reads are not Codespace acquisition.

The isolated reference now has:

- `MemoryClaim.assert_codespace_start_permitted`: **effectful
  Codespace access may be authorized only after `PREPARED`**, from
  the currently bound worker; old/refused workers are fenced out.
- `MemoryClaim.finish_without_codespace`: a **test-only v3
  refusal CAS** that binds a correctly shaped, identity-matching
  no-acquisition receipt, without calling or stopping Codespace
  and without fabricating `Shutdown` or a model result.
- `tests/test_no_codespace_acquisition_reference.py`:
  **PM26–PM35** (10 cases) plus three static workflow checks.
  A different request's Codespace may remain `Available`
  when A is properly terminalized **without touching it**.

**Critical authority limit:** the tests *inject* authenticated
complete run trace, qualified mandatory start fence and knowledge
of every potentially dispatched worker. A test's positive boolean
is **not** an authenticated GitHub Actions run inventory, nor proof
that every deployed worker or out-of-band path respects the start
gate. Missing/ambiguous run, start or worker observation must
remain blocked. A refusal **before any worker is registered**
has not yet been qualified by the candidate receipt and requires
separate evidence or remains blocked.

If a Codespace side effect was attempted or its outcome is
unknown, do not use this receipt or terminalize A as a proven
non-acquirer. Acquiring-resource cleanup still requires an
independently qualified exclusive owner/Shutdown boundary.
No distributed lease is introduced merely to close a refusal
that never acquired the Codespace.

GitHub Actions CI run 41064672091 first demonstrated
**559 total PASS** including the ten new PM cases and
three static workflow checks. The final README-only follow-up
retains the same test-only scope.

## Follow-up: preventive gate proof, not exhaustive skipped-step inspection

The [source-confronted conditional gate tests](../../test_codespace_nonacquisition_gate_basis.py)
read the **actual existing** `review-request.yml`,
`review-reconciler.yml`, `orchestration.prepare_issue`,
`reconciliation.py` and `codespace.py`. They confirm that the current
main review workflow prepares before its first Codespace start,
that the dedicated Codespace token is absent from the
`internal-prepare` step, and that the present Codespace start
step has **no v3 journal-side access gate**. The reconciler
and the independent `internal-stop-codespace` CLI entry point
are additional effectful routes. Therefore **the deployed broker
does not yet meet the candidate universal gate premise**.

For a *future* v3, there is a simpler, narrowly scoped proof:

1. All deployed, eligible **trusted** worker/executor revisions
   and Codespace-affecting entry points enforce the same mandatory,
   durable `PREPARED` + current reservation/worker/generation
   guard **before every Codespace side effect**.
2. The exact workflow/executable version, old-worker exclusion,
   transitive entry-point closure and pre-preparation Codespace
   credential confinement are independently qualified.
3. The exact journal permanently refused this attempt while
   still `REQUESTED/ADMITTED`, with zero invocations and
   **no past `PREPARED` transition**.

Given **all** these premises, no trusted broker-owned path can
have acquired Codespace for that refused attempt. A late worker
will also fail at the side-effect gate. An exhaustive enumeration
of `skipped` workflow steps is therefore **not a necessary
separate proof obligation**, although authenticated Actions
run/step records remain useful diagnostic evidence.

All of these positive "gate qualification" premises are
**injected Booleans and placeholder SHA values in the tests**:
they are not established by green CI or by a GitHub jobs API
response. A single unchecked CLI/reconciler path, unisolated
older worker, mismatched executing code identity, or missing
credential confinement makes the inference fail closed.
Out-of-band/third-party access to the **global** Codespace
is not ruled out, but is irrelevant to the scope of *this*
attempt's no-access terminal; no shared-machine stop occurs.

The earlier first-stage
`no-codespace-access-v1.candidate.schema.json` receipt requires
a run trace and registered worker. It remains a historical
experimental candidate that is **too strong as a default** if
the preventive gate is actually proven. Its final minimal
receipt basis needs a separately reviewed revision binding
immutable journal/refusal evidence and the audited gate/
executable/rollout basis; **no normative schema is adopted**.

**Actual code comparison, separate from these tests:** draft
PR #57 also exercises real `CodespaceController.stop` and
`stop_and_observe_shutdown` with wholly fake `gh` transport.
The former stops by Codespace name only; the latter binds
the returned `Shutdown` observation to the caller's request
ID without authenticating exclusive request-level ownership.
This is the current bounded behavior, not an observed live
cross-request incident.

A complete real v3 `AttemptRecord` contract must also close the production
admission/result/publication/evidence structures, the exact trusted versions
of those schemas and its migration path. This journal fixture deliberately
restricts terminal behavior to the **pre-model slice**; it is not a complete
successor of all `TERMINAL_CAPTURED`, `VALIDATED`, `REPORTED` and indeterminate
execution paths.

A passing PM01–PM25 reference test would show only that the **model**
satisfies its own bounded assertions. It does **not** show real PM01–PM25
fault injections on the installed broker, or that an older deployed
v1 journal reader cannot overwrite future v3 controls. The current-code
hazards were separately reproduced in test-only PR #57.

Design upstream: draft PR #55
`docs/architecture/pre-model-preparation-failure-protocol-draft.md`.
No schema migration, permission change, model invocation or merge is
authorized by these artifacts.
