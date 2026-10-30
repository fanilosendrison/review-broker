# Issue #51 — v3 rollout, legacy workers and Codespace credential boundary

**NON-NORMATIVE / READ-ONLY QUALIFICATION.** This report does not approve a
GitHub App permission change, repository secret mutation, workflow rerun,
new claim ref, Codespace operation, Codex inference, production schema,
implementation or PR merge.

## 1. Authenticated read-only evidence

Repository: `fanilosendrison/review-broker` (private, default `dev`).
Production baseline: `f9e902ee577d3a22330c3bf2fb04dcae28ed3034`.

A two-page GitHub Actions REST read on 2026-10-30 returned **154** workflow
run records when the attached historical manifest was made.
Exactly **18 completed runs** named `Review request` were found; they
used **8 distinct executing commit SHAs**. Their exact IDs, event type,
executing SHA and first-run status are pinned in
`legacy_review_request_run_inventory.v1.json`.

The observed history also contained **6 completed `Review reconciler`
runs** (5 distinct executing SHAs) and **5 completed independent
`Codespace control qualification` runs**. A separate Actions-status
read observed **zero `in_progress`, `queued`, `pending` and `waiting`
workflows** at that instant. This is **not a permanent worker-fence
certificate** and says nothing about a process still running
inside a Codespace.

GitHub [re-run documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
states that older workflows can be rerun within 30 days of their
first run using the **original `GITHUB_SHA` and `GITHUB_REF`**.
Consequently current `dev` alone is NOT a proof that all older
binaries are permanently excluded.

## 2. Replayed actual historical ReviewRequest admission code

The 8 historical `Review request` SHAs all use exactly **two source
blobs** for `src/review_broker/request.py`:

| Historical parser family | Verified Git blob SHA | Accepted versions |
| --- | --- | --- |
| Older | `dc5eee76967778ca9d3a417bc5ac96ce02e9b013` | v1 only |
| Later | `e156c6669d14e9d2b8b0ffbd9091686e3fe14500` | v1 and v2 only |

Original exact source files are committed under `tests/fixtures/pre_model_v3/`
as `legacy_request_v1.py` and `legacy_request_v1_v2.py`.
Their original Git blob hashes are asserted in
`tests/test_legacy_request_v3_fence.py`. Tests import and
execute the actual historical parser bodies (against the
current installed identity/schema dependencies), confirming:
**schema_version 3 is rejected, the v3 Issue marker is rejected,
and a v3 payload cannot be smuggled inside an accepted v1/v2 marker.**

GitHub source reads also verified the **four historical
`review-request.yml` workflow blobs** associated with these eight
SHAs. All call `internal-prepare` **before the first Codespace
start**, have no v3 Issue marker, and retain the normal
`review-broker-single-reviewer` concurrency group. These
workflow observations are source-confronted but are not
separately replayed as complete historical workflow binaries
in the test runner.

**Narrow conclusion:** an observed old `Review request` run, including
a rerun at its original SHA, cannot process a *genuine*
schema-v3 request **through that original request parser**.
It may still legitimately operate Codespace for an old
v1/v2 request — a separate physical-resource concern.

## 3. Important independent risk: old reconciler sees claim refs

The real reconciler scans two inputs independently:
1. the open Issue list, validated via the old request parser;
2. **all Git refs** under
   `refs/heads/review-claims/` through
   `matching-refs/heads/review-claims/`,
   including refs without a live matching Issue.

At all **5 observed reconciler executing SHAs**, the source is
consistent on this exact old prefix and
`GitHubRefJournal._claim_ref()` also generates
`refs/heads/review-claims/<request-digest>`. The current
`AttemptRecord.from_dict` can read hypothetical future
journal-v2 fields and silently re-serialize as v1 without
`pre_model_control`, as directly reproduced in draft PR #57.

**Therefore request-parser version rejection by itself is NOT
sufficient isolation if v3 claims share the existing Git-ref
namespace.** The old reconciler can reach a claim by ref alone.

### Minimal proposed isolation, without a new scheduler

Use **disjoint version namespaces** (proposal, not adopted):

```text
refs/heads/review-claims/<digest>      # existing v1/v2
refs/heads/review-claims-v3/<digest>   # candidate future v3
```

The sibling `review-claims-v3/` is deliberately **not** a child
of `review-claims/`. A proposed v3 claim must never be written
to `refs/heads/review-claims/v3/`, because that **would** fall
inside the old scan. New v3 controllers must use strict v3
claim decoding and a versioned CAS; old v1/v2 workers and
journals remain unchanged.

The [nine offline namespace tests](https://github.com/fanilosendrison/review-broker/pull/58)
verify the real old journal namespace, the actual old
reconciler's v3-Issue rejection with a mocked ref listing, and
the safety difference between sibling and nested prefixes.
The experiment neither creates a Git ref nor proves GitHub
will permit a new branch namespace. Read-only GitHub API
returned **6 refs** under `review-claims/` and **zero**
under `review-claims-v3/` at observation. A repository-rulesets
read returned HTTP 403 with an account/plan feature error;
therefore **ruleset or create-ref acceptance has NOT been qualified**.

## 4. Credentials and execution entry points: exact source claims

The [13 current-source credential and rollout tests](https://github.com/fanilosendrison/review-broker/pull/58)
qualify only workflow **declarations**, not deployed
effective secret privileges:

- `review-request.yml` sets `GH_TOKEN=github.token` and a
  separate source token for `internal-prepare`. It does
  **not** inject the dedicated
  `REVIEW_BROKER_CODESPACE_TOKEN` into that prepare step,
  and first places it in a later admission check,
  followed by Codespace start/SSH/copy/stop steps.
  The current start step is conditional on successful
  preparation and still has **no v3 gate**.
- The separate `review-reconciler.yml` deliberately
  supplies the Codespace token to `internal-reconcile`;
  that code can inspect and **stop by resource name**,
  so a claim-scoped v3 non-acquisition proof must not
  assume this separate actor had no access to the machine.
- `codespace-control-qualification.yml` independently
  holds a Codespace credential, uses its own Actions
  concurrency group, and can start/use/stop its
  **hard-coded** Codespace name.
- The pilot 03/04/05 transport inherits credential
  behavior from its invocation environment and can
  select a syntactically valid Codespace identity,
  but its fixed synthetic request identities are
  checked before transport preparation.
- The CI workflow does not inject a Codespace credential,
  and the source-qualification workflow explicitly
  clears `REVIEW_BROKER_CODESPACE_TOKEN`.

GitHub documents that [secrets are exposed by explicit action
inputs or workflow/step environment](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets),
and repository/organization secrets are read when a workflow
run is queued. **Step-scoped token absence is not a proof of
global secret revocation or of a token's actual effective
scope.** The current connector did **not** permit inspecting
the configured non-secret `REVIEW_BROKER_CODESPACE_NAME`
variable, the real secret values, their token permissions, or
environment protection rules.

## 5. Two different guarantees; two different acceptance gates

### A. Non-acquisition by a permanently refused v3 claim

The narrowly sufficient approach is:
- an exact v3 admission and unique v3 claim ref namespace;
- strict v3 journal decoder plus permanently recorded refusal
  *before* any PREPARED transition;
- a mandatory version-pinned worker/claim gate before all
  **Codespace effects attributable to that v3 identity**,
  with no unguarded caller able to impersonate that identity.

Under these premises, a late legacy v1/v2 ReviewRequest does
not become v3 worker A, the old reconciler cannot find A's
journal, and a refused A never acquires Codespace through
the trusted broker. **No exhaustive negative step-log review
or global machine stop is needed for A's terminality.**

**This is design direction, not deployed fact:** no v3
worker, claim namespace, journal codec or side-effect gate
has been installed. Verified command/credential closure and
source-complete independent review are still required.

### B. Exclusive physical ownership during a real review

An old valid v1/v2 workflow or unrelated pilot may still
start/stop the same *physical* Codespace. A fixed pilot
RequestID does not prevent physical collision. Actions
concurrency protects workflows in the **same** group, not
the independent Codespace qualifier, manual CLI actions or
possibly lingering remote processes. The configured review
Codespace variable and qualifier's hard-coded name could
not be compared with authenticated live config.

This **separate resource-owning** concern remains HOLD,
particularly for cleanup of a Codespace actually acquired
by another request. Do not let it reintroduce a blanket
global-Shutdown requirement for **non-acquiring A**.

## 6. Disposition

**GO — exact historical parser v3 rejection, old-namespace discovery
boundary and current declared step-token scoping**, with explicit
source/SHA limitations. **GO_FOR_NON_NORMATIVE_DISJOINT_V3_REF_DIRECTION**.
**HOLD — operational new-ref permissions/rulesets, exact v3
worker gate, old-run credential authority, remote processes,
physical Codespace equality/exclusivity and normative migration.**

The final test-only branch CI is linked in PR #58; the
source snapshot originally added 9 historical parser tests,
13 credential/rollout tests and nine namespace-isolation tests.
No existing root schema, `src/review_broker`, GitHub Actions
workflow, credential or runtime is modified by these files.

`LEGACY_REVIEW_REQUEST_RUNS_SNAPSHOT=18`
`LEGACY_REVIEW_REQUEST_SHA_COUNT=8`
`LEGACY_PARSER_BLOBS=2`
`LEGACY_RECONCILER_SHA_COUNT=5`
`V3_LEGACY_PARSER_ACCEPTANCE=REJECTED_BY_TESTS`
`LEGACY_JOURNAL_REF_SCAN=review-claims/`
`PREFERRED_V3_CLAIM_REF=review-claims-v3/`
`V3_REF_CREATED=NO`
`V3_REF_PERMISSION_QUALIFIED=NO`
`DEPLOYED_WORKER_GATE=NO`
`SECRET_CONTENT_READ=NO`
`CODESPACE_CONTROLLED=NO`
`INFERENCE_INVOKED=NO`
`NORMATIVE_ACCEPTANCE=HOLD`
