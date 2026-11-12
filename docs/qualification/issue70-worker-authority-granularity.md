---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "strict"
name: "Issue70 Worker Observation Granularity"
version: "0.1.0"
---

# Issue70 Worker observation granularity

## Scope and preserved historical results

This correction addresses repeated provider authentication during local packet
work. It changes no request, journal, packet or receipt wire identity, timeout,
dispatch opportunity, upload opportunity or mutation opportunity. It is an
implementation and qualification correction with no normative adoption.

Request101 remains consumed, unresolved and permanently non-retryable.
Request105 remains durably PREPARED with an original Worker that exceeded its
45-minute bound and terminated cancelled. Its original live review remains
NO_GO and its result PARTIAL. A corrected historical replay is not original
Worker success. No new live qualification, source-App mint, claim mutation,
Artifact upload, Codespace, ARMED or model execution is authorized here.

## Measured mechanism

The unchanged construction candidate was
`1d8ea4d1da5f3fdceee48925820c8fc66c54f063`. A complete provider-shaped simulation
uses actual Controller, Worker, admission, policy, journal, packet, retention,
Artifact and cold-observer code. Doubles implement only external provider/Git
acquisition and the official Artifact child. Qualification wrappers count actual
methods and requests without replacing domain decisions or retaining headers.

The baseline records 2,018 complete current-Worker authentications, 2,608 Actions
run reads, 2,608 job reads and 10,263 journal-ref reads. Local retention alone
causes 427 complete authentications. Historical corpus collection reconstructs
the ACK 237 times. The causal call chain is:

```text
local file/hash/verifier callback
  -> policy before_effect
  -> current Worker require_current
  -> journal/ref confrontation and Actions run/job observation
  -> additional journal confrontations around those provider calls

historical local callback
  -> complete historical verify
  -> admission/ACK/Controller/Worker reconstruction
```

These counters qualify the amplification mechanism, not a unique attribution of
every minute in the original live run. Historical commit times are approximate
phase markers: ADMITTED to PREPARED was approximately 2,558 seconds, followed by
approximately 87 seconds before cancellation. The original direct operator
observer also timed out after 2,400 seconds with last progress at 5,700 reads.
The earlier supplemental frozen-response replay remains its separate historical
69.884-second observation.

## Responsibility and authority separation

`WorkerLocalPhaseV3` owns local integrity of the exact authenticated Worker phase.
It is issued only through the original current-Worker authority after full
current authentication. It binds the original context, snapshot bytes, journal,
expectation, execution boundary, dispatch authority, principal and active
original decision. It has no dispatch, upload, journal-write or policy-selection
API. Copy, deepcopy, pickle and raw-state clones cannot register as the original
scope. Phase transfer invalidates the old scope. There is no wall-clock lease,
TTL, persisted permission or restart continuation.

The concrete live composition explicitly enables these local scopes. Historical
injected composition retains its strict callback behavior. Local policy and
packet byte/file operations check the original scope and decision without
inherently reconstructing complete GitHub authority per operation.

External access uses a distinct current-effect guard. Mutable reference reads,
source acquisition guards, Artifact child spawn and return, metadata/readback
use, and PREPARED preparation/CAS still confront mutable journal and runtime
currentness. A cancelled Worker cannot gain new effects. The existing mutation
operation binding, exact expected predecessor, original decision consumption and
expected-old CAS remain independently required. The local scope cannot replace
any of them. This is causal boundary checking, not cross-system atomicity.

`PreparedJournalHistoryV3` authenticates the historical admission, transition,
ACK and runtime links at construction. It seals exact historical bytes and
trust-dependency identity for pure local integrity checks. Explicit `verify()`
still revalidates the trust authorities, including revocable injected
recognition. Provider boundaries use that explicit method; local extraction and
historical policy callbacks use `require_local_integrity()` instead.

`GitHubProtectedPolicyAuthorityV3` may reuse the exact already-verified immutable
selection tuple. The original active selection guard is unchanged; this cached
data grants neither selection nor mutation authority. Changed receipt, source,
context or expectation does not hit the tuple. Historical observers remain
read-only and independently obtain their authority outside downloaded packets.

## Regression and safety qualification

Four new tests first fail against unchanged source: local retention complete
authentication, local packet Actions reads, repeated historical ACK
reconstruction and a finite historical provider-read ceiling. A 10-to-100 local
operation scaling witness requires zero added remote authentication.

The safety witnesses exercise stale refs before source and upload, movement
after upload, cancelled Worker, wrong job/principal/executable, stale phase,
copy/serialization/raw clone, restarted construction, cached data presented as
mutation authority and a competing expected-old CAS. They retain one original
Python Worker, one child upload and no automatic retry. Existing RWP01–05,
original-process, replay, ACK, Artifact, failure and v1/v2 oracles remain intact.

An initial correction regressed the existing RQ17 explicit trust-revalidation
oracle. Its RED result is retained. Restoring explicit full `verify()` while
separating local integrity resolves that finding without changing the oracle.
The final Issue70 receipt owns exact-source measurements, full regression,
Ubuntu CI, direct replay and independent-review evidence; planned gates in this
document are not represented as already accepted.

## Diagnostics and direct historical replay

The closed observation diagnostics own only safe counters and monotonic phase
durations. They retain no provider body, header, URL, credential or exception
text. Delivery failure cannot change a domain result or consumed opportunity.
They are emitted separately from canonical journal/packet identities and never
act as authority or a deadline lease.

Required phases include ACK, source B capture, Worker binding, ADMITTED, packet
build/verification, local retention/cold verification, upload/readback, PREPARED
CAS and final cold reconstruction. Counters distinguish ref, immutable Git,
workflow, run/job, ACK reconstruction, source and Artifact reads.

The direct historical replay uses fresh authenticated provider reads, native
immutable Git-object caching and the corrected native verification stack, not an
ad-hoc API-response cache. Its preselected limits are 600 seconds and 1,000
provider reads. It must reconstruct Request105's exact packet and remote receipt
with zero source mint, dispatch, claim mutation or upload. An earlier passing
replay on an intermediate correction is not substituted for the final source.

The local full-suite umask-077 failure in the unrelated unsafe-root fixture is
tracked by [Issue107](https://github.com/fanilosendrison/review-broker/issues/107).
The same failure reproduces at the unchanged baseline; umask022 is its positive
control. This task changes neither that test nor its production guard. The
failed suite remains failed; final normal-environment and exact Ubuntu outcomes
must be reported separately.

## Remaining qualification boundary

PR93 remains draft and unmerged. Issue70 and parent67 remain open even after a
successful correction: nominal live terminal completion is not demonstrated by
read-only replay. Any future terminal live PREPARED qualification requires its
own owner mandate and independent specimen. Neither historical request may be
retried or reused. No next task executes automatically.
