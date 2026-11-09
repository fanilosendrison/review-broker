---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "RB91 F1 Candidate Provenance Qualification"
version: "0.1.0"
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

The F1 set adds **26 tests**, preserving the earlier739-test selection and
all38 earlier candidate tests. Current candidate selection: **64 PASS**.
Current full suite: **765 PASS**, zero failures/errors/skips/expected failures.
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

Final local results:64 tests in17.856s,765 tests in215.740s, process exits0;
compilation PASS. Earlier narrower60/62/63 candidate runs and764 full tests also
passed and remain distinct receipts, not substituted for the final selection.
Historical RED exits1 remains a RED on the old baseline only.

Full logs, synthetic source/ZIP/transport examples and command/exit/timing
receipts remain private. Exact published SHA, runner checkout, CI outcome and
NEW independent verdict must be verified separately at publication; none follows
merely from these local results.

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
