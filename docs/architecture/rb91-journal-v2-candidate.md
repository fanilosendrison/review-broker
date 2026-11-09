---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "candidate-contract"
domain: "independent-review"
severity: "draft"
name: "RB91 Complete Journal V2 ABI Candidate"
version: "0.1.0"
---

# RB91 — Complete journal v2 ABI candidate

**Non-normative, offline candidate only. No production implementation/admission.**
This completes the missing journal object domains in PR94 J01–J23 without
altering PR94/Q4. Its standalone executable
[JSON Schema Draft 2020-12](qualification/rb91-journal-v2-candidate.schema.json)
is a candidate resource under architecture, NOT an accepted resource in schemas/.
It is not imported by product code. The historical core schema stays unchanged.

## Boundary of completeness

The candidate defines every journal field and embedded object, including claim,
admission, capacity, binding, history, artifact metadata, publication reservation
and receipt. It intentionally keeps external evidence as exact content-addressed
artifacts, using existing `artifact:sha256:` byte identities. A reference is not
an opaque accepted object: exact bytes, length, contract and retrieval location
must validate before the consuming operation. Missing/unavailable/expired content
blocks that operation, never execution-recovery permission.

This closes **RB91-JQ-003 as candidate ABI specification work**, not as deployed
ABI qualification. Candidate-schema tests cover all nested domains. The pure
candidate model checks structural/identity/parent-child relations, not external
admission, issuer validity, actual artifact retention, GitHub publication or
quiescence authentication. Those remain separate mandatory gates below.

Five separate levels are maintained:

1. Complete candidate contract: this document and exact schema.
2. Executable candidate schemas and offline semantic fixtures: present and tested.
3. Real production v2 reader/writer/launcher: NOT implemented here.
4. Operational qualification/J20: NOT performed here.
5. Normative adoption: NOT performed here; only owner may accept.

## Wire and reference rules — J01–J07

**J01.** Literal JSON integer journal `schema_version=2`, `protocol_id=j-ch-v1`
from the FIRST claim. Request schema1/schema2 is selected independently. No
historical v1→v2 transformation exists, including unarmed PREPARED records.
Claim ref remains the existing deterministic mapping for the request digest,
conditional on future J20 same-namespace isolation; no new namespace is selected.

**J02.** The schema is the exact structural field table. All fixed-key objects
are closed. Artifact inventories alone are dynamic maps with bounded safe
relative-path keys and closed `{artifact_id,byte_length}` entries. Decode strict
UTF-8, reject duplicate members/nonfinite numbers, and require RFC8785 bytes plus
one LF. Raw journal maximum is 524,288 bytes; oversize refuses without partial
parsing. Integers are exact JSON integers, never booleans/coerced text; canonical
raw bytes, not Python equality, determine immutable-content preservation.
Unknown versions, keys, contracts and unsupported framing fail before writes.

**J03.** Required root fields are the historical candidate's fourteen fields plus
`admission` and `admission_authority`. `input_capacity` is optional until assessed;
it is absent, not null, before assessment. All four artifact/publication slots
and `arm_binding` are explicitly null at claim. Each can be set only by its
own operation; once set it is canonical-byte immutable. Admission is mandatory,
non-null and immutable from claim, for both supported request versions.

The resolved admission object closes exactly `schema_version=1`, full request,
request ID, resolved subject, subject ID, mission ID, policy ID, plus derived
review-intent ID ONLY for request2. The request subobjects reproduce the pinned
public schemas, not an arbitrary JSON escape hatch. Resolved subject closes
kind/repository/numeric repository ID/PR/head/base/merge-base. Every derived
identity is recomputed through existing identity functions. Request2's expected
head must equal the resolved head; predecessor/nonce authorization uses the
accepted ReviewRequest v2 rules and independently verified predecessor evidence.

`admission_authority` closes actor, admission mode, authorization-evidence ID,
broker repository numeric identity (decimal text), and executing broker SHA.
Its referenced evidence must independently establish authenticated requester,
allowlists, exact admitted executable and applicable public/private/source-App
checks. Neither a caller's actor string nor a digest grants authority. Claim
creation is forbidden until actual authorization/predecessor evidence passes.
The three modes retain existing semantics, including material credential-leak
veto and decision27; a mode cannot activate its own operational configuration.

**J04.** Request ID is the canonical complete request digest; attempt is exactly
`attempt_identity(request_id,1)`. Admission/subject/mission/policy and derived
intent, broker/runtime and packet/capacity evidence must agree. No operation
changes them. Changed-head/repeat reviews need distinct authorized requests,
not another ordinal, challenge, executor or rewritten subject.

**J05–J06.** The twenty closed binding fields are those in the retained core
schema: version1, prepared parent P, challenge N, request/attempt/packet/input,
capacity receipt ID, subject, reviewer policy/executable digests, broker numeric
ID, workflow ref/SHA, controller run/attempt, Codespace name/ID, launcher digest
and preflight digest. N is generated only in the original passive live launcher.
The complete preflight referenced by its digest binds original session ownership,
recipient, runtime and exact checked packet. Actual trust configuration and
observations, not merely consistent strings, authorize those fields.

Binding must match immutable admission, capacity and runtime/executing SHA;
capacity receipt ID uses canonical receipt bytes plus LF. Full packet/profile,
workflow/ref/run and recipient observations must pass before ARM. The candidate
model checks relational subset; it does not authenticate these observations.
Binding stays null before ARM and byte-identical after it, including terminal
and indeterminate descendants. Count and exact ARM history disambiguate pre/post.

**J07.** A is a unique direct child of P. P may be committed in the binding;
A cannot occur inside its own bytes. Only the later, separately versioned OIDC
envelope binds A/P/N and canonical binding digest. Git object responses must
meet the current R1 scope/identity/fact checks; no weakened fallback is proposed.

## Operations, state and evidence — J08–J13

**J08–J09.** Claim is REQUESTED/count0 with one origin history entry and no model
grant. Existing REQUESTED→ADMITTED→PREPARED stages append evidence, preserving
admission. AtomicArm alone transitions PREPARED/count0/null→ARMED/count1/binding
with one `ATOMIC_ARM_CONSUMED` event. Generic transition-to-ARM and legacy
`record_invocation` are forbidden. Capacity PASS, freshly rechecked exact bytes,
original live session and validated runtime/preflight are prerequisites.

**J10.** Primary path remains ARMED→TERMINAL_CAPTURED→VALIDATED→REPORTED→STOPPED.
Legal alternatives follow the accepted legal state graph, with INDETERMINATE
then STOPPED. For candidate v2, every incompatible post-ARM terminal/indeterminate
transition additionally requires the D06 quiescence fence; legacy mark-first
order is NOT changed. Pre-ARM INDETERMINATE/STOPPED retain count0/null; post-ARM
states retain count1/original binding/event. No terminal state grants invocation.

External evidence is mandatory, not replaced by schema-valid metadata:

- ADMITTED/PREPARED require authorized resolved/verified packet evidence and
  exact reconstruction under existing preparation contracts.
- TERMINAL_CAPTURED requires the accepted capture validator, exact packet/run
  identities, complete credential-screened artifact inventory and one consistent
  started/terminal sequence. Absent final evidence remains absent.
- VALIDATED requires independent reconstruction/validation of those exact bytes;
  citation validity never implies semantic correctness.
- REPORTED requires precommitted creator-owned intent, validated retained result
  and independently observed exact comment/actor/nonce/body; no ambiguous repost.
- INDETERMINATE after ARM requires D06 quiescence and truthful uncertainty.
- STOPPED requires exact observed Shutdown for bound Codespace/context; no desired
  state, cancellation ACK, timeout or missing file can satisfy it.

**J11.** Capacity receipt uses its accepted closed v1 shape and pinned counting
policy; first assessment appends `INPUT_CAPACITY_ASSESSED`. Rejected receipt
remains immutable PREPARED/count0 and forbids every subsequent dispatch/ARM or
transition that would reclassify it as a model-capable indeterminate execution.
No capacity replacement or implicit renderer upgrade is allowed.

**J12.** History starts `{state:REQUESTED,evidence_ids:[]}`. Each mutation appends
exactly one closed event/state entry and matching evidence IDs; no prefix can
change. ARM event includes protocol/count1/binding digest. Same-state capacity,
locator-plan, locator and publication-reservation events have distinct owners.
Evidence list equals the history's ordered flattened evidence references.
Every referenced evidence artifact is validated under its own contract before
its corresponding specialized operation; a hash alone is insufficient.

**J13.** No-op writes, grant rebinding, duplicate ARM, count decrement, history
rollback, arbitrary metadata replacement and terminal reversal refuse. Exact
idempotent reads return existing data without a new commit or creator grant.
The candidate pure transition model deliberately does not impersonate the
external-evidence authentication gate. Passing it is necessary, not sufficient.

## Nested artifact/publication ABI — disposition of JQ-003

The schema's plan and locator shapes close the existing artifact metadata fields:
repository, request/attempt/subject/packet, original run/attempt, name, stage,
inventory; locator adds Actions numeric artifact ID, archive digest/size and
creation/expiry timestamps. Canonical exact inventory and safe extraction are
validated by existing artifact validators. Locator must match its plan and
bound ARM identities. Missing, duplicate, expired or contradictory observations
block recovery. Plan only at TERMINAL_CAPTURED; locator at TERMINAL_CAPTURED or
VALIDATED; both persist unchanged thereafter, including interrupted outcomes.

Candidate publication intent is explicitly **schema2** and a new evidence type
`jch-result-publication-intent-v2`. This is NOT silently compatible with the v1
publisher. It closes issue, request/attempt, result ID, publisher login/numeric ID,
nonce, reservation time, publication ID, comment-body digest and `result_artifact`.

`result_artifact` is a CLOSED exact-byte reference: artifact ID, byte length,
`application/json`, `review-result-v1`, and a CLOSED Actions location (repository,
original run/attempt, numeric artifact ID, name, archive digest and fixed path
`review-result.json`). After validation, result bytes are retained in a separate
private Actions artifact and its metadata/digest observed BEFORE intent creation.
This does not insert a future result into the earlier terminal-capture plan.
The location may be absent/expired at recovery; that blocks publication, not a
new invocation. No general new content-addressing format/store is invented.

Exact result bytes must be canonical JSON+LF, match byte identity/length,
validate the accepted public ReviewResult v1 contract and credential veto, and
match request/attempt/subject/policy/packet and independently reconstructed
validation. The journal does not embed or normalize that versioned public
payload, whose existing extensibility is NOT silently tightened by this draft.
The closed journal has no untyped nested result object. Retrieval verifies exact
Actions archive metadata and safe single-path extraction before byte validation.

Candidate publication ID is `publication:sha256:` plus SHA256 of canonical intent
basis excluding ONLY `evidence_type`, `publication_id`, `comment_body_sha256`.
This basis includes schema2, result reference/location, publisher, nonce and time.
Body digest is SHA256 of the existing result renderer with that publication ID.
Only the intent CAS creator can issue one POST. Unknown outcome leads to exact
comment observation only, not a second POST; result retention is not posting
permission. The receipt closes current observation fields and must match intent,
actor, issue, exact comment ID/node/URL/timestamps and rendered body. It is set
only together with REPORTED, whose history includes its exact artifact ID.

The new reference avoids cloning an open public result payload into the closed
journal ABI, but introduces an explicit result-retention/retrieval obligation
and additional upload/read costs. Owner adoption and future implementation must
include that obligation; no existing v1 intent/result is transformed.

## GitHub and OIDC — J14–J19

**J14.** PRESENT_VERIFIED / ABSENT_AUTHENTICATED / UNKNOWN remain distinct.
Authenticated absence applies only to a new eligible claim with verified repo
and credential capability. It cannot prove no privileged historical deletion.
Unknown/auth failure/malformed/scope/path/content contradictions forbid further
authority effects. Current integrated R1 is prerequisite source evidence, not
live scoped-credential qualification.

**J15–J16.** Every v2 update is explicit `updateRefs` expected-old, unique direct
child, non-force, clean response and exact independent readback. One submitted
AtomicArm per original controller/session; no singular-updateRef/REST fallback.
Only that live submitting controller can proceed to one OIDC mint.

**J17.** Any ambiguity at/after submission forbids retry/mint/reconnect/rebind.
Later A observation is evidence only. Generic Q3 errors are not typed conflicts.

**J18.** Future OIDC envelope uses disjoint protocol domain and binds the complete
accepted v1 workload/input/capacity/recipient facts plus N/A/P/binding digest and
launcher identity. Exact issuer/claims/time/audience verification remains
mandatory. D03 defines bounded candidate transport; final wire envelope and
maximal-size vectors require separate implementation qualification. Before ARM,
the constructor must prove the complete bounded future proof fits; otherwise
refuse. Post-mint authoritative mismatch refuses delivery permanently.

**J19.** GitHub does not enforce business transitions, non-cloning, non-deletion,
issuer ordering or provider inference exactly once. Trusted validators,
controller and protected one-shot launcher remain essential.

## Interoperability and gates — J20–J23

**J20.** Reject-before-publish is mandatory for all effective old writers. Source
R1/R2 integration is only the first prerequisite. Historical rerunnable SHAs,
wheels/manual CLI, in-flight jobs and direct privileged writers require verified
drain/deny/isolation. No claim2 until the operational plan passes independently.
If not demonstrable, stop; separate-namespace alternatives need explicit decision.

**J21.** Preserve original7 and extended11 v1 bytes/IDs/count/history. No v1 token,
metadata, publication intent or local consumption reset becomes J-CH authority.
No implicit migration and no new attempt ordinal. Historical #82 stays consumed.

**J22.** GitHub/approved writers remain trusted under D01. Monotone checks and
minimized credential custody remain required; destructive privileged writes are
incidents, never a trigger for automatically recreating authority.

**J23.** Candidate tests/model exploration, real bounded Q2/Q3, actual integrated
implementation qualification, J20, independent design review and owner adoption
are different gates. This document completes candidate data semantics, not
production correctness or execution admission. No J-CH implementation issues
are created as accepted work before the formal architecture decision.
