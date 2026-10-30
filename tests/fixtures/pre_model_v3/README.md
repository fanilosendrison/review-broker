# Issue #51 — candidate v3 pre-model contracts (test-only)

**UNACCEPTED / NONNORMATIVE / NOT INSTALLED / NOT EXECUTABLE BY REVIEW BROKER.**

This fixture directory defines **four non-normative closed Draft 2020-12 schema candidates**: the original broad pre-model journal prototype, a smaller v1-compatible journal migration candidate, and two receipt shapes.
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
