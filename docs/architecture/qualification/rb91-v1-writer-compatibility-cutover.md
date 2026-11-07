---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "RB91 Legacy V1 Journal Writer Compatibility and Cutover Gate"
version: "0.1.0"
---

# RB91-JQ-001 — V1 writer compatibility: implemented guard vs operational cutover

**Status: implementation PR #100 DRAFT / CI-confirmed source-level behavior; J-CH v2 admission NOT AUTHORIZED.**

This report is narrow implementation evidence for [Issue #97](https://github.com/fanilosendrison/review-broker/issues/97) and [architecture #91](https://github.com/fanilosendrison/review-broker/issues/91), not an approved v2 journal schema, migration, security review or operational enablement. The companion J-CH design remains [Draft #94](https://github.com/fanilosendrison/review-broker/pull/94).

## Confirmed code-level guard

The accepted v1 `AttemptRecord.as_dict()` format is unchanged. Its `from_dict()` now requires the **literal integer 1** at top-level `schema_version`; a missing, boolean, noninteger or future version fails before v1 parsing. The required v1 field set is closed, with only `admission` and `input_capacity` optional; an extra top-level `protocol_id`, `arm_binding` or other future metadata fails rather than disappearing on v1 reserialization. The decoder checks field container types, count `0/1`, and exact semantic round trip to reject lossy inputs.

In `GitHubRefJournal._read()`, a v2/unknown record causes a `ValueError` from the decoder, which the existing journal adapter transforms into `StateTransitionError("JOURNAL_CONTENT_RESPONSE_INVALID")`. A subsequent `claim`, `get`, `get_snapshot`, `transition`, `record_invocation`, `record_capacity`, `record_terminal_capture`, `record_stopped` or `record_publication` therefore fails before its first journal write. Offline adversarial tests use synthetic v2/hybrid ref contents and verify **no POST/PATCH** occurs. No real v2 ref was written for this qualification.

## Source inventory (observed, not full privileged-actor census)

| Journal-capable surface on `dev` | Existing code path | GitHub Actions workflow SHA / risk |
| --- | --- | --- |
| `.github/workflows/review-request.yml` | `reviewctl internal-prepare`, `internal-input-capacity`, `internal-arm-authorize`, terminal/evidence/result/stop commands through shared `GitHubRefJournal` | `contents:write`; event `issues` and manual `workflow_dispatch`; historical runs can be re-run |
| `.github/workflows/review-reconciler.yml` | `reviewctl internal-reconcile`, `reconciliation.py` -> `GitHubRefJournal.claim/get/transition/record_stopped` | `contents:write`; hourly schedule and manual dispatch |
| `.github/workflows/publication-recovery.yml` | `reviewctl internal-recover-publication`, shared `GitHubRefJournal` | `contents:write`; manual dispatch, currently constrained to a historical issue |
| Manually invoked `reviewctl` / pinned wheel | `cli.py` and `github_journal.py`, including direct `internal-transition` | Possible authorized writer credentials are external to source-control inventory; cannot establish all deployed copies from repository code alone |
| Historical reruns | Old workflow SHA + old package/source | **Not fixed retroactively by merging source on `dev`** |

Source code inspected under `dev` at `64ee8062c5016cdc5a862b49b8acea18eec0aab4`. During qualification, `dev` advanced independently to `84f4ee15d3841e724f656c9f2f97100c0c1cc4c6` by merging PR #92, containing **two inert v3 pre-model workflows only**; it did not modify `queue.py` or `github_journal.py`.

GitHub documents that re-runs may retain original `GITHUB_SHA`, `GITHUB_REF`, and initial actor privileges for up to 30 days, subject to its re-run controls: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs. An old workflow SHA can therefore continue executing an old v1 decoder if it is permitted to re-run, irrespective of the current branch head. No claim here that old runs have already been disabled or made safe.

## Empirical compatibility of current journal histories

At preflight, **all ten** `refs/heads/review-claims/*` heads were inspected **read-only** and contained top-level `schema_version:1` with the required v1 fields. Nine contained optional `admission` and one omitted it; the current snapshots omitted optional `input_capacity`. Synthetic tests cover both optional fields, STOPPED/count-one, PREPARED/count-zero and nested ReviewRequest v2 admission. The actual historical Git ref heads are retained exactly; neither the implementation branch nor tests alter them.

The CI for [PR #100](https://github.com/fanilosendrison/review-broker/pull/100) on head `73eb732b72a180c4ffb49ef70e3f8850dafe0522` passed **628 tests / 0 failures**, including the new eight-test module. The initial CI failure was confined to the newly authored mock's `gh api --method GET` argument index, corrected without changing the production source.

## Two distinct decisions — do not conflate

**(A) Code-level v1 refusal:** qualified on this branch. A v1 decoder built from this source rejects unknown/future journal records without producing a v1 write. This safety patch may be independently reviewed and integrated under the v1 accepted authority without enabling a v2 claim.

**(B) Operational v2 cutover / all effective writers:** still **BLOCKED**. Before any new v2 claim, an authorized separate rollout must:

1. Merge and verify the v1 refusal guard in each active writer build (and deployed wheels), with exact SHA and tests.
2. Enumerate scheduled/manual/request-triggered workflows, in-flight Jobs, historical re-run eligibility, and all privileged direct/API writers. No assumption that listing current workflow files proves historic writer revocation.
3. Drain or disable old execution entrypoints and prevent old authorized writers from touching the same claim refs; if this cannot be demonstrated, select a *separately accepted, disjoint v2 ref namespace* with versioned discovery/recovery and explicit authority rules.
4. Independently check real `GITHUB_TOKEN`/App/PAT scopes and the absence of unknown writer paths for the selected v2 ref namespace. Never expose the values of these credentials.
5. Qualify `GitHubRefJournal._read()` 404-vs-UNKNOWN error handling and the **full** version-2 record schema, before real AtomicArm/OIDC. This PR does not address those gates.
6. Obtain separate owner acceptance for the v2 migration/activation and exact source/operational qualification. Never re-arm Request #82 or any consumed historical attempt.

**Important:** A patch that merely refuses v2 on new source does not prove a global no-old-writer guarantee. Conversely, that missing global guarantee is not a reason to delay the *safe v1-only compatibility fix*. J-CH v2 remains **not accepted and not implemented**.

```text
TASK=RB91_JQ001_LEGACY_V1_WRITER_GUARD
CODE_GUARD=IMPLEMENTED_ON_DRAFT_PR100
V1_SCHEMA_SERIALIZATION=UNCHANGED
FUTURE_SCHEMA_REFUSAL=TESTED_OFFLINE_IN_REAL_PACKAGE_CI
HISTORICAL_REFS=READ_ONLY_UNCHANGED
HISTORICAL_WORKFLOW_SHA_REVOCATION=NOT_PERFORMED
V2_ROLLOUT_AND_ALL_WRITER_DRAIN=NOT_QUALIFIED
JCH_V2_CLAIM_ADMISSION=DISABLED
PR94=OPEN_DRAFT
PRODUCTION_ARM_QUALIFIED=NO
```
