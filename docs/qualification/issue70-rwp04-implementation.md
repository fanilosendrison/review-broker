---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-04 Offline Remote Retention Implementation"
version: "0.1.0"
---

# Issue 70 RWP-04 — Offline remote retention implementation

## Exact input and disposition

This experimental successor starts at PR #87 SHA
`65e38e3546fc92d99880eb315729c13c95590f65`, tree
`29b2a85da15bbdcfbf9dd4b20e3af276c49325ff`. Its RWP-01/02/03 offline PASS,
964-test Linux CI and independent GO remain separate historical facts. Earlier
STOP/NO_GO verdicts are not transferred to that accepted base or overwritten.

The [RWP-04 architecture candidate](../architecture/issue70-rwp04-remote-retention-candidate.md)
records owner-selected experimental semantics. No public schema, accepted
contract, production workflow, prior qualification report or #83 file changes.
This report records evidence acquired before publication; exact final CI and
review receipts belong in the successor PR and bounded #70 handoff.

```text
RWP04_OFFLINE_REMOTE_RETENTION_AND_PREPARED=NOT_QUALIFIED
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
EFFECTIVE_CODEX_POLICY=NOT_ATTESTED
```

No overall RWP-04 PASS is asserted until exact-source Ubuntu CI and the prescribed
independent construction review are complete.

## Implemented composition

The original Worker continuation consumes its successful process-local handoff
once. A caller-created result, packet ID, retained path, fresh continuation
object or ADMITTED read cannot recreate that permission. The claim determines
the retained path. The packet loader, actual Packet v2 verifier and guarded
historical inventory recheck original admission, source snapshots, policy source
and independent selection before upload. The original offline receipt is built
purely and is never written into the authorized evidence inventory.

The injected Actions upload boundary accepts one deterministic plan and bounded
ZIP with retention target 30 days, without overwrite, deletion or retry. It is
not a fabricated REST upload implementation and is not an operational workflow
connection. ACK, established refusal and unknown outcome remain distinct.
An unknown upload can be resolved through bounded exact-object observations
within the same still-authorized continuation, before its single PREPARED CAS.
Ambiguity leaves an orphan without a second upload or cleanup.

Metadata and exact-attempt Worker observations use independent injected HTTP
boundaries. Complete scoped pagination rejects drift, duplicate identities,
inconsistent counts and missing continuation. Complete final prev/first links
are accepted. The original timestamped Worker-binding preimage is not claimed
to be reconstructible. The verified job ID identifies the recognized Worker,
not the artifact uploader. Mutable observation time and job status do not
participate in the remote receipt.

Download resolution is an authenticated GitHub request; its validated HTTPS
storage destination receives a new credential-free request. The ZIP's exact
streamed bytes are counted and hashed, with no implicit network fallback.
Budgets are explicit constructor inputs. ZIP handling rejects ambiguous or
unsafe paths, symlinks, special types, duplicates and collisions. Directories
and files are private from creation. Declared and actual byte counts are
checked before writing. Empty admitted-reference structure is restored without
inventing missing files. Complete authorized packet verification follows.

The remote receipt has the exact closed experimental schema, canonical bytes
and one LF. Its offline receipt identity is recalculated from authenticated A,
the verified manifest and unchanged ordered inventory. It excludes its own ID,
P's SHA, signed URLs, credentials and mutable observation fields. JSON numeric
fields are exact bounded integers; artifact/job identifiers are canonical decimal
strings, including values above the binary64 exact-integer range without rounding.

The existing prepare transition and CAS remain authoritative. Freshness reaches
inventory enumeration and file reads, archive operations, injected transports,
Git commit preparation and the CAS request. A narrow writer wrapper guards
write-producing internal transport calls while leaving reconciliation read-only.
These guards do not provide a transaction between Git and Actions.

Historical reconstruction reads authenticated P and its actual Git parent A by
SHA, validates independent origin and mutation evidence and compares P with the
exact existing transition applied to A and R's identity. The historical policy
boundary is a distinct closed class, not a subclass or fake current journal.
It reuses the complete policy verification rules while keeping selection bound
to A. Builders and persistence reject it before effects.

After an attributable PREPARED outcome, subsequent read or retention failure
preserves COMMITTED/PREPARED and reports reconstruction UNAVAILABLE. No source
recapture, new selection, artifact replacement, journal rollback or redispatch
is exposed by the observer path.

## Qualification mechanisms and independent oracles

The new tests extend the real RWP-03 scenario. Only external service and trust
boundaries are injected. Actual canonicalization, packet construction/loading,
full Packet v2 verification, state transition and journal CAS execute.
Transport-side effect lists independently count upload and PREPARED requests.
Fixtures do not merely assert decision strings.

The cold test serializes separate simulated-server origin, mutation, dispatch,
admission and selection observations outside the downloaded ZIP. It then deletes
the entire original Worker root, both source clones, original packet and parent
readback and discards Python objects. A distinct interpreter starts from the
remote archive and independent fixture trust. Complete manifest, inventory,
offline receipt, remote receipt and packet ID are compared with parent byte
oracles. Forbidden capture, selection, source-read, packet-build, upload, claim,
commit and ref-mutation entry points are independently observed and must have
zero calls. A second cold case has no remote references.

On Linux the new child installs and verifies the existing libseccomp boundary
before reconstruction, with minimal environment and closed inherited file
descriptors. Download and authentication of observations remain outside that
child. Existing twelve RWP-03 Linux isolation tests are unchanged; they remain
mandatory without skips on Ubuntu. macOS functional reconstruction is not Linux
network-isolation qualification.

The pure receipt oracle uses literal field sets, direct integer/decimal cases,
independently sorted ASCII JSON and SHA-256. ZIP adversaries include byte-level
NUL names rather than names silently sanitized by the fixture writer. Actual
expansion accounting is exercised at the decompression stream boundary, with
zero oversized bytes written. Production inventory and transition rules are not
copied into a second implementation.

## Local validation and retained failures

The isolated Python 3.11 environment uses an editable installation with declared
`rfc8785` and `jsonschema` dependencies. Dependency consistency passed.
Platform observation is Darwin x86-64; Linux isolation is not locally qualified.

Executed targeted receipts, in chronological order:

- Initial real remote nominal: 1 test PASS, 43.595 seconds.
- Initial continuation suite: 11 tests PASS, 348.613 seconds.
- First pure receipt/archive suite: 12 tests, one fixture failure and one
  exception-expectation error. The ZIP writer had truncated NUL before the test
  reached verification; the timestamp parser correctly raised its established
  typed error rather than ValueError. Both test defects were corrected without
  weakening production rejection. The original failed log is retained.
- Corrected pure receipt/archive plus cold: 14 tests PASS, 107.834 seconds.
- Historical observation plus empty-reference cold: 8 tests PASS, 95.680 seconds.
- Internal freshness and interruption tests: 7 tests PASS, 217.008 seconds.
- Full local suite: **1004 tests in 2176.866 seconds; one failure, 12 Linux skips**.
  This is FAILED evidence, not a suite PASS. The new historical transport helper
  imported the concrete live transport's error type, violating the existing
  import-isolation oracle. The error type was extracted into a transport-neutral
  module; the live public error import remains compatible. The isolation test
  and workflows were not modified.
- A new post-CAS unavailability witness then reproduced a task-local state
  classification defect: a later failed read downgraded an already attributable
  COMMITTED journal outcome. That RED is preserved. The corrected continuation
  retains COMMITTED/PREPARED and reports availability separately.
- Final correction checks: 20 tests PASS, 147.727 seconds, including original
  transport-isolation tests, receipt/archive falsifications, coherent historical
  synthetic downgrade, unknown ambiguous upload, divergent CAS readback and
  post-CAS unavailability. This is not a complete-suite PASS.

Compilation, CI-equivalent JSON parsing, whitespace and all changed/new Python
400-line checks passed. Pre-existing unrelated source-size excesses are not
waived or reformatted. The final complete suite is required in normal
Ubuntu 24.04 CI after draft publication; local evidence does not substitute for
that exact-tree gate. All logs and transient evidence remain private and ignored.

## Q01–Q24 coverage inventory

The entries below identify executable witnesses, not an overall acceptance verdict.
The exact-source CI must execute all final tests, including the cold processes.

- Q01: real four-reference continuation and full cold disappearance roundtrip.
- Q02: real no-remote-reference admission and cold structural-empty directory.
- Q03: every closed field, numeric domain, canonical decimal, LF and date ordering;
  builder checks integer types before canonicalization can erase a float's type.
- Q04: later clock, observation metadata and terminal job retain receipt identity.
- Q05: latest rerun differs while exact attempt 1 and its jobs remain selected.
- Q06: absent, expired, duplicate, substituted ID and changed committed metadata.
- Q07: incomplete, duplicate, cyclic, out-of-scope and inconsistent pagination;
  complete final prev/first links pass.
- Q08: repository/run/attempt/workflow/SHA/job faults and absent/ambiguous job.
- Q09: exact remote byte mutation, truncation and additional bytes.
- Q10: invalid redirects stop before storage; valid storage requests have no
  GitHub Authorization or cookies.
- Q11: all budget types and limits, metadata pages/responses, actual expansion.
- Q12: traversal, aliases, NUL, special members, collision and creation modes.
- Q13: changed/missing source, reference, policy, manifest, prompt and origin;
  extra/missing inventory members.
- Q14: independent source/selection authority loss and historical origin loss.
- Q15: a fully valid synthetic packet/layout passes its historical default loader
  but is refused under the historical authorized boundary.
- Q16: journal movement inside inventory, ZIP writes, observations and after
  preparation authority prevents subsequent effects.
- Q17: wrong parent, unrecognized origin/write identity and repository identity;
  exact canonical A/P transition remains required.
- Q18: historical authority cannot enter builders/persistence; copied handoff
  cannot enter the active remote continuation.
- Q19: established refusal, interruption before creation, lost response after
  creation and ambiguous objects; independently counted zero repeated uploads.
- Q20: before/after CAS interruption, lost ACK and divergent readback; independently
  counted zero repeated PREPARED requests.
- Q21: cold-process forbidden-effect counters and ADMITTED observer refusal.
- Q22: committed journal survives missing/expired/replaced retention and later
  read failure without rollback.
- Q23: mutable remote Issue changes after engagement do not trigger recapture.
- Q24: existing v1/v2, offline receipt and RWP-01/02/03 tests are retained intact;
  final exact-tree CI is the complete regression gate.

## Governance observations and remaining gates

Live preflight confirmed #87 at the exact mandated SHA/tree, OPEN/DRAFT, and no
RWP-04 successor before implementation. Official adapter inspection found #70
absent from Project 17. This is a `no-normative-impact` repository-governance
observation, not new product semantics. The explicit mandate prohibits Project
changes; no item, field, label, milestone or Issue lifecycle was modified.

The required review is a fresh Pi session fixed to
`openai-codex-1 / gpt-6.1-sol / high`, with read-only tools. Installed Pi 0.84.2,
the exact alias/model catalog and non-sensitive OAuth readiness were observed.
These checks are not a completed review or GO. Exact session/tool evidence and
substantive final verdict remain required after publication and CI.

Real Worker dispatches, prepared-artifact uploads, operational journal mutations,
source acquisitions, Codespace effects and broker model invocations are zero.
Construction review and governed commit-planning inference are separate effects.
Production activation, normative adoption, dev integration, #83 changes, merge,
#70/#67 closure and RWP-05 execution are excluded. No successful CI or review can
authorize those effects implicitly.
