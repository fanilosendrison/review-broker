---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-01 Offline Initial Controller"
version: "0.1.0"
---

# RWP-01 — offline initial Controller

## Scope and immutable base

This experimental component implements only RWP-01 of the 2026-11-02 Issue #70
overlay. It is not a live Controller, Worker workflow, accepted v3 contract,
production authorization source, or activation decision.

```text
BASE_PR=77
BASE_SHA=2c757eef954ff0c809adff331c31e28371f8624b
BASE_TREE=f1f5723351773a375872dd35e3efdefe2b91cab0
PR71_HEAD=9258617056e9d2e20cce7f05e6be71ea82dfbd23
PR72_HEAD=e65e4db932cb59d7a0fcfbd442ba19e548fc141d
PR55_PROTOCOL=d827df21b1ccd179408f0624709cc2446795e134
```

The mandatory overlay marker is
`<!-- rb-int03-real-workflow-preparation-plan-2026-11-02 -->`.
The work starts in a new detached worktree at that exact base. Publication is
limited to the experimental successor branch, a draft PR against
`feat/issue70-v3-offline-composition-20261102`, ordinary CI, and documentary
handoff. PR #71/#72/#77, Issue #70 and parent #67 are not merged or closed.
No Project item is created or changed.

The protocol source is the pinned non-normative
[pre-model preparation proposal](https://github.com/fanilosendrison/review-broker/blob/d827df21b1ccd179408f0624709cc2446795e134/docs/architecture/pre-model-preparation-failure-protocol-draft.md).
Its selected experimental reservation/ambiguity rules do not acquire normative
status through this implementation, CI, or independent review.

## Added files and responsibilities

- [pre_model_controller_v3.py](../../src/review_broker/pre_model_controller_v3.py):
  admission reconstruction, external Controller decision binding, journal
  orchestration, and the one initial dispatch boundary.
- [pre_model_dispatch_v3.py](../../src/review_broker/pre_model_dispatch_v3.py):
  frozen target/request/result values and one injected transport protocol;
  no HTTP implementation, subprocess, credential, environment or Actions hook.
- [test_issue70_rwp01_controller.py](../../tests/test_issue70_rwp01_controller.py):
  five nominal and fifteen negative scenario methods, with additional boundary
  variants under those same scenario identities.
- [issue70_rwp01_test_support.py](../../tests/issue70_rwp01_test_support.py):
  measured extensions of the existing fake Git server, exact fixture authority,
  and recording dispatch transport.
- This non-normative qualification report.

No existing tracked file is modified. In particular, workflows, public schemas,
contracts, historical journals/reconciler, Packet v2, retention, packet authority,
and Actions identity components are unchanged.

## Existing components actually reused

Admission comes from the existing `AuthenticatedScenario`, including the real
origin reader, requester authority, PR observation interfaces and
`PreclaimAdmissionV3`. Its four reference kinds and scope/provenance remain
those of the separately qualified offline composition; no source capture is
performed by the new Controller.

The Controller reconstructs `admission.journal_admission()` with
`validate_journal_admission_v3` and the retained `origin_body_bytes`. It checks
canonical request/provenance bytes and observed requester identity. The existing
validator owns request, intent, origin, numeric identities, history eligibility,
subject HEAD, reference identities, scope and provenance consistency.
An external decision must be an exact, strictly true `ControllerAuthorizationV3`
bound to the complete canonical admission, original body, exact broker repository
and node ID, and immutable workflow/ref/executable target. Missing, non-boolean,
substituted or inconsistent decisions fail before any journal interaction.
The fixture authority independently pins these values; it is not qualified as a
general production Controller authority. A successful GET or a token is never
treated as authorization.

The actual `GitHubJournalV3.claim`, `read` and `reserve_initial` operations,
`JournalOutcomeV3`, `OutcomeStatusV3`, strict journal decoder, canonicalizer,
expected-old CAS, predecessor/mutation authorities and
`preparation_dispatch_identity` remain authoritative implementations of their
existing experimental responsibilities. Their algorithms are not copied.

The existing v3 claim namespace is retained. A transport `MISSING` observation
means absence established under that transport's qualified read contract;
`UNAVAILABLE` is never interpreted as absence. The test fake explicitly injects
those observations. No live read or write authority is thereby qualified.
Existing claims are verified and admission-confronted before any reservation.
Only exact `REQUESTED` / generation 0 / `UNRESERVED` / no-worker control can
reach the existing reservation operation. Reserved or later claims are observers,
not a reason to call `claim` again.

## Dispatch and attribution boundary

The request carries exact broker repository, request ID, attempt ID, claim ref,
reservation ID, generation 1, expected Worker workflow, execution ref and
executable SHA. Mission prose supplies none of the execution configuration.
The frozen target presented to the authority is retained through dispatch;
subsequent mutation of a Controller attribute cannot substitute another target.

Only the result of the current synchronous `reserve_initial` operation can grant
the dispatch path. It must be `COMMITTED`, with a verified exact successor,
direct predecessor linkage, matching admission/control/namespace, and accepted
mutation evidence. The Controller checks that evidence against the existing
mutation authority for the exact expected-old/successor update. It never obtains
a dispatch right by observing `RESERVED`, calling read-only reconciliation, or
reusing another operation's successful snapshot.

Two independent Controllers can propose byte-identical reservation commits.
The injected Git server enforces expected-old CAS even for identical targets.
Only the acknowledged, attributed operation proceeds; the other operation
remains `UNRESOLVED` under the existing journal's identical-target attribution
rules. Target equality is not writer attribution.

The transport may report an observed response, acceptance without a run ID,
an ambiguous response, response loss, or an exception before/during transport.
An observed positive run ID is response data only, never authenticated Worker
identity. Missing/unverified run identity remains `DISPATCH_UNRESOLVED`.
No Worker registration or Actions-authentication implementation is added.

There are no automatic loops, sleeps, retry deadlines or generation-2 recovery.
The per-instance local attempted/result cache only denies repeated operations
and preserves their unresolved classification. It grants no durable authority
and is not a second journal. Its local thread lock does not arbitrate independent
Controllers; the shared journal CAS does. After restart, a committed reservation
continues to deny redispatch through the journal. An unavailable read or
unresolved operation never authorizes the current operation to continue.

## Scenario matrix

All counts below refer to **simulated** cumulative fixture effects, including
explicitly seeded claims/transitions. `C/A/D` means claims created, CAS attempts,
and calls to the injected dispatch transport. None is a GitHub mutation or a
real Actions dispatch. Every negative case separately confronts these counters,
the final journal, and available claim/reservation outcome statuses.

`R0` is `REQUESTED / 0 / UNRESERVED / no Worker`; `R1` is
`REQUESTED / 1 / RESERVED / no Worker`. Later-state fixtures exercise existing
journal operations only; they do not qualify RWP-02 or packet preparation.

| Case | Observation | Counts |
| ---- | ----------- | ------ |
| N01 | Both writes COMMITTED; R1 precedes dispatch. | 1/1/1 |
| N02 | Duplicate discovery observes R1 only. | 1/1/1 |
| N03 | Identical targets: one winner, one UNRESOLVED loser. | 1/2/1 |
| N04 | Crash at R0, then one fresh reservation. | 1/0/0 then 1/1/1 |
| N05 | R1, ADMITTED, PREPARED are observers. | 1/{1,3,4}/0 |
| F01 | Unauthorized requester decision denied; no journal. | 0/0/0 |
| F02 | Wrong Issue or changed body denied; no journal. | 0/0/0 |
| F03 | Incomplete/incoherent history denied; no journal. | 0/0/0 |
| F04 | Wrong HEAD or numeric repository denied. | 0/0/0 |
| F05 | Non-v3 request denied; no journal. | 0/0/0 |
| F06 | Admission conflict rejected before new effects. | See below |
| F07 | Unknown creation/read stays UNRESOLVED. | {0,1}/0/0 |
| F08 | Stale CAS REJECTED; winner's R1 is not dispatch right. | 1/2/0 |
| F09 | Applied/ack/read ambiguity: UNRESOLVED; R1. | 1/1/0 |
| F10 | Ambiguous/exceptional dispatch: no retry; R1. | 1/1/1 |
| F11 | No run ID: unresolved, no bound Worker; R1. | 1/1/1 |
| F12 | Lost response; later Worker observation cannot resend. | 1/{1,2}/1 |
| F13 | Bad authority denied; target-snapshot positive retained. | {0,1} each |
| F14 | Legacy route/wire or untrusted writer never dispatches. | 0/0/0 etc. |
| F15 | No attributed COMMITTED snapshot: R0, no dispatch. | 1/0/0 |

F06 measures 1/0/0 for a seeded conflicting claim. Its local-cache variant
first measures 1/1/1, then constructs a valid different-origin admission through
the existing admission interfaces. The canonical Request ID is identical but
the admission identity differs: rejection adds no effect to 1/1/1.
F07 leaves no journal or R0, with no CAS attempt, including interruption after
the genuine claim operation applied. F13 invalid decisions measure 0/0/0; its
positive target-reconfiguration sensitivity variant measures 1/1/1.
F14 measures 0/0/0 for a legacy route, 1/0/0 for a seeded historical wire
(rejected without changing its bytes), and 1/1/0 with R1/UNRESOLVED when mutation
authority does not accept the observed update. These are separate variants,
not alternative interpretations of the same observation.

F15 deliberately injects malformed boundary outcomes to test the Controller's
defensive gate. It is not counted as a successful journal transition. The
nominal/race/ambiguity cases traverse the actual reservation and reconciliation
implementation against the existing injected CAS transport. The tests compare
journal state and exact mutation tuples, not just a dispatch counter.
Test barriers have bounded deadlock protection; their timeout is not an
operational rule for deciding that an unknown GitHub operation failed.

## Verification and preserved REDs

Local verification commands use Python 3.11 and the declared project dependencies:

```bash
python -m pip install .
python -m unittest tests.test_issue70_rwp01_controller -v
python -m unittest tests.test_issue70_offline_composition -v
python -m unittest tests.test_issue68_nominal -v
python -m unittest tests.test_issue68_failures -v
python -m unittest tests.test_issue68_recovery -v
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

Observed with Python 3.11.9 on the final local code:

- RWP-01: **20 tests PASS**, covering N01–N05 and F01–F15 with their variants.
- Existing offline composition: **13 tests PASS**.
- Historical #68 nominal/failure/recovery: **2 + 11 + 3 tests PASS**.
- Complete discovery: **836 tests in 719.937 seconds, OK**, with no failures,
  skips or expected failures. The earlier complete candidate runs are retained
  separately rather than substituted for this final-code run.
- Identical-target concurrent-CAS scenario repeated **8 times, PASS**; this is
  finite injected evidence, not exhaustive real-server interleaving coverage.
- `compileall` for both `src` and `tests`, JSON/schema checks on 17 artifacts,
  OKF frontmatter, relative documentation links, Markdown lint, and patch
  whitespace: PASS.
- All four added handwritten Python files are within 400 physical lines.
  The pre-existing `admission_v3.py` has 404 lines at the immutable base and
  remains byte-exact; this change neither fixes nor waives that existing issue.
- Only the five authorized files are added; original tracked bytes and v1/v2
  implementation paths remain unchanged.

Final complete-suite log SHA-256:
`86de55ce8cac2c280a0e015a18d9f96b5b5c6835ab60ce53324829746176ac4a`.
Final RWP-01 focused log SHA-256:
`cbba46e7b3eee375890542a71614e17d267f845e080a157d565d1a57490949b4`.
Concurrent-CAS repetition log SHA-256:
`eaa22fc5f633524a5e69e325df85137f6b5466b0296bd7e5e3f554996cdc1f76`.

No interrupted/incomplete test command is classified as PASS. These commands
exercise broker fixtures only, not reviewed consumer code or live orchestration.

The initial TDD import failure is retained. A subsequent strengthened test run
exposed three failures in the new code: repeated unresolved calls lost their
status, and late target reconfiguration changed the authorized SHA. These are
`no-normative-impact` implementation/verification corrections within RWP-01,
entailed by the pinned no-favorable-inference and exact-input boundaries.
The result cache now retains uncertainty and confronts the complete admission
before returning a previous classification. Dispatch uses the original frozen
authorized target; exceptions after starting claim/reservation preserve the
possibility of application. The regression tests pass through the real journal.
No historical test assertion is weakened, and no contract decision is introduced.

Initial RED log SHA-256:
`1a0b7e41fbe1989dac71fd79bd0575743e6ac7b044445e74a378ec1b1ca1f003`.
Replay/target regression RED log SHA-256:
`5000bb5f3b6f2fe7aa0df151b993938bdec5df32e328acd9ef8f69d347d78b34`.

## Publication gate — STOPPED

The installed mandatory publisher was invoked after successful local validation,
with this exact worktree, `origin`, and the reserved experimental destination.
Run `01M6GA4Z0VP09K0PP5R31VXVDP` stopped during discovery on
2026-11-03, before any commit or push:

```text
Destination: refs/heads/feat/issue70-v3-rwp01-controller-20261102
Reason: explicit publication requires an existing destination branch.
```

The remote destination was required to be absent by the execution mandate.
Raw `git commit`, `commit-tree` and `push` are prohibited by the enclosing
commit enforcer. No bypass, seeded substitute destination, tool patch, change
of publication base or mutation of another repository was attempted.

This is a `no-normative-impact` integration/governance capability gap, not a
Controller contract decision or a failing runtime test. Evidence is the exact
publisher command/error and retained execution run. It affects publication and
therefore the final qualification claim. Resolving the publisher's first-branch
capability or supplying another explicitly approved, non-bypassing publication
mechanism requires authority outside this RWP-01 implementation scope.

The unpublished worktree and local evidence remain available for inspection.
HEAD is still detached at the immutable base; the five additions are staged.
No successor commit, remote branch, draft PR, exact-source CI or independent
review exists. No qualification handoff was posted to Issue #70, because that
write is authorized only after qualification. The Issue body/state, parent,
Project and source PRs remain unchanged.

```text
RESULT=STOPPED
FAILED_GATE=PUBLICATION_DESTINATION_CREATION_UNSUPPORTED
EXACT_SHA_CI=NOT_RUN
INDEPENDENT_REVIEW=NOT_RUN
RWP01_OFFLINE_INITIAL_CONTROLLER=NOT_QUALIFIED
```

Resumption requires a legitimate first-publication mechanism, fresh identity and
scope checks, publication of the validated detached candidate, exact-source CI,
and the mandatory independent GO. It does not start RWP-02.

## Qualification limits and final acceptance

The final bounded qualification label is
`RWP01_OFFLINE_INITIAL_CONTROLLER=PASS` **only after** successful exact-source
ordinary CI and a fresh independent exact-commit GO. Those subsequent receipts
belong to the successor draft PR and Issue #70 handoff; this local report does
not pre-assert either gate or qualify a live workflow.

The required construction reviewer is `openai-codex-1 / gpt-5.6-sol / xhigh`,
with read-only tools, no model substitution and the exact final source. This is
a separately authorized construction review, not a Review Broker invocation.

RWP-02 authenticated Worker binding, RWP-03 packet authority/production technical
policy, RWP-04 remote retention/PREPARED, and RWP-05 minimum failure/BLOCKED
handling remain unimplemented by this change. No claims of authenticated Worker
execution, live permissions, token scope, remote retention, PREPARED, ARMED,
ReviewResult, Codespace ownership, generation-2 recovery or v3 activation derive
from the injected observations. Existing v1/v2 workflows, bytes and guarantees
are preserved by an additive-only change and complete regression coverage.

```text
REAL_WORKFLOW_PREPARATION=IN_PROGRESS
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
GITHUB_JOURNAL_MUTATIONS=0
REAL_WORKER_DISPATCHES=0
SOURCE_APP_TOKEN_MINTS=0
CODESPACE_EFFECTS=0
REVIEW_BROKER_MODEL_INVOCATIONS=0
V3_PRODUCTION_ACTIVATION=NO
NORMATIVE_ADOPTION=NO
```
