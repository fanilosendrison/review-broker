---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-03 Offline Authorized Packet Implementation"
version: "0.1.0"
---

# Issue 70 RWP-03 — Offline authorized packet implementation

## Status and immutable input

This experimental implementation follows the frozen RWP-03 design in
[the architecture candidate](../architecture/issue70-rwp03-authorized-packet-candidate.md).
The base is draft PR #86, commit
`60faf3fc892321f6887572402f189215f222ea6d`, tree
`e08bd14f63dcf729f5d30160f7c39fbeaedfdc4e`.
The architecture document SHA-256 is
`ffbf1693a0711aa7c7d344618d63a36043ddb4b220e31e3c3aa765c13c0390c7`.
It is unchanged documentary design input, not operational authority.

The authenticated historical baseline is Actions run `41685772972`, job
`126090973457`, SUCCESS with 868 tests. Its checkout commit
`522d60d24c03e18236bf062eb98d940e28d8b0a4` has the exact base tree.
The earlier local pre-implementation attempt remains interrupted by a tool
execution timeout; it is neither a local PASS nor a demonstrated test failure.

Publication, exact-source CI, and independent review are separate subsequent
gates. No final qualification is asserted by this document alone.

## Implementation boundaries

Phase A separates exact expected-policy content, broker source provenance, and
request-bound selection permission. The source and selection protocols require
independently supplied authorities. Canonical receipt bytes include one LF;
receipt identities are not members of their own bases. Reviewer agreement
includes backend, model, and reasoning effort. Neither a content hash nor a
caller-created profile object grants selection permission.

Phase B adds a distinct current-Worker authority and a process-local one-attempt
continuation. RWP-02 registration remains unchanged. Every continuation checks
the original ACK, strict binding history, current generation/reservation,
authenticated predecessor, and fresh Actions run/job. The ACK's reservation
commit is historical and is not compared with the parent of a later snapshot.
An ADMITTED CAS must be COMMITTED with no pending write, exact predecessor and
successor bytes, recognized mutation evidence, and fresh readback. Rejection,
ambiguity, interruption, and identical-target losing CAS never grant capture
rights or automatic retry.

Capture and packet stages are explicit injected dependencies. Each stage must
honor the supplied freshness guard at its actual transport and write boundaries.
Freshness checks do not establish cross-system atomicity. Atomicity requests
are rejected in this tranche. Source acquisition and all four reference kinds
reuse the existing source, admission, Git, physical-line, and reference-order
verification mechanisms.

Phase C moves the historical synthetic policy responsibility into a dedicated
module, preserving its positional API, allowed fields, content identity, and
packet bytes. The new closed candidate variant is
`PREMODEL_POLICY_SOURCE_VERIFIED_ONLY`. Its complete technical-policy object,
including source and selection evidence identities, participates in packet
identity. The program continues to reference policy content separately.

The authorized loader requires an independently supplied verification boundary
and current validated ADMITTED journal. The retained bytes cannot create fresh
source or selection permission. Local retention uses private exclusive writes,
staging, full inventories, symlink rejection, and an atomic no-replacement
rename. Existing destinations are never overwritten. The historical synthetic
layout and default loader calls remain unchanged.

## Exact expected policy

The broker-owned source path is
`src/review_broker/profiles/pre-model-v3-expected-policy.json`.
Its exact canonical UTF-8 bytes include one trailing LF:

- Byte length: `589`.
- SHA-256: `6f9c0d9ed04cc708fd633bb7ed12e168338d1c91e92456f7a7188205deb63e63`.
- Git blob OID: `5bdd27d4d8fd66b591f07a6d165a73aca15a50de`.
- Content identity: `technical-policy:sha256:f8bc47647605790cc41fbc51f801bd702617ab96da50d8807a15ed442800c024`.

The logical policy name is not an installed, path-dependent Codex profile.
Required restrictions are expected intent, not observed effective permissions.
The executing source SHA is supplied externally and is not embedded in policy
content or hardcoded to the architecture base.

The authorized retained evidence adds exactly:

- `evidence/expected-policy.bin`.
- `evidence/policy-source-observation.json`.
- `evidence/policy-selection-receipt.json`.

It does not write `evidence/technical-profile.bin` or a PREPARED receipt.

## Verification coverage

The new tests use the actual candidate admission, journal, source, packet,
retention, and verifier implementations with injected external transports.
The RWP-02 Worker scenario is reused with an additive RWP-03 state-transition
measurement transport; historical fixtures and assertions are unchanged.

- N01–N02: exact content/schema/identities, independent authorization, reviewer agreement.
- N03: complete file-inventory byte identities and packet/schema identities from an independent oracle produced by the exact base's synthetic implementation.
- N04: equal policy content with different independently approved selections changes packet identity.
- N05: attributed ADMITTED and current-Worker handoff, without false packet completion.
- N06: complete authorized four-reference packet with full verification.
- N07: a fresh interpreter verifies retained bytes after capture memory is discarded.
- N08: concurrent identical-target continuations admit one attributed packet winner.
- F01–F12: absent provenance/approval, substitution, repository/path/commit/blob/content/schema faults.
- F13–F23: reviewer mismatch, request/attempt/reservation/Worker/executable/claim replay, forged approval.
- F24–F27: absent/unrecognized ACK, invalid binding history, runtime/job/actor/rerun/freshness faults.
- F28–F30: rejected, unresolved, and identical-target losing ADMITTED operations never capture or retry.
- F31–F33: subject drift/diff/merge-base errors, incomplete pagination, reference/source/order corruption.
- F34–F35: missing/substituted policy evidence and absent independent cold trust fail closed.
- F36: independent inventory, permission, symlink, prompt, manifest, and prohibited-effect checks.

Interruption injection covers both sides of ADMITTED and both sides of every
new policy-evidence write. No interrupted attempt reports completed retention
or retries automatically. Current-journal movement and authority loss prevent
subsequent packet effects.

The fresh process blocks socket connections. Source provenance comes from an
independent deterministic fixture archive. Selection comes from an external
test-owner decision recorded after observing the simulated ADMITTED server
state, not from a producer receipt. Cold predecessor recognition compares the
exact journal object with a separately supplied server observation archive.
These are explicit offline trust roots, not real GitHub attestations or
cryptographic attestations of the original RWP-02 observation archive.

## Validation receipts

The current corrected RWP-03 targeted run passed 64 tests in 105.062 seconds
with exit code 0. RWP-01/RWP-02 regressions passed 52 tests in 8.950 seconds.
Historical packet/admission/journal regressions passed 113 tests in 61.223
seconds with exit code 0. Scope inspection found exactly the 17 authorized
files. Candidate schemas, exact policy identities, compilation, changed-file
line limits, and whitespace checks passed. The candidate was reinstalled into
the isolated Python 3.11 environment with no dependency changes; installed
modules, policy package data, and pip dependency consistency were verified.

An earlier targeted run failed after the new independent journal fixture
introduced a missing `canonical_bytes` import. That task-local support defect
was corrected; its failed log remains separate from the passing run.

The complete post-implementation suite has NOT RUN. Its prescribed supervised
launch was rejected by the active enforcer with:

```text
Writing to protected paths is strictly forbidden. Never attempt to bypass this restriction. (path: /usr/)
```

No launcher PID, supervisor log, suite log, or completion receipt was created;
no corresponding active suite process was observed. The prepared supervisor
script remains in a private qualification directory with mode 0700. No
alternative launch or enforcer bypass was attempted.

### Qualification-environment discovery

- Statement: the prescribed `/usr/bin/nohup` supervisor launch is currently blocked.
- Source and evidence: the launch tool returned the exact denial above; read-only inspection found only the prepared script.
- Existing authority: the task requires persistent supervision and forbids bypassing active enforcers or publication before full validation.
- Semantic disposition: `no-normative-impact`.
- Affected layers: `verification-or-qualification-evidence`, `integration-or-conformance`, `repository-governance-or-documentation`.
- Related consequences: complete-suite, publication, exact-source CI, review, and handoff gates remain incomplete.
- Required authority: the owner or harness administrator must resolve the permitted supervisor-launch mechanism separately; harness/enforcer edits are outside this task.
- Next action: inspect the existing run directory before any authorized launch; never create a duplicate suite or relabel incomplete evidence as FAIL/PASS.

### Owner-authorized CI-first qualification recovery

A subsequent explicit owner mandate changed only the validation mechanism and
ordering: the complete suite must run in normal GitHub Actions against the
exact published candidate tree. Publication of a draft candidate before that
run is authorized solely to make qualification possible. It is not qualification,
review GO, merge permission, or production activation. The supervisor denial and
all earlier STOP observations above remain historical evidence. No supervisor
retry, alternative supervision command, or enforcer modification is authorized.

Read-only prepublication inspection confirmed exactly the 17 allowed files,
unchanged source/test bytes since the passing targeted run, byte equality with
the installed candidate package, compilation, candidate JSON schemas, exact
policy length/digests/content identity, changed-source line limits, and
whitespace checks. Existing targeted evidence remains applicable; targeted
checks are not a complete-suite substitute.

```text
LOCAL_FULL_SUITE=NOT_RUN_ENFORCER_DENIAL
LOCAL_FULL_SUITE_PASS=NOT_CLAIMED
FULL_SUITE_QUALIFICATION=AWAITING_EXACT_SOURCE_CI
INDEPENDENT_REVIEW=NOT_RUN
RWP03_OFFLINE_AUTHORIZED_PACKET=NOT_QUALIFIED
```

### First exact-source CI failure and task-local correction

Draft PR #87 first published candidate
`791f18c8365ec5ef74b8bdf8fb9e78210632339b`, tree
`f900ca9e683284e3e1aac6ceb7a72da8e71dfb8c`.
Actions run `41732810510`, job `126254241168`, completed with FAILURE:
932 tests in 282.243 seconds, one error, exit code 1. Installation passed;
subsequent compilation/JSON steps were skipped and are not claimed PASS.
The observed merge checkout `3409a9dfdd2b39b802c3bceba8b65655ab66a0fe`
has that exact candidate tree. This is failed evidence, never qualification.

The error was confined to new test N03: its runtime `git show` of the exact
architecture base required a historical object absent from Actions' shallow
checkout. The real CI log reproduces the failure end to end. No production
module, historical assertion, dependency, or workflow required modification.

The corrected N03 retains an independent golden oracle: all nine historical
packet file SHA-256 values, packet ID, and canonical synthetic-schema digest
were obtained from the exact base implementation, not generated from candidate
output. The base `packet_v2.py` SHA-256 is
`4e7f14fe0ea7e0fa8b1a45bfbb7291401075e1619a4b59162fdce28c8eac48c3`.
CI now checks the full historical inventory without requiring historical Git
objects or a network fetch. The normal shallow-checkout CI provides the
regression environment. The failed run and original local STOP records remain
preserved. The global known-bugs registry is outside the authorized file scope
and was not modified.

Final qualification and publication receipts remain pending. The successor PR
and Issue #70 handoff must identify the exact published SHA/tree, complete CI
suite result/count, CI checkout tree, and independent review receipt.
No intermediate component PASS substitutes for those joint gates.

## Independent NO_GO and bounded remediation

The original reviewed source remains
`3c68aa0621e82cfe5ae056b06ee8bbf43182aa9e`, tree
`96832379b259760efca681d9e53564456f041be0`. Its normal CI run
`41734320780`, job `126259444003`, passed 932 tests in 281.568 seconds,
installation, compilation and JSON validation. The logged checkout
`d8a7a45c8ad14604b33e9582584f826a3a513b29` has that exact tree.
That CI PASS did not resolve the subsequent independent **NO_GO**.

The complete original review is retained in the
[PR #87 qualification receipt](https://github.com/fanilosendrison/review-broker/pull/87#issuecomment-6617863759).
Trace SHA-256:
`9f1c2fddcd9eb45eb53a8a5af751d4a77a0f994c78eda21ce459b199844b973e`.
Session SHA-256:
`4547896345e33c6be7b42d674ea7ed76ea82e934ecd4184b85a4ab8ebe34cc6f`.
Review-text SHA-256:
`df33e601f6ae7e148fc3c516f29f8522326388e0fc0c6920bfe884812d186f9e`.
Its five findings are not relabeled PASS.

### R1 through R4 implementation and targeted evidence

The owner explicitly mandated these corrections without changing the frozen
architecture or adopting normative v3 semantics:

- R1: all authorized entry points compare the complete canonical admission with
  the authenticated snapshot's original admission before profile acceptance.
  An independently admitted same-request/different-origin-authorization fixture
  is individually valid but fails this exact binding at build, verify and load.
- R2: an independently supplied authorized boundary requires the authorized
  profile and qualification. A complete valid synthetic packet and retained
  layout remain supported by historical default calls but cannot downgrade an
  authorized invocation.
- R3: authorized materialization and verification compare original Issue/Comment
  content and provenance, excluding only the new observation timestamp. Body
  replacement, comment replacement and a coherent change after the first
  accepted observation fail; observation-time-only advancement succeeds.
- R4: one guarded Git adapter protects each subprocess in subject proof and the
  injected capture provider. Authorized reference capture guards every injected
  HTTP call. Source/selection implementations receive the existing current
  effect guard and must invoke it before each internal external observation.
  Packet/evidence creation, unbuffered writes, fsync, native rename and retained
  content reads use the same authority. Authority loss prevents subsequent
  operational reads/writes; interrupted private staging is not cleaned by a
  stale authorization. A freshness check still provides no cross-system lock
  or atomicity. The reviewer program remains derived from the resolved policy
  content, not from selection approval, in the technical-policy responsibility.

The installed original source and original fixtures were exercised with the
new coherent/internal-boundary tests before installing corrections: 10 tests,
9 expected assertion failures and zero errors; the observation-time positive
control passed. The original RED log remains private and unchanged.

A first combined targeted run and a cold-file run exceeded their 180-second
tool deadlines. Both are INCOMPLETE, not PASS; no matching process remained.
A later test exposed an unguarded Git reader inside the injected capture
provider. Its failed log is retained; the provider now uses the same guarded
adapter, without changing historical source acquisition.

Final installed-source focused receipts are disjoint: policy/effect 31 PASS,
continuation 27 PASS, cold packet first partition 12 PASS and remaining partition
8 PASS: **78 targeted tests PASS**, including all original N01–N08/F01–F36
cases. Existing packet/admission/journal and RWP-01/RWP-02 regressions passed
**165 tests**. These are execution results, not an independent closure of R5.
The original 868 historical tests remain unchanged; corrected-source complete
CI and a new exact-source independent review remain mandatory.

### R5 capability discovery and unresolved qualification boundary

- Statement: no sufficient, permitted network-isolation qualification boundary
  has been established for both the local cold process and CI.
- Source and evidence: the actual local host reports Darwin 17.7.0, macOS
  10.13.6, not the generic workspace's Monterey assumption. Its existing
  sandbox-exec executable accepted a per-process deny-network profile;
  connect_ex and UDP sendto returned EPERM. This is partial capability evidence,
  not cold reconstruction or complete alternate-route qualification.
- Source and evidence: a fuller assessment with a minimal explicitly selected
  environment, stream, connect_ex, UDP, native and descendant probes was denied
  before execution by the active enforcer: protected path `/usr/`. No output
  receipt or probe PASS is claimed for that denied command. No substitute path,
  supervisor, privilege elevation, dependency installation, global security
  policy change or enforcer modification was attempted.
- Source and evidence: authenticated prior CI identifies ubuntu-24.04 and its
  ephemeral hosted runner. The exact runner-image software-manifest reference
  in that log returned HTTP 404. Installed tools, unprivileged isolation support
  and descendant inheritance on that actual runner are not established.
- Existing authority: the remediation mandate requires read-only capability
  assessment before changing the cold-process harness, and forbids substituting
  Python patches or environment cleanup for OS-enforced network denial.
- Semantic disposition: `no-normative-impact`.
- Affected layers: verification-or-qualification-evidence;
  integration-or-conformance; repository-governance-or-documentation.
- Related consequences: the old cold subprocess launcher and socket monkeypatch
  remain unchanged. Earlier network-blocked language does not establish
  universal isolation. Cold byte reconstruction passes, but network denial and
  overall RWP-03 remain NOT_QUALIFIED. No effective Codex policy is attested.
- Required authority: a permitted channel for the exact local capability probes
  under the active enforcer, plus authenticated assessment on the actual hosted
  CI environment. An owner-provided probe receipt or separately authorized
  capability-only execution can supply that evidence; no implicit workflow
  edit, dispatch, elevated privilege or system-policy permission is inferred.
- Next action: obtain that narrow capability evidence, then modify only the
  allowed cold harness, prove stream/connect_ex/datagram/native/descendant denial
  and successful ordinary cold reconstruction inside the verified boundary.

```text
R1_ADMISSION_BINDING=TARGETED_PASS
R2_MODE_DOWNGRADE=TARGETED_PASS
R3_MUTABLE_REFERENCE_DRIFT=TARGETED_PASS
R4_INTERNAL_FRESHNESS=TARGETED_PASS
R5_ISOLATION_CAPABILITY=UNAVAILABLE
R5_REMEDIATION=BLOCKED
R5_COLD_NETWORK_DENIAL=NOT_QUALIFIED
RWP03_TARGETED_TESTS=78_PASS
RWP03_OFFLINE_AUTHORIZED_PACKET=NOT_QUALIFIED
```

No Issue #70 handoff is permitted until all five findings are independently
closed, exact-source complete CI passes and fresh review returns GO. Partial
correction publication on existing draft PR #87 is not that handoff.

## Qualification limits

```text
RWP01_OFFLINE_INITIAL_CONTROLLER=PASS
RWP02_OFFLINE_WORKER_BINDING=PASS
RWP03_OFFLINE_AUTHORIZED_PACKET=NOT_QUALIFIED
EFFECTIVE_CODEX_POLICY=NOT_ATTESTED
REMOTE_PACKET_RETENTION=NOT_QUALIFIED
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
GITHUB_JOURNAL_MUTATIONS=0
REAL_WORKER_DISPATCHES=0
SOURCE_APP_TOKEN_MINTS=0
REAL_SOURCE_ACQUISITIONS=0
CODESPACE_EFFECTS=0
REVIEW_BROKER_MODEL_INVOCATIONS=0
V3_PRODUCTION_ACTIVATION=NO
```

The historical ACK schema-fixture suggestion remains a nonblocking observation;
it is not changed by this work. RWP-04 remote retention/PREPARED and RWP-05
failure/recovery remain separately authorized future work. No merge, Issue
closure, Project mutation, production readiness, or effective Codex policy
attestation follows from this offline implementation.
