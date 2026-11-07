---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "J-CH ARM-Bound Challenge Authority Protocol Proposal"
version: "0.1.1"
---

# J-CH ARM-Bound Challenge Authority — Protocol Proposal v0.1.1

**NON-NORMATIVE DESIGN CANDIDATE — NOT ACCEPTED — NOT IMPLEMENTED — NOT QUALIFIED**

## 0. Authority, provenance, and status

This document is a *versioned candidate specification* for
[RB-ARCH-ARM-01 #91](https://github.com/fanilosendrison/review-broker/issues/91).
It proposes the minimal J-CH (journal-bound, pre-ARM launcher challenge)
protocol as an alternative to a separate post-ARM consumption CAS (J2-B)
or durable state inside the Codespace (B).

Proposal rules labeled **P01–P24** are **requirements for a hypothetical
implementation only**. They have no authority over existing code or operating
procedures. In particular, this document does **not** amend, supersede or
activate the accepted
[OIDC ARM Authority v1](../contracts/oidc-arm-authority.md),
[ReviewRequest v2](../contracts/review-request-v2.md),
[recovery runbook](../operations/recovery.md), or
[governing specification](../specification/review-broker-spec.md).
The version in this file is the **proposal version**, not a deployed
wire-schema or enabled protocol version.

Evidence basis (each result remains bounded to its original model/evidence):
- [#91 phase 1 — code inspection and conceptual counterexamples](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6695366356).
- [#91 phase 2 — finite-state J2-B exploration](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6697694942).
- [#91 Q1 — live read-only GitHub authority audit](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6698134952).
- [#91 phase 3 — same-model J-CH/J2-B comparison](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6699304864).
- Phase 4 (2026-11-07): bounded split-ARM vs single-CAS AtomicArm comparison; the v0.1.1 proposal adopts **AtomicArmBound as the preferred candidate**, subject to real protocol and threat-model qualification. Model evidence is not a live GitHub guarantee.
- [#27 — accepted risk-proportionate v1 security decision](https://github.com/fanilosendrison/review-broker/issues/27).

Phase 3 enumerated 3,300 reachable states in the **bounded trusted J-CH
model** with no violation and found counterexamples when privileged process
state was cloned, journal semantics were rolled back, challenges were reused,
or the launcher could re-enter. That is **not** a proof about GitHub,
Codespaces, SSH, or the production executable.

## 1. Goal and non-goals

J-CH aims to make the existing GitHub attempt journal the only **durable
consumption history**, while requiring a fresh, still-running privileged
launcher to participate in ARM authorization **before** the irreversible
commit. A consumed grant cannot be reassigned after interruption.

The proposed safety property is:

```text
for every attempt_id a:
  authorized_codex_process_starts(a) <= 1
  start(a) => bound_armed(a) AND bound_count_one(a)
              AND verified_oidc(a) AND unique_live_continuation(a)
```

This counts **broker-authorized Codex process starts**, not provider-side
model inference, messages, callbacks, or an administrator's unauthorized
direct access to Codex credentials. No exactly-once provider effect, execution
liveness, universal host attestation, or resilience to a fully compromised
GitHub/host administrator is promised.

The alternative J2-B adds a **third** CAS after ARM/count-one. Earlier J-CH
v0.1.0 retained **two** separate ARM/count-one commits; that design leaves
a stranded `ARMED/count=0` interruption window requiring original-controller
ownership for the second write. **J-CH v0.1.1 proposes one atomic GitHub
commit** for `PREPARED/count=0 -> ARMED/count=1` with the challenge and
binding. It eliminates that intermediate state for **new J-CH records only**.
Legacy accepted OIDC ARM v1 retains its original two-write implementation,
with no retrospective schema/state rewrite.

## 2. Actors, privileges, and trust assumptions

| Actor | Trust/permissions | Must not do |
| --- | --- | --- |
| Requester | Untrusted mission/source input, authorized by broker admission | Select ARM authority, mint workload tokens, rewrite journal |
| GitHub Actions controller C | Trusted pinned workflow/source; journal write, scoped OIDC; separate Codespaces-control credential | Send those credentials to reviewer or launcher; reissue grants after uncertainty |
| GitHub claim journal J | Trusted durable ref and expected-parent fast-forward CAS under qualified writer assumptions | Silently treat lost/unknown history as a new unconsumed attempt |
| Codespaces transport T | Authenticated selected recipient, bounded session and bytes | Treat delivery success as proof of live privileged process continuity |
| Privileged launcher L | Trusted verified program, protected execution context, challenge generator; **no GitHub journal-write credential** | Create a new authority, re-enter launch, fork/copy authorized state |
| Codex reviewer R | Separate untrusted/model-visible execution boundary, pinned distribution/profile | Receive OIDC JWT, claim-writer credentials, controller credentials or launcher control |

**Candidate, not owner-accepted threat boundary:** ordinary crashes,
concurrency, duplicate delivery, replay, stale reads, network/SSH ambiguity,
host restarts/replacements and malicious reviewed material **are in scope**.
An adversary controlling a GitHub journal writer/administrator, GitHub itself,
or the privileged host at arbitrary memory/snapshot level is proposed as an
explicit residual trust failure, **not a supported guarantee**. A demonstrated
secret leak or unexpected privileged access always blocks the affected path.

This perimeter is consistent in spirit with #27 but **does not follow
automatically from #27**. Owner adjudication remains an open gate.

**P01 — Credential separation.** C alone performs journal mutations and
requests GitHub OIDC; L/R must not receive the GitHub journal, publication,
source-reader or Codespaces-control credentials. R must not receive the OIDC
bundle or the authority/challenge protocol as model-visible input.

**P02 — Trusted launch boundary.** All model-capable invocations from this
broker must pass through the exact protected L entrypoint. A second runnable
legacy `internal-invoke` or alternate Codex launch entrypoint with different
authorization semantics is a blocker, not a convenience fallback.

## 3. Versioning and legacy isolation

**P03 — Explicit protocol identity.** The new binding uses a distinct
literal protocol identifier `j-ch-v1`. No existing OIDC ARM v1 envelope,
old `ARMED` record or caller-supplied boolean is valid under J-CH by
default. J-CH is versioned independently of ReviewRequest v1/v2/v3.

**P04 — Journal schema compatibility.** Proposed new J-CH-eligible attempts
use a *newly specified* journal record schema/version with closed, validated
fields and a preselected protocol marker from initial claim/admission.
Existing v1 journal records remain readable under their own schema and
immutable. An old record must **not** silently acquire a J-CH marker through
ARM, replay, recovery, migration, reserialization or historical readback.

This choice entails an explicit separate migration/compatibility decision.
No pre-existing `PREPARED` claim is silently eligible; future v3
`PREPARED`-only development is unaffected. An accepted future
contract may define an expressly authorized migration for *unarmed* records,
but it cannot infer a new attempt or rehabilitate an `ARMED` one.

**P05 — Closed decoding.** A J-CH reader/writer must validate the exact record
schema, protocol marker, state/field combinations, challenge and binding
invariants. Older code must reject unsupported future records instead of
dropping unknown fields during serialization. Existing
`AttemptRecord.from_dict` and `as_dict` need qualification
for this issue; **current permissive decoding is not sufficient**.

**P06 — Legacy permanent non-replay.** Request #82 and every historical
`ARMED`, `INDETERMINATE`, `STOPPED` or otherwise
consumed attempt remain ineligible for J-CH regardless of whether they have
a challenge field. No new attempt ordinal, no reset of count, no repeat
authorization inferred from recovery. Changed-head/repeat requests continue
to require the existing distinct, owner-authorized ReviewRequest v2 operation.

## 4. Proposed binding and message domains

Wire shapes here are **design-level field contracts**, not an accepted JSON
Schema, JWT issuer customization, executable API, or implemented CLI.

### 4.1 Launcher's pre-ARM hello (L -> C)

C must receive one bounded canonical hello from an already authenticated
remote session *before* any model-capable side effect. Proposed fields:

| Field | Proposed domain / rule |
| --- | --- |
| `protocol` | Exactly `j-ch-v1` |
| `challenge` | New 256-bit CSPRNG value, lowercase 64 hexadecimal characters, generated by L **in its live process** |
| `request_id`, `attempt_id`, `packet_id` | Exact identities of the prepared immutable packet and ordinal-1 attempt |
| `broker_repository_id`, `codespace_name`, `codespace_id` | Authenticated configured recipient identities, not arbitrary caller assertions |
| `executing_broker_sha`, `launcher_program_sha256` | Exact verified trusted code identities |
| `input_sha256`, `capacity_receipt_id`, `reviewer_runtime_identity` | Exact bound pre-arm observations |
| `handshake_version` | Closed major/minor negotiation; unknown version rejects |

The CSPRNG value is **not a secret credential once journaled**. Its
security role is to distinguish a live launcher incarnation. A nonce alone
does not prove that the same OS process remains alive or that it was not
copied; those are separate protected-launcher assumptions.

### 4.2 New journal record's ARM binding (C -> J)

**P07 — Atomic ARM and one consumption.** The proposed **single**
`PREPARED/count=0 -> ARMED/count=1` fast-forward Git commit atomically
sets the attempt state, spends its single invocation allocation and records
one closed, immutable `arm_binding` containing at minimum:

- Protocol/schema version, exact request/attempt/packet/subject evidence
  identities, input/capacity and reviewer executable/policy identities.
- Exact GitHub repository numeric ID, pinned workflow path/SHA/ref,
  controller run ID and run attempt.
- Exact Codespace name and numeric ID, challenge, verified launcher identity,
  and the SHA-256 of the preflight/recipient observation on which C relied.
- Commitment to the intended *one specific launcher incarnation*; no
  mutable `current_launcher` pointer or post-ARM rebinding rule.

The record must identify the challenge unambiguously. A hello by itself,
its SHA-256, a Codespace name or the successful SSH connection does not
grant model execution.

**P08 — Exclusive ARM authorization and original session ownership.**
C may create that atomic ARM/count-one commit only after fresh, authoritative
`PREPARED/count=0` and exact capacity/packet observations, actual recipient
validation, trusted runtime/profile checks, and a challenge produced by
**the specific passive launcher connected to C's own authenticated session**.
The full binding and count are committed in **one** updated journal object,
not written in separate commits. A different controller must not adopt an
already-open peer launcher challenge merely because it saw that challenge in
a message or GitHub record. The accepted preparation and source/head rules
remain independent and mandatory.

**P09 — No rebind after ARM.** Any non-PREPARED snapshot or another
`arm_binding` is a hard refusal. Crashes and unavailable recipients
after ARM never authorize another challenge.

### 4.3 Atomic ARM/count-one ownership (C -> J)

**P10 — No stranded split transition.** New J-CH records MUST NOT use the
legacy `PREPARED -> ARMED/count=0 -> ARMED/count=1` two-commit path.
One new, versioned `arm_once_challenge_bound` operation proposes exactly
one CAS from the fresh `PREPARED/count=0` snapshot to
`ARMED/count=1`, binding the original controller and live launcher in the
same committed object. The **single successful commit is the irreversible
consumption decision**. Any independently observed `ARMED/count=0` record
is legacy or invalid for J-CH and never an invitation to finish count-one.

The current `record_invocation()` method has no controller-identity
argument and allows any appropriately privileged direct caller to advance
an `ARMED/count=0` record; the normal `arm_and_authorize()` entrypoint
nonetheless refuses such a record at its PREPARED precondition.
This is a **primitive-level J-CH design concern**, not evidence of a live
unauthorized replay through the currently implemented full workflow.

**P11 — Original-owner confirmation and ambiguity.** A new CAS must have
a unique child commit of the exact observed parent. **Only the same live
controller that submitted it**, with its original authenticated active
launcher session, may continue after positively verifying the exact commit,
record, binding and count. Another job, process, runner restart or reconciler
may observe the consumed result for recovery but MUST NOT mint OIDC from it.
If the CAS or its acknowledgement is ambiguous, the original caller
must **not** retry a grant, infer ownership from a matching head, rebind,
mint OIDC or launch. A lost opportunity is acceptable; a second grant is not.
The original controller's possession of a live session is a trusted-process
assumption requiring qualification, not something GitHub ref ancestry proves.

### 4.4 New OIDC-bound authorization (C -> L)

**P12 — Mint only after the confirmed atomic ARM commit.** Only the
winning live C, still holding its original launcher connection, may request
OIDC after it has positively verified its own exact `ARMED/count=1`
versioned atomic commit and complete binding. A second controller cannot mint
merely by reading that consumed state, replaying a challenge, or sharing a
GitHub run ID without the original local session authority.

**P13 — Closed new envelope.** The candidate `j-ch-v1` envelope must
include all accepted ARM v1 claim checks plus the exact challenge, **single
atomic ARM/count-one commit SHA**, arm-binding digest and verified launcher
program identity,
workflow/run identity, request/attempt/packet/input/capacity evidence and
recipient identity. The custom GitHub OIDC audience must be SHA-256-bound
to the complete canonical versioned envelope; it is not a generic bearer
grant unrelated to the chosen challenge. The issuer remains the pinned
GitHub Actions OIDC issuer; issuer keys, signing algorithm, expiry and
workflow claims remain independently verified.

An authorization ID or JWT `jti` is not a replay-reset nonce. No
static signing key is introduced. Invalid, missing, stale, differently
versioned or mismatched envelopes fail closed.

**P14 — Same live launcher only.** L validates OIDC against its own
privately held challenge, exact active-session context and trusted configuration.
A *newly started* process must generate a different challenge and must not
accept a caller-selected, journal-recovered, restored or reused challenge.
The OIDC document **does not cryptographically attest the OS process**:
the inability to copy the already authorized process is an explicit host
assumption to qualify, not an accomplished cryptographic property.

### 4.5 One in-process continuation (L -> Codex)

**P15 — Atomic local launch fence.** After verification, the exact protected
L instance atomically changes a private in-process state
`WAITING -> CLAIMED` once, and only the winning continuation invokes
the pinned Codex subprocess. No second entrypoint, background retry,
implicit crash recovery, queue redelivery, forked copy of authorization state,
or reentrant code path may launch. A process crash after CLAIMED but before
`exec` loses the attempt; it does not reset the journal.

**P16 — Evidence and sanitization.** The launcher must retain independently
checkable one-shot execution/failure evidence **without** writing tokens,
the protected challenge context or authorization bytes into packet,
model-visible environment/argv, logs, artifacts or Issue comments.
Only the minimal verified input snapshot and approved runtime environment
reach Codex. The original result, evidence, publication and observed
Shutdown boundaries remain separate.

## 5. State and transition table

| Authority state | Live launcher | Allowed model-side operation | Failure disposition |
| --- | --- | --- | --- |
| `REQUESTED/ADMITTED/PREPARED` no ARM binding | Optional passive prepared instance | No model; new qualifying pre-ARM session may be prepared under current rules | Existing pre-ARM recovery, subject/capacity revalidation |
| `ARMED/count=0` in a new J-CH record | None | **Forbidden/unreachable under candidate atomic transition; refuse** | Reject invalid versioned state; preserve legacy records by their own semantics |
| `ARMED/count=1` with atomic binding | Same original L only | One OIDC-bound local continuation after original C positively observes its single CAS | Lost token/session/process: permanently consumed, no replay |
| `ARMED` with response/transport ambiguity | Unknown | No new model grant or new launcher | `INDETERMINATE` where evidence requires; stop/observe |
| `TERMINAL_CAPTURED/VALIDATED/REPORTED` | No execution grant | Only evidence/validation/publication operations | Existing post-model recovery |
| `INDETERMINATE/STOPPED` | No execution grant | No new model process | Cleanup or historical read-only |

For J-CH v0.1.1, **ARMED and count-one are the same durable state change**.
`ARMED/count=0` remains possible in historical **legacy** records and
remains non-replayable under their accepted contracts. No v0.1.1 validator
may reinterpret a legacy ARM as a fresh challenge-eligible grant. Count-one
is not evidence that the provider actually received a model request.

### Protocol trace, ideal non-failing case

```text
C validates authorized PREPARED request/packet/capacity/runtime/recipient
C starts L through authenticated bounded SSH (no model capability yet)
L -> C : HELLO(j-ch-v1, challenge=N, exact identities)
C -> J : ONE CAS_ATOMIC_ARM(PREPARED/count0 -> ARMED/count1,
                            immutable binding(N,L,C), new J-CH schema)
J -> C : positive exact-commit readback of state, count, binding and parent
C -> GitHub issuer : request OIDC(audience=sha256(versioned envelope + N))
C -> L : closed envelope + JWT through same protected session
L : independently verify exact envelope, issuer, claims, nonce, code, inputs
L : atomic WAITING -> CLAIMED (once)
L : start pinned Codex exactly once
C : recover evidence; validate; publish if valid; observe Shutdown
```

**P17 — No downstream authorization from desired state.** A successful SSH
exit, JWT signature, Git commit existence, workflow success, file hash or
result comment cannot individually establish the complete state transitions
above. Unknown or conflicting evidence blocks.

## 6. Failure and adversarial cuts

| Cut | Required candidate behavior | Evidence to qualify |
| --- | --- | --- |
| Two controllers, same request | One wins the single AtomicArm CAS; loser cannot ARM again or mint | Exact competing ref parent/head, losing controller refusal |
| Two passive launchers, distinct challenges | A controller must own the session producing its challenge; no peer-hello adoption or new binding after ARM | Session context and cross-process rejection |
| Crash before AtomicArm commit | Existing PREPARED recovery only, with exact input/capacity revalidation and a fresh controller-owned session | Journal remained unarmed |
| AtomicArm CAS committed, ACK lost | No OIDC mint, no retry/rebind; attempt spent even if original readback later sees it | Git head and lost-ACK witness |
| Crash between ARM/count-one | **Impossible in new J-CH atomic history**; legacy ARMED/count0 is read under old non-replay rules | Offline state exclusion and backward-compatibility tests |
| Controller dies after atomic count-one | Active L must not gain a new permission; disconnect/timeout semantics need explicit qualification | Transport and launcher state |
| OIDC response or SSH delivery lost | No mint retry, no new launcher, eventual cleanup/uncertainty | Exact issue/run/attempt and no new model start |
| Same JWT delivered twice to same L | Local atomic fence allows at most one Codex start | Two delivery concurrent test |
| Old JWT to fresh process/Codespace | Different fresh challenge/recipient, reject | Real recipient and challenge checks |
| Codespace shutdown/rebuild/deletion | Missing local consumption file does not mint permission; old ARMED attempt stays spent | Journal current head; no launcher replay |
| Model starts, response lost | `INDETERMINATE` if terminal evidence absent; never retry | Independent execution/evidence record |
| Journal 403/5xx/timeouts, malformed read | Distinguish UNKNOWN from authenticated 404; refuse any consumption or new mint | Fault-injected GitHub transport tests |
| Journal ref delete/recreate, force or semantic rollback | **No unconditional safety claim under current repo settings.** Threat ownership/control must be accepted or stronger authority introduced | Effective writers/rulesets, ancestor and transition analysis |
| Privileged L cloned after authorization | **Counterexample** without an excluded host compromise or separate non-copyable enforcement | Host/launcher trust decision and attack-model review |
| One L reenters its claimed continuation | Must be impossible by construction; test race/reentrant/fork path | Exact executable/system-call observations |
| Journal transition to `INDETERMINATE` races with a live authorized continuation | **OPEN BLOCKER**: reconcile cancellation/Shutdown and active launcher fencing without asserting false non-execution | Operational interleaving/cleanup qualification |

**P18 — Conservative recovery.** Every uncertain post-ARM cut prevents
new grant issuance. Losing the chance to call the model is accepted; losing
consumption history or accepting a second launcher is not.

## 7. GitHub journal authority — explicit unresolved constraint

Q1 observed a private repository with all ten
`review-claims/*` branches marked `protected:false`,
no protected branches among the 61 enumerated, and three current workflows
declaring `contents: write`. Ruleset listing returned a
GitHub-plan-related 403; branch-protection detail was inaccessible to the
integration. The owner has admin access. A full inventory of writers and
bypass actors has **not** been established.

**P19 — Writer trust or stronger authority.** Production cannot claim
monotonic consumption against compromised/misbehaving authorized writers
merely because the broker uses a non-forced Git ref update. A descendant
commit can carry a semantically older `attempt.json`. Ref deletion
can make a formerly consumed request indistinguishable from a request whose
claim was never created. If these threats remain *in scope*, J-CH needs a
separately justified non-rollback anchor or a different trust architecture.

**P20 — Fail-closed journal errors.** Proposed journal reads distinguish
an authenticated, exact not-found response from permission/network/server
errors; the latter must not be interpreted as absence and must never permit
fresh claim/ARM. **Even a genuine 404 cannot prove that a claim was never
created and then deleted**. Claim creation after a missing historical ref is
an unresolved authority problem, not solved by better HTTP status parsing.

**P21 — No silent semantic rollback.** Every versioned writer must reject
invalid state regressions and preserve recorded binding/history/count fields.
Append-only/ancestor validation may detect some faults **only if** the
authoritative history and refs themselves remain trustworthy. No proposed
hash, Git ancestry test or branch rule is claimed to defeat an actor with
full in-scope admin control.

## 8. Versioned interface changes (proposal, not implementation authorization)

| Existing owner | Minimal change required if J-CH were accepted |
| --- | --- |
| `queue.py` and journal record contracts | Separate legacy vs J-CH schema; closed binding; **atomic ARMED/count1 transition**; forbid J-CH ARMED/count0 |
| `github_journal.py` | One versioned atomic pre-arm-to-consumed operation with exact parent/binding/readback; strict unknown/absent transport; history semantics |
| `arm_controller.py` and workflow | Pre-ARM bidirectional L handshake with session ownership; exact run/recipient binding; **one** new J-CH CAS; new OIDC audience |
| `arm_authority_contract.py` / `arm_oidc.py` | Disjoint versioned envelope and exact challenge/commit validation; no v1 JWT acceptance by J-CH |
| `arm_execution.py` / `codex.py` | Protected same-incarnation launch continuation; one-shot fence; disable legacy bypass |
| `arm_consumption.py` | Remains authoritative for accepted legacy path; **no removal prior to an accepted replacement and migration plan** |
| Recovery / reconciliation | Never mint/rebind/complete another controller's ARMED record; explicit session/cancellation ambiguity |
| Trust/profile/bootstrap | Maintain protected launcher/runtime and credential isolation; distinguish reconstructable trust config from immutable historical consumption |

An accepted future J-CH deployment must use an explicit
`j-ch-v1` feature/admission gate bound to its reviewed SHA and
compatible schema. It must not be enabled by merging a design proposal,
passing an offline fixture, or receiving a favorable independent review.

## 9. Falsification and qualification plan

**P22 — Offline model and fixture gate.** Extend the bounded state-model
from #91 phases 2/3 and phase 4 (AtomicArm) with exact recorded binding,
original-controller/session ownership of the **single** CAS, lost ACK,
duplicate proof, nonce reuse, reentrant/forked launcher, competing
Git writes, semantic rollback, ref deletion, permission failure and reconciler
races. Assert at most one authorized Codex start; independent actor/call
counts and traces must make the property non-vacuous. Do not mislabel a
bounded finite checker as an unbounded formal proof.

**P23 — Sacrificial non-inference gate.** Only under *separate* owner
authorization, test an isolated disposable GitHub claim namespace/repository,
real GitHub Actions and Codespaces SSH/stdin, bound OIDC, process start/reentry,
disconnection, restart and shutdown. Replace Codex with a fake executable
whose process-start observation is independent and non-volatile. Never use
Request #82 or a real consumer source for these tests. No API/model token
is used for a fake-model probe. An absent receipt alone is not proof of
zero process starts.

**P24 — Independent review and adoption gate.** Obtain an independent
hostile technical review on exact versioned candidate bytes and applicable
threat model. Resolve/accept every material finding. Then produce an
explicit comparative owner decision J-CH/J2-A/J2-B/E/B and, **only after
owner acceptance**, propose a normative contract/ADR migration and bounded
implementation issues. Live ARM, OIDC issuance, protected bootstrap and
model-capable qualification require separate operational authorization.

## 10. Decision ledger

| ID | Open decision / missing evidence | Recommended provisional disposition |
| --- | --- | --- |
| D01 | Are compromised writers/admins and process-memory clones excluded for low-sensitivity use? | Explicit owner risk acceptance required; not inferred from #27 |
| D02 | Where to introduce a new journal schema and J-CH eligibility for never-ARMED attempts? | Favor new claim-time protocol marker; no implicit legacy upgrade |
| D03 | Can the *same* privileged launcher retain trustworthy bidirectional SSH continuity from hello through launch? | Controlled operational proof needed |
| D04 | Can a **single** versioned AtomicArm CAS safely combine ARMED and count-one while ensuring only its original live controller/session may mint? | Preferred finite-model candidate; exact GitHub/SSH qualification and contract redesign required |
| D05 | Can active L be prevented from reentry/bypass and proven non-copyable within accepted threat model? | Core independent-review blocker |
| D06 | How to fence a possible live continuation during reconciler cancellation/`INDETERMINATE`? | Block design GO until resolved |
| D07 | What is acceptable anti-semantic-rollback protection with private unprotected refs? | Writer-boundary acceptance or stronger authority |
| D08 | Is J-CH still cheaper/safer than J2-A, J2-B, E and B once all obligations are counted? | Compare before architecture adoption |

## 11. Acceptance criteria for this *draft specification*

- Every grant is bound **before ARM** to one exact request/attempt,
  packet, input, workflow/run, recipient and *live launcher challenge*.
- For **new** J-CH records, the **single** `PREPARED/count0 -> ARMED/count1`
  CAS binds the challenge and consumption together; no intermediate
  `ARMED/count0` state or second completion operation is permissible.
- Every token minted by the original live controller after positively
  confirmed **AtomicArm** is challenge- and commit-bound, checked only
  in its original intended live L process.
- At most one protected one-shot continuation reaches the Codex process.
  A crash after ARM cannot authorize a fresh launcher or token.
- Claim deletion, semantic rollback and in-scope privileged compromise
  remain explicit blockers, not falsely modeled as solved by a hash.
- v1 OIDC/local consumption and all historical attempt identities remain
  valid under their accepted contracts; no old consumed attempt is replayed.
- Independent security/model review and owner adoption are **not**
  inferred from a publication or finite-state PASS.

```text
PROPOSAL=RB91_J_CH_ARM_BOUND_CHALLENGE
PROPOSAL_VERSION=0.1.1
PROPOSAL_STATUS=DRAFT_NON_NORMATIVE
DESIGN_PREFERENCE=J_CH_ATOMIC_ARM_BOUND_CONDITIONAL
ACCEPTED_ARCHITECTURE=NONE
ACCEPTED_OIDC_CONTRACT=V1_UNCHANGED
NEW_WIRE_SCHEMA=NOT_IMPLEMENTED
THREAT_MODEL_OWNER_ADJUDICATION=PENDING
INDEPENDENT_HOSTILE_REVIEW=NOT_PERFORMED
IMPLEMENTATION_AUTHORIZED=NO
PRODUCTION_ARM_AUTHORITY_QUALIFIED=NO
PRODUCTION_ADMISSION=DISABLED
HISTORICAL_REQUEST82=IMMUTABLE_CONSUMED
V3_PREPARED_ONLY=UNCHANGED
```
