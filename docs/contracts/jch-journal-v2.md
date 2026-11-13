---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "J-CH Journal v2"
version: "0.1.0"
adoption_status: "accepted"
---

# J-CH Journal v2

**Owner-accepted normative contract; effective only upon integration into dev.**
This contract governs future claims explicitly selected as journal2/j-ch-v1.
It does not change legacy journal1, admit a request, implement a writer, qualify
J20, or activate execution. [Adoption boundary](../adoption/jch-normative-adoption.md).

## J01–J04 — Version, exact bytes and identity

Journal version, ReviewRequest version and workload-envelope version are distinct.
A new eligible claim has strict JSON integer `schema_version=2` and literal
`protocol_id=j-ch-v1` from creation. No existing claim, including PREPARED, is
implicitly migrated. Request1/request2 retain their own accepted semantics and
canonical identities; one request has only `attempt_identity(request_id,1)`.

[The versioned schema](../../schemas/jch-journal-v2.schema.json) owns all exact
field names, required/optional sets, types and nested closure. The fifteen
required root keys are schema/protocol, request/attempt, state/count/history/
evidence IDs, arm binding, immutable resolved admission and admission authority,
and four explicit-null artifact/publication slots. Capacity is absent until
assessed, never an implicit null. Unknown versions/keys and unsupported nested
objects refuse BEFORE mutation; no lossy decode/encode or future-field stripping.

Raw journal bytes are strict UTF-8, RFC8785 canonical JSON plus exactly one LF,
maximum524288 bytes. Duplicate members, BOM, CRLF, nonfinite numbers, coercion,
invalid canonical form and size/parse uncertainty refuse. Integer fields never
accept booleans. Immutable structured identities compare canonical bytes, not
language equality such as True==1. Artifact identity uses exact bytes; an
unchanged digest cannot bless changed content.

Resolved admission closes the full request, resolved repository/PR/head/base/
merge-base, derived subject/mission/policy and (only for request2) Review Intent.
Recompute all identities; expected head must equal resolved head for request2.
Verify authorized initial/changed-head/repeat operation and predecessor evidence
BEFORE claim. Admission authority records authenticated actor/mode/executable/
broker context and exact authorization evidence, not a caller's assertion.
Request/attempt/protocol/admission/subject identities cannot change in descendants.

## J05–J09 — One irreversible AtomicArm

Before ARM, count is0 and binding null. A rejected capacity receipt remains
immutable PREPARED/count0 and cannot dispatch, transition to a model-capable
indeterminate state or be replaced to create another opportunity. PASS receipt
and exact final rendered input are checked before lifecycle and again at ARM.
Existing rendering/receipt/runtime/profile policies and credential veto apply.

Only `arm_once_challenge_bound` may propose PREPARED/count0/null→ARMED/count1/
binding. Generic ARM and legacy record_invocation are illegal for journal2.
There is no new journal2 ARMED/count0 intermediate state. The complete closed
binding includes original prepared parent P, live launcher challenge, request/
attempt/packet/subject/input/capacity, reviewer policy/executable identities,
broker/workflow/run, recipient and launcher/preflight identities. Cross-check
all against authenticated context and exact bytes, not only matching strings.

Compose one unique direct child A of authenticated P and validate parent and
child together. A may contain P, never its own recursively self-hashed SHA.
One GraphQL **updateRefs**, not updateRef or REST fallback, submits exact ref,
`beforeOid=P`, `afterOid=A`, `force:false`. Remote acceptance of A is the
irreversible consumption point, even if no controller receives its ACK or no
model process starts. Count1 means consumed authorization, not observed inference.

Only the original live submitting controller retaining its original authenticated
launcher stream may proceed after clean HTTP/GraphQL success AND fresh exact
readback of A, canonical record, direct parent, count and binding. clientMutationId
is correlation, not authority or idempotence. A different job/process/reconciler
cannot adopt a winner or reconstruct permission by reading matching history.
The original nonce/unique child and explicit expected-old exclude same-target
and divergent proposals under trusted GitHub semantics.

## J10–J13 — History and downstream states

The ordinary path is REQUESTED→ADMITTED→PREPARED→ARMED→TERMINAL_CAPTURED→VALIDATED
→REPORTED→STOPPED, with accepted explicit INDETERMINATE alternatives. History
starts with REQUESTED/empty evidence. Each mutation appends exactly one closed
operation-owned event and its evidence; ordered evidence IDs equal flattened
history. All prior history/evidence is prefix-preserved. ARM appends one
ATOMIC_ARM_CONSUMED event with count1/protocol/binding digest.

Binding/count remain null/0 through pre-ARM INDETERMINATE/STOPPED and original/
1 through every post-ARM descendant. Exact history, not the terminal enum alone,
disambiguates consumption. Binding and established capacity/metadata are
canonical-byte immutable. No no-op grant write, rebind, duplicated ARM, count
decrement, earlier state, erased event or terminal reversal is legal. Exact
idempotent reads create no commit/grant. Git fast-forward alone is insufficient.

Specialized evidence gates remain mandatory:

- ADMITTED and PREPARED require authorized resolution and exact verified packet.
- Capacity metadata is assessed once under the accepted conservative policy.
- TERMINAL_CAPTURED requires exact credential-screened inventory and one
  consistent started/terminal sequence for the bound packet/run.
- VALIDATED requires independent reconstruction/validation of those bytes;
  anchored citations do not establish semantic correctness.
- Locator plan/locator fields are closed and immutable, match original execution
  request/attempt/subject/packet/run and complete safe file inventory.
- Publication reservation/result/reference/receipt obey the separate
  [retention contract](jch-result-retention.md), faithful evidence projection
  and one live creator/no ambiguous second POST.
- Every incompatible post-ARM terminal/indeterminate decision obeys
  [S2](jch-recovery-s2.md). STOPPED additionally requires actual observed Shutdown.

Schema-valid metadata or a pure transition model is necessary, never sufficient
external evidence. Missing/expired/mismatched/contaminated proof blocks the
operation, not consumption history. New execution grants never arise downstream.

## J14–J19 — Observations and ambiguity

PRESENT_VERIFIED requires authentic scoped HTTP/API success, exact repository/
ref/commit/tree/content identity, canonical decoding and consistency of all
applicable observed facts. ABSENT_AUTHENTICATED is only a new-claim observation
with independently established repository/credential/effective-read capability.
Even an authenticated404 cannot prove no previous privileged deletion.

All other outcomes are UNKNOWN: auth/permission/rate-limit/server/transport error,
partial/deep/malformed data, contradictory scope/object/path/role/source facts,
GraphQL errors even with HTTP200, or incomplete observations. UNKNOWN is never
absence or permission. It forbids further authority effects; prior legitimate
completed effects remain counted/retained, not magically rolled back.

At/after the first AtomicArm submission, any ambiguous ACK/readback permanently
forfeits retry, mint, delivery, reconnection, rebinding or replacement continuation.
Later readback of A is evidence-only. Q3's generic provider errors are NOT typed
CAS conflicts. After positive ARM acknowledgement, mint once under the
[workload contract](jch-workload-authority.md), recheck the exact authoritative
reservation before delivery and forfeit on any changed/unknown observation.

GitHub validates neither business monotonicity nor launch uniqueness, no-delete,
job-to-reservation ordering or provider exactly-once inference. Trusted
qualified writers/controller/launcher remain necessary, with explicit residual
privileged destruction risk under ADR-001. No default repair/initialization.

## J20–J23 — Isolation and qualification boundary

Before the FIRST eligible claim2, every effective old reader/writer must reject
unsupported authority without mutation or be demonstrably drained/denied/isolated.
Inventory current/in-flight and rerunnable historical workflows, wheels/manual
CLI/direct writers, effective credentials and complete discovery/recovery paths.
New source does not patch old executables. A ref prefix is not access control.
If isolation cannot be proven, STOP admission; no implicit alternate namespace.

Original7/extended11 journal1 bytes, identities, parent OIDs, ordinal1, consumed
counts, local consumption and legacy two-write ARM remain unchanged. Request82
and all past ARMED/consumed attempts remain permanently non-replayable. No
historical renderer, result, evidence, journal or receipt is rewritten.

Formal normative adoption, implementation, independently qualified J20 and exact
operational admission are separate gates. Offline schemas/models and bounded
Q2/Q3 observations do not qualify live issuer/job custody, actual runtime/start
fences, durability, isolation or provider effects. A new request still requires
its own accepted explicit authorization; publication of this contract grants none.
