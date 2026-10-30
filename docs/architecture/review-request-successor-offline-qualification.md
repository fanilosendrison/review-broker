---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-qualification-note"
domain: "independent-review"
severity: "draft"
name: "Successor Contract Offline Falsification — Experimental Evidence"
version: "0.1.1"
---

# Successor contract — offline falsification (experimental)

**EVIDENCE-BOUNDED DESIGN EXPERIMENT. NOT A QUALIFICATION OF THE RUNNING BROKER.**

## 1. Scope, result and environment

A standalone **synthetic Python reference model** was constructed from the
non-normative PR #55 design in order to challenge the proposed v3 request,
Git-revision atomicity, pre-model journal dispositions and minimal
ReviewResult-v2 policy/reference-coverage shape. It does not import,
invoke or modify the running Review Broker. Its tests **do not establish
implementation correctness**, normative acceptance, effective Codex
sandbox enforcement, cross-document independent review or live source
permissions.

The final local execution yielded:

```text
EXPERIMENTAL_CASES=55
PASS=55
FAIL=0
ERROR=0
SKIP=0
CODEX_INVOCATIONS=0
GITHUB_MUTATIONS=0
NETWORK_ACQUISITION=NONE
REAL_BROKER_V3_EXECUTED=NO
```

Environment: Python 3.13.5, `jsonschema` 4.26.0 and Git 2.47.3.
The standalone runner creates local Git commits B, H and H2 and checks real
Git-tree/blob bytes using the Git CLI. Its authorization, repository API
identity and journal/compare-and-swap behaviors are **synthetic models**;
no real private GitHub Issues, Apps, codespaces or remote artifacts were
examined.

The SHA-256 digests of the original, locally generated artifacts are:

```text
experimental runner .py:
54e74065511da35057130a50da9ab1adb7f2b97b7e44db8eb632938315e72bab

machine-readable JSON report:
49230424d41c5fe69bdeb13f261a0c0f19357acc1fc11b440dbd62b012fb91e4
```

These artifacts were generated in the originating assistant's file session;
**the executable runner is not committed to PR #55** to preserve its
document-only design scope. Accordingly, this note is not, on its own,
an independently reproducible source-code qualification artifact.
Future qualification must re-run an exact reviewed harness or
replacement tests in an independently controlled environment.

## 2. Test families and observed behavior

| Case IDs | Count | Experiment | Outcome |
| --- | ---: | --- | --- |
| Q01–Q07 | 7 | Closed request shape: mandatory `references: []`, duplicate IDs, JSON boolean and stable positive repository ID, unsupported optional kind | 7 PASS |
| Q08–Q14 | 7 | ASCII-subset canonical identities: exact request vs logical intent, changed inline bytes, HEAD, version pin, source order, atomicity, repository ID | 7 PASS |
| Q15–Q18 | 4 | Synthetic repository name transfer/rename/reuse, recovery target drift, wrong Issue/comment object ID | 4 PASS |
| Q19–Q28 | 10 | Actual local Git B/H/H2 object checks: allowed PR+inline+same-H Git, disallowed second commit, mutable Issue, wrong repo/head, changed diff, tampered blob/inline, missing path | 10 PASS |
| Q29–Q36 | 8 | Synthetic permanent refusal, no Shutdown/no STOPPED, wrong receipt, transient retry block, changed-target recovery refusal, stale CAS, finite replay, one invocation maximum | 8 PASS |
| Q37–Q44 | 8 | Technical-profile digest identity; captured/omitted coverage; required/optional distinction; subject sources vs reference sources; undeclared source rejection | 8 PASS |
| Q45–Q55 | 11 | Experimental v2 result schema and provenance: field shape, installed-profile mismatch, historical `policy_id` rejection, no inferred reference freshness, coverage mismatch, subject/source examined distinction, invalid-evidence GO rejection, packet mismatch and ambiguous absence | 11 PASS |
| **Total** | **55** | **Synthetic model only** | **55 PASS** |

### Important individual counterexamples

- **Q02:** missing `references` is rejected; no canonical alias with `[]`.
- **Q09:** changed inline bytes produce a different exact request but
  can retain the same logical intent. This is *not* evidence equivalence.
- **Q11/Q15–Q18:** numeric repository ID and object identity changes
  are rejected, independent of identical displayed names or content.
- **Q20:** PR B/H + fixed inline + Git file at the identical H in the
  identical repository gives a valid **Git-version** candidate proof.
- **Q21/Q22/Q26:** a different commit, mutable Issue or substituted blob
  cannot pass that initial `atomicity=true` profile.
- **Q30/Q31:** absent observed Shutdown or a mismatched refusal receipt
  cannot create terminal `STOPPED` in the synthetic model.
- **Q32/Q34/Q35:** a blocked transient claim is not automatically
  redispatched forever, and a stale journal CAS loses. The example
  finite replay budget (=1) is **a synthetic test parameter, not an
  approved operational default**.
- **Q43/Q44:** subject source `S001` can be examined even when
  references are empty, while an undeclared source cannot be
  passed off as examined reference material.
- **Q45/Q46/Q47:** a minimal experimental ReviewResult v2 replaces
  old semantic `policy_id` with a digest of the verified installed
  permission-profile name and bytes; mismatches and old-field reuse fail.
- **Q48/Q49/Q50/Q55:** a subject-current result does not imply
  external-reference freshness, and omitted/ambiguous material
  cannot be counted as examined or truthfully captured.

## 3. Test-method limitations

1. **Not testing the implementation.** Current `queue.py` and
   `reconciliation.py` do not implement the proposed permanent
   pre-model refusal path or CAS-bound retryable-blocked disposition.
   Q29–Q36 exercise a *mock state-transition reference model*;
   they cannot prove durable race safety under real GitHub refs.
2. **Restricted canonicalization.** Sorted compact JSON equals RFC 8785
   only for the selected **ASCII-only, simple-key/value fixtures**.
   Full JCS string ordering, Unicode/number serialization, edge
   cases and collision-domain qualification remain untested.
3. **Git consistency, not multi-provider atomicity.** Real local Git
   objects are checked; there is no actual GitHub PR metadata race,
   authorization-token behavior, mutable Issue API snapshot or
   cross-provider coherent-cut proof.
4. **Synthetic policy/result.** Result-v2 is tested against a
   standalone candidate subset, not the accepted v1 result parser,
   v3 schema, full artifact receipt, publisher attestation or
   existing `reviewctl result` code.
5. **No independent reviewer.** These are producer-created
   experiments. No new ReviewRequest, Codex invocation, GitHub
   permission change or Codespace runtime was authorized or used.
6. **Ephemeral fixture.** The local Git repository was generated
   in a temporary directory and destroyed after testing;
   the runner is required to reproduce it.

The experiment **tests logical discriminating cases** but does not
qualify construction, persistent correctness, or actual externally
authenticated evidence. The named examples and observed PASS
results are suitable for guiding separately approved implementation
tests; they are **not** sufficient for merging an executable contract.

## 4. Implications for the PR #55 draft

The synthetic model **did not falsify** the narrow design directions
for mandatory explicit references, stable GitHub IDs, pre-model
permanent/transient refusal, PR-head Git coherence and minimal
result-policy/coverage binding **under its explicitly stated
assumptions**.

This is not a claim that those assumptions are true in production.
The following gates still require separate, more authoritative evidence:

- Accepted, closed full v3, packet-v2 and result-v2 schemas with
  complete RFC 8785 vectors and migration/compatibility fixtures.
- Actual immutable GitHub object identity and source-App permission
  qualification, including transfers, aliases, 404 ambiguity and
  recovery against authenticated external APIs.
- Crash, replay and concurrency injection against the **real journal,
  reconciler and Codex armament boundary**, verifying specialized
  permanent pre-model termination and bounded retry.
- Git HEAD/B proof and source role validation integrated into the
  actual packet construction and verifier, not a standalone model.
- Real result-v2 publication/retrieval verification, closed coverage
  checks and honest evidence-retention behavior.
- An independent reviewer that receives actual #43/#44/#51 and
  governing contract/code snapshots, not only a PR diff.

## 5. Separate fault injection of current real broker modules — PR #57

A subsequent, separately authorized test-only [draft PR #57](https://github.com/fanilosendrison/review-broker/pull/57)
**imports the real production v1/v2** `GitHubRefJournal`, `InMemoryJournal`,
`reconciliation.reconcile_repository`, `recovery`, source-reader,
change-scope and request parser modules. The GitHub API, Codespace
and transport boundaries are explicitly simulated to avoid live
privileged side effects. The test file is not in PR #55.

**Exact tested SHA:** `890d4166c1507ef1989c4e2f666d7e683e545561`.
**CI evidence:** [GitHub Actions run 41037602888](https://github.com/fanilosendrison/review-broker/actions/runs/41037602888).
**Result:** 500 total unittest cases, `OK (expected failures=2)`.
The new file contributed **15 cases: 13 PASS and two expected
failures** explicitly describing *unimplemented successor behavior*.

| Actual-module observation | Reproduced fact | Contract implication |
| --- | --- | --- |
| Reconciler over an already `ADMITTED` claim | Three sweeps cause **three pre-model dispatch decisions**, while retaining one request/attempt | Permanent failure needs durable blocked/terminal disposition; current claim state is not sufficient |
| Queue pre-model terminal path | Real `record_shutdown_transition` rejects direct `REQUESTED/ADMITTED -> STOPPED` as `ILLEGAL_TRANSITION` even with valid Shutdown | Specialized v3 failure receipt and allowed state path need implementation and qualification |
| `PREPARED` evidence | Mismatched rebuilt packet ID rejected | Preserve existing immutable packet-binding boundary |
| `ARMED` recovery | No further dispatch/invocation, indeterminate outcome and validated Shutdown | Preserve current separate at-most-once inference boundary |
| GitHubRefJournal CAS/claim | Failed non-fast-forward ref update and lost create-ref without winner both fail closed | Preserve journal conflict/ambiguity handling |
| Git objects / PR scope | Real local Git HEAD/B objects are byte-pinned; extra reference source cannot masquerade as a changed PR image | Maintain separation of subject and references in packet-v2 |
| Request parser and IDs | Current parser rejects v3; v1 resolved PR metadata includes repo ID but canonical v1 subject does not | Stable `repository_id` in v3 remains future, not implemented |

The **initial CI attempt** failed because a test fixture omitted
`workflow_run_attempt` in two synthetic shutdown receipts; it
was corrected without changing production source. The final 500-test
run succeeded with both future-behavior failures correctly marked
`expectedFailure`.

These tests establish actual present-code behavior under controlled
I/O injection, **not a qualification of unimplemented v3** and not
real GitHub API authorization, cloud journal concurrency, or Codex
effective-policy correctness. The parent 55-case synthetic experiment
and this 15-case production-module suite must be reported **separately**
rather than added together as 70 implemented-system passing tests.

**Actual-module disposition:** current safeguards verified on the
tested boundaries; permanent pre-model refusal and prevention of
unbounded dispatch remain **demonstrated implementation gaps**.

**Disposition: `EXPERIMENTAL_OFFLINE_FALSIFICATION_PASS_WITH_STRICT_BOUNDS`.**
This is a research result, not an implementation authorization or
normative acceptance.

`EXPERIMENTAL_TESTS=55`
`EXPERIMENTAL_PASS=55`
`REAL_IMPLEMENTATION_QUALIFIED=NO`
`FULL_RFC8785_QUALIFIED=NO`
`INDEPENDENT_REVIEW=NOT_PERFORMED`
`NORMATIVE_SCHEMA_ACCEPTED=NO`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
