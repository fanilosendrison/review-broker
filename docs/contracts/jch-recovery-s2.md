---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "J-CH S2 Recovery"
version: "0.1.0"
adoption_status: "proposed"
---

# J-CH S2 Recovery

**Proposed normative contract for journal2 only; no lifecycle operation authorized.**
Legacy recovery retains its accepted mark-indeterminate-then-stop order. Version
and protocol dispatch precede recovery action. An unsupported record refuses;
it is never absent, migrated or offered a new grant.

## Safety priority

Once AtomicArm is accepted, consumption remains spent independently of ACK,
model start, executor death, result availability or cleanup. No recovery actor
may mint execution authority, redeliver/rebind a proof, reconnect for invocation,
allocate another ordinal or restore a challenge/continuation. Recovery is
lifecycle/evidence/validation/publication authority only, within exact admitted
scope. A storage-purpose proof changes none of that.

For new v2, an incompatible terminal/indeterminate journal decision follows a
verified quiescence fence under held lifecycle custody. Neither INDETERMINATE
nor a stop request retroactively cancels a process. A first start may happen
while cancellation/stop is in transit; it must be counted and never called zero
inference. A fresh head read before exec has a check/use gap and is not a fence.

## Custody and bounded fence

All trusted start/stop/deploy/qualification paths for the same recipient must
participate in one controlled lifecycle custody boundary. Shared Actions
concurrency is scheduling only; it does not kill orphaned processes or serialize
arbitrary direct credential users. Uncontrolled ordinary mutators block operational
qualification. Source pins, exact recipient identity and independently checked
observations remain mandatory. No new distributed store is selected here.

The conservative default is stop the EXACT bound Codespace and independently
observe actual Shutdown, retaining custody through subsequent fresh-head checks
and terminal CAS. ShuttingDown, a requested state, SSH disconnect, controller
exit, cancellation transit, timeout, missing file or absent receipt cannot stand
in for Shutdown. A cold restart must not restore an authorized process image;
new launchers have fresh challenges and cannot inherit the consumed grant.

An optional protected cancellation receipt is sufficient ONLY if a separately
implemented/qualified supervisor atomically fences WAITING/CLAIMED against any
future spawn AND proves every previously started child has exited. A queued ACK
alone is insufficient. This alternative is not a second authority or permission
to invoke a new launcher; until qualified, use actual observed Shutdown.

The closed [quiescence receipt](../../schemas/jch-quiescence-v1.schema.json)
records exact request/attempt/protocol/count, recipient, original ARM commit and
binding digest when armed, method, observed state/time, lifecycle context and
custody/observation evidence IDs. Every field must match independently observed
trusted context. Schema-valid hashes or a `quiet=true` assertion are not a fence.
No JWT/control credential enters the receipt or evidence.

## Ordering under interruption and evidence races

1. Acquire/verify custody and reobserve exact current authoritative record and
   recipient. A lost ARM ACK remains consumed even if A is now visible.
2. Retain any recoverable exact runtime bytes privately without claiming a new
   terminal state. Preserve credential screening/quarantine and incomplete
   recovery diagnostics. Evidence collection itself creates no invocation grant.
3. Establish the actual quiescence fence. Any unknown/failure leaves consumed
   ARMED/current state plus infrastructure incident and evidence-only cleanup;
   do not fabricate a no-start terminal decision, reset state or select another L.
4. While custody remains held, freshly reobserve canonical current journal and
   terminal evidence. If valid capture appeared, follow evidence-only validation/
   publication; never overwrite it as absent. Otherwise propose the exact legal
   ARMED→INDETERMINATE transition with quiescence evidence.
5. Use expected-old CAS of the actual current head. Head drift, stale terminal
   proposal or uncertain acknowledgement never overwrites another outcome or
   creates mint/retry authority. Reclassify for evidence/recovery only.
6. STOPPED additionally requires the specialized actual Shutdown observation
   bound to recipient/request/attempt/context. A process-tree quiet receipt alone
   is not Codespace Shutdown. Preserve original binding/count/history throughout.

Normal terminal capture also requires proof that its original one-shot
continuation can no longer start a child and that the accounted process tree
has completed. If only Shutdown can establish that fact, retain raw evidence
first, observe Shutdown, then commit capture and downstream evidence decisions.
Do not infer process absence from a terminal enum or JSON event alone.

## Per-state limits

- Pre-ARM REQUESTED/ADMITTED/PREPARED may resume only the SAME attempt after
  reauthorization/reconstruction of exact recorded identities. Rejected capacity
  remains PREPARED/count0 and never dispatches automatically.
- Pre-ARM INDETERMINATE/STOPPED retain count0/null binding; no ARM opportunity is
  inferred from recovery. Post-ARM equivalents retain count1/original binding.
- TERMINAL_CAPTURED/VALIDATED recover exact original artifacts without inference.
  [Authenticated recovery storage](jch-result-retention.md) may use another job
  without relabeling the execution or changing content/evidence truth.
- Reserved or reported publication permits complete exact observation only to
  noncreators; no additional POST capability or result relocation resets intent.
- STOPPED remains historical; current mismatch is an incident, not a grant.

Cleanup liveness, artifact availability and universal exactly-once provider
inference are not promised. Missing/expired/contradictory proof blocks use while
consumption stays immutable. Real custody/Shutdown/child-tree/orphan/cancellation
qualification remains separate from normative adoption and offline models.
