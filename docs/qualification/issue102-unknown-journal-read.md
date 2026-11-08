---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "strict"
name: "R1 v1 GitHub journal UNKNOWN-read qualification"
version: "0.1.0"
---

# R1 v1 GitHub journal UNKNOWN-read qualification

## Subject and authority

This report concerns the bounded implementation repair tracked by
[Issue #102](https://github.com/fanilosendrison/review-broker/issues/102), under
[parent #91](https://github.com/fanilosendrison/review-broker/issues/91).
The baseline is `671ae588f25464b6ac80bddb44af83b8ca6b9af8`, observed as both
local and remote `dev` before construction. The persistent checkout was clean.
Existing worktrees and open PRs were inventoried without overwriting their
state. No competing R1 repair was observed. Issue #102 was absent from Project
17; no membership or lifecycle status was invented.

The product specification, accepted execution, capacity, OIDC and recovery
contracts remain authority. Issues and this report do not amend those
contracts. PR #100's historical R2 NO_GO and later bounded GO remain distinct,
and its seven-field and eleven-field v1 compatibility remains required.

## Historical RED

The exact independent sources published in
[PR #100's original review](https://github.com/fanilosendrison/review-broker/pull/100#issuecomment-6708992062)
were retrieved and executed before the production fix:

- `reviewer_probe_support.py`: SHA-256
  `0f6743b12defac89f44934d32f6e8760b2c60dca970950c4b308d1a451da6fab`.
- `reviewer-unknown-read-counterexample.py`: SHA-256
  `74936e7b93f5ddab216d0ffabde4a74f3ff151d79cc24fdddcd5fd454ecd9012`.

All seven required no-mutation assertions were RED: injected 401, 403, 422,
429, 500, 503 and a CLI transport failure each caused four speculative Git
mutation requests before the later unsupported-content refusal. This reproduces
R1, not a new R2 regression.

An additional independent replay loads the exact baseline adapter from Git and
seeds the frozen original STOPPED/count1 record in a new local bare repository
for each fault. Each of seven cases emitted four mutation requests and actually
created four orphan Git objects. Atomic create-ref failed against the existing
ref; its SHA and original content remained unchanged. A subsequent actual
`record_invocation()` refused. These observations establish speculative object
creation, **not successful historical replay or ref overwrite**.

The original RED logs, complete synthetic inputs, request payloads, before/after
object inventories and ref identities remain private local receipts. A first
exploratory matrix reused one fixture across subcases; its cumulative object
counts are not per-case counts. The later independent seven-repository replay
provides the per-case observation above.

## Transport and classification

`github_journal_http.py` owns bounded status-bearing transport and sanitized
errors. `github_journal_read.py` owns the three-way observation. The existing
journal owns claims and state changes; no wire schema or attempt identity changes.

An actual installed `gh` 2.37.0 was exercised against an injected loopback HTTP
server with an inert credential and isolated configuration. `--include` emitted
HTTP status on stdout for 200/201 and all tested errors. Error exits were 1,
not differentiated HTTP codes. No English stderr text is classification authority.
A separate read-only authenticated identity probe established availability for
the local authenticated GitHub CLI account only, not an Actions-token deployment.

The adapter pins `github.com`, requests JSON, disables shell execution and uses
a 30-second subprocess timeout. It rejects missing/invalid status framing,
redirect observations, contradictory CLI exit/status, incomplete JSON, duplicate
JSON keys and non-finite values. Diagnostics contain fixed reason codes, not
raw provider bodies, headers, subprocess exceptions or stderr.

- `PRESENT_VERIFIED`: HTTP 200, exact REST ref and repository URL, commit target,
  40-lowercase-hex SHA, content requested at that immutable SHA, canonical v1
  bytes, strict existing decoder and exact request/ordinal-1 attempt identity.
- `ABSENT_AUTHENTICATED`: ref-specific HTTP 404 plus successful REST repository
  metadata, an authenticated GraphQL viewer/repository observation agreeing on
  repository name and numeric identity, a recognized repository role, and a
  separate successful Git-data base-ref read agreeing with the observed default
  branch and commit. Repository role alone is not effective token capability.
- `UNKNOWN`: every other outcome. `_read()` raises `JournalReadUnknown`, a
  `StateTransitionError`, rather than returning absence. The typed observation
  exposes its classification independently for verification.

The extra identity checks use the existing credential and GitHub APIs; no new
credential, authority store, permission grant or dependency is introduced.
Credentials lacking any required proof fail closed. Availability of this exact
absence proof under the eventual scoped Actions credential is **not live
qualified** by local transport tests. Present historical reads do not depend on
these additional absence-only probes.

A genuine 404 cannot prove that a historical ref was never deleted. Trusted
GitHub and approved writers remain assumptions; this repair supplies no
anti-administrator rollback guarantee.

## Creation and ambiguity

Authenticated absence permits only the existing v1 admitted new-claim path.
Base-ref and parent-tree observations are validated before object construction;
object acknowledgements are validated before another mutation.

A well-formed HTTP 201 claim acknowledgement requires independent exact
SHA/record readback. Lost response, exception, malformed acknowledgement,
unavailable readback or contradictory head fails without retry or grant.
Already accepted Git objects/refs are not rolled back.

HTTP 422 is not interpreted as a typed conflict. Only a separately verified
**different** winning commit can supply the existing deterministic claim under
the accepted v1 duplicate rule. Observing the submitted commit after a 422 is
ambiguous and refuses. Admission mismatch still refuses. A consumed winner
stays consumed; reading it never creates a fresh attempt or arm permission.
Two scheduled contenders retain one ref and one deterministic attempt, and the
existing distinct-sibling ARM/count-one CAS tests retain one reservation owner.

These tests do not establish a new retry policy. Later authenticated observation
and any pre-model recovery remain governed by existing v1 contracts, not by an
exceptional POST result. No observation retries, replacement identities or
post-ARM reauthorization were added.

## Consumer audit and GREEN evidence

The shared reader precedes journal transition, invocation, capacity, terminal,
shutdown, evidence-locator and publication writes. Unknown does not become
`KeyError` or `None`. Publication-reservation recovery can only observe an
existing intent and cannot gain creator permission after an ambiguous CAS.

Preparation calls claim before source acquisition. Reconciliation calls claim
or get before dispatch and lifecycle work; a journal UNKNOWN aborts rather than
creating a fallback attempt. Manual CLI boundaries report a nonpassing sanitized
error. Artifact resume and result/predecessor lookup propagate or wrap refusal,
never allocate execution. Independent safety cleanup and local diagnostic-file
creation are not claimed to be suppressed by every journal read failure.

The real controller was faulted at each of its eight pre-mint journal reads,
including after ARM/count-one persistence. Each fault caused zero OIDC calls,
no further Git operation after UNKNOWN, an empty authorization output and no
reset of already consumed state. Reconciliation Issue/ref paths showed zero
dispatch or Codespace calls. Manual transition reported nonzero status.

Local qualification on Python 3.11.9 includes:

- 61 targeted tests PASS, including original/extended v1, R2, actual local Git
  objects/refs, error classification, create/readback faults and controller cuts.
- Full repository suite: **659 tests PASS**, no skips or expected failures.
- Package compilation, JSON artifact parsing, whitespace checks and the
  400-line hand-written-source guard PASS.
- Seven original reviewer inputs/runner rerun: UNKNOWN before any mutation.
  Only the expected refusal boundary changes, not the archived historical source.
- Instrumented local-Git UNKNOWN scenarios assert mutation requests, object
  inventories, ref identities and downstream permission refusal separately.

All production GitHub ref observations were read-only. The ten historical
`review-claims/*` heads were retained before construction and compared during
qualification. Final publication, exact-SHA CI, independent-review verdict and
final historical-ref comparison are separate receipts on the PR/Issue, not
inferred from these local results.

Two early targeted runs remain nonpassing receipts: one exposed a new HTTP
fixture incorrectly reporting 200 instead of 201 for object creation; another
used the wrong position for a global CLI option. Only the fixture/test invocation
was corrected. Neither failure is represented as a passing run.

## Discovery classification and remaining gates

Statement: unknown GitHub observations cannot authorize claim construction or
execution progress. Source/evidence: baseline RED and the fail-closed candidate
matrix. Existing authority: product failure semantics and accepted execution,
OIDC and recovery contracts. Semantic disposition:
`derived-from-existing-authority`. Affected layers:
`architecture-or-implementation`, `integration-or-conformance`,
`verification-or-qualification-evidence`. Consequence: replace the unsafe
absence inference, not the accepted v1 authority model. Required authority:
independent exact-SHA review and separate owner-governed integration. Next action:
retain the Draft PR until those distinct gates are addressed.

No schema-v2, AtomicArm, SSH/OIDC redesign, Codespace startup, consumer review,
production ref mutation, PR #94 change, J20 cutover, admission activation or merge
is performed. New binaries do not revoke old workflows, wheels or writers.
J-CH v2 remains unaccepted and disabled. CI/review GO, if obtained, is evidence
for the owner, never an integration authorization.
