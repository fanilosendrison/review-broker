---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "RB91 F1 Candidate Provenance Qualification"
version: "0.1.2"
---

# RB91-F1 — Offline candidate qualification

## Authority, source and scope

Date:2026-11-09. Baseline PR112:
`85149a17c6eda3e8f7cbc5f0f00c280f1b5ecdf9`.
Owner decision: [comment6731259973](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973).
The five conditional architecture directions remain accepted; formal normative
adoption, merge, production construction, J20 and admission are NOT performed.

The [F1 contract](../rb91-f1-storage-provenance.md) and closed result-reference
resource separate original execution, actual authenticated storage and exact
result/evidence identities. Candidate journal resource version0.2.0 incorporates
this breaking pre-adoption ABI revision. The journal wire discriminator remains2;
this does not migrate any previously stored record. Public schemas, accepted
contracts, production source/dependencies and operational workflows are unchanged.

## Historical RED and current GREEN

The old independent GO remains unchanged at its exact SHA. A NEW disposable
clone at that SHA reproduced the original-run positive control and a genuine
required later-run RED (`RESULT_RUN != ACCEPTED`, one failure/exit1). The exact
old input/source/oracle/output remain private. This is a historical predicate
reproduction, not proof that the old model authenticated a recovery job.

The earlier independent probe that EXPECTED `RESULT_RUN` correctly described
old behavior. The owner now explicitly rejects that availability limitation.
The new positive oracle therefore requires authentic recovery storage to pass;
it does not erase or reinterpret the old observation as an old PASS.

Current positives use real local packet/evidence construction, canonical bytes,
ZIP archives and the real accepted packet/terminal/citation/credential validator.
Synthetic RSA issuer keys exercise the real shared GitHub OIDC verifier. Official
Actions read operations are injected; no live token mint, issuer call, artifact
upload, publication, Codespace or broker-model invocation is performed.

## Verification matrix

| Case | Actual candidate judgment |
| ---- | ------------------------- |
| Original run stores result | PASS; complete workload/artifact/evidence verification, no execution-state change |
| Later authorized recovery run | PASS; original execution and content IDs unchanged, distinct authenticated storage |
| Later attempt of original run | PASS as explicitly authorized recovery mode, not forged original attempt |
| Recovery claims original run | REFUSE even with newly signed synthetic statement; issuer/API/role identities cannot be substituted |
| Unapproved workflow/actor/trigger/event | REFUSE; policy is outside the input reference and independently scope-bound |
| Wrong workload/audience/signature | REFUSE; raw declarations and ARM-purpose JWTs cannot satisfy storage verification |
| Wrong request/attempt/subject/policy/packet/ARM/evidence | REFUSE; cross-check against immutable execution snapshot and actual retrieved bytes |
| Result bytes altered | REFUSE; archive and exact content identities/length/body/validation must agree |
| Terminal evidence absent or invalid | REFUSE; a consistent archive/capture hash with invalid citations still fails REAL validation |
| Artifact missing/expired/contradictory | REFUSE; actual repository/run/job/upload-step/metadata/bytes are independently confronted |
| Recovery attempts another ARM | REFUSE; count1, original binding/history and no-rearm remain unchanged |
| Publication already reserved/reported | NO new POST capability; receipt, nonce, mode or matching bytes do not reconstruct creator ownership |
| Correct recovery after original job interruption | PASS through evidence download, validation, new storage admission, one reservation and one synthetic POST |

The F1 set adds **39 tests**, preserving the earlier739-test selection and
all38 earlier candidate tests. Current candidate selection: **77 PASS**.
Current full suite: **778 PASS**, zero failures/errors/skips/expected failures.
Explicit normal umask022; no claim that the independently tracked Issue107
umask077 fixture defect is repaired or qualified.

Tests additionally cover overlapping identical reservations with reproducible
barrier-controlled verification, one creator capability, interrupted storage
before reservation, lost reservation ACK, POST reply loss with a real-to-model
retained comment, unknown POST outcome with no retry, duplicate comment incident,
and unavailable complete comment reads with zero POST. The real existing
publisher supplies bounded pagination/HTTP transport in these fixtures; the
v2 ownership state machine is an independent verification oracle, NOT production
implementation. No new durable publication or consumption mechanism is deployed.

Strong non-tautological negatives include newly signed references and consistent
metadata/ZIP hashes with incompatible evidence/content. Tests require the actual
terminal-validator and result-retrieval boundaries to be reached (six/eight
observed read requests), not merely any earlier exception. Incidental official
actor metadata is accepted while contradictory actor identity is rejected.

## Commands, environment and results

Python3.11.9; declared `.[test]` dependencies in a private venv. Exact detached
CI fixtures remain PR72 e65e4db932cb59d7a0fcfbd442ba19e548fc141d and Issue83
f3f24d942ad13d368975843f4796b1943dc7cdcb with their CI-specified trees and actual
workflow blob. The source-derived original7/extended11 corpus is unchanged.

```sh
python -m unittest discover -s tests -p 'test_rb91*.py' -v
python -m unittest discover -s tests -p 'test*.py' -v
python -m compileall -q src tests
```

Current local results:77 candidate tests in27.533s and778 full tests in216.543s,
process exits0, with the final complete suite's temporary root confined to the
private task worktree. Earlier60/62/63/64/66/72 selections and764/765/767/773 full runs remain distinct
passing receipts, not substituted for current qualification. Initial F1 SHA
5426d3c2aac30ce6c92eabfcbb69e3f7f2eb97eb had CI42560133595/full765 PASS;
that result does NOT cover the later discovered negative case described below.
Historical baseline RED exits1 remains a RED on its old source only.

Full logs, synthetic source/ZIP/transport examples and command/exit/timing
receipts remain private. Exact published SHA, runner checkout, CI outcome and
NEW independent verdict must be verified separately at publication; none follows
merely from these local results.

## Additional typed-admission counterexample — preserved RED/GREEN

A fresh producer probe on first published F1 SHA
5426d3c2aac30ce6c92eabfcbb69e3f7f2eb97eb reached all eight authenticated
read/ZIP/validation boundaries but accepted a result whose embedded resolved
admission changed integer policy.version1 into boolean true. The issuer proof,
reference/ZIP hashes and other identities were internally consistent. Python
mapping equality treated True as1; it did not establish exact JSON identity.

One required-refusal test then genuinely FAILED on5426d3c, exit1. Its unchanged
source passes after replacing resolved-admission equality with canonical-byte
comparison. A separate projected provider-actor comparison receives the same
strict guard. Added tests reject boolean/integer aliases at the intended eighth
or second read boundary and retain valid original admission and integer actor1
controls. No schema, authority, expected identity or refusal oracle is weakened.

Classification: no-normative-impact realization/verification correction of the
already-required exact admission/provenance rule; no new owner choice. The
counterexample does not create another model start or mutate consumed history,
but it blocks qualification of the first F1 bytes as exact provenance. Old CI
PASS and any independent result on those bytes remain bounded historical facts;
neither is reused as the final amended-SHA review. Inputs, RED and GREEN are
retained separately in private evidence.

## Independent NO_GO on first F1 bytes and required remediation

The [complete independent report](https://github.com/fanilosendrison/review-broker/pull/112#issuecomment-6732304834)
on5426d3c2aac30ce6c92eabfcbb69e3f7f2eb97eb is **NO_GO for normative adoption**.
Its R1/R2/R3 identifiers are local to F1, not reopened integrated Issues102/97.
The old report and source remain immutable. Three findings were corrected:

- R1 HIGH: a freshly signed result could turn a valid NO_GO into GO, erase
  anchored findings, invent reviewer attestations or contradict execution status
  while retaining an honest embedded validation. The gate now reuses accepted
  result construction to confront the complete faithful projection from actual
  terminal/validation/attempt data. Public v1 reviewer extensions remain allowed
  as non-authoritative data; accepted schemas are not tightened or rewritten.
- R2 MEDIUM: whole-object comment-user comparison erased exact publication
  observations when normal GitHub user metadata appeared. Canonical login/ID
  projection now preserves real provider responses and no-repost ownership.
- R3 MEDIUM: the original-terminal download path inherited an incomplete source
  metadata comparison. Every original and result artifact read now confronts
  applicable ID/run/source/repository assertions against its respective trusted
  context, including contradictions appearing only on a later metadata read.

The producer copied and hash-froze both independent programs BEFORE replay.
An exact rejected-SHA clone reproduced the isolated21-method outcome:
15 PASS/6 genuine safety FAIL, exit1. On corrected source the unchanged21-method
program has20 PASS/1 ERROR: the manufactured-GO method now raises the REQUIRED
RESULT_STORAGE_UNVERIFIED before its old unsafe-path observations/late
assertion. This is retained as a nonpassing historical-oracle replay, NOT
called21 PASS. Its input, signature, prior structural checks and eight read
boundaries remain reached; the error is the desired earlier refusal, not a new
unsafe permission or hidden transport failure.

A separately named derived oracle changes ONLY that method to explicitly require
the early refusal, no reserved intent, zero POST and unchanged original snapshot;
the other20 methods are inherited unchanged. This derived selection passes21/21.
The oracle adjustment follows the already-required fail-closed-before-reservation
contract, not a new product choice or a weakened assertion. Maintained tests add
honest NO_GO controls, forged coherent negatives, faithful v1 extension positives,
realistic publication actors, original-source contradictions and later-read drift.

Classification: model/evidence/conformance realization corrections of existing
accepted result semantics and F1 provenance rules. No new normative architecture
choice is selected. The NEW corrected SHA still requires an independent rereview;
all old verdicts, REDs and CI observations remain exact-SHA historical facts.

## Residual observation NO_GO and stronger consistency gates

A second [independent NO_GO](https://github.com/fanilosendrison/review-broker/pull/112#issuecomment-6732917984)
on402de887b554874f0bc42258555b078cfbcde2cf confirms the preceding corrections
but identifies two remaining conformance claims not established by those bytes:

- N1: a later artifact read could contradict earlier creation/size observations,
  and explicit original branch assertions could be ignored. Original locator
  metadata and applicable source/run/repository/branch/URI assertions now match
  their trusted contexts. Canonical recognized immutable observations are retained
  and confronted on every fresh read; a later contradiction cannot grant a
  reservation. This is an observation-fact table, not a response cache or new
  durable authority. Concordant complete metadata remains accepted.
- N2: matching actor/body could still accept wrong Issue/HTML attribution or a
  replacement for a historical receipt comment. Explicit API/Issue/HTML URLs
  now match repository/Issue/comment ID; historical observation confronts the
  exact retained comment/node/URL/creation identity before returning success.
  Contradictions leave receipt/history unchanged and never grant another POST.

Both independent programs were copied/hash-frozen before producer replay.
Exact rejected-source replay reproduces14 tests with5 FAIL/1 ERROR, plus the
supplement's19 tests with1 FAIL. Corrected-source unchanged replay has14 tests
with4 ERRORs and19 with1 ERROR: four unsafe-path methods now stop at the
required earlier contradiction refusal, while one pre-existing top-level-boolean
fixture/schema error remains a setup/oracle boundary. These nonpassing logs are
retained, NOT relabeled as passing independent suites.

Separately named derived oracles require the precise early refusal, unchanged
intent/receipt/snapshot and zero extra effects. They inherit all other methods
unchanged and pass33/33 (including the supplement's12 imported existing
publication controls). The renderer/schema boolean refusal is explicitly checked
at its actual owning boundary. Maintained regressions independently cover late
metadata drift, original branch/locator mismatches, correct provider extensions,
wrong Issue/API/HTML URLs, replacement IDs/node IDs/times and unchanged one-POST
ownership. The corrections restore existing exact-observation obligations; no
owner direction or public schema is changed. A NEW exact-SHA review remains
required and no old GO or NO_GO is reused for these amended bytes.

## Exact whitespace correction

Only lines13 and14 in the PR112 COPY of
`docs/architecture/jch-journal-contract-proposal.md` lose two ASCII spaces each.
There is no prose, observation, rule, version or historical PR94 change.

- Old blob:`accb3e6d84ecaa0a32a20393064b707de79a779c`.
- New blob:`42f6bc25e3808db8480e854bb72475f36ab77ad0`.
- Old SHA256:`d337893e85d4fe9107c9ea52d030215f3a143cbbb3a8b5a9596cbdecedeea65a`.
- New SHA256:`b485450118c29733efbe516cfa4a45abea53e6fff562cc79d1beca0873117f7a`.

That copy is NO LONGER byte-identical. The other four retained historical
proposal/report/schema/model inputs remain byte-identical, and all original
bytes remain at PR94's unchanged exact SHA. A private alternate Git index includes
new files while checking the complete dev-base→candidate range with standard
`git diff --cached --check`: exit0. The actual committed range must also pass
`git diff --check 3057192..HEAD` after publication.

## Discovery disposition and adoption handoff

F1's observed original-run-only blockage was a no-normative-impact verification
finding plus a decision-required choice. The owner has now selected the revision
direction. This work realizes that bounded candidate decision, not final product
adoption. Affected layers: candidate contract/architecture, verification evidence,
integration/conformance and documentation. No accepted authority is promoted by
a passing fixture, schema or issuer signature alone.

The candidate uses existing issuer verification and Actions/journal primitives
with a disjoint storage authentication purpose. The authority receipt is created
ONLY after workload, policy, provider observations and exact evidence/bytes pass;
a self-computed receipt cannot substitute for that admission. Historical receipt
custody uses authenticated immutable journal history, not a newly available JWT.

The next gate is a NEW exact-SHA independent review of readiness for normative
adoption. Formal adoption would amend the governing specification, execution/
journal and OIDC authority contracts, evidence/result-publication/recovery,
component and security custody documents and architecture decision. The known
request-v2 status discrepancy needs governed reconciliation in that transition.
No accepted document/ADR is modified here.

Real v2 adapter/launcher, exact workflow/job/storage-proof permissions and issuer
capability, upload/job identity custody, abrupt crash/quiescence, reviewer/control
credential isolation, end-to-end retention/publication and J20 all-writer cutover
remain separate construction/operational qualifications. Neither this report nor
its future independent GO enables a v2 claim or production ARM.
