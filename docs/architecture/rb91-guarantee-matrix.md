---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-analysis"
domain: "independent-review"
severity: "draft"
name: "RB91 Guarantee Matrix"
version: "0.1.0"
---

# RB91 — Guarantee matrix

## Classification and observation domains

`ESTABLISHED` means only the cited bounded fact, not complete system safety.
`CONTRADICTED` identifies an actual source/model counterexample to the stated
claim. `UNKNOWN` lacks adequate observation. `REQUIRES_QUALIFICATION` identifies
an explicit candidate obligation with a plausible mechanism but no deployed
integrated qualification. All twelve complete-system J-CH guarantees currently
**REQUIRE_QUALIFICATION**. The matrix separates their narrower evidence.

Authority abbreviations: S = product specification, X = review-execution,
O = OIDC-arm-authority, E = review-evidence, R = recovery, I = reviewer
independence, C = candidate journal/launcher contracts in this dossier.
Accepted S/X/O/E/R/I remain unchanged; C would require owner adoption.
Evidence Q1–Q4 and R1/R2 is linked in the
[current disposition](qualification/rb91-current-evidence-disposition.md).

## G01 — Stable logical attempt

- Authority: S/X and ReviewRequest v2; C J01/J04.
- Linearization: deterministic claim creation; request canonical bytes and
  `attempt_identity(request_id,1)` identify the only attempt before any ARM.
- Observations: exact request, authorized operation/predecessor, repository/PR,
  head/base/merge-base, subject/mission/policy identities and canonical claim.
- Evidence: `ESTABLISHED` source and R2/local-Git original7/extended11 tests.
  Q4 tests candidate derivation, not real admission.
- Counterexample: changing ordinal or interpreting a changed head as recovery
  would create unauthorized work; protocol forbids it.
- UNKNOWN response: no new claim or substituted identity.
- Trust: authenticated source and deterministic canonicalization, trusted admission.
- Remaining: full v2 claim/admission integration and exact source evidence.

## G02 — Consumption survives Codespace disappearance

- Authority: S/X/R non-replay; C J05/J08/J21.
- Linearization: GitHub accepts AtomicArm P→A, count1 plus immutable binding.
- Observations: exact commit/record/history, not existence of a local file.
- Evidence: `ESTABLISHED` bounded Q3 durable ref update and Q4 core monotonicity;
  complete J-CH system `REQUIRES_QUALIFICATION`.
- Counterexample: sole-ref deletion/recreation or semantic rollback removes
  authoritative history; no Git hash detects deletion of all anchors.
- UNKNOWN: permanently deny replacement permission; retain consumed ambiguity.
- Trust: GitHub and controlled writers; malicious privileged destruction is a
  declared residual risk, accidental destructive writes are incidents.
- Remaining: actual adapter, retention incident handling and replacement tests.

## G03 — Concurrent controllers cannot both obtain new permission

- Authority: X exclusive claim; C J09/J15–J19.
- Linearization: one `updateRefs(beforeOid=P,afterOid=A,force:false)`.
- Observations: clean response plus original-controller exact independent
  readback; live original session ownership, immutable parent and child.
- Evidence: `ESTABLISHED` Q3 A/B and A/A each one accepted update; historical
  AtomicArmBound model 1,220 states/3,436 edges. Neither proves all executions.
- Counterexample: CAS winner issues two independent challenges/proofs, or a
  launcher reenters. CAS exclusivity alone is `CONTRADICTED` as launch proof.
- UNKNOWN/generic error: no retry, no mint, no adoption of a peer's winner.
- Trust: documented GitHub predicate, conforming controller and launcher.
- Remaining: integrated ownership, identical/divergent contenders and mint cuts.

## G04 — Identifiable irreversible consumption

- Authority: S/X before model transport; C J07–J09.
- Linearization: remote acceptance of A, NOT local success/readback or model start.
- Observations: P direct parent of A; canonical ARM event, count1, challenge and
  binding digest; A occurs only in later envelope, never self-hashed into A.
- Evidence: `ESTABLISHED` candidate core assertions and Q3 primitive separately.
- Counterexample: legacy split ARMED/count0 is reachable; silently finishing it
  under J-CH violates claim-time protocol selection.
- UNKNOWN ACK: consumption may have happened; permanently forfeit continuation.
- Trust: GitHub durability and correctly verified canonical child construction.
- Remaining: real one-write adapter and crash cuts with count0 state exclusion.

## G05 — UNKNOWN GitHub response creates no permission

- Authority: S/O failure semantics, exact-commit X; C J14/J17.
- Linearization: none on UNKNOWN; refusal before any subsequent authority effect.
- Observations: authentic HTTP/status/exit, repo/ref identity, canonical content,
  supplied Git object/path/role consistency and effective capability for absence.
- Evidence: `ESTABLISHED` bounded R1 integrated at 3057192 with 701-test post-merge
  CI and exact independent GO. Live scoped Actions absence probes remain UNKNOWN.
- Counterexample: pre-R1 `_read()` treated nonzero GET as absence. Historical REDs
  remain valid on old SHAs. A self-consistent malicious service is not detected.
- UNKNOWN: no speculative objects/ref, claim, mint or fallback continuation;
  already completed legitimate objects are retained, not rolled back.
- Trust: authenticated GitHub, known credential context and validated observations.
- Remaining: actual token capability and new GraphQL adapter failure taxonomy.

## G06 — Lost ACK creates no second authorization

- Authority: O original creator; X/R no post-ARM retry; C J16–J18.
- Linearization: A acceptance may precede lost ACK; no recovery linearization mints.
- Observations: original submission identity and clean ACK/readback retained in
  live controller memory; later matching head is evidence only.
- Evidence: `ESTABLISHED` Q3 client-discarded ACK and bounded core gate tests.
- Counterexample: reread A then reconstruct mint after controller restart defeats
  live-owner rule, even if only one ref mutation occurred.
- UNKNOWN: zero retry/reissue/rebind/reconnect for execution, cleanup only.
- Trust: controller's one-shot mint/delivery state, not `clientMutationId`.
- Remaining: real network interruption and integrated controller fault injection.

## G07 — Old bundle/JWT cannot authorize a new launcher

- Authority: O exact workload/recipient bindings; C P12–P14/J18.
- Linearization: launcher verifies proof against its own private live context.
- Observations: new envelope domain, audience, A/P/binding digest/N, source/workflow,
  runtime/input/capacity, recipient and same session; exact issuer/time/claims.
- Evidence: `ESTABLISHED` Q2 wrong-challenge rejection, local synthetic replacement
  tests; real J-CH OIDC remains `REQUIRES_QUALIFICATION`.
- Counterexample: importing old challenge, a bearer-only ticket, or copying complete
  authorized process state can redeem twice. Nonce is NOT non-cloning proof.
- UNKNOWN: reject; no import/restore, second mint or legacy envelope fallback.
- Trust: protected CSPRNG, host/process custody and actual issuer verification.
- Remaining: real issuer, expiration, replay, old/new envelope and replacement cuts.

## G08 — One launcher accepts at most one continuation

- Authority: X one invocation; C P15 and D05 boundary.
- Linearization: local atomic WAITING→CLAIMED before one start call; failure after
  claim forfeits, even if no child exists.
- Observations: one protected entrypoint, control FD ownership, no fork/reentry,
  explicit child env/FDs, independently counted synthetic starts.
- Evidence: `ESTABLISHED` Q2 duplicate sends with one fake start; phase6 local
  fork-after-claim counterexample; bounded model one-shot assumption only.
- Counterexample: copied CLAIMED state starts twice; ordinary reentry is a BUG,
  not excluded by trusting the host. PID equality is insufficient.
- UNKNOWN: abandon/no retry; unconfirmed child creation is indeterminate.
- Trust: qualified protected program and OS, no arbitrary privileged snapshot copy.
- Remaining: concurrency/reentry/fork/bypass tests on actual protected launcher.

## G09 — Executor death/replacement cannot restore authority

- Authority: X/R/O consumed attempts; C J21 and D05.
- Linearization: A fixes the original N; process death destroys its continuation.
- Observations: fresh process samples new N; no persisted continuation or restored
  memory image; original count and binding remain in GitHub.
- Evidence: `ESTABLISHED` bounded model replacement refusal; #83 45→46→45 does NOT
  establish durable local continuity. Full system `REQUIRES_QUALIFICATION`.
- Counterexample: restart with recovered N or snapshot of authorized memory.
- UNKNOWN: deny all new grants; even definitely zero starts gives no retry right.
- Trust: trusted host lifecycle, no checkpoint restoration of an authorized process.
- Remaining: process kill, Codespace replacement/rebuild and stale proof tests.

## G10 — No start after incompatible terminal reconciliation

- Authority: E/X STOPPED needs observed Shutdown; C D06 proposes stronger S2.
- Linearization: independently observed quiescence of exact bound incarnation,
  followed by expected-old terminal CAS while lifecycle custody remains held.
- Observations: cancellation ACK alone insufficient; exact recipient Shutdown or
  protected start-fence/child-tree-exit receipt, fresh head/evidence conflict check.
- Evidence: `CONTRADICTED` for mark-first stronger temporal claim by phase5 six-event
  trace. Stop-first bounded model supports candidate, not operational proof.
- Counterexample: proof delivered, C dies, R marks INDETERMINATE, L starts late.
  A fresh journal read before exec still has a check/use race.
- UNKNOWN stop/host: remain consumed ARMED with infrastructure incident; no false
  terminal fence, replacement grant or claim of zero starts.
- Trust: actual Shutdown semantics, no resume of old memory, controlled lifecycle.
- Remaining: real orphan/start/stop races, all resource mutators and current-head
  CAS; owner adoption of v2 stop-first ordering. No retroactive cancellation.

## G11 — Control credentials outside reviewer reach

- Authority: S/O/I credential boundaries; C P01/P16 and D05.
- Linearization: sanitized child construction before any reviewer execution.
- Observations: exact environment/argv/FDs, process/credential custody, packet and
  retained output screening, inaccessible control stream and no alternative API.
- Evidence: `ESTABLISHED` bounded Q2 environment names/FD observations; accepted
  source controls. Comprehensive effective isolation remains unqualified.
- Counterexample: parent `/proc`, inherited FD, same-user credential file or alternate
  tool route can invalidate a deployment. Flags alone are not effective isolation.
- UNKNOWN: refuse affected path; observed material leak blocks regardless of profile.
- Trust: approved host and proportionate decision27; NOT arbitrary reviewer tools.
- Remaining: actual launcher child isolation and specific exposed capabilities;
  no blanket maximal Codex-internals prerequisite is reintroduced.

## G12 — Historical v1 immutable and non-replayable

- Authority: S/X/O/R historical preservation; C J01/J20/J21.
- Linearization: version dispatch BEFORE decode/write; no historical v1→v2 edge.
- Observations: original7/extended11 bytes, parent OIDs, ordinal/count/history,
  old reader refusal, claim inventory before/after and executable provenance.
- Evidence: `ESTABLISHED` R2 exact source/GO/merge/post-merge tests; all ten historic
  heads unchanged in prior receipts. New task adds read-only before/after inventory.
- Counterexample: old permissive writer strips v2 binding; source merge does not
  prevent a rerun of that writer or a manually installed old wheel.
- UNKNOWN: no migration, normalization, fallback absence or old-attempt rearm.
- Trust: controlled writer custody; arbitrary privileged deletion remains residual.
- Remaining: operational J20 inventory/drain/deny and exact historical controls on
  future deployed versions. No new v2 claim is allowed by this matrix.
