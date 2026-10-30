---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Successor Pre-Model Preparation Failure Protocol"
version: "0.1.2"
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
and no second model invocation. No clock timeout, new service, or general
`AttemptState` is required as the starting design.

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

This object is stored and updated **inside the single deterministic
Git-ref claim**, using the existing non-force fast-forward compare-and-
swap (CAS); there is no second cross-ref transaction or external
database. The journal history appends immutable versioned evidence-ID
events on each accepted change.

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

## 5. Terminal refusal and shutdown transaction ordering

For a proven `PERMANENT` failure **after claim, before PREPARED**:

1. Read the current claim. Require `REQUESTED` or `ADMITTED`,
   the current reservation/generation, a bound resolved admission,
   and `invocation_count=0`. Reject any record with `PREPARED`,
   `ARMED`, prior model invocation or contradictory history.
2. Validate the bounded permanent-failure receipt and **CAS-commit
   `REFUSED_PERMANENT` before any resource cleanup**. This disposition
   is an admission/armament veto in *every* v3 workflow, journal
   transition, prepare recovery and reconciler path.
3. Establish the **current global ownership** of the dedicated
   Codespace before any `stop` command. A per-request claim
   cannot by itself exclude an *other* request's active worker
   on the same Codespace. The existing GitHub Actions concurrency
   group `review-broker-single-reviewer` across both review and
   reconciler workflows is a **candidate serialization mechanism**,
   not yet a qualified resource-owner proof for v3 or out-of-band
   controllers. Bind the Codespace name, authenticated workflow run,
   request/attempt/generation and an exclusive owner/lease
   observation. If another attempt owns it or exclusivity is
   unestablished, **do not stop the other attempt's resource**;
   record a blocked cleanup incident for this refused claim.
   Only after safe resource ownership is established, obtain a
   genuine `Shutdown` observation for that exact Codespace.
   A worker that never started its Codespace still needs a real
   observed Shutdown under the existing rule. Never synthesize it.
4. Via a **specialized** version-gated journal CAS, move only
   `REQUESTED → STOPPED` or `ADMITTED → STOPPED` if the exact
   already-committed `REFUSED_PERMANENT` receipt, no-`ARMED`
   history, `invocation_count=0` and matching Codespace Shutdown
   receipt are validated. This is **not** enabled through the
   generic `transition_record`/`record_shutdown_transition` API.
5. Preserve both immutable evidence IDs and a terminal reason
   `PREPARATION_REFUSED` in the version-2 journal. Emit a truthful
   pre-model refusal disposition, **not** a fake `ReviewResult`
   claiming Codex `COMPLETED`/`GO`/`NO_GO`.

If the process crashes after the refusal CAS but before shutdown,
the reconciler performs **cleanup only**; it must not resume
acquisition, dispatch or arm. If it cannot verify shutdown, leave
the blocked refusal durably visible and report an infrastructure
incident. A late worker loses its attempt/generation CAS, and
cannot overwrite a permanent refusal with `PREPARED`.

The narrower proposed `STOPPED` route changes future v3-only
semantics. Existing v1/v2 post-publication and indeterminate cleanup
remain exactly as they were. No global expansion of arbitrary
STOPPED transitions is approved.

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
| PM07 | Permanent-refusal CAS committed, cleanup crashes | Reconciler cleans up only; no redispatch or model invocation |
| PM08 | Invalid/mismatched Shutdown receipt or other attempt's Codespace | Never `STOPPED`; infrastructure incident remains visible |
| PM09 | Correct permanent failure, valid Shutdown | Specialized `REQUESTED/ADMITTED → STOPPED`, zero invocations |
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
| PM22 | Claim A refusal/cleanup overlaps claim B's Codespace ownership | A cannot stop B's Codespace or record falsely owned Shutdown; block without verified exclusivity |
| PM23 | v3 Issue opening event and reconciler discover the same request concurrently | Both use one reservation controller; only one worker dispatch, no direct `issues:opened` bypass |
| PM24 | Worker A validates generation, worker B wins recovery/refusal CAS before A commits `PREPARED` or `ARMED` | Versioned transition CAS rechecks worker/generation/disposition **atomically**; A cannot commit with a stale prior read |
| PM25 | Manual generation advance from `PREPARED`, or failed worker cleanup tries to carry old `worker`/failure fields forward | Refuse advance from `PREPARED`; successful earlier-state advance atomically resets current worker/failure fields and preserves immutable history |

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
pre-model `STOPPED` transition. Reconciler must never infer liveness
or permission from a timeout. An ambiguous/unknown outcome is
explicitly blocked pending authorized recovery or disposition.

**Not resolved by this draft:** strict dual-version journal reader
and rollout incompatibility with older deployed workers; implementation
API/schema details of the v3 claim, proven GitHub worker-input correlation
and atomic fencing at `PREPARED/ARMED`; global Codespace ownership proof
across requests, actual permission administration, offline race/fault
test results or independent review of all governing sources. These require **separately authorized**
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
`WORKER_GENERATION_FENCING_QUALIFIED=NO`
`SHARED_CODESPACE_OWNERSHIP_QUALIFIED=NO`
`REAL_JOURNAL_CONCURRENCY_QUALIFIED=NO`
`INDEPENDENT_REVIEW=NOT_PERFORMED`
`IMPLEMENTATION_AUTHORIZED=NO`
`LIVE_INFERENCE_AUTHORIZED=NO`
