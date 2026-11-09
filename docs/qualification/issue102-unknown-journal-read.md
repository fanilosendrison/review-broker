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

- 87 targeted tests PASS, including original/extended v1, R2, actual local Git
  objects/refs, error classification, create/readback faults and controller cuts.
- Full repository suite: **685 tests PASS** under the normal CI umask, with no
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

## Tree-ancestor consistency refinement

The rereview of `31f07ad3a45e04afd435429611e3149867b7afdf` concluded
**NO_GO** with `R1-31F-01` (Medium). A supplied root-only tree ACK could name
`.review-broker` as a blob while the request writes
`.review-broker/attempt.json`. Its standalone mode/type/SHA were valid, but that
ancestor cannot contain the requested file. In real-gh/local-Git reproductions,
claim creation made two further requests, one commit and a new ref after the
contradiction. The actual controller made ten further mutation requests and
reached the inert issuer sentinel once. Earlier legitimate objects were counted
separately; no live OIDC or model was invoked.

One shared path-consistency check now verifies both supplied tree descriptions
and their combination with requested entries. Every described ancestor of a
nested path must be a tree. A requested blob cannot simultaneously have a
reported descendant. Blob, symlink and gitlink ancestors refuse before further
mutation, while correct root-only trees and expanded leaves retain their
positive controls. This is standard Git path consistency, not a new journal or
execution rule. The original report and its two RED manifestations stay intact.

The unchanged expanded independent matrix now passes **28/28 tests** in a fresh
coordinator replay, including both new assertions, all prior controls, actual gh
loopback and Git-environment tests. The complete current suite remains **675
PASS** under the normal CI umask. A new exact-SHA independent verdict and CI
receipt, rather than the previous NO_GO, must qualify the resulting commit.

## Known object roles and explicit path witnesses

The rereview of `4b09f9cd08185c3d4ddaf43444ad8f858e741649` concluded
**NO_GO**, with `R1-4B09-01` and `R1-4B09-02` (both Medium). The ACK could
label a held, verified blob or parent commit ID as a containing tree. An expanded
sibling sharing the first path component could also pass without the requested
leaf or an explicit containing ancestor. Actual-gh/local-Git tests observed
post-ACK commit/ref writes and inert issuer-boundary reachability. No real OIDC,
model invocation or consumed-attempt replay was established by these cases.

The immutable proposal now carries the already-established object roles into
ACK validation. A supplied child entry cannot contradict a known blob, tree or
commit identity. When the exact requested leaf is absent, the descriptor must
contain an explicit compatible tree ancestor, not merely an unrelated sibling
with the same first component. No new remote graph fetch, history field or
authority service is introduced. Minimal legacy ACK metadata and valid root,
leaf and combined descriptions keep their positive controls.

All **36 unchanged independent controls PASS** in a separate coordinator replay,
including the six previously RED manifestations. Maintained regressions cover
known blob/commit subtree aliases and sibling-only descriptions. The source
suite remains **675 PASS** under umask 022, with **77 targeted tests PASS**.
The earlier reports and RED data remain immutable; a new independent exact-SHA
verdict and CI receipt must qualify this refinement.

## Joint root and descriptor role consistency

The rereview of `e522bf5114581cad47424c4655943414a52efd2d` concluded
**NO_GO** with `R1-E522-01` (Medium). One ACK could assign both tree and blob
roles to a newly described ID, in either order. Its root could also name an
already-known parent commit as a tree. The mixed-role controller reached the
inert issuer boundary. The invalid root case emitted one extra commit request,
but native Git rejected it: zero new post-contradiction objects/refs or returned
grant were observed in that case. Attempted and completed effects are not merged.

A single local role table now covers prior context, request facts, the response
root and recursively supplied object references. Contradictory kinds refuse
order-independently; repetitions with the same kind remain valid. This table is
per observation/proposal, not global mutable state or a new durable authority.
A native repeated-subtree Git DAG remains a passing positive control.

The unchanged **42-test independent matrix PASS** in a separate coordinator
replay, including all five formerly RED manifestations. Three maintained role
unit tests independently check both orders, root/nested conflicts and same-kind
sharing without mutating caller context. A further snapshot control rejects a
commit/blob role collision across ref and supplied Contents identity. Current
totals are **679 full-suite** and **81 targeted tests PASS** under the normal CI environment. All old reports
and RED data remain unchanged; only a new exact-SHA independent GO and literal
CI receipt may qualify this result.

## Retaining checked facts across proposal responses

The review of `549cdeca8ce27d9eea36823af5c306ca4a5a7342` concluded
**NO_GO** with `R1-549-01` (Medium). Per-response role validation returned only
the root ID, discarding other checked facts. A standard parent entry could first
declare the held proposal blob ID to be a commit; later blob hashing did not
retain that fact. Actual claim/controller tests produced post-observation writes
and reached the inert issuer. A checked subtree could likewise be forgotten and
accepted as a later commit ACK root, causing one extra rejected ref request but
zero new post-ACK objects/refs. Requested and successful mutations stay distinct.

Validated identity now returns both root and all checked role facts. The proposal
threads the complete local context through parent, blob, tree and commit steps.
The context is copied/extended explicitly, remains local to the proposal and
supports same-kind DAG reuse. A conflicting held-byte identity fails before the
first blob POST; a later contradictory ACK fails before the next request. No
remote graph fetch, global cache, durable store or execution-policy change is
introduced. The unchanged **46-test independent matrix PASS** in coordinator
replay, including all three new RED assertions and truthful-parent control.
Current totals are **680 full-suite** and **82 targeted tests PASS** under umask
022. A transport interruption during the old review was preserved and resumed;
it was never treated as a verdict or product result. Old reports and REDs remain
unchanged; fresh exact-SHA review and CI must qualify the resulting commit.

## Retaining held-blob sizes independently of reference paths

The review of `c64c6dedf1aa2470172c77894c812d03fffc844b` concluded
**NO_GO** with `R1-C64-01` (Medium). A supplied alias could name the same
already-held blob but report a different byte length. The exact requested leaf
was checked, while the alias was not. Actual-gh/local-Git cases observed two
post-contradiction claim requests, one new commit and a ref; the controller case
observed ten later requests, nine new objects, ref updates and one inert issuer
call. Legitimate earlier objects and the pre-existing alias were preserved and
counted separately. No consumed replay, live OIDC, model invocation or remote
one-use bypass was established. The original report, two RED assertions and
all earlier evidence remain unchanged.

Shared identity validation now returns checked blob-size facts alongside object
roles and rejects inconsistent sizes for every recognized reference to the same
blob, irrespective of path, order or root/leaf representation. The proposal
explicitly retains those local facts through parent, blob, tree and commit
responses. Held bytes bind their length before blob POST. Redundant root and
exact-leaf size comparisons were removed; the shared validator owns the rule.
Caller maps remain copied, and truthful aliases remain supported. No global or
durable cache, remote size fetch, new wire field or authority is introduced.

The unchanged **50-test independent program matrix PASS** in a new producer
replay, including both latest RED manifestations. Three additional producer
actual-gh/native-Git tests PASS: a contradictory parent fact stops before blob
POST, checked size survives into nested commit metadata, and truthful parent/
commit aliases remain valid. These are producer results, not an independent GO.
Current maintained totals are **681 full-suite** and **83 targeted tests PASS**
under umask 022. The original seven inputs again stop at UNKNOWN; 68 freshly
recorded scenarios independently assert zero mutation requests, new objects,
ref changes and authorization calls. Installed-package byte comparison,
compilation, tracked JSON, whitespace and the complete Python line guard PASS.
Issue #107 remains independently tracked and outside this repair.

The local fact-table mechanism is `no-normative-impact` in implementation and
verification layers; the existing fail-closed and immutable-snapshot obligations
remain authority. It does not demand unknown-object size fetching or complete
remote graph authentication. Fresh independent exact-SHA review and literal
runner checkout CI must qualify the resulting published revision.

## Explicit supplied-link cycle refinement

Further producer falsification on published
`136c40a5dc61df1b802d376d7108ea145cf5c034` exposed a distinct local
contradiction: nested tree metadata could explicitly describe root R containing
subtree S containing R. The existing self-link check rejected a direct self-link
but not that cycle. Actual-gh/native-Git claim and real controller probes, also
reproduced with a byte-verified isolated installation of that exact SHA, were
RED. After the contradictory ACK, claim made two mutation requests, one new
commit and a ref; controller made ten requests, nine new objects, ref updates
and one inert issuer call. Legitimate earlier objects were preserved. No live
OIDC, actual model invocation, consumed replay or remote one-use bypass occurred.
This is producer evidence, not a finding attributed to an independent reviewer.
The old exact-source review remains separate evidence on its own subject.

The shared validator now uses Python's maintained `graphlib.TopologicalSorter`
to reject cycles in the finite links already supplied or necessarily established
by submitted proposals. Checked links, roles and sizes remain explicit local
facts across parent/blob/tree/commit responses. A cycle cannot hide between
sibling descriptions or successive responses. Valid repeated subtrees and DAG
sharing remain compatible. No remote graph is fetched or reconstructed, and
missing links are not invented. This is not authentication of a complete remote
commit graph, malicious-service resistance or a new durable authority/cache.
No public journal/request ABI, dependency, privileged workflow or execution
semantics changes.

The original two-method RED regression and both actual-gh RED manifestations
remain retained. The corrected maintained suite passes **684 full-suite** and
**86 targeted tests**, and the unchanged 50-program independent replay passes in
a fresh producer run. Actual-gh claim/controller cycle controls now refuse with
zero later mutation requests, object/ref changes or issuer calls. Maintained
regressions also cover tree/commit cycles, sibling order, retained links and
valid sharing. Installed-package bytes, compilation, JSON, whitespace and all
handwritten Python line limits pass on the corrected source.

Discovery: accepting explicitly cyclic supplied Git ancestry as permission to
advance contradicts the existing immutable-proposal and fail-closed boundary.
Disposition: `derived-from-existing-authority`; affected layers: implementation,
integration/conformance and verification/qualification. The standard-library
finite-link mechanism is replaceable and introduces no product choice. Required
next action: publish and independently qualify a new exact SHA, never reuse the
old SHA's verdict or CI as acceptance of this correction.

## Identity projection compatibility and reviewer continuation

The independent review of `136c40a5dc61df1b802d376d7108ea145cf5c034`
concluded **GO** in its bounded tested scope: 50 prior controls plus four fresh
joint-fact probes passed. That old GO is preserved separately from the producer
cycle counterexample and is not acceptance of either later revision.

The finite-link correction in
`4c38e4545c372b8fa5f7be9d3f4173be93e80a6f` changed the existing
`git_object_identity` return shape. The unchanged independent positive caller
control then failed with too many values to unpack. That producer replay RED is
retained. The established three-value identity/role/size projection is now
preserved by a wrapper over the single canonical `git_object_facts` validator;
the immutable proposal uses that complete-fact entry point and retains links.
No validator or production rule is duplicated, and the old oracle is unchanged.
All **54 unchanged independent controls PASS** in a new producer replay, with
**684 full-suite** and **86 targeted tests PASS**. Five additional actual-gh/
native-Git size/cycle controls pass. Installed-byte matching and static gates
also pass. This is a `no-normative-impact` implementation/verification repair.

The native reviewer launch for 4c38e45 failed before review with a context-window
error, producing no verdict. Pi's documented native same-session compaction
succeeded on that reviewer's own history, preserving the complete historical
file prefix. No producer-authored summary, new conversation, model substitution,
credential inspection or harness patch was used. Intentional continuation and
lossy native compaction remain attestation limits, not fresh-conversation proof.
The incomplete attempt stays separate from every old verdict and from product
execution. A new exact-SHA independent verdict and literal CI must qualify the
projection-compatible correction.

## Flat recursive tree ancestry

Fresh independent falsification on
`bca462ac1fe402cd1ebfc5906a9746e71323914b` found two RED manifestations
of one remaining link-consistency gap. A standard flat recursive tree listing
could explicitly name `first(S)`, `first/to-second(T)` and
`first/to-second/back(S)`. All prefix paths and identities were supplied, but
validation recorded only root-to-entry links and missed S-to-T-to-S. Actual-gh/
native-Git claim and real-controller tests observed post-ACK effects and issuer
sentinel reachability. Nested, sibling-distributed and retained-link cycle
controls already refused; the flat representation did not. This does not prove
consumed replay, live OIDC, model invocation or a remote one-use bypass.

One canonical tree-path routine now validates path syntax/types and derives
ancestry only between explicitly supplied prefix identities. The shared local
link validator receives those necessarily implied links as well as root links.
No missing tree identity is inferred or fetched. The existing path-validation
None return and three-value identity projection stay compatible. Genuine native
recursive trees, same-kind sharing and sparse descriptions without an identified
prefix remain supported. No public wire, dependency or authority change occurs.

The maintained regression was first RED on the old source and now passes for
both entry orders, explicit ancestor links, valid sharing and no invented prefix
node. The unchanged expanded independent program replay passes **62 tests**,
including both previously RED actual-gh manifestations and all older controls.
Current maintained results: **685 full-suite**, **87 targeted tests PASS** under
umask022, plus installed-byte, compilation, JSON, whitespace and complete Python
line-limit checks. Earlier failed fixture attempts, genuine REDs and exact-source
review results remain separate, immutable receipts.

Classification: `derived-from-existing-authority` for rejecting the explicitly
supplied cycle; implementation and verification realization only, without a new
product choice or complete remote-graph attestation. A new exact published SHA
must receive its own literal CI and independent verdict; the old subject's
findings and results cannot qualify the corrected bytes.

## Same immutable tree child bindings (R1-9F7-01)

A completed independent correctness examination of
`9f7326563ef496c4a62d9b235f8afbbb45fef987` concluded **NO_GO** with
`R1-9F7-01` (Medium). This completed report is separate from the earlier
provider-refused incomplete attempt on that SHA. Both remain immutable.
The full private report SHA-256 is
`b1983ee2dd575dd2c0f06073971e1c1fdb293201dcae21f9a06d4f3b237f72fc`;
its sanitary finding and exact additional programs are preserved in
[the historical review comment](https://github.com/fanilosendrison/review-broker/pull/106#issuecomment-6729001852).

Two aliases could explicitly identify the same immutable tree S, yet describe
`S/alpha.txt` as different blobs. Flat and nested responses passed individual
role, size and finite-link checks. The unchanged independent matrix had
**66 PASS / three safety FAIL**; maintained **685 full / 87 targeted PASS** did
not waive the defect. Actual-gh/native-Git flat and nested claims each made two
later mutation requests, one commit and a new ref. The controller made ten later
requests, nine new objects, ref updates and one inert issuer call, reaching
ARMED/count1. Legitimate earlier effects remain separately counted. No actual
model, live OIDC, consumed replay or remote one-use bypass was demonstrated.

Before repair, all sixteen frozen transport/test/recorder programs were copied
to a new producer scratch root, with their hashes verified. An exact disposable
clone of the rejected SHA reproduced all three original required-refusal REDs
unchanged (exit 1); four positive methods passed. Original receipts and the
reviewer worktree were not modified.

The narrow tree-binding module now reconciles explicit
`(tree identity, relative Git path)` assertions including mode, kind and child
identity. It retains sparse rooted paths and rebases suffixes only when an
explicitly identified prefix permits it, including a prefix supplied in a later
ACK. Compatible partial lists do not assert missing children are absent. Exact
Git path strings are not normalized through OS paths, case folding or Unicode
normalization. No absent identity is inferred and no graph is fetched.

The identity module remains the single provider-fact validator. A separate typed
complete context carries bindings, roles, sizes and links through one immutable
proposal, including submitted paths. Existing three-value `git_object_identity`
and four-value `git_object_facts` projections delegate to it without changing
shape. The proposal owns object construction; the journal still owns refs and
business authority. No global cache, durable state, schema, dependency, workflow,
attempt, nonce, CAS, retry or admission change is introduced.

Producer qualification on the repaired bytes passes **69 unchanged independent
methods**, including the three formerly RED assertions, **103 maintained targeted
methods** and **701 full-suite tests** under umask022 with exact fixtures.
Sixteen new maintained methods cover alias orders, modes/types, exact path
names, mixed flat/nested and compatible partial descriptions, deferred-prefix
retention, and native-Git successive-ACK refusal before any further request.
All previous role, size and cycle controls remain passing. Seven original R1
inputs still refuse at UNKNOWN; fresh scenario receipts separately record
requests, objects, refs and authorization effects.

A first producer full-suite run incorrectly supplied a symlink as the strict
PR72 fixture path and failed fixture validation; its complete nonpassing output
is retained. The corrected run uses the original exact non-symlink fixtures,
without an oracle change. A packaging attempt disabling build isolation failed
because that private environment lacked `bdist_wheel`; the normal pinned
isolated build then installed successfully. Neither setup failure is represented
as a passing run or confused with the original three product REDs or the
independent, still-open umask077 fixture defect in Issue #107.

Discovery: contradictory child bindings cannot establish a valid immutable
proposal or permission to advance. Existing authority is the accepted immutable
snapshot and fail-closed execution boundary. Disposition:
`derived-from-existing-authority`; affected layers are implementation,
integration/conformance and verification/qualification. The binding table is a
replaceable `no-normative-impact` mechanism, not a new product choice or stronger
malicious-service/full-graph guarantee. Required next action: publish and obtain
new literal exact-SHA CI and independent review, preserving all old verdicts.
Those gates are separate public receipts, never inferred from producer tests.

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
