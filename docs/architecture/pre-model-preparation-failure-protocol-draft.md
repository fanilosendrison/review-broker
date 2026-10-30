---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Successor Pre-Model Preparation Failure Protocol"
version: "0.2.0"
---

# Successor v3 — durable pre-model preparation outcomes

**UNACCEPTED, NON-NORMATIVE, NOT IMPLEMENTED. No workflow, journal, Codespace, source-permission or Codex operation is authorized by this proposal.**

## 1. Why this contract is needed

This is a focused companion to draft PR #55 under Issue #51. It addresses
#56 F001/F005 and the demonstrated current-behavior gaps in
[test-only draft PR #57](https://github.com/fanilosendrison/review-broker/pull/57)
at its later exact head `4ef45da3e0de2fe852d2a4a88df0644acbc67d46`,
whose [CI](https://github.com/fanilosendrison/review-broker/actions/runs/41042188166)
was `PASS` (501 tests, two explicitly expected future-contract failures).
The earlier 500-test evidence remains unchanged.

Actual `reconciliation.reconcile_repository` dispatches an `ADMITTED`
claim on every sweep; current `queue.py` prohibits direct
`REQUESTED/ADMITTED → STOPPED`. The additional real
`GitHubRefJournal._read` counterexample proves that the existing v1
decoder reads a hypothetical v2 journal but `AttemptRecord.as_dict`
then **re-serializes it as v1 without `pre_model_control`**.
These are observed **current-code** boundaries, not passed v3 tests.
A durable request/attempt identity alone prevents neither repeated
pre-model dispatch nor a future unsafe version downgrade.

The design goal is **one automatic initial pre-model dispatch**, a
truthful immutable refusal receipt for permanently impossible requests,
explicitly authorized *same-attempt* recovery for transient faults,
and no second model invocation. **A v3 attempt that never acquired
the shared Codespace need not stop that Codespace merely to terminate
its own claim**. This narrows the original blanket Shutdown requirement.
No clock timeout, new service, or general `AttemptState` is required
as the starting design.

## 2. Version boundary and strict state ownership

For accepted v1/v2, preserve the entire historical journal schema v1,
transition map, claim identities, request bytes, result markers and
reconciliation behavior. **Do not silently add fields or reinterpret
a historical `STOPPED` as a preparation refusal.**

For future v3 only, the candidate `AttemptRecord` journal wire format
is **schema_version 2** with one extra **closed** `pre_model_control`
object. It retains the existing request ID, ordinal-1 attempt ID,
admission, history, evidence IDs, invocation count, packet identity
and publication fields under their existing semantics.

**Mandatory decoder/version gate (observed #57 gap):** current
`AttemptRecord.from_dict` does **not** check `schema_version` or reject
extra fields, while `as_dict` unconditionally emits `schema_version: 1`.
The new journal read path MUST validate the **full canonical wire
object before constructing any attempt record**, dispatch only the
exact recognized journal version, and preserve every v2 control byte
and semantic field on read/CAS-write/recovery. Unknown versions, unknown
fields and missing v2 control fail closed, without silently invoking the
v1 decoder. Historic v1 records remain interpreted with their original
semantics. **Rollout must prohibit an older v1-only executable from
processing or rewriting a v2 claim**; merely changing the new parser
does not retroactively protect older deployed workers. This version
migration is a prerequisite before any v3 claim is enabled.

### Minimal journal v2 migration candidate — isolated qualification #58

[Test-only PR #58](https://github.com/fanilosendrison/review-broker/pull/58)
now contains a **second, smaller** closed journal-v2 candidate alongside
the original overwide pre-model prototype. The
`journal-v2.compat.candidate.schema.json` variant retains **all
production v1 `AttemptRecord.as_dict` fields under their original
names**, plus `schema_version=2` and **only one new top-level field:
`pre_model_control`**. It preserves historical `history[]` state/event
entries (and their `evidence_ids`), appending bounded v3-only
pre-model events without rewriting previous entries. The initial
prototype's extra `packet_evidence_id` is unnecessary: `PREPARED`
already binds packet evidence through its transition history and
`evidence_ids`.

The isolated compatibility adapter calls actual production
`AttemptRecord.from_dict`/`as_dict` and `transition_record` for the
legacy portion **after** a strict v2 schema/version check. It is
not installed in `src/review_broker` or the live GitHub-ref journal.
[CI 41052515721](https://github.com/fanilosendrison/review-broker/actions/runs/41052515721)
reports **546 passing tests**, including 12 new migration-shape
roundtrip/CAS tests and 15 separately mocked external-authority
boundary tests. The full experiment is test-only; no v3 deployed
journal, old-worker rollout, distributed GitHub-ref CAS or
Codespace owner is thereby qualified.

**Important v1 transition detail:** current production may durably
record `state=ARMED` with `invocation_count=0` before separately
setting invocation count to 1. The minimal candidate round-trips
this intermediate as a valid state; a future trusted executor may
invoke Codex **only after** the one-invocation durable boundary is
established. If v3 chooses to combine ARMED and count=1 in one CAS,
that is a separate normative change requiring counterexamples
and preserving v1 historical records.

The required `pre_model_control` fields are:

| Field | Type and meaning |
| --- | --- |
| `schema_version` | Integer 1 |
| `generation` | Integer ≥0; 0 at claim, incremented exactly once per accepted dispatch authorization |
| `disposition` | One of `UNRESERVED`, `RESERVED`, `BLOCKED`, `REFUSED_PERMANENT` |
| `reservation_id` | Null for generation 0; otherwise exact immutable dispatch-reservation identity |
| `authorization_id` | Null for generation 0; otherwise exact initial request ID or independently authorized recovery receipt ID |
| `worker` | Null until bound; otherwise **exactly** `{"run_id": <positive integer>, "run_attempt": <positive integer>}`, persisted by worker-winning CAS before acquisition |
| `failure_receipt_id` | Null until a current generation's validated failure receipt is durably bound |

The schema and combination rules are **closed**. `UNRESERVED` is legal
only at generation 0. `RESERVED` permits initial acquisition by exactly
the bound generation/worker. `BLOCKED` requires a typed `TRANSIENT` or
`UNKNOWN` failure receipt. `REFUSED_PERMANENT` requires a typed
`PERMANENT` refusal receipt. `PREPARED` and later states may not be
entered from `BLOCKED` or `REFUSED_PERMANENT`. On a separately
authorized generation advance, **clear current `worker` and
`failure_receipt_id`, set `disposition=RESERVED` and the new
`reservation_id`/`authorization_id` in the *same CAS*, while preserving
prior reservation, failure and approval evidence immutably in history.
A disposition left `RESERVED` after an ambiguous external dispatch
does not invent a failure receipt or indicate that nothing happened.
Generation advance is forbidden once the claim is `PREPARED` or later.

**Illustrative component only** (not an executable existing journal):

```json
{
  "schema_version": 1,
  "generation": 0,
  "disposition": "UNRESERVED",
  "reservation_id": null,
  "authorization_id": null,
  "worker": null,
  "failure_receipt_id": null
}
```

This object is stored and updated **inside the single deterministic v3
Git-ref claim**; there is no second cross-ref transaction or external database.
For every future transition on an existing claim, the selected non-normative
candidate commit primitive is GitHub GraphQL `updateRefs` with exactly one ref
update: authenticated broker `repositoryId`, exact
`refs/heads/review-claims-v3/<digest>` `name`, mandatory predecessor
`beforeOid`, successor `afterOid`, and `force=false`. The successor commit must
name the observed predecessor as its direct parent. REST non-force fast-forward
updates do not satisfy the mandatory explicit expected-old-SHA condition.

Before constructing the successor, the writer must strictly decode the exact
predecessor snapshot and validate the state transition together with current
generation, reservation, worker and disposition. GraphQL CAS commits that
already-validated transition; it does not perform semantic validation. A
successful transport response is insufficient if the GraphQL response contains
`errors` or exact identity-bound readback does not reconcile to the intended
successor. Failed or ambiguous updates cause no automatic mutation retry, no
second model dispatch and no assumption that the transition committed.
Readback equality alone does not prove which actor originated an identical
commit. The journal history appends immutable versioned evidence-ID events on
each accepted change. The mutation has no cross-ref transaction semantics and
introduces no additional lock, database, service or ledger.

## 3. Dispatch reservation, winner and bounded retry policy

### Exactly one automatic initial dispatch

1. Authenticated v3 request and stable GitHub target identity must
   pass admission before claim. An invalid request creates no claim.
2. Create/reuse the deterministic v3 claim with `UNRESERVED,
   generation=0` and the immutable resolved admission evidence.
3. The trusted v3 controller is the **only** initial-dispatch route.
   Both the `issues:opened` notification and scheduled/manual reconciler
   provide *discovery* only and converge on that same controller.
   A v3 `issues:opened` workflow must not itself prepare, arm or invoke
   a reviewer. The controller CAS-reserves `generation=1,
   disposition=RESERVED` in the deterministic claim **before**
   invoking exactly one externally dispatched worker workflow.
   A v1/v2 direct-Issue handling path remains unchanged.
4. `reservation_id` is deterministic:
   `"preparation-dispatch:sha256:" + SHA256(RFC8785({schema_version:1,request_id,attempt_id,generation,authorization_id}))`,
   where the initial authorization ID is the authenticated original
   `request_id`. The future closed schema fixes exact byte encoding.
5. The dispatched workflow must receive `request_id`,
   `reservation_id` and `generation` as **literal, verified inputs**;
   the broker revalidates them against the same CAS journal claim and
   authenticated original request. The worker CAS-binds its exact
   protected GitHub `run_id/run_attempt` once before any source
   acquisition. A duplicate worker for the same reservation is an
   observer, not an executor.
6. At the **atomic journal CAS that commits `PREPARED`, `ARMED`,
   and any authorized transition toward model invocation**, the
   versioned transition itself must check: current generation,
   reservation ID, worker run identity, unchanged admitted source
   identities, permitted disposition and prior state. A separate
   read-before-write check is **insufficient**: another recovery or
   refusal CAS could win in between. Competing current/stale workers
   cannot commit from local cached authority.
7. Prevent all v3 worker paths—including a manually dispatched
   workflow, event replay, and trusted CLI subcommand—from bypassing
   this versioned reservation gate. Keep all v1/v2 event and
   publication semantics unchanged.

A successful reservation CAS is **not evidence that GitHub accepted
the dispatch**, and an ambiguous response is **not a license to
re-dispatch**. A reconciler observing `RESERVED` must not automatically
create another reservation or resend the same external dispatch.
A failed/stale CAS is re-read; it is never force-updated or blindly
retried. Losing dispatch or journal-write acknowledgement cannot
create a second model-capable invocation.

**Actual GitHub Actions API boundary (October 2026):** the
[workflow dispatch endpoint](https://docs.github.com/en/rest/actions/workflows)
supports an optional `return_run_details: true` argument returning
`200` with `workflow_run_id`; its default remains `204` without a run
ID. The current broker's `dispatch_review_workflow` does **not**
yet request or persist this optional result. A future v3 controller
may use the richer acknowledged run ID as evidence **only after**
authenticated independent GET readback verifies exact broker
repository ID, workflow ID, expected executable HEAD, run attempt
and registered worker/reservation correlation. A `204`, invalid
200 response or lost transport is **UNKNOWN**, not a reason for
automatic redelivery. The run ID alone is **not** a source App
authorization, an owner approval or a Codespace ownership lease.

### Explicit recovery only, no arbitrary timeout

The automatic dispatch budget is **exactly one per v3 canonical claim**.
There are **zero automatic redeliveries** after that reservation
(including after an unobserved crash or a transient remote error).
No timeout, retry-after duration or hourly sweep count silently
resets this limit.

A new `generation = previous + 1` reservation is permitted
**only while the attempt is `REQUESTED` or `ADMITTED` and no
`PREPARED` packet has ever been committed**. It requires a fresh
authenticated owner/operator recovery authorization, with a 128-bit
nonce, exact request/attempt ID, previous reservation and generation,
verified original admission, and an observation of the previous
workflow's status and owned resource. One authorization permits
**one** new dispatch reservation. No `PREPARED`, `ARMED`, terminal
or indeterminate claim may reset generation to obtain a new source
capture or model attempt.
A stale nonce/generation or concurrent owner CAS attempt is rejected.

A previous workflow may be queued or start late. Therefore its
generation and worker identity must be rechecked at `PREPARED` and
`ARMED`; an old run cannot arm after another generation is current.
If previous-run termination or identity cannot be established,
record `BLOCKED / UNKNOWN` and do not infer that retry is safe.
A historical observation of *no currently running workflow*
**cannot prove** an ambiguously accepted external dispatch will
never be delivered later. A new generation may be admitted only
with the required owner authorization, verified absence of a
prior `PREPARED`/`ARMED` transition, and enforceable **atomic
generation fencing** of any late old worker at registration,
`PREPARED` and `ARMED`. If any of those controls cannot be proven,
remain blocked. An owner may decline recovery; a blocked unarmed
attempt is not a completed review.

### Exact candidate recovery-authorization basis

The **only** qualifying v3 recovery authority is an authenticated
owner/operator action that produces this closed receipt (illustrative
typed placeholders, **not** a live authorization):

```json
{
  "schema_version": 1,
  "evidence_type": "pre-model-recovery-authorization",
  "request_id": "request:sha256:<64 lowercase hex>",
  "attempt_id": "attempt:sha256:<64 lowercase hex>",
  "previous_generation": 1,
  "previous_reservation_id": "preparation-dispatch:sha256:<64 lowercase hex>",
  "authorization_nonce": "<32 lowercase hex>",
  "actor_github_id": 12345,
  "prior_run_observation_id": "artifact:sha256:<64 lowercase hex>",
  "authorized_at": "2026-10-30T00:00:00Z"
}
```

The recovery authorization ID is
`"pre-model-recovery:sha256:" + SHA256(RFC8785(receipt))`.
Its `actor_github_id` must be verified from trusted GitHub/operator
authentication for the exact requester/claim; the raw field is
**not** proof of authorization. The prior-run observation must
establish an appropriately quiescent previous workflow/resource,
or fail closed. The authenticated receipt is durably bound in
the single Git-ref journal before new dispatch. A unique nonce
alone never grants permission, and repeat use of the same receipt
cannot create another generation.

The first generation uses `authorization_id=request_id`; subsequent
generations use the above verified `pre-model-recovery:sha256:` ID.
A recovery CAS must require `previous_generation` and the current
prior reservation to match the latest journal state. Recovered
generation number and dispatch reservation are derived
deterministically from that winner; no independent counter or
new model-attempt ID is allocated.

This is a **finite automatic policy without timeouts**. It does
not impose an arbitrary cap on separately approved manual owner
decisions, each of which is independently audited and cannot change
the one-invocation guard.

## 4. Permanent, transient and unknown preparation failures

The **trusted broker**, never the untrusted source or mission prose,
assigns an exact closed classification and reason code. Three
semantically distinct outcomes are necessary:

| Class | Illustrative technical reasons | Journal rule |
| --- | --- | --- |
| `PERMANENT` | unsupported source kind, disallowed repository, authenticated immutable object-ID mismatch, invalid selector, verified expected-digest mismatch, unsupported requested atomicity | Record `REFUSED_PERMANENT` by CAS; no `PREPARED` or new same-claim dispatch |
| `TRANSIENT` | separately evidenced recoverable API/service transport interruption, local source-transfer failure with identities intact | Record `BLOCKED` with validated transient receipt; explicit recovery only |
| `UNKNOWN` | ambiguous 403/404, missing authentication proof, uncertain dispatch acceptance, contradictory evidence, crash without a reliable failure cause | Remain `BLOCKED`; never call it a proven absence/permanent refusal or auto-retry |

A **confirmed** nonexistence under authenticated complete read
authority may qualify a permitted optional `omitted` packet entry,
but is not equivalent to an ambiguous 404. A required source
with proven absent content fails preparation; whether its source
error is permanent must be established by verified observations.

The candidate **closed failure receipt** has the following fields:

```json
{
  "schema_version": 1,
  "evidence_type": "pre-model-preparation-failure",
  "request_id": "request:sha256:<64 lowercase hex>",
  "attempt_id": "attempt:sha256:<64 lowercase hex>",
  "admission_evidence_id": "artifact:sha256:<64 lowercase hex>",
  "generation": 1,
  "reservation_id": "preparation-dispatch:sha256:<64 lowercase hex>",
  "workflow_run_id": 123,
  "workflow_run_attempt": 1,
  "classification": "PERMANENT",
  "reason_code": "SOURCE_DIGEST_MISMATCH",
  "reference_id": "contract",
  "observation_evidence_id": "artifact:sha256:<64 lowercase hex>",
  "observed_at": "2026-10-30T00:00:00Z"
}
```

Placeholders are illustrative, not valid hash values. For a refusal
at generation 0, the reservation and workflow fields are null.
For non-reference reasons `reference_id` is null. A workflow may
also be null if no worker was bound, **without claiming a
negative observation from absent fields**.

The receipt ID is `artifact:sha256:SHA256(RFC8785(receipt) + LF)`,
matching the existing canonical-newline evidence convention. The
receipt binds the failure to the exact journal generation and
admission, with a bounded non-secret technical reason, an immutable
evidence ID for the actual trusted observation, and no raw token,
private content, arbitrary traceback or untrusted prose. A caller-
supplied error string is **not** sufficient to certify failure class.

The receipt and new disposition are written by **one CAS update
of the same claim ref**. A failed CAS means re-read and classify
the winner; do not assume the failure was stored. A worker may not
proceed from a rejected/blocked generation simply because its local
memory still says `ADMITTED`.

## 5. Terminal refusal: attempt finality is not Codespace shutdown

**Normative-direction correction (v3 proposal only):** terminality of a
ReviewRequest is not a claim that the *globally shared* Codespace is
`Shutdown`. The historical v1/v2 `STOPPED` contract **remains
unchanged**; the successor may introduce a narrowly specialized
v3-only `STOPPED` receipt for a permanently refused, **unarmed,
pre-`PREPARED`, Codespace-non-acquiring** attempt.

### 5.1 Minimal resource-acquisition boundary

The [current workflow](https://github.com/fanilosendrison/review-broker/blob/f9e902ee577d3a22330c3bf2fb04dcae28ed3034/.github/workflows/review-request.yml)
runs `internal-prepare` **before** the first Codespace
`start` step. Its stop step is conditional on
`steps.start.outcome != 'skipped'`. Hence a failure before
preparation can occur without this worker touching the Codespace.

For future v3, all **effectful Codespace operations**, including
`start`, `stop`, remote `ssh/exec`, copy/transfer and other
Codespace lifecycle mutations, MUST be reachable **only after**
the exact attempt's journal is durably `PREPARED`, from a worker
whose reservation/generation/identity is checked through the
trusted broker. Access to remote GitHub source APIs during
preparation does **not** count as Codespace acquisition; the
no-acquisition claim is strictly about the Codespace and does
not claim zero network activity.

A stale or queued worker must be denied **before any Codespace
side effect**, even if it is launched after a permanent-refusal
CAS. The journal-side guard must enforce the current v3
reservation, committed `PREPARED` state and worker identity.
A log indicating that `start` was skipped is **not enough**
to establish this guarantee in the presence of unknown work,
alternative CLI entry points, old deployed workers or an
ambiguous start request. All such bypasses must be excluded
before v3 operational enablement.

### 5.2 Zero-Codespace-access permanent refusal

1. Verify the original exact admission and `REQUESTED`/`ADMITTED`
   claim, with `invocation_count=0`, no `PREPARED` history
   and no model-capable transition. A permanent failure receipt
   is already bound by CAS to `REFUSED_PERMANENT`; this
   prevents any later preparation/arming or Codespace start.
2. Prefer **a preventive, version-bound gate proof** over
   attempting to prove a negative from every GitHub step log.
   Qualify all of the following *together*:
   - the authenticated immutable **workflow/executor version**
     actually permitted to process this v3 claim, with an
     exhaustive list of effectful Codespace command entry points
     (including trusted CLI and reconciler paths);
   - a **mandatory trusted pre-side-effect guard** on every such
     path: the current worker's exact reservation, generation,
     immutable admission and a durably committed `PREPARED`
     must be accepted by the same journal authority;
   - **older/unfenced executable exclusion** during rollout,
     including already queued or delayed workers, and absence
     of independently available pre-`PREPARED` Codespace
     control credentials or bypass routes;
   - the exact claim's immutable journal history and
     `REFUSED_PERMANENT` CAS: **no `PREPARED` or `ARMED`
     was ever committed**, and zero model invocations.
   Under these **qualified preventive premises**, any late
   worker executing an effectful Codespace command must be
   fenced out. Therefore this claim did not acquire Codespace
   **through the trusted broker**, regardless of how many
   workflow deliveries were pending. Exhaustively replaying
   all GitHub step logs is **not necessary** to establish
   this implication. The authenticated run/jobs API remains
   useful for *diagnostics and provenance*, but a `skipped`
   step or absent log line alone proves nothing about
   bypasses, alternative commands or other workers.

   **If any preventive premise is unverified**—including
   exact deployed version, code/credential entry-point
   coverage, old-worker exclusion, journal-fence atomicity
   or possible unguarded side effects—**do not** infer
   non-acquisition. Retain the blocked refusal. An
   individual run trace does not repair an unguarded
   delayed-worker path. A worker-unbound claim can use
   this proof **only after** global entry-point/rollout
   coverage is genuinely qualified; the earlier isolated
   fixture covers registered workers only.
3. Bind an exact **no-Codespace-acquisition receipt** to the
   permanent-refusal CAS. Its eventual minimal basis should be
   the request/attempt/reservation/generation, immutable journal
   no-`PREPARED` evidence, and **independently qualified
   executable/gate/rollout evidence IDs**. Run identity and
   step observations may be added when genuinely needed for
   provenance, but no `codespace_access_attempted=false`
   boolean from requester text can replace the gate proof.
   [PR #58's original synthetic receipt fixture](https://github.com/fanilosendrison/review-broker/pull/58)
   still requires complete injected run-trace and registered
   worker coverage: **that is an earlier, deliberately
   overconstrained experimental shape, not the accepted
   minimum**. The receipt's final schema, canonical identity
   and proof validator must be separately closed before
   implementation; do not silently promote this fixture.
4. Use **one specialized, version-gated journal CAS** to enter
   `STOPPED` directly from `REQUESTED` or `ADMITTED`,
   validating both the permanent-refusal receipt and the
   no-acquisition receipt, with no `PREPARED`, `ARMED`
   or inference. Preserve evidence IDs and terminal reason
   `PREPARATION_REFUSED_NO_CODESPACE_ACCESS`.
   **Do not call `controller.state()`, `stop()` or
   `start()` on the shared Codespace.** Do not create a
   synthetic Shutdown receipt or a fabricated ReviewResult.

The Codespace may legitimately remain `Available` under
**another** request's ownership. This has no bearing on the
terminal refusal of A if A provably never touched it. The
new receipt proves bounded **non-acquisition by A**, not that
the global machine is stopped or unused.

### 5.3 When no-acquisition cannot be established

If a Codespace `start`, `stop`, `ssh`, `copy` or
remote execution was **actually attempted** by this claim
before its permanent refusal, or its result is unknown
**and the universal preventive gate is not qualified**,
do **not** issue the no-access receipt. Retain
`REFUSED_PERMANENT`, avoid redispatch/inference, and
report a blocked cleanup/authority incident. An ambiguous
effectful external command cannot be reclassified as
non-acquisition because the machine later appears idle.

**However**, missing individual run/step logs are *not by
themselves* a blocker once an independently qualified
universal gate, protected credential entry points, deployed
worker-version exclusion and a no-PREPARED journal jointly
prove the absence of **broker-authorized** acquisition.
A skipped step remains diagnostic evidence only. The
actual current broker has not yet established these
premises; do not interpret this distinction as live
authorization to terminalize any existing claim.

If another path genuinely acquired the shared Codespace,
remote cleanup requires a **separately qualified, exclusive
cross-request resource-owner boundary** held continuously
through the stop operation, followed by authentic observation
of `Shutdown`. A per-request claim and the shared GitHub
Actions concurrency string do not alone prove that ownership.
If another request owns the Codespace, **do not stop it**.
Any attempt that reached `PREPARED` or `ARMED` remains
under its normal packet/at-most-once recovery path, not the
preparation-refusal shortcut.

A crash after `REFUSED_PERMANENT` before terminal receipt
causes the reconciler to **assess non-acquisition proof or
report BLOCKED**. It must not automatically stop the shared
Codespace. The old blanket `STOPPED`-requires-`Shutdown`
rule applies to **historical v1/v2 attempts** and to v3
cleanup paths that actually acquired the resource, not to
this specialized v3 no-acquisition terminal receipt.

### 5.4 Qualification boundary

[Test-only PR #58](https://github.com/fanilosendrison/review-broker/pull/58)
exercises **PM26–PM35** on an in-memory reference with
injected trace/gate/worker-coverage assumptions. A later
**source-confronted preventive-gate test** also demonstrates
the *conditional logical implication*: permanent pre-`PREPARED`
journal + a universally enforced, version-qualified
Codespace side-effect gate + exclusion of old executables
implies no broker-authorized Codespace acquisition. It also
reproduces present-code gaps: direct `review-request.yml`
`start` has no v3 gate and `internal-reconcile`/CLI
expose additional Codespace-affecting entry points.

The real [GitHub Actions run/jobs API](https://docs.github.com/en/rest/actions/workflow-jobs)
can authenticate run and step metadata, but does **not
independently attest the absence of arbitrary side effects**
inside an executing step. Every code-path/gate/credential
and rollout premise still needs independent evidence before
v3 can terminalize on the preventive basis. The current
CI experiments **do not qualify a deployed gate**.

## 6. Transient refusal, crashes and safe resumption

For a `TRANSIENT` or `UNKNOWN` failure, CAS-write `BLOCKED`
with the failure receipt **before** returning a failed pre-model
workflow outcome. The reconciler emits a blocked observation,
not another workflow dispatch. If no failure receipt was committed
because of a crash, the surviving `RESERVED` generation is
**ambiguous**, not eligible for automatic redispatch.

A manual recovery authorization may advance a genuinely quiescent
`BLOCKED` or `RESERVED` generation to a newly reserved generation
only after independent inspection of the prior run and exact
journal/target identity. Each authorized resume retains the same
request ID, ordinal-1 attempt, canonical request, immutable
repository/object IDs and version pins. Only **unpinned bytes of
the same authenticated mutable source** may change before
`PREPARED`.

If `PREPARED` exists, replay must rebuild the **identical packet**
and cannot perform a new remote-source capture. If `ARMED` or
model-capable transport might have occurred, use the existing
indeterminate/no-retry semantics. No owner authorization can
reset invocation count or mutate a historical packet.

## 7. Deterministic counterexample and crash matrix

These are **required future implementation tests**, not already
executed or independently qualified fixtures:

| ID | Injection / conflict | Required observation |
| --- | --- | --- |
| PM01 | One v3 Issue observed by reconciler three times | **One** dispatch reservation and at most one dispatch, not three |
| PM02 | Two concurrent reconcilers reserve generation 1 | One CAS winner, one losing observer, no second dispatch |
| PM03 | CAS committed; GitHub dispatch response lost | No blind second dispatch; persisted reserved ambiguity |
| PM04 | Dispatch delivered late after explicit generation 2 | Generation 1 worker cannot bind, `PREPARED` or `ARMED` |
| PM05 | Permanent failure while source acquisition might already be in flight | CAS blocks **new authorized** acquisition/packet commit/arm; already-started read may complete but has no permission to advance |
| PM06 | Permanent-refusal CAS vs competing `PREPARED` CAS | Exactly one CAS winner; losing worker cannot commit or arm, but already-completed external reads are not erased |
| PM07 | Permanent-refusal CAS committed, terminal-evidence processing crashes | Reconciler only verifies no-Codespace-access proof or blocks; no blind Codespace stop, redispatch or model invocation |
| PM08 | Invalid/mismatched terminal proof, or unknown Codespace acquisition | Never `STOPPED` without the appropriate verified evidence; do not stop another request's Codespace |
| PM09 | Pre-`PREPARED` permanent failure with verified no-Codespace-access receipt | Specialized `REQUESTED/ADMITTED → STOPPED` **without any global Codespace operation**, zero invocations |
| PM10 | Temporary API failure with saved blocked receipt | No automatic retry; one fresh owner recovery authorizes one generation |
| PM11 | Ambiguous permission/404 or unknown dispatch ownership | `BLOCKED/UNKNOWN`; never optional omission or unverified resume |
| PM12 | Crash before failure/disposition CAS | Reserved generation is ambiguous, not automatically re-dispatched |
| PM13 | Worker A and worker B race over one reservation | One run-bound winner; stale worker cannot prepare or arm |
| PM14 | `PREPARED` packet rebuilt with different mutable bytes | Rebuild rejected without rewriting history |
| PM15 | `ARMED` then lost transport response | Existing indeterminate/no-retry path; no manual reuse of invocation |
| PM16 | Replayed/stale owner recovery nonce, wrong actor or previous reservation | No new reservation; no generation increase or authorization from asserted actor text |
| PM17 | v1/v2 claim/read/reconciler and historical results | Exact old bytes/semantics remain unchanged |
| PM18 | Receipt contains raw secret, unsupported code or malformed canonical bytes | Validation rejects and no successful terminal disposition |
| PM19 | Permanent refusal already `STOPPED` when duplicate event arrives | No new claim, dispatch, or model call |
| PM20 | Reservation and failure-write endpoint return ambiguous status | Read exact committed claim state; do not assume external success or retry |
| PM21 | Current journal reader receives canonical v2 record with `pre_model_control` | Future decoder must reject unknown version or preserve v2 control byte-for-byte, **never** downcast to v1 (reproduced current gap in PR #57) |
| PM22 | Refused A has not acquired Codespace, while B legitimately owns an Available Codespace | A may terminate **without touching B** only with verified no-access proof; otherwise block; never stop B's resource |
| PM23 | v3 Issue opening event and reconciler discover the same request concurrently | Both use one reservation controller; only one worker dispatch, no direct `issues:opened` bypass |
| PM24 | Worker A validates generation, worker B wins recovery/refusal CAS before A commits `PREPARED` or `ARMED` | Versioned transition CAS rechecks worker/generation/disposition **atomically**; A cannot commit with a stale prior read |
| PM25 | Manual generation advance from `PREPARED`, or failed worker cleanup tries to carry old `worker`/failure fields forward | Refuse advance from `PREPARED`; successful earlier-state advance atomically resets current worker/failure fields and preserves immutable history |

| PM26 | Refusal before `PREPARED` with complete no-Codespace-access proof | Specialized `STOPPED` without Shutdown observation or Codespace I/O |
| PM27 | Codespace already Available under independent request B | A's verified non-acquisition terminal has zero start/SSH/copy/stop effect on B |
| PM28 | Unqualified mandatory start gate, executable identity or old-worker path coverage | Terminal no-access proof fails closed; missing step logs alone are not disqualifying once *universal preventive coverage* is independently established |
| PM29 | Start/SSH/copy/stop observed or outcome ambiguous, despite declared false flag | Reject no-access receipt; no false terminal state |
| PM30 | Old worker attempts Codespace start before `PREPARED` or after refusal | Mandatory trusted start gate rejects before external command |
| PM31 | Claim has reached `PREPARED` or `ARMED` | No pre-model non-acquisition terminal shortcut |
| PM32 | Receipt binds wrong request, worker, admission, reservation, generation or Codespace | Reject before terminal CAS |
| PM33 | Crash after permanent refusal but before run-evidence collection | No blind cleanup; remain blocked until qualified trace is available |
| PM34 | Unknown run delivery and incomplete step logs | Never infer no acquisition from a skipped step alone; a separately proven universal preventive gate can make exhaustive run enumeration unnecessary |
| PM35 | Terminal receipt CAS loses to concurrent state change or is replayed | No stale transition, second terminal receipt or model invocation |

Test GitHub-ref CAS with injected stale parent commits, not only an
in-memory journal. Test the real reconciler, new result-independent
refusal receipt validation, model-arm guards, workflow inputs,
journal version decoder and **shared Codespace ownership**.
Inject at every boundary between journal CAS, external dispatch,
worker registration, source acquisition, failure disposition,
another request's ownership, shutdown observation and `STOPPED`.

## 8. Acceptance limits and authority

**Decisions proposed for #51/PR #55:** keep existing attempt states
and journal-ref CAS; introduce only a versioned preparation-control
record, a tightly bounded dispatch reservation and a specialized
pre-model `STOPPED` transition with **two evidence-bound contexts**:
verified no-Codespace-acquisition refusal (no global stop required),
versus resource-owning cleanup after real acquisition. Reconciler
must never infer liveness or permission from a timeout. An ambiguous/unknown outcome is
explicitly blocked pending authorized recovery or disposition.

**Qualification boundary:** the real GitHub experiment completed bounded
qualification of GraphQL `updateRefs` as an explicit-`beforeOid`, single-ref,
non-force CAS primitive. It observed wrong-predecessor rejection, stale replay
rejection, one competing-writer single-winner case and non-fast-forward
rejection. It did not test every runtime interleaving. The experiment used the
owner's authenticated GitHub identity, not the future GitHub Actions journal
writer token.

**Not resolved by this draft:** acceptance of the new minimal
v1-compatible journal-v2 wire candidate (its earlier overwide
alternative remains explicitly superseded only as a **design
preference**, not a normative artifact), strict dual-version decoder
rollout isolation against **older deployed workers**, integration of GraphQL
CAS with real v3 journal transition validation, concurrent initial claim
creation, effective GraphQL mutation authority for the intended GitHub Actions
`GITHUB_TOKEN`, external dispatch 200/204 evidence recovery, authenticated
worker/run and owner-approval sources, and atomic worker fencing at
`PREPARED`/`ARMED` and **before any Codespace side effect**. Proof of no Codespace acquisition
from authenticated complete workflow traces remains **unqualified**
outside injected tests. **Cross-request shared Codespace ownership
is still unproven**, but it is not a prerequisite for terminalizing
an attempt that provably never acquired that resource. No
operational stop authorization derives from those tests. Live external fault injection and
source-complete independent review also remain missing. These require **separately authorized**
normative-contract acceptance and implementation/qualification.

No existing v1/v2 source files, workflows, package schemas,
test-run artifacts, app permissions, Codex credentials or results
were modified by this proposal.

`PREMODEL_PROTOCOL_STATUS=PROPOSED_NOT_NORMATIVE`
`DISPATCH_POLICY=AUTO_INITIAL_ONE_MANUAL_EXPLICIT_ONLY`
`AUTOMATIC_RETRY_AFTER_RESERVATION=ZERO`
`GENERAL_ATTEMPT_STATE_ADDED=NO`
`SPECIALIZED_STOPPED_TRANSITION=PROPOSED_NOT_IMPLEMENTED`
`STRICT_JOURNAL_V2_DECODER_QUALIFIED=NO`
`MINIMAL_JOURNAL_V2_SHAPE_TESTED_OFFLINE=YES`
`ACTUAL_GITHUB_DISPATCH_AUTHORITY_QUALIFIED=NO`
`WORKER_GENERATION_FENCING_QUALIFIED=NO`
`SHARED_CODESPACE_OWNERSHIP_QUALIFIED=NO`
`PREMODEL_NO_CODESPACE_TERMINAL=PROPOSED_NOT_IMPLEMENTED`
`NO_CODESPACE_PROOF_EXTERNAL_AUTHORITY=UNQUALIFIED`
`PREVENTIVE_GATE_PROOF_CANDIDATE=SOURCE_CONFRONTED_NOT_DEPLOYED`
`COMPLETE_RUN_STEP_TRACE_AS_MANDATORY=NOT_REQUIRED_IF_PREVENTIVE_GATE_QUALIFIED`
`NO_RESOURCE_STOP_REQUIRED_FOR_PROVEN_NONACQUISITION=PROPOSED`
`GRAPHQL_EXPECTED_OLD_CAS_PRIMITIVE=BOUNDED_REAL_EXPERIMENT_PASS`
`V3_WORKFLOW_ACTOR_GRAPHQL_CAS_AUTHORITY=UNQUALIFIED`
`CONCURRENT_INITIAL_CLAIM_CREATION_QUALIFIED=NO`
`INTEGRATED_V3_JOURNAL_TRANSITIONS_IMPLEMENTED=NO`
`REAL_JOURNAL_CONCURRENCY_QUALIFIED=NO`
`INDEPENDENT_REVIEW=NOT_PERFORMED`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
