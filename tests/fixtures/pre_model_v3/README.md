# Issue #51 — candidate v3 pre-model contracts (test-only)

**UNACCEPTED / NONNORMATIVE / NOT INSTALLED / NOT EXECUTABLE BY REVIEW BROKER.**

This fixture directory defines three **closed Draft 2020-12 candidate wire
schemas** for the narrow pre-model slice of the proposed v3 request lifecycle.
They do **not** live under the root `schemas/` directory and are not loaded by
`reviewctl`, a running reconciler, a production workflow, or a Codespace.

- `journal-v2.candidate.schema.json`: version-separated journal with
  request/attempt state, evidence history, single dispatch generation,
  reservation, worker identity and terminal preparation disposition.
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
