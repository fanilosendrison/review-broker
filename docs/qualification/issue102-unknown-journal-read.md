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
errors. `github_journal_identity.py` validates identity-bearing response
metadata shared by reads and writes. `github_journal_read.py` owns the three-way
observation. The existing
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

- 77 targeted tests PASS, including original/extended v1, R2, actual local Git
  objects/refs, error classification, create/readback faults and controller cuts.
- Full repository suite: **675 tests PASS** under the normal CI umask, with no
  skips or expected failures. A pre-existing unsafe-mode fixture fails under
  umask 077 on both baseline and candidate; it is separately tracked in
  [Issue #107](https://github.com/fanilosendrison/review-broker/issues/107).
  This environment-specific failure is not represented as a passing run.
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

## Additional classification refinement

After the first Draft candidate `5ef92a98d1cdd1ce203277f41470f214612383c4`
was published, a coordinator adversarial control supplied 2,000 nested JSON
arrays. Python raised `RecursionError` rather than returning the explicit
UNKNOWN observation. The call remained fail-closed with one GET and zero
mutation; no execution permission was observed. The prior receipt is retained
as RED classification evidence, not a mutation or replay counterexample.
Both HTTP JSON parsing and decoded journal parsing now classify this resource
limit as UNKNOWN, with a positive existing-record oracle retained by the
unchanged v1 tests. The new two-boundary regression passes in the current
675-test suite. The earlier independent review remains a separate exact-SHA result;
only a new exact-SHA review can qualify the refined candidate.

The independent review of that first SHA concluded **NO_GO**, with one Medium
blocking finding, `R1-REVIEW-01`: a capability response explicitly naming the
wrong repository/ref was accepted because its commit SHA matched. The same
wrong-scope response passed the later creation-base lookup. Independent real-gh
loopback tests observed four real new Git objects and a new claim on an absent
request; an existing consumed request instead retained its ref but acquired
four orphan objects. Neither observation establishes model invocation or
historical replay. The original independent report and both failing safety
assertions remain unchanged.

A single shared ref validator now checks exact ref, repository URL, target type
and SHA in present reads, effective-capability reads and creation-base lookup.
A supplied target URL must also agree. Creation acknowledgements validate their
known target and any supplied scope before the separate authoritative readback.
Parent commits must identify the requested SHA; content must identify the exact
journal path and file type. Explicit default-branch/read-permission contradictions
in repository metadata refuse rather than being ignored. These are transport
identity checks, not changes to stored v1 data.

New negative scope/partial-response tests cover capability and subsequent
creation-base reads independently, asserting UNKNOWN or refusal, zero Git
mutation requests and unchanged real object/ref inventories. The coordinator
replayed the independent scripts: ten R1 and four consumer/concurrency tests
pass; four loopback remediation controls pass. One original consumed-state
observation expected a successful claim return before asserting no writes;
fixed code refuses earlier. Its replay error is retained, and a separately named
derived oracle requires typed UNKNOWN, unchanged objects/refs and permanent
count-one refusal. A separate initial consumer replay omitted the repository
root from PYTHONPATH; its three import errors and corrected run are retained.
Neither setup/oracle adjustment changed the reviewer's archived code or verdict.

These are implementation/verification refinements of the already selected
three-way classification, not a new product decision or authority model.
A new independent exact-SHA verdict is required for the remediated candidate.

## Returned immutable-content and object identity remediation

The independent review of `d61539d572e4652675565e87653175c1d322652e` concluded
**NO_GO**, reporting `R1-D615-01` (High) and `R1-D615-02` (Medium). Its original
report, three RED safety assertions and complete local receipts remain unchanged.
The earlier bounded GO on `e0378c5...` is not reused as current acceptance.

A real-gh loopback test returned an old PREPARED response, explicitly naming the
old commit in its Contents URL, for a current STOPPED/count1 ref. The snapshot
incorrectly paired that old record with the current SHA. The actual controller
then produced 12 mutation requests and 12 new Git objects, advanced the current
journal through capacity/ARM/count-one, called an inert issuer sentinel once and
wrote authorization output. No live OIDC or model invocation occurred, and the
remote one-use defense was not tested or bypassed. Original parent objects
remained immutable; this was a new erroneous descendant, not ref deletion or
administrator action. Wrong-repository parent and blob-ACK URLs separately
permitted subsequent speculative writes.

The shared identity module now requires the returned Contents API URL to bind
the exact repository/path/requested commit, not merely the outbound request.
Supplied HTML, blob, self and download links must agree; supplied name, size and
blob identity metadata must be coherent. Private raw download URLs are never
followed or retained in diagnostics. Object URLs, commit HTML/tree/parent links
and supplied commit-ACK tree/parents are checked against scope and submitted
bindings before another mutation. Optional redundant links are not invented as
execution authority, but an explicit contradiction is never ignored.

The reader still trusts authenticated GitHub endpoint semantics; these checks do
not independently reconstruct and hash-authenticate complete remote Git commits.
No stronger malicious-service or anti-administrator guarantee is asserted.

The unchanged third review programs were replayed on the corrected bytes:
**16/16 controls PASS**, including all three formerly RED assertions, the real
controller stale-content refusal and actual loopback gh. The first replay lacked
the programs' `temporary-files` fixture directory and failed setup; that output
is retained separately from the correctly prepared passing run. New maintained
regressions independently cover zero mutation/mint on stale consumed contents,
parent/tree scope, completed-object ACK boundaries and each supplied content
identity operand, with positive complete-metadata controls. At that stage,
70 targeted and 668 full-suite tests passed; the current totals are listed above.

This remediation follows existing immutable-snapshot and fail-closed authority,
not a new product or consumption decision. A fresh independent exact-SHA verdict
is required; no historical NO_GO is relabeled GO.

## Blob-byte and remaining acknowledgement binding

The independent rereview of `d476f157cc38a7a2fa6bde999c30870f192700bb`
concluded **NO_GO** with `R1-D476-01` (High) and `R1-D476-02` (Medium).
Its immutable report and two new RED assertions remain separate historical facts.
A supplied current blob SHA could contradict older PREPARED inline bytes while
all supplied URLs matched. The actual local controller again produced 12
mutation requests/objects and reached an inert issuer sentinel once; no live
OIDC or model call occurred. A blob POST ACK naming another existing blob also
allowed three subsequent mutations before final readback refused.

Supplied Contents blob SHA is now compared with the Git blob identity of the
exact decoded bytes. Blob POST ACK identity is compared with the known submitted
bytes before another mutation. The implementation uses the official
`git hash-object -t blob --stdin --no-filters` primitive, not a second hand-written
Git encoder. A private empty SHA-1 context isolates caller SHA-256 repositories,
Git configuration, templates, filters and environment overrides. It stores no
claim or consumption authority and does not initialize protected ARM state.
The hash operation has no `-w`; journal bytes remain on stdin, not in command
arguments or temporary data files. Git subprocesses receive no inherited GitHub
credentials. Primitive failure, timeout or malformed output remains UNKNOWN.
Git remains an existing runtime dependency; no Python dependency is added.

`github_journal_objects.py` separately owns immutable proposal construction,
preserving the original canonical bytes, LF, parent and fresh transaction nonce.
It never creates or updates a claim ref. The existing journal still owns atomic
reference operations and all execution-state orchestration. Supplied tree entry,
mode, size and parent/message bindings are checked against the request; duplicate
or explicitly truncated tree metadata and impossible self/child identities
refuse. Root-only and expanded-entry responses and ordinary Git terminal-LF
message representation have positive compatibility controls.

A coordinator audit also reproduced contradictory repository URLs and PATCH ACK
scope reaching claim progress or an inert issuer sentinel. These now refuse at
their own boundaries. ACK faults at capacity, ARM and count-one preserve already
completed legitimate updates but grant no mint or additional write. The legacy
empty JSON PATCH ACK remains compatible only with the existing exact unique-
proposal readback rule; supplied contradictory identity is never ignored.
Separate RED/after-correction receipts distinguish requests, objects and refs.

All 20 unchanged independent tests, including the five previously RED assertions
across the last two reviews, now pass in a separate coordinator replay. The
current 77 targeted and 675 full-suite tests also cover hash unavailability,
caller Git/environment isolation, byte mismatches and all newly checked ACK
operands. A first new complete-history fixture lacked a required shutdown-context
field and failed before its intended fault; its log is retained, and only that
fixture was corrected. The final isolated installed package was byte-compared
with all six current modules before validation, preventing old-package fallback.

These checks derive from existing exact-byte snapshot and fail-closed obligations.
They do not independently authenticate the complete remote commit graph, detect
fully self-consistent lies by a malicious GitHub authority, or change v1 states,
consumption, retry policy or historical serialization. A new independent GO and
literal exact-commit CI receipt are still required for the newly published SHA.

## Exact CI commit selection

The initial PR CI runs were successful but checked out GitHub's synthetic merge
commit, despite their run metadata identifying the published head. Those runs
remain passing observations on their actual checkouts, not literal exact-commit
qualification receipts. The read-only CI now selects
`github.event.pull_request.head.sha || github.sha` through the pinned official
checkout action. A regression oracle checks that selection and unchanged
read-only permissions. No privileged review workflow, admission, secret,
production authority or result is changed. Fresh runner checkout logs and run
metadata must both identify the final published commit; earlier CI is not reused
as proof of this stronger execution-identity check.

This is a `no-normative-impact` verification mechanism realizing the mandate's
exact-SHA CI gate, not a change to product or execution authorization semantics.
The final independent review must include this workflow change.

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
