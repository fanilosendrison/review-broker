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
- N03: byte-for-byte comparison with the exact base's synthetic packet implementation.
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

Final qualification and publication receipts remain pending. The successor PR
and Issue #70 handoff must identify the exact published SHA/tree, complete CI
suite result/count, CI checkout tree, and independent review receipt.
No intermediate component PASS substitutes for those joint gates.

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
