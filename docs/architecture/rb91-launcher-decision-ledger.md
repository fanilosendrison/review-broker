---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "RB91 Launcher Boundary and Decision Ledger"
version: "0.1.0"
---

# RB91 — D01–D08 and protected continuation

## D01 — Trust assumptions

**Disposition: prior owner decision preserved; no new anti-admin prerequisite.**
[2026-11-07 decision](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6706691402)
trusts GitHub and approved authorized writers for ordinary Review Broker.
Fully adversarial privileged history destruction is outside that claim.
Ordinary crashes, malformed input, permissive credentials, leaked credentials,
wrong transitions and protocol implementation bugs remain qualification targets.

The accepted OIDC contract already excludes compromised runtime administrators.
Arbitrary root-level memory snapshot/cloning is outside the candidate claim;
ordinary accidental fork, restart with imported state, shared nonce, reentry or
reviewer-accessible launch paths are NOT excluded. This boundary must be
confirmed in owner adoption, not assumed proved by Q2 or an opaque process ID.

## D02 — Versioning

**Disposition: complete candidate, not adopted or deployed.**
New claims select journal2 / `j-ch-v1` from creation. Request1 or request2 is
independent. Version1 retains its exact original7/extended11 producer shapes,
local consumption and two ARM writes. Unknown versions/keys fail before writes.
No migration of existing PREPARED or consumed records is proposed.
R2 source refusal is integrated; J20 operational enforcement is still open.
A v2 reconciler must dispatch by record protocol before selecting recovery;
legacy reconciliation must refuse v2, not reinterpret it as absent.

## D03 — One session

**Disposition: Q2 PASS_BOUNDED; failure lifetime unqualified.**
Q2 observed same launcher PID, birth ticks and control-pipe inodes across HELLO,
three-second controller delay and PROOF on one non-TTY SSH command. Four nominal
scenarios plus supplemental successful duplicate sends are described exactly in
#95. Separate observer/staging SSH sessions did not authorize another launcher.
A PID, birth tick or pipe inode is corroboration, not unforgeable process identity.

Candidate framing: one passive process, one original controller-owned stream,
4-byte network-order byte-length followed by canonical UTF-8 JSON, clean stdout,
separate bounded diagnostics. HELLO maximum 16,384 bytes; PROOF maximum 100,000
bytes including envelope/JWT JSON, with JWT at most 32,768 ASCII characters.
The 16-KiB historical fixture is NOT a PROOF limit. A future constructor must
measure maximal envelope/proof bytes before ARM; if the complete bound cannot
fit, refuse pre-ARM rather than truncate or split/reconstruct authority. DONE
carries no token. Control frames never become model input or retained evidence.
Unknown frame versions/types, duplicate keys, oversized/truncated/noncanonical
frames, partial EOF and timeout abandon the session. No post-ARM reconnect.

Candidate pre-ARM wait has a monotonic 120-second deadline; proof must satisfy
existing issuer time checks and that original deadline. A timeout forfeits the
session; it is not evidence that an already running child stopped. This is a
bounded proposed policy, not a timing guarantee or chosen production setting.
Abrupt SSH loss/controller SIGKILL/orphan behavior is still to be qualified.

## D04 — AtomicArm

**Disposition: one proposed update; Q3 bounded primitive evidence.**
One unique direct child A of P commits PREPARED/count0/null→ARMED/count1/binding.
The exact original controller submits one GraphQL `updateRefs` with explicit
P/A and `force:false`, checks clean response and freshly verifies exact A and
its bytes/direct parent. It then mints once and rechecks before delivery.
Any generic GraphQL error, ambiguous response or changed/unknown readback is
permanent NO_MINT/NO_RETRY, even if A later appears. `clientMutationId` is only
correlation. Q3's losing errors are untyped; no CAS-conflict inference is valid.
A remains the consumption point even if no controller knows it succeeded.

## D05 — Privileged launcher boundary

**Disposition: specified conditional mechanism; actual executable unqualified.**
Preferred L-S retains the synchronous child/evidence arrangement rather than
inventing an external supervisor required by exec-in-place L-X. L-X remains a
hardening option, not a necessary second authority.

Candidate responsibilities:

- A pinned protected supervisor owns the control descriptors, CSPRNG state,
  monotonic deadline, immutable preflight snapshot, challenge and one-shot state.
  It never executes packet code, extensions, plugins or reviewer callbacks.
- It starts from a clean protected executable/config/import environment BEFORE
  any challenge exists. No user-selected nonce, restore/checkpoint, inherited
  authorized state or journal-recovered challenge is accepted.
- A fresh 256-bit challenge belongs only to that process incarnation and its
  original authenticated controller stream. Its public journal value is not a
  bearer secret. Controller memory owns the original stream handle and pending
  mutation; another run or reconstructed stream cannot adopt that ownership.
- One serial message dispatcher validates the complete proof against private N,
  exact A/P/binding, workload/recipient/runtime/input and protected configuration.
  It atomically changes WAITING→CLAIMED once BEFORE any child-creation call.
  Concurrent duplicate messages lose. CLAIMED never becomes WAITING again.
- One syntactic call site starts one pinned child with prompt bytes held in memory,
  no control stdin, closed unrelated FDs, approved environment and separate output.
  Spawn error, timeout, uncertain spawn, child failure or post-claim crash NEVER
  retries. Evidence capture remains a separate responsibility after the start.
- No fork, worker pool, serialization, callback registration or copy of challenge/
  authorization/continuation is permitted after challenge creation. The intended
  child is not a second authorizing launcher and cannot invoke the start call.
  An ephemeral exclusive packet marker is defense in depth, not durable authority.
- After proof handling, control bytes are not written to packet, argv, child env,
  ordinary logs or uploaded artifacts. Reviewer tools cannot read the supervisor's
  memory/control FDs or invoke an alternative legacy J-CH-unbound entry point.
  Exact OS/user/process boundary and inherited capabilities require qualification.

### Non-cloning and ordinary defect cases

1. Two separately started passive launchers: independent N values; only one N
   can be bound by AtomicArm. The loser receives no valid proof.
2. Launcher restarted with old JWT: new N; reject. Caller cannot set N.
3. Two threads/process messages to one launcher: one atomic claim/start call.
4. Fork after N or after CLAIMED: prohibited program behavior; negative control
   demonstrates two starts are possible if this obligation is removed.
5. Privileged snapshot copy after authorization: protocol cannot distinguish the
   copies; outside arbitrary-admin trust boundary, never claimed prevented.
6. Reviewer accesses control pipe, `/proc` authority bytes, alternate CLI or launch
   callback: deployment/implementation FAIL, not a trusted-host exclusion.
7. New Codespace, remount or missing evidence marker: no durable rebinding; spent
   GitHub authority remains spent. Old N cannot be reconstructed into permission.

A PID, nonce, SSH connection, executable hash or `O_EXCL` file alone cannot
establish all these properties. The one-shot program proof and effective
capability/isolation tests remain mandatory. Current source does not implement it.

## D06 — Reconciler and active launcher

**Disposition: counterexample retained; minimal candidate repair specified.**
Existing review/reconciler/publication Actions share
`review-broker-single-reviewer`, `cancel-in-progress:false`. They do not ordinarily
run concurrently. This does NOT kill an orphaned remote launcher after its
Actions controller exits. The Codespace qualification workflow uses another
group and can interfere; every future lifecycle mutator needs common custody.

Two distinct semantics:

- S1: INDETERMINATE records uncertainty, not revocation. Existing v1 mark-first
  recovery remains truthful under S1 and never permits a second grant.
- S2 (recommended for candidate v2): a terminal journal decision advertised as
  incompatible with a future start follows a proven quiescence fence. This adds
  an ordering obligation, NOT retroactive cancellation or exactly-once effects.

Counterexample to naive S2: AtomicArm accepted; clean ACK/proof delivered; C dies;
L claims continuation; R begins and marks INDETERMINATE; L starts first child.
At-most-once still holds, but no-start-after-terminal does not. The same trace
exists if R merely sends cancellation. Checking GitHub just before spawn has a
check/use gap and is not a repair.

### Proposed priority and fencing rules

1. No recovery actor may mint, redeliver, rebind or reconstruct an authorization.
   Lost ARM ACK remains spent/uncertain even if later observed exactly at A.
2. After controller loss/cancellation, R acquires the common lifecycle scheduling
   custody covering ALL trusted start/stop/deploy/qualification paths for that
   recipient. No new grant is created by acquiring custody. Out-of-Actions tools
   must participate through the same controlled path or have no effective
   lifecycle privilege during the operation. Arbitrary admin misuse remains
   residual; an uncontrolled ordinary mutator blocks operational qualification.
3. R may send one bounded cancellation request. A positive protected receipt is
   sufficient ONLY if the supervisor atomically fences WAITING/CLAIMED against
   future spawn AND confirms every already started child has exited. A queued
   request, socket EOF or controller death is not such a receipt.
4. The conservative default is stop exact bound Codespace and independently
   observe actual Shutdown. This fences ALL possible old launcher/child starts
   under trusted provider semantics. No process-memory restore is allowed.
   A stop timeout/UNKNOWN leaves consumed ARMED plus infrastructure incident;
   it does not publish a false S2 terminal decision or permit another attempt.
5. While custody remains held, reobserve the current canonical journal. If valid
   terminal capture has appeared, use evidence-only recovery, not overwrite it
   as absent. Otherwise CAS exact current ARMED→INDETERMINATE using the bound
   quiescence evidence; then specialized STOPPED only with Shutdown receipt.
   If head changed, do not overwrite; reclassify for recovery without minting.
   Uncertain terminal CAS is evidence-only reconciliation, never execution retry.
6. The v2 INDETERMINATE transition from other post-ARM states also requires
   quiescence; REPORTED/STOPPED and captured terminal evidence cannot silently
   coexist with an unaccounted live continuation. Reconciliation of pre-ARM
   states never invents a grant; bound cleanup still requires truthful receipts.
7. A launcher observing an incompatible terminal state before it claims/spawns
   abandons. That observation is an extra refusal check, not the sole fence.
   After a child has started, terminal observation/cancellation cannot undo it;
   outcome remains uncertain until complete evidence exists.

Starts between proof delivery and actual quiescence are allowed first starts
and must be counted; even stop-first cannot promise zero inference in that
interval. Once Shutdown is established, a cold restart generates fresh state,
not a continuation of the consumed incarnation. Lifecycle custody prevents
restart races from invalidating the shutdown observation before terminal CAS.

Owner adoption must approve the v2 ordering change. Existing v1 recovery is NOT
modified. Actual Shutdown, cancellation ACK integrity, all-mutator custody,
remote child death and terminal-evidence races require separate live qualification.

## D07 — Retention and rollback

**Disposition: ordinary trusted-writer boundary retained.**
All writers validate parent/child monotonicity, strict versions, evidence prefixes,
count and immutable binding; no protocol operation deletes consumed authority.
Ref deletion, forced rewrite or semantically regressive descendant by a fully
privileged actor cannot be defeated by CAS/hash alone. These remain explicit
residual incidents under D01, not a reason to require a second store solely for
malicious GitHub administration. Missing/corrupt/inaccessible state denies grants;
404 does not prove no historical deletion. No automatic repair or resurrection.

## D08 — Selection

**Disposition: RECOMMEND_J_CH conditional, owner selection outstanding.**
The [comparison](rb91-architecture-comparison.md) uses the exact historical
variants, including J2-B's post-ARM late-binding semantic question. J-CH is not
preferred merely because earlier comments preferred it: it removes the split
ARM window without exposing a writer to the executor or requiring unqualified
persistent storage. Its D05/D06 obligations remain real and are not removed by
choosing another durable store alone.
