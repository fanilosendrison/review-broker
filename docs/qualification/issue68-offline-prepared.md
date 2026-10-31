---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Issue 68 Offline Integrated PREPARED Qualification"
version: "0.1.0"
---

# Issue 68 Offline Integrated PREPARED Qualification

## Status and scope

`OFFLINE_INTEGRATED_PREPARED=PASS` records deterministic offline qualification
of the candidate v3 path through committed `PREPARED`. The starting SHA is
`83b02c1b9b5bad6c6f64af76affb140957fcbd38`. The final candidate is the exact
Git commit containing this record; its SHA and tree SHA are recorded in the
draft pull request and Issue #68 evidence report because a commit cannot embed
its own Git object identity.

The qualification composes the actual v3 admission, packet, journal, expected-old
CAS, worker fencing, retention, and reconciliation components. All GitHub source
responses and journal transport effects are injected. The PR subject uses a real
temporary local Git repository and exact Git object reads. No GitHub source
request, production claim, workflow dispatch, Codespace operation, inference,
or publication occurred in the qualification path.

`LIVE_SOURCE_AND_SUBJECT_AUTHORITY=NOT_QUALIFIED` and
`LIVE_PREMODEL_PREPARED=NOT_QUALIFIED`. Physical power-loss durability,
production retention, external workflow delivery, GitHub App permissions,
Codespace isolation, and model invocation safety remain unqualified.

## Canonical qualification identities

The deterministic canonical fixture produced these identities:

- Request: `request:sha256:a25ed5ec29a4e93730619fead29ceb17bb3e6d97a1d9293f78228dabb18f298e`.
- Review Intent: `review-intent:sha256:75aef8d458a48fd0b1ee45a84d767f0b899f37f45258a816b095d766fb9e268d`.
- Attempt: `attempt:sha256:f2dec3252a6169a082a619d092f2f29b34087f6f13421d458f647860d8db14d1`.
- Reservation: `preparation-dispatch:sha256:1088fe5a0410f5165bafe18e0c2c8b5533d794fa57af8c261838a721373a9898`.
- Packet: `packet:sha256:f61983f22470e189cb4ec6b8f30a66e3c27fe6818fdb49cda5bff8c22d40dc32`.
- Packet evidence: `artifact:sha256:b62e4627462bf9d0a489834baaa40e61afbe7674bb3f4d4b069775c32a23e8e7`.
- Subject capture: `artifact:sha256:5e76c1c0ec22a478151ebec4eb3673f25f1fbb03c9332f1d71b42da9fac9fd48`.
- Technical policy: `technical-policy:sha256:ac08f3bc9b40c06b5ab244b0d5e95995cf05fc345f2e2cba33e3fe27ffebf79b`.
- Retained inventory: `artifact:sha256:35b1791e8e421bc19bc6cfb66d1e49bc49cef75081236b69255f42ae4056d40c`.

The packet identity and journal packet-evidence identity remain separate domains.
The evidence identity hashes the exact canonical preparation receipt plus LF.
The receipt binds repository, claim, ADMITTED predecessor, request, intent,
attempt, admission, reservation, generation, worker, packet, subject capture,
technical policy, and retained inventory.

## Retained artifacts and integrity

The configured retention base deterministically derives one locator from the
64-hex claim-ref digest. The retained `packet/` directory at that locator is the
unmodified Reviewer Packet v2 artifact inventory. The auxiliary `evidence/`
directory contains the original request
body, technical-profile bytes, admission-time remote-reference bytes, and the
exclusive preparation receipt. Construction occurs in a private staging tree,
verification precedes publication, and one same-filesystem rename exposes the
complete tree. Existing claim locators, symlinks, unsafe identifiers, non-owner file modes,
missing entries, extra entries, changed bytes, and receipt rewrites fail closed.
The packet authority is configured with the retention base, expected technical-
policy identity, and independently captured subject-evidence identity; none is
selected from packet-controlled metadata. A coordinated pre-receipt rewrite of
the diff, manifest, prompt, packet ID, and recomputed capture evidence therefore
cannot authorize PREPARED because it cannot match the external expected capture
identity.

Admission-time mutable-reference bytes remain separate from preparation-time
packet snapshots. Cold reconstruction verifies admission receipts from the
former and packet provenance from the latter. Git-file reconstruction checks
SHA-256, Git blob OID, byte length, repository identity, and evidence identity.
Subject reconstruction uses `SourceRecord.from_bytes`, exact retained images,
diff, manifest inventory, and recomputed subject evidence. The technical profile
is reconstructed from retained original bytes and the manifest-bound name.

## Journal sequence

The nominal injected journal sequence is:

1. `claim`: `REQUESTED`, committed.
2. `reserve_initial`: generation-1 reservation event, committed by expected-old CAS.
3. `register_worker`: exact worker binding event, committed by expected-old CAS.
4. `record_admission`: `ADMITTED`, committed by expected-old CAS.
5. `prepare`: `PREPARED`, committed by expected-old CAS after non-permissive packet authority.
6. `read`: exact committed `PREPARED` journal readback.
7. Fresh-process read and packet reconstruction: same packet and evidence identities.

The deterministic nominal transition record is:

| Operation | Expected old | Committed successor | Readback | Evidence | Permitted next operation |
| --------- | ------------ | ------------------- | -------- | -------- | ------------------------ |
| claim | none | `28c0f3cfd585f4b50b9480a09a75a8591b8536ac` | REQUESTED | admission authority and synthetic writer evidence | authority-gated reservation |
| reserve_initial | `28c0f3cfd585f4b50b9480a09a75a8591b8536ac` | `3417a4fde0670ef4ff7777a98801188b3b8bf2af` | REQUESTED | synthetic expected-old writer evidence | one dispatch and worker binding |
| register_worker | `3417a4fde0670ef4ff7777a98801188b3b8bf2af` | `975b862e108fd1204511e76746d316b146dab6c5` | REQUESTED | worker authority and synthetic writer evidence | admission recording |
| record_admission | `975b862e108fd1204511e76746d316b146dab6c5` | `ed81208bc103d61df6c1322d9baf00636054c5ae` | ADMITTED | admission evidence and synthetic writer evidence | verified packet preparation |
| prepare | `ed81208bc103d61df6c1322d9baf00636054c5ae` | `bc5f07ed56371281ace74f963267f3c1bee2b8fc` | PREPARED | packet evidence `artifact:sha256:b62e4627462bf9d0a489834baaa40e61afbe7674bb3f4d4b069775c32a23e8e7` | read-only recovery only |

These are synthetic transport Git identities, not GitHub writer attestations.
Every mutation records its starting commit, expected-old commit, intended
successor, outcome, committed readback, writer/authorization evidence, and
permitted continuation in test instrumentation. Rejected and unresolved
injections additionally assert their exact outcome and prohibit blind retry.

## Fresh-process recovery

`tests.issue68_reload_probe` runs in a separate Python interpreter. It restores
only serialized synthetic refs/commits and a configured retention base. It
derives the packet locator from the journal claim, reads the journal through
`GitHubJournalV3`, reconstructs admission/capture/profile objects from retained
bytes, runs the actual packet verifier, recomputes inventory and receipt
identities, and confronts the committed direct parent and PREPARED evidence.
No original admission, capture, profile, reader, or packet object crosses the
process boundary. No HTTP or Git-source reacquisition interface is available.

Corrupted source, missing profile, changed request, changed admission-time
reference, forged receipt, changed manifest, altered journal readback, public
file modes, and a missing packet all fail closed. Repeated recovery causes no journal update.
Later mutable remote bytes cannot replace the committed packet because recovery
has no remote reader and the retained target cannot be overwritten.

## Adversarial scenario matrix

| ID | Status | Exercised result |
| -- | ------ | ---------------- |
| I68-N01 | PASS | Four-reference lifecycle commits through PREPARED. |
| I68-N02 | PASS | Exact committed PREPARED readback matches receipt and direct parent. |
| I68-N03 | PASS | Separate interpreter reconstructs the identical packet and evidence. |
| I68-N04 | PASS | Unpinned Issue body changes under the admitted stable identity before capture. |
| I68-N05 | PASS | Unpinned Issue comment changes under the admitted stable identity before capture. |
| I68-F01 | PASS | Invalid request/admission evidence is rejected without mutation. |
| I68-F02 | PASS | Different request or intent identity is rejected. |
| I68-F03 | PASS | Wrong repository numeric identity fails admission. |
| I68-F04 | PASS | Wrong stable reference identity fails admission. |
| I68-F05 | PASS | Required unavailable reference fails admission. |
| I68-F06 | PASS | Ambiguous or unauthorized optional access is not omitted. |
| I68-F07 | PASS | Pinned digest mismatch fails admission. |
| I68-F08 | PASS | Changed Git-file bytes or blob identity fails cold authority. |
| I68-F09 | PASS | Changed subject image or diff fails packet authority. |
| I68-F10 | PASS | Changed manifest, prompt, or snapshot fails packet authority. |
| I68-F11 | PASS | Forged receipt/evidence refuses PREPARED before mutation. |
| I68-F12 | PASS | Missing or changed technical profile fails reconstruction. |
| I68-F13 | PASS | Stale expected-old update is rejected. |
| I68-F14 | PASS | Wrong reservation, generation, or worker is fenced. |
| I68-F15 | PASS | Concurrent/stale reservation has one winner and no redispatch. |
| I68-F16 | PASS | Duplicate discovery reuses the claim; the integrated reservation controller dispatch counter remains one. |
| I68-F17 | PASS | Interruption before materialization remains ADMITTED. |
| I68-F18 | PASS | Materialized packet without CAS remains ADMITTED. |
| I68-F19 | PASS | Applied mutation with ambiguous response remains UNRESOLVED without retry. |
| I68-F20 | PASS | Unconfirmed ambiguous mutation remains UNRESOLVED without retry. |
| I68-F21 | PASS | Competing descendant remains UNRESOLVED and cannot inherit authority. |
| I68-F22 | PASS | Repeated confirmed recovery is read-only and identity-stable. |
| I68-F23 | PASS | Post-PREPARED overwrite/reacquisition is rejected. |
| I68-F24 | PASS | Later mutable bytes do not alter the committed retained packet. |
| I68-F25 | PASS | Historical namespace and full v1/v2 regression behavior remain unchanged. |

Crash classifications preserve the existing vocabulary. A confirmed direct
successor is `COMMITTED`; provider-typed expected-old mismatch is `REJECTED`;
lost or unattributed acknowledgment and competing/lagging readback remain
`UNRESOLVED`. No unresolved mutation is repeated and no arbitrary timeout
converts uncertainty into failure. Reservation is not represented as external
dispatch success; the injected dispatch counter remains exactly one.

## Validation

The required new, related, compilation, JSON, diff, source-size, and complete
repository commands are recorded in the draft PR evidence. The complete suite
must pass at the exact published candidate before this record is final. The
historical v1/v2 request, parser, journal, packet, reconciliation, result, and
publication tests remain part of that complete suite rather than being inferred
from namespace assertions alone.

## Limitations

The qualification does not establish filesystem power-loss durability. `fsync`
is used for retained files, but directory-entry persistence under sudden power
loss is not claimed. It does not establish production access controls, GitHub
retention, authenticated source authority, actual GraphQL writer authority,
external workflow dispatch acceptance, or any Codespace/model boundary. The
PR #55 documents remain design context only and are not promoted to normative
authority by this evidence.
