---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-analysis"
domain: "independent-review"
severity: "draft"
name: "RB91 Durable Authority Alternatives"
version: "0.1.1"
---

# RB91 — Definitive bounded architecture comparison

## Exact alternatives and common scope

Definitions come from [#91 phase1](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6695366356),
[phase3](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6699304864),
[phase4](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6699837657)
and [#83 conditional B](https://github.com/fanilosendrison/review-broker/issues/83#issuecomment-6668614720).
These are research definitions, not accepted technical authority.

- **J-CH** here is phase4 AtomicArmBound, not phase3's split ARM/count-one:
  passive pre-ARM challenge; ONE new atomic journal ARM/count1/binding; original
  controller mints after clean ACK; original launcher consumes one continuation.
- **J2-A** is the privileged REMOTE launcher performing an additional exclusive
  final journal consumption CAS after legacy ARM/count1, using a narrowly scoped
  journal-write capability. It is NOT an external durable service.
- **J2-B/Challenge** is Actions retaining journal writes and driving the launcher
  over SSH, with an additional THIRD consumption CAS after the existing two
  ARM/count writes. Its historical model allows a launcher selected after ARM;
  an ARM-bound refinement is identified separately, not substituted silently.
- **E** is a separately controlled durable consumption authority independent of
  Codespace lifetime: a minimal service/controlled runner/storage authority with
  authenticated exclusive `ConsumeForLaunch(attempt,authorization,recipient,
  challenge)`. No database/vendor/VM is preselected by this comparison.
- **B** is protected persistent backing exposed at the executor's canonical
  authority/state paths, under root custody, trusted mounts and complete history
  retention, retaining accepted local exclusive/no-follow/fsync consumption.
  It is NOT today's overlay or any merely ext4-looking service volume.

All require immutable request/subject/attempt, no post-consumption retry,
credential isolation, truthful uncertainty, independent evidence and observed
Shutdown. A different durable store does NOT automatically solve launcher-copy,
reentry, cancellation, endpoint authentication or provider-effect ambiguity.

## Comparison matrix

| Dimension | J-CH | J2-A | J2-B | E | B |
| --------- | ---- | ---- | ---- | - | - |
| Consumption authority | Existing GitHub journal | GitHub journal, remote writer | GitHub journal, Actions writer | Separate durable controlled authority | Protected retained local history |
| Linearization | Single AtomicArm P→A with N/count1 | Final remote consumption CAS after legacy ARM/count | Third Actions CAS after legacy ARM/count | Authority's atomic consume, exact primitive to specify | Exclusive record creation plus validated durable persistence before start |
| Durability | GitHub independent of executor | Same GitHub assumption | Same GitHub assumption | Separate retention/custody contract required | Backing retention and original history across lifecycle required |
| Interrupted recovery | Consumed original L forfeits; evidence/cleanup only | Consumed final grant forfeits; pre-final ARM remains no automatic retry | Historical model's late L binding needs normative adjudication | Committed consume never reissues; uncertainty loses opportunity | Missing/changed/corrupt store refuses; never reconstruct empty history |
| Replay | N+A+original C/session+one-shot L | Must bind CAS winner to one continuing L; reusable receipt insufficient | Challenge+third CAS+original continuation | Unique consume receipt still needs non-replayable delivery/start boundary | Existing record blocks duplicate attempts under retained-store assumptions |
| Concurrency | One expected-old ARM winner; one local continuation | Remote contenders compete for final expected-old | Final expected-old plus same local fence | Atomic authority transaction plus local start uniqueness | O_EXCL/concurrent process behavior and retained filesystem semantics |
| Network ambiguity | Any submitted ARM uncertainty forbids retry/mint | Uncertain final CAS forbids local continuation/retry | Extra CAS adds another ACK/failure cut | Uncertain consume response cannot be retried into permission | Journal/OIDC ambiguity plus filesystem persistence/spawn ambiguity |
| Credential isolation | No journal writer in executor | Remote writer is a new privileged custody surface; GitHub credential scoping is not per-state semantics | Actions retains writer, like J-CH | New service caller credentials and endpoint; model must not see either | No extra journal credential, but backing aliases/root custody need protection |
| OIDC | New envelope binds N/A/P, original workflow/run and recipient | OIDC may precede final consume; new binding/ordering contract required | New post-final-CAS envelope, challenge-bound | OIDC workload authentication can identify caller, not prove consume by itself | Accepted OIDC-v1 delegation plus durable local consume |
| Codespace lifecycle dependence | Ephemeral L dies/forfeits; GitHub history survives | Launcher lifetime plus remote credential safety; history survives | Same ephemeral continuity issue as J-CH | Durable state independent, remote continuation still lifecycle-bound | Core unresolved dependency: permitted retained substrate/generation/history |
| Residual risk | Trusted GitHub/writers/host; clone/admin rollback outside guarantee | Same plus remote writer leakage/misuse | Same plus late-binding semantic risk | New authority/operator compromise; clone/reentry not inherently fixed | Backing loss/rollback/aliases/provider clearing; privileged deletion |
| Implementation complexity | New schema/AtomicArm/controller/framing/launcher/recovery; substantial | All binding/start work plus remote credential and final-CAS path | All binding/start work plus three-write ownership and late-binding rules | New minimal interface, durable storage/caller/custody adapters plus integration | Existing consume algorithm, new trusted allocation/mount/startup and generation guards |
| Operations complexity | Existing GitHub plus J20/all-mutator lifecycle custody | Credential issuance/rotation on remote plus J20 | More stranded phases plus J20 | Separate availability, retention, auth, backup/incident and deployment surface | Persistent allocation, root setup, lifecycle/mount/alias incidents |
| External dependencies | Existing GitHub/OIDC/SSH/Codespaces/OS | Existing providers plus remotely held write credential | Existing providers | Additional independently controlled service or runner/storage domain | Provider-approved persistent backing and trusted presentation |
| Plausible added cost | Extra metadata/API/evidence retention and one result artifact, existing compute | Additional GitHub calls, credential handling and compute | Additional CAS/API/evidence and compute | Service/runner/storage/requests/backup, possibly recurring minimum; no quoted tariff | Persistent allocation/storage and lifecycle management; no established eligible allocation/pricing |
| Contracts impacted | Journal2, OIDC domain, launcher, recovery/J20; request/result public bytes unchanged | Journal final-consume, remote credential boundary, OIDC/start/recovery/J20 | Journal third-consume, OIDC/start/recovery/J20 and post-ARM semantics | New consume/custody/auth/retention contracts, OIDC/execution/recovery | Deployment/storage identity/retention/startup; accepted local consumption unchanged only if full contract met |
| Available evidence | Q1 trust limits; Q2 bounded SSH; Q3 bounded expected-old; Q4 core; integrated R1/R2; new D05/D06/ABI fixtures | Conceptual phase1 only; no actual remote-credential isolation qualification | Phase2 3,140 states/9,092 edges; phase3 comparable model and hostile traces | Required interface and custody analysis only; no selected implementation | #83 local algorithm/sacrificial ordinary-cycle evidence; 45→46→45 discontinuity and nine-candidate survey |
| Remaining qualification | Actual full adapter/OIDC/one-shot L, child isolation, abrupt cuts, quiescence, J20 | Actual remote writer scope/isolation, complete final CAS/start and all common faults | Third CAS ownership, late-binding decision, all common transport/launcher/recovery faults | Concrete authority/provider primitive, persistence/failure/auth/receipt/start integration and operations | Exact permitted allocation, custody/aliases, complete history, identity, mount-loss/rebuild/fsync/replay and operational gates |

## What the alternatives do not establish

`ESTABLISHED`: the historical trusted finite J-CH/J2-B models had no at-most-once
violation within their stated bounds. Both admitted double starts under clone,
semantic rollback, shared challenge and reentry faults. Counts are state-space
measurements, not performance or production safety scores.

`CONTRADICTED`: an extra CAS or external database alone makes the winning
continuation non-copyable. A copy of a locally authorized continuation can start
twice without contacting that authority again. B's local marker also fails if
authorization state is copied after its exclusive creation. A correct boundary
still needs qualified one-shot process control or an authority that itself owns
and serializes the actual start side effect, which is a different concrete design.

`UNKNOWN`: exact E/B deployment feasibility and monetary cost. There is no
qualified eligible B allocation; no E provider/interface has been selected.
Neither unknown should be converted into a claim that the option is impossible.

`REQUIRES_QUALIFICATION`: every complete candidate on the real deployment.
Source R1/R2 correctness does not qualify Actions token capability or a new
OIDC/launcher. J20 does not disappear merely by adding a field or namespace.

## Explicit recommendation and reversal conditions

**RECOMMEND_J_CH**, conditionally selected by the owner on 2026-11-09, with the
five obligations in the dossier and the required F1 revision. The owner retained
B/E as reconsideration alternatives; no reselection is requested here.
The reason is authority placement and semantics, not development cost:
GitHub already provides the required durable ordinary-profile history;
AtomicArm eliminates stranded split-ARM ownership, fixes the launcher before
consumption, avoids remote writer exposure and does not need an unqualified
persistent backing or a new custody domain. It deliberately loses availability
instead of recovering a consumed grant.

J2-A adds a credential exposure boundary without evidence of a necessary added
guarantee. Historical J2-B permits post-ARM late selection that conflicts with
the conservative no-recovery boundary unless separately adopted; an ARM-bound
J2-B removes that behavior but retains an otherwise unjustified third CAS.
E is justified if another necessary invariant cannot be enforced with trusted
GitHub, or if the owner chooses the distinct compromised-GitHub assurance tier.
B is no longer the preferred deployment target under that owner decision; it
remains a nonpreferred reconsideration option, not a demonstrated retained store.
F1 separates immutable execution from authenticated recovery storage using
existing GitHub workload identity, Actions artifacts and journal custody. Its
storage-proof issuer/read/retention costs and qualification are additional
obligations, not a second consumption mechanism or a new service.

Reverse or suspend this recommendation if a conforming ordinary-profile trace
still gives two starts, if D06's real quiescence fence cannot be qualified, if
reviewer-accessible authority/bypass cannot be removed, or if J20 cannot isolate
old writers. A counterexample within accepted assumptions is a blocker, not an
accepted residual by wording. The recommendation does not adopt J-CH, reject
B normatively or authorize constructing E as a fallback.
