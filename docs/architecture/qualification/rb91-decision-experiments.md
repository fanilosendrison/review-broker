---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "RB91 Decision Preparation Offline Experiments"
version: "0.1.0"
---

# RB91 — Decision preparation experiments

## Scope, source and method

2026-11-09, task based on dev3057192a6ad4e80663b3b8168cbaa52657c3db27.
Only new candidate documents/schemas and test-only modules are added. Production
source, public schemas, accepted contracts and workflows are unchanged.
Historical PR94 core fixtures/model remain intact; only its obsolete currently
executed decoder assertions are reconciled to the integrated source.

Python3.11.9, jsonschema Draft202012Validator with format checking, RFC8785,
normal umask022. Exact detached historical fixture checkouts are PR72
`e65e4db932cb59d7a0fcfbd442ba19e548fc141d` tree
`420a18d006e421e197d23b8e93681376fbabc2db`, and Issue83
`f3f24d942ad13d368975843f4796b1943dc7cdcb` tree
`acc12a1ee8ef01166ac44fe184d575585d6a0956`, as required by CI.

## D05/D06 finite exploration

Model: [rb91_continuation_model.py](../../../tests/rb91_continuation_model.py).
One already consumed AtomicArm attempt, one original controller, one original
launcher, one reconciler; proof can remain in transit after controller loss.
ACK pending/verified/lost, controller death, launcher claim/crash/start,
cancellation transit/protected fence, Shutdown and terminal journal events are
explicit. Negative modes add one copied/reentrant continuation. Start count is
bounded to2 so counterexamples can be witnessed. There are no real processes,
GitHub calls, JWTs, SSH or provider effects in this model. Exhaustive BFS visits
each reachable state within exactly these finite rules, without fairness/liveness.

[Executed result/shortest traces](rb91-continuation-results.json):

| Mode | States | Edges | At-most-once | No start after terminal |
| ---- | ------ | ----- | ------------ | ----------------------- |
| stop_first | 98 | 172 | No violation found | No violation found |
| mark_first | 138 | 288 | No violation found | Counterexample |
| cancel_only | 112 | 220 | No violation found | Counterexample |
| read_before_start | 161 | 339 | No violation found | Counterexample |
| clone | 155 | 319 | Two-start counterexample | No violation found |
| reenter | 116 | 202 | Two-start counterexample | No violation found |

Every mode reaches a first start and STOPPED. None starts after a lost ACK or
records STOPPED without Shutdown. Every mode allows a start while cancellation
is merely in transit; even stop-first does not retroactively cancel that start.
The stop-first model assumes observed Shutdown kills the entire authorized
incarnation and that trusted lifecycle custody prevents resurrection; it does
NOT prove those provider/OS properties. It also assumes the one-shot local
boundary except where deliberately removed. Clone/reentry controls demonstrate
why that assumption requires real code evidence.

Reproduce from root with tests on PYTHONPATH: call `explore(mode)` for the six
literal modes above. `test_rb91_continuation_candidate.py`: **3/3 PASS**. Model
results are not a claim of a concurrent Actions-vs-Actions race in the shared
scheduler, nor an unbounded proof of J-CH.

## Complete candidate ABI falsification

`test_rb91_full_abi_candidate.py`: **12/12 PASS**. Covers initial claim,
request1/request2 admission identities, nested closure/missing fields in each
definition, immutable admission and field-owned metadata operations, bound
artifact plan/locator, typed retained result reference/body/publication IDs,
receipt links, rejected capacity, pre/post-ARM stop distinction and historical
original7/extended11 decoder preservation. Candidate result bytes validate the
existing public result schema and exact identity; they do not claim a posted
comment or authenticated artifact store.

The pure model is explicitly necessary-but-insufficient: tests can structurally
construct terminal states without authenticating real terminal/Shutdown receipts.
Those are fixture/model states, NOT accepted authority. Production specialized
validators, exact evidence retrieval/admission checks and D06 quiescence remain
mandatory in the proposed contract. No fixture PASS supplies an operational gate.

Current-source reconciled historical core suite: **23/23 PASS**, no skip or
expected failure. Removed assertions are precisely old-decoder-accepts/strips and
its expected refusal failure; replacements assert integrated strict v2/hybrid
refusal and original7/extended11 preservation. Original Q4 report/test source is
still available on its pinned PR94 SHA, unchanged there.

## Full suite, failure honesty and validation

Command: `python -m unittest discover -s tests -p 'test*.py' -v` with the two
exact fixture environment variables specified by CI. Current run: **739 tests,
739 PASS, zero failures/errors/skips/expected failures**, 254.745 seconds unittest
time, process exit0. Package install passed. This includes existing R1/R2 tests,
not a substitute for their independent or operational scopes.

One initial new ABI-test run produced **11 PASS/1 ERROR**: the unknown-version
negative expected ValueError but Draft202012Validator correctly raised its
ValidationError instead. The test-only exception expectation was corrected;
the version refusal and candidate schema were not weakened. Original full log
`full-abi-first.log` remains private; subsequent complete ABI/full runs pass.
Classification: no-normative-impact, verification-or-qualification-evidence;
current-task oracle correction, not an unrelated product failure or waiver.

Issue107's independently established historical umask077 fixture defect remains
OPEN/unfixed; this task uses explicit normal022. No failed full-suite result is
represented as passing, and no umask077 qualification is claimed.

Full logs, command/exit/duration receipts, installation and API readbacks remain
private in ignored task evidence. Machine-independent model outputs and read-only
J20 inventory are versioned. Publication receipts and independent verdict belong
to exact later published SHA and must not be inferred from this local run.

No new real experiment is needed to select a conditional concept: Q2/Q3 and the
finite negative controls already delimit the necessary obligations. The separate
[live protocol and risk budget](rb91-j20-preparation.md) is prepared only.

```text
Q4_HISTORICAL=UNCHANGED_PARTIAL_CORE_PASS_FULL_CUTOVER_NO_GO
CURRENT_CORE_TESTS=23_PASS
FULL_ABI_CANDIDATE_TESTS=12_PASS
CONTINUATION_MODEL_TESTS=3_PASS
FULL_SUITE=739_PASS
D05=SPECIFIED_CONDITIONAL_REAL_IMPLEMENTATION_UNQUALIFIED
D06=COUNTEREXAMPLE_AND_STOP_FIRST_CANDIDATE_BOUNDED
JQ003=CANDIDATE_ABI_COMPLETE_OPERATIONAL_QUALIFICATION_OPEN
LIVE_JCH_OIDC_OR_ARM=NOT_EXECUTED
J20=NOT_EXECUTED
BROKER_MODEL_INVOCATIONS=0
```
