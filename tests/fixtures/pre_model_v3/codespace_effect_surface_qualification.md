# #51 — Codespace effects, entry-point and preventive-gate source qualification

**NON-NORMATIVE, SOURCE-BONDED, TEST-ONLY. Does not authorize any v3 implementation,
resource start/stop, model invocation, GitHub App permission, or merge.**

## Source and executed evidence

- Production code snapshot: `dev` at
  `f9e902ee577d3a22330c3bf2fb04dcae28ed3034` (complete Git tree listing).
- Pinned inventory:
  `tests/fixtures/pre_model_v3/codespace_effect_surface_inventory.v1.json`,
  with **16 statically recognized effect/dispatch/proxy surfaces**, three
  supporting control-path files and each source's exact Git blob identity.
- Source scanner and 14 counterexamples:
  `tests/test_codespace_effect_surface_inventory.py`.
- Four real pilot identity/isolation tests:
  `tests/test_pilot_codespace_identity_exclusion.py`.
- [CI 41075380577](https://github.com/fanilosendrison/review-broker/actions/runs/41075380577):
  **585 tests, zero failed**, including 18 new inventory/pilot tests.
  One earlier candidate CI failed because the source scanner omitted the
  shared `run_synthetic_pilot_controller` wrappers used by pilots 04/05.
  The scanner was fixed; neither path was removed from the inventory.
- [Prior conditional preventive model](https://github.com/fanilosendrison/review-broker/pull/58):
  eight source/gate assertions, and PM01–PM35 on isolated v3 model
  (not actual deployed v3).

The test enumerates all `.github/workflows/*.yml`, package `*.py`
(including transitive pilot controllers) and `scripts/*.py|*.sh`
at this tracked snapshot, applying a **bounded static pattern
recognizer**, not whole-program semantic analysis. Unknown recognized
Codespace commands/SSH/CLI routes fail the inventory CI; injected
new-command fixtures also fail membership checks. An entirely new
obfuscated or dynamic invocation not matching those patterns is
outside this detector's proof. No result establishes which historical
executables are still running or which secret principal has authority.

## Verified source-route families

| Family | Source-confronted behavior | Gate/exclusivity disposition |
| --- | --- | --- |
| Normal review workflow | `review-request.yml` calls `internal-prepare` before direct Codespace start, followed by raw `gh codespace ssh/cp` and CLI cleanup | Existing v1/v2 sequencing **verified statically**. Mandatory v3 pre-side-effect gate **not installed** |
| Reconciler | `review-reconciler.yml` uses `review-broker-single-reviewer` and injects a Codespace token; `internal-reconcile` can issue a name-scoped stop through `reconciliation.py` | Same Actions group as normal review, but cannot prove global exclusive owner. Must classify v3 no-acquisition refusal before any cleanup |
| Independent control qualification | `codespace-control-qualification.yml` does direct start, SSH, copy, stop and failure cleanup; group `review-broker-codespace-control-qualification` differs from the review group | **Not serialized by the normal review group**. Hard-coded Codespace name `review-broker-reviewer-4q4v769jr65hjww9`. Equality to the *live* `vars.REVIEW_BROKER_CODESPACE_NAME` is **unverified** because the connected read API does not expose that variable |
| CLI and core transport | `cli.py` can independently invoke `internal-recover`, `internal-stop-codespace`, `internal-reconcile`; `codespace.py` provides name-scoped lifecycle, SSH/copy/recover; `execution_recovery.py` can stop a name-scoped Codespace | No v3 request worker generation guard in current code. A name-only Shutdown receipt is not an owner lease |
| Synthetic pilot 03/04/05 | Controllers call the same `run_synthetic_pilot_controller`, with **deterministic pilot-specific request/attempt IDs** and mandatory execution authorization matching **before transport.prepare**; the transport starts, uses OpenSSH/proxy, copies and stops | Pilot identity cannot be freely replaced by an unrelated v3 RequestID via authorization and still start. But `--codespace` may select a syntactically valid physical name; a fixed pilot identity is **not** an exclusive machine lease |
| Private-source/publication-only workflows | Source qualification sets Codespace credential empty; publication recovery does not issue Codespace effects | Excluded from effectful surfaces by the bounded scanner; negative control only |

### Actual pilot authorization evidence

The real `run_synthetic_pilot_controller` derives the fixed
pilot request and attempt from `pilot_fixture_03/04/05` via
`synthetic_pilot_identities`. It invokes
`authorization.require_matches(pilot_id,request_id,attempt_id,
review_broker_source_sha,broker_wheel_sha256,codespace_identity)`
**before** `transport.prepare()`. An intentionally mismatched
RequestID is rejected with zero fake transport calls in the
four new tests. No real Codespace or inference is involved.

Consequently, protecting v3 claim A does not automatically
require imposing the v3 journal protocol on *every unrelated*
administrative actor using the globally shared Codespace.
The qualification must, however, establish that such paths
**cannot act *as* A or bypass A's versioned worker identity**.
Their ability to collide physically with a legitimate
resource-owning review B is a different and still unqualified
**resource-exclusivity** concern.

## Minimal proof target — narrowly attributable to v3 claim A

The proposed permanent-refusal no-acquisition terminal is
valid without global machine shutdown **only if**:

1. A has trusted exact admission, journal version, permanent
   failure CAS, zero model invocations, and **no prior PREPARED**.
2. Every worker/CLI/reconciler action **attributable to that v3
   claim identity** has an enforceable, version-pinned, durable
   current-worker/reservation check before Codespace-affecting
   work, and cannot start before the committed PREPARED boundary.
3. All older or independently callable entry points that could
   impersonate A are *provably excluded* or share that same
   trusted gate. An out-of-band controller with a distinct
   synthetic/administrative identity need not be fenced on A's
   behalf merely because it touches the same physical machine.
4. The actual executable SHA, GitHub workflow identity,
   credential scope and mixed-version rollout are qualified;
   a mere source-code SHA or skipped-step log does not prove
   those deployment conditions.
5. No worker can bypass the pre-effect admission boundary
   through raw `gh` or OpenSSH, including the separate
   pilot/qualification/CLI surfaces **if** they can carry A's
   authority. Otherwise those unrelated identities remain
   separate and cannot be promoted as evidence of A's activity.

If any premise is unknown, remain `REFUSED_PERMANENT` / blocked;
do not infer non-acquisition, fabricate `Shutdown`, or stop the
shared Codespace. **No global lease is needed just to close a
provably non-acquiring A.** A resource-owning B still requires
a separate real exclusive-ownership check before cleanup.

The main architectural difference is **claim attribution versus
physical-resource ownership**. They must not be conflated.

## Required next real qualification, without new infrastructure

- Confirm the current, non-secret configured Codespace name
  and whether it equals the hard-coded qualification target.
  The value was **not retrievable through the current connected
  GitHub read capability**; do not infer equality.
- Qualify the actual deployable v3 request dispatch path, worker
  identity fencing and strict journal version rollout. Direct
  shell commands cannot be claimed protected by a Python
  `CodespaceController` guard unless the entry points are
  changed or excluded.
- Qualify source closure for the *specific* v3 claimant, rather
  than demanding a global new distributed lease for pilots
  that have provably distinct logical identities.
- Inject late-worker, direct-CLI, qualification-workflow,
  pilot and Codespace credential access counterexamples against
  actual v3 wiring. No deployed v3 exists yet.
- Assess separate physical Codespace ownership if multiple
  actors are allowed to control the same named resource.

**Disposition:** `GO_FOR_PINNED_CODE_SURFACE_INVENTORY_AND_PILOT_LOGICAL_IDENTITY`;
**HOLD for deployed universal or claim-scoped Codespace gate,
credential/executable authority and shared-resource exclusivity**.
The standard CI test suite proves the inventory's baseline and
the simulated counterexamples, not production runtime safety.

`BASELINE_SHA=f9e902ee577d3a22330c3bf2fb04dcae28ed3034`
`RECOGNIZED_EFFECT_SURFACES=16`
`SUPPORTING_BOUNDARIES=3`
`INVENTORY_NEW_TESTS=14_PASS`
`PILOT_IDENTITY_NEW_TESTS=4_PASS`
`FULL_CI_41075380577=585_PASS`
`CODESPACE_NAME_MATCH=UNVERIFIED`
`GATE_DEPLOYED=NO`
`LIVE_CODESPACE_INVOKED=NO`
`CODEX_INVOKED=NO`
`NORMATIVE_ACCEPTANCE=NO`
`MERGE_AUTHORIZED=NO`
