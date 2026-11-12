---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "J-CH Normative Adoption Preparation Validation"
version: "0.1.6"
adoption_status: "proposed"
---

# J-CH normative adoption preparation — validation

## Exact inputs and scope

Fresh dev base:3057192a6ad4e80663b3b8168cbaa52657c3db27.
Qualified F1 input:b7316e5e8cadc718872ea56dfecfb61709c636ce, preserved PR112.
This is the RB91_JCH_GOVERNED_NORMATIVE_ADOPTION preparation, not final authority
acceptance or integration. PR94/PR112 and historical verdicts remain unchanged.

[The packet](jch-normative-adoption.md) owns the proposed transition and ED04
reconciliation. It proposes five separate ADR scopes, a minimal pinned ADR
profile, five dedicated protocol contracts and scoped legacy-owner amendments.
The existing v1 body tails remain exact except the explicit request2 status
paragraph correction; [the baseline manifest](jch-baseline-preservation.json)
provides depth-one-CI-preserved evidence. No accepted ADR existed or is rewritten.

## Qualified transfer, not new F1 investigation

[Sixteen qualified files](jch-qualified-inputs.json)—thirteen verification modules
and three candidate schema references—are byte-identical to the qualified input.
All780 prior tests remain selected. The journal/result normative resources have
exactly equivalent constraints under explicit $id/$ref/root-annotation relocation,
except the later owner-authorized Issue130 challenge-length delta documented in
[the adoption packet](jch-normative-adoption.md#issue130--explicitly-authorized-challenge-domain-exception).
Tests do not silently discard unknown schema keywords or widen the ABI.

New proposed resources add exact closed execution envelope, protected policy,
authority hash-preimage, broker-metadata, stream and quiescence shapes. Their
ordinary wire concretization preserves selected bindings and safety obligations;
no new execution/storage service or durable authority is chosen. JSON Schema
validity does not establish signature, original controller/session ownership,
quiescence, actual job custody or admission.

## Local validation results

Python3.11.9, declared `.[test]` dependencies in private venv; normal umask022,
worktree-confined TMPDIR and disabled bytecode writes. Exact detached historical
fixtures and CI variables remain PR72 e65e4db932cb59d7a0fcfbd442ba19e548fc141d and
Issue83 f3f24d942ad13d368975843f4796b1943dc7cdcb with their pinned trees/workflow.

```sh
python -m unittest discover -s tests -v
python scripts/render-adr-index.py --check
python -m compileall -q src scripts tests
```

Initial local preparation: **805 PASS**, 243.267s, exit0. Exact published initial
SHA72d1869331bec7d0ead6515c5f1ed6883a1f0882 also ran805 tests in CI42635116796.
Its independent review nevertheless returned NO_GO; that outcome remains intact.

Corrected local preparation: **809 PASS**, 378.607s, exit0, no failures/errors/
skips/expected failures. It includes the780 qualified tests plus29 new controls:

- 7 ADR/profile controls: calendar-aware dates/leap days, pin/hash/schema,
  proposed IDs, exact body/H1/metadata, duplicate/BOM/CRLF/alteration refusal,
  immutable accepted/retired record transitions and pure stale/missing-index refusal.
- 6 adoption/ED04/legacy/frozen-source integrity controls.
- 13 normative-schema/relocation/positive-negative binding/wire/frame/quiescence
  controls, including exact publication basis, metadata domain, actual Gregorian
  date-time assertions and missing/permissive-checker fail-closed controls.
- 3 synthetic-key actual JOSE checks for new execution purpose versus legacy/
  storage/wrong-workload/changed-binding proofs. No live mint or model call.

Index rendering is explicit write; check computes expected bytes and refuses
missing/stale output WITHOUT repair. Public schema examples test real resource
resolution and qualified valid/invalid vectors. Complete proof budget uses the
maximum32768-character JWT and full canonical wrapper, not the16KiB research
fixture. Metadata-hash substitution and shape-valid cross-binding changes refuse.
Quiescence schema fixtures are NOT evidence of actual Shutdown or custody.

[ED04](jch-normative-adoption.md#ed04--governed-status-reconciliation) is an
implementation-status amendment under existing accepted request semantics.
PR41 merge50b89e4ed46963e11846e0159975bdebc0a30f40 precedes base dev. Pure request2
validation passes, while absent operational enablement refuses BEFORE source/
claim effects. Request version is independent of journal/workload version.

The ADR format/profile itself is proposed; no existing local convention was
silently asserted. Shared schema provenance is pinned to dotagents
aa84e816385f082ea353b6254e490d85fe17bceb and SHA256
55c9ff189e686cb1d545d0cbcfc9527a72dd1e1185c5ba595a3a1da7f3aa8c57. Native proposed
records have no asserted outgoing ADR amendments to nonexistent prior records.
Their index derives reverse relations from source metadata, never stores both.

## Preserved initial review and atomic dispositions

[The complete initial NO_GO](https://github.com/fanilosendrison/review-broker/pull/113#issuecomment-6743090544)
reviews only SHA72d1869331bec7d0ead6515c5f1ed6883a1f0882. Its report SHA256 is
27451138cf8e3f4248f939deb7795009b0a16f5357b906b29e1c8c3f84a6a2aa.
The independent805-test PASS does not erase its8-probe run with1 failure.
A preliminary reviewer representation-comparison oracle also failed; its corrected
explicit-expansion comparison passed. Both original outputs remain preserved.

### NR-01-TRANSFER — metadata/profile prose correction

- **Statement/source/evidence:** the initial workload prose ascribed profile
  fields to the closed ten-field metadata domain; fresh extension probes refused
  those fields and distinct protected profile contexts retained identical metadata.
- **Existing authority:** the qualified source's preserved metadata preimage and
  distinct preflight/runtime bindings; the preparation mandate requires fidelity,
  not a new hash domain. The initial reviewer classified its uncertainty separately.
- **Semantic disposition:** `no-normative-impact` for correcting this proposed
  transfer; no accepted product obligation is promoted or changed.
- **Affected layers/impacts:** normative-contract proposal,
  integration-or-conformance and repository-governance-or-documentation.
- **Relations/required authority/next action:** NR-01 concerns the initial prose;
  version0.1.1 states the actual separate owners. Final owner integration remains
  required; no profile fields or alternative metadata version are introduced.

### NR-02-TRANSFER — omitted qualified publication derivation

- **Statement/source/evidence:** the initial normative proposal omitted the
  complete schema2 publication basis. Two shape-valid bases had different IDs;
  the frozen semantic oracle rejected the legacy-derived alternative.
- **Existing authority:** qualified sourceb7316e5e8cadc718872ea56dfecfb61709c636ce,
  `docs/architecture/rb91-journal-v2-candidate.md`, its result-retention/publication
  section explicitly excludes ONLY three fields and uses the existing renderer.
  This is the mandate's exact proposal input, NOT accepted journal2 authority.
- **Semantic disposition:** `no-normative-impact` for the fidelity/extraction work
  alone. The procedural mandate uniquely selects which candidate bytes to transfer;
  it does NOT accept their product semantics or derive them from accepted v1.
- **Affected layers/impacts:** normative-contract proposal,
  verification-or-qualification-evidence, integration-or-conformance and
  repository-governance-or-documentation.
- **Relations/required authority/next action:** the reviewer's NR-02
  `decision-required` final acceptance question remains owner-locked. The proposed
  contract now carries the already qualified reference-inclusive rule explicitly;
  the incompatible legacy-derived alternative is neither adopted nor substituted.
  Separate owner integration may accept, reject or defer this proposal. No new
  semantic arbitration, F1 reinvestigation or current normative adoption occurs.

### NR-03-VERIFICATION — effective date-time assertion

- **Statement/source/evidence:** the initial environment lacked registered
  `date-time` support, accepting impossible Gregorian dates; the independent
  negative assertion failed and remains preserved unchanged.
- **Existing authority:** declared schema `format: date-time` and the validation
  obligation, not a new execution, chronology or trusted-observation rule.
- **Semantic disposition:** `no-normative-impact`.
- **Affected layers/impacts:** verification-or-qualification-evidence,
  integration-or-conformance and repository-governance-or-documentation.
- **Relations/required authority/next action:** NR-03 is corrected through pinned
  test-only `rfc3339-validator==0.1.4`, registration and positive/negative functional
  qualification of the exact checker used. Missing or permissive implementations
  refuse before schema validation. A byte restoration guard permits ONLY this
  test-extra line change in pyproject; every runtime/build/entry-point byte stays
  exact. No runtime adapter or production requirement was changed.

All three initial witnesses were rerun without changing their assertions:
**8 probes PASS**, 0.532s, exit0. Probe source SHA256 is
514fb013dda700fa35d7b6930f919f3b41a1604ba9a1774b8f9bbade85e68ed7.
Profile fields remain absent from metadata; two structural publication shapes
remain schema-valid while the semantic oracle rejects the legacy basis; impossible
date-time now refuses. Prose transfer, not schema tightening, resolves the first
two mismatches. These are new outcomes, not retroactive changes to the initial
review. No equivalent new memory entry is needed: the shared registry already
documents optional-format fail-open behavior and positive/negative qualification.

## Resumption review and NR-04 complete-string correction

Canonical publication of the preserved eight-file correction produced
08c67a2f9a5d1f57743a04e99d211a4a97c5575c, tree
acc4ff7469829d562dcc8d5d703f424a81f1f05f. Publisher run
01M77D697CFG0GCCHS1B9WZ4CH used qualified installed release0.11.1.
The complete suite passed809 tests locally and in CI43181486933; official runner
logs establish checkout of that literal SHA, not a synthetic merge.

[The fresh complete-packet independent NO_GO](https://github.com/fanilosendrison/review-broker/pull/113#issuecomment-6818861832)
remains historical on that SHA. Its809-test PASS coexists with12 independent
probes containing one failure and an unchanged targeted failure. A separate
symlink-dereferencing preservation oracle failed; a separately named symlink-aware
oracle passed without changing the timestamp witness. Neither failure is erased.

### NR-04-VERIFICATION — trailing LF accepted by the format dependency

- **Statement/source/evidence:** schema validation accepted
  `2026-11-09T00:00:00Z\n`; JSON round-trip preserves that embedded LF. The pinned
  dependency uses Python regex `$`, which permits matching before a final LF.
  The independent probe source SHA256 is
  6287ff72c85eb9d9408b3c23898d85073acf7fa5af3404fd03c9be20bba01564.
- **Existing authority:** the schema's RFC3339 `date-time` assertion and the
  mandated effective-format qualification already require complete-string
  rejection. No chronology or execution-authority rule is added.
- **Semantic disposition:** `no-normative-impact`.
- **Affected layers:** verification-or-qualification-evidence,
  integration-or-conformance and repository-governance-or-documentation.
- **Related consequence:** NR-03's earlier calendar/availability correction is
  preserved but its lexical qualification was incomplete.
- **Required authority:** the resumption mandate authorizes in-scope NO_GO
  remediation; final normative integration remains a separate owner decision.
- **Correction/impacts:** only the offline checker instance rejects LF before
  delegating unchanged input to the registered maintained validator. No trimming,
  independent calendar parser, global registration mutation, runtime change or
  frozen-qualified-file amendment is introduced. Missing/permissive-checker
  qualification remains active, with a final LF-refusal self-check.
- **Verification/next action:** the new real-schema regression was RED on five
  valid timestamp forms with appended LF. The identical regression is now GREEN
  across five valid forms and35 invalid suffix variants, preserving input bytes.
  All12 unchanged independent probes pass locally. Complete-suite validation,
  new publication and exact-SHA CI/review remain required for this new candidate.

## NR-05 — established RFC3339 leap-second conformance

[The independent NO_GO on86a22b6254f55b3d3fd88bd644ac07368cd474e5](https://github.com/fanilosendrison/review-broker/pull/113#issuecomment-6819602223)
remains unchanged. Its810-test PASS and15 adversarial PASS coexist with two
positive RFC3339 example errors. The exact independent oracle SHA256 is
3480059279127aeed8b031d7ca4d94f87a8db0142efbb293690b3bee15b0ea30.
Replaying it before correction reproduced both errors without changing the file.

### Discovery and bounded correction

- **Statement/source:** `rfc3339-validator==0.1.4` excludes seconds60 syntactically,
  rejecting the two established1990 leap-second examples in RFC3339 section5.8.
- **Authority:** RFC3339 sections5.6–5.8 and the existing six `date-time` schema
  sites; the resumption mandate requires established leap events, not arbitrary
  acceptance of every syntactically shaped second60.
- **Disposition:** `no-normative-impact`; verification-or-qualification-evidence,
  integration-or-conformance and repository-governance-or-documentation.
- **Relation:** completes NR-03 positive coverage while preserving NR-04's
  complete-string refusal. Neither finding changes execution authority.
- **Correction:** the offline `tests/jch_datetime.py` adapter preserves the
  registered library validator for ordinary timestamps, with the explicit
  year0000 correction below. Its separate full-match
  seconds60 branch checks Gregorian calendar/minute fields with the standard
  library, validates the numeric offset, and compares the end of the containing
  UTC minute against established positive leap transitions. Fractions remain
  exact digit sequences; no precision truncation or timestamp replacement occurs.
  No input second is rewritten to59/00, and no normalized timestamp is returned.
  Negative-zero offset retains the RFC3339 known-UTC/unknown-local-offset meaning.
- **Qualification:** positive/negative functional checks apply to the actual
  checker instance, including ordinary offsets/fractions/lowercase syntax and
  established leap events. Missing, incomplete or permissive checkers fail;
  missing or changed external data refuses qualification. Registration stays
  instance-local. Non-string format checks defer type rejection to the schemas.
- **Required authority/next action:** mechanical repair is authorized by the
  NR-05 mandate; final normative integration still requires the separate owner
  decision after new exact-SHA validation and independent complete-packet GO.

### External leap facts, provenance and support boundary

The public-domain [IANA-distributed IERS table](https://data.iana.org/time-zones/tzdb/leap-seconds.list)
is retained byte-for-byte as `tests/fixtures/iana-leap-seconds.list`, SHA256
`db5a895f16853b03bfc865e8d68f9fc8710ef1740e3400c701cd46a5bbbc3433`.
It identifies IERS Bulletin C as the source of decisions. Its update marker is
NTP3992312697; expiry is NTP4023129600, **2027-06-28T00:00:00Z**.
The initial1972-01-01 offset is a baseline, NOT an insertion. The27 subsequent
positive transitions cover every listed insertion through2016-12-31. No negative
transition is present. Data bytes and their declared horizon are qualification
inputs, not authenticated observation timestamps.

An asserted second60 outside the pinned interval raises the explicit
`LEAP_SECOND_OUTSIDE_PINNED_COVERAGE` capability error. It does not establish
that the timestamp is normatively invalid. Within coverage, a nonexistent event
or wrong UTC minute is rejected. Ordinary timestamps are not restricted to the
leap table's interval. This is bounded conformance against the pinned evidence,
NOT universal knowledge of future leap decisions or pre1972 time adjustments.
RFC3339 itself says future insertions cannot be predicted and should not be
emitted before announcement. The syntax checker does not establish chronology,
clock accuracy, custody or authenticity of an observation.

Updates require a separate explicit data-maintenance change: obtain the official
IANA/IERS revision, inspect bulletin provenance, compare complete transition
history and metadata, replace the raw fixture and pinned digest together, then
rerun historical/offset/coverage tests and independent qualification. There is
no automatic network refresh, wall-clock-dependent repair or ambient host table.
A future negative leap requires separately qualified ordinary-second exclusion;
merely changing the fixture/digest cannot activate that unsupported path because
checker qualification refuses any negative transition. These are capability
limits, not a narrower replacement for the normative RFC3339 contract.

### Regression evidence

Nine new maintained tests cover all27 established events, all2879 numeric minute
offsets from-23:59 through+23:59 with contradictory-minute negatives, actual
schema types/40-character limits at all six sites, Gregorian invalid dates,
fractions, lowercase T/Z, forbidden separators/suffixes, local registration and
missing/permissive/incomplete checkers/data. Space is not selected as a date/time
separator: the existing JSON Schema RFC3339 grammar uses T/t; no new optional
application syntax is introduced. The original two-case independent oracle is
unchanged and passes after correction. Complete-suite, exact publication/CI and
new independent verdict are separate evidence gates below, not inferred from
these focused results. Runtime files, historical schemas, frozen qualified
modules, dependencies and owner decisions remain unchanged.

### Preserved first NR-05 remediation review and boundary corrections

[The complete independent NO_GO on1bbfdfc6390c644de37b6b11cb67bea57b526a31](https://github.com/fanilosendrison/review-broker/pull/113#issuecomment-6820734402)
remains unchanged. Its817-test PASS and successful unchanged NR-05 oracle did not
erase fresh errors: two year0000 positives failed at all six schema sites, and
complete-resource boundary probes exposed five error subcases. Both unchanged
probe programs and original outputs are preserved separately from later outcomes.

- **R1 statement/source/authority:** the ordinary dependency explicitly rejects
  year0000, despite RFC3339 section1's0000AD–9999AD scope and four-digit grammar.
  The correction reuses the dependency's full-match lexical grammar for that
  previously excluded year and standard-library proleptic Gregorian month lengths.
  It does not reinterpret a timestamp as another year, trim bytes, change schemas,
  or substitute a new ordinary-date grammar. Actual positive/negative checker
  qualification now includes year0000 and its leap-day/calendar boundaries.
- **R2 statement/source/authority:** Python datetime arithmetic overflow at the
  year boundaries became `False`, contradicting the documented distinction
  between invalid calendars and unavailable leap-event coverage. Calendar and
  offset fields are now validated first, then UTC-minute boundaries are computed
  with integer Gregorian ordinals. No floating-point or datetime boundary
  conversion truncates/normalizes the asserted event. Valid year0000 leap
  assertions are necessarily outside the table and report that capability error;
  malformed calendars still reject as invalid.
- **Disposition/layers:** each record is `no-normative-impact`, affecting
  verification-or-qualification-evidence, integration-or-conformance and
  repository-governance-or-documentation. R1 is an inherited dependency limitation;
  R2 was introduced by the first bounded adapter. Neither concerns live authority.
- **Required authority/next action:** the NR-05 remediation mandate authorizes
  both mechanical fixes. The two new maintained tests were RED before correction
  and GREEN afterward. The unchanged four-method boundary probe and12-method
  adversarial probe now pass, including155466 leap/offset assertions. A new
  publication, full exact-SHA qualification and complete independent verdict
  remain required; no previous GO or PASS is transferred.

## Issue130 — exact challenge and separate class-audit findings

The owner explicitly authorized only the challenge lexical correction and its
narrow fidelity exception. The historical NO_GO on
7a740e5550e3739c98356200ff9f4a2e490ce9a2 remains unchanged. The original oracle
SHA2560fef77d33b2d929520d156e1fe90c9b411fcc73df893254ceb9c1f696233a668
reproduced two failed schema subcases before correction and passes unchanged
after adding only journal challenge minLength64/maxLength64. Its canonical
record still contains an embedded LF, and its binding digest is recomputed;
no unrelated digest failure substitutes for the lexical rejection.

Three new real-resource tests cover valid lowercase hex and63/65-character,
LF/CRLF/internal-LF/TAB/Unicode/uppercase/nonhex/empty/nontext negatives across
journal, ARM and HELLO, with complete objects and consistent binding digests.
They distinguish JSON-string LF from final document framing and explicitly
preserve the old model's historical acceptance. The full-resource equality test
permits only the two exact length constraints at the authorized pointer; a new
sensitivity test refuses missing/misplaced/changed lengths and unrelated changes
in either relocated resource. The sixteen frozen inputs remain untouched.

### Historical Issue130 class audit — non-challenge engine conformance failed

At the Issue130 handoff, the retained machine-readable inventory bound all eight
proposed schema resources by SHA256 and listed every164 pattern occurrence with
JSON Pointer, constraints, positive sample and LF/CRLF/TAB/NUL outcomes. Its
explicit outcome was `FAIL_NON_CHALLENGE_LEXICAL_DOMAINS`. That exact historical
snapshot is preserved in the handoff patch, not rewritten as a PASS. The current
[inventory](jch-lexical-audit.json), reproduced with
`python tests/jch_lexical_audit.py`, additionally distinguishes historical and
corrected-engine outcomes as described in Issue132 below. Emitting a report is
not itself a conformance-success receipt.

- **Already exact for the tested mechanism:**36 occurrences refuse every tested
  terminal suffix. Fixed-width hex/digest fields with matching maximum lengths
  (including the corrected challenge) have a direct complete-domain argument.
  This bounded audit does not claim a universal proof for arbitrary patterns.
- **Confirmed lexical gaps:**128 occurrences accept the valid sample plus LF.
  Families include unguarded journal hashes/IDs, prefixed identities with overly
  loose maximum lengths, numeric IDs, repository/name/event/workflow-path strings,
  JWT shape and artifact-path/URI patterns. A maximum larger than the exact token
  length does not repair the dollar-anchor behavior. These are observed
  subschema failures, not hypothetical risk or operational bypass evidence.
- **Complete interinterface witness:** a canonical journal carrying a launcher
  program digest plus LF, with its binding digest consistently recomputed, is
  accepted by journal, ARM and the frozen model but refused by HELLO. This
  independently demonstrates another real interface mismatch outside challenge.
- **Semantic barriers remain distinct:** an exploratory input-digest witness
  also exposed schema acceptance but the unchanged semantic capacity validator
  refused it. Its original source/output and the separately narrowed launcher
  witness are preserved; no capacity/authentication bypass is inferred.
- **Unclassified/theoretical occurrences:** none within this enumerated pattern
  corpus; other lexical mechanisms and operational paths are not universally
  qualified by this suffix audit.

**Discovery disposition:** `no-normative-impact` for the observational records;
affected layers proposed normative contract, verification-or-qualification-evidence,
integration-or-conformance and repository-governance-or-documentation. The gaps
predate this challenge correction. Their repair is not covered by the exact
challenge-only exception; separate explicit amendment authority is required.
[Issue132](https://github.com/fanilosendrison/review-broker/issues/132) retains the
complete occurrence inventory and standalone launcher witness, also reproduced
against the untouched published7a740e5 baseline. It is a verified native blocker
of Issue130, not permission to extend that mandate.
Neither all-green maintained tests nor frozen-source fidelity waived those
failures. They blocked publication at that handoff pending separately governed
Issue132 disposition, recorded below. No other schema was changed.

## Issue132 — local ECMA-262 conformance

The owner-authorized Issue132 remediation preserves all proposed regex strings
and constraints, apart from the separately approved challenge-length exception.
The former128 LF acceptances were conformance-engine discrepancies, not128
independent normative decisions. The original failing audit and complete-object
launcher witness remain preserved with their exact sources and outcomes.

**Discovery/authority:** Draft2020-12 validation section6.3.3 specifies ECMA-262
regular expressions; JSON Schema pattern is a search, not implicit anchoring.
Here all164 occurrences explicitly start with^ and end with$, covering26 exact
expressions in eight resources. Python's default search accepts a final LF before
its dollar anchor, unlike the native no-flags ECMAScript end assertion. The
atomic correction is `no-normative-impact`, affecting verification evidence,
integration/conformance and documentation; it realizes the already declared
schema dialect, not a narrower product domain or new execution mechanism.

The local `tests/jch_patterns.py` adapter admits only the exact committed
26-expression catalogue. It uses maintained Python fullmatch for these explicitly
anchored expressions, with ASCII ranges/escapes, quantifiers, noncapturing groups,
negative lookahead and negated classes preserved. The two expressions containing
wildcard dots (artifact-path lookaheads and the comment URL) explicitly map that
wildcard to the ECMAScript non-multiline class excluding LF, CR, LS and PS. The
comment URL's unescaped dot is NOT silently changed into a literal dot. Native
engine differential tests exposed that distinction before correction.

The catalogue excludes shorthand classes, flags, backreferences, lookbehind,
Unicode properties and other unqualified constructs. Any new expression fails
admission and requires explicit catalogue review and new equivalence evidence.
No general regex translator or universal regex conformance claim is made.
Per-expression reasoning establishes the used operators' correspondence;
maintained tests independently compare native Node RegExp over deterministic
mutations, lengths, ASCII scalars, Unicode/astral/surrogate values, separators,
controls, internal/prefix/suffix contamination and valid-domain controls. Missing
Node is a qualification failure, not a skipped differential check. Node24 is
already supplied by inherited CI, with no new runtime dependency.

Draft2020-12's pattern callback is extended only in a local validator class.
Because jsonschema normally reselects a global class when resolving a resource
with an explicit dialect marker, private evaluation copies remove ONLY the
root `$schema` after requiring its exact Draft2020-12 value. Referencing resources
are explicitly bound to that same specification. IDs, refs, annotations and all
constraints remain exact. Nested dialect changes and unknown patterns refuse
before validation. No global registration, public resource, accepted historical
validator or frozen model is modified. A real ARM-to-journal reference regression
proves the local callback is not bypassed during evolution.

Current audit reports **164 occurrences,26 distinct patterns, zero unresolved
suffix gaps** using the qualified local validator; separate per-occurrence
historical results retain the former128 LF acceptances. Positive samples are
required to pass before suffix tests. The unchanged original challenge and
launcher oracles now pass against complete canonically resealed objects, without
using stale hashes to force rejection. The frozen model's old acceptance remains
visible. Snapshot-freshness PASS is still not a substitute for conformance tests.

The [base reconciliation](jch-base-reconciliation.md) and explicit
[upstream preservation manifest](jch-upstream-preservation.json) separately govern
the ascending merge of PR131's v3 PREPARED context. No old824-test result is reused
as qualification of that integrated candidate. Historical reports, external-data
RFC3339 capability limits and every operational gate remain unchanged.

## Remaining publication and review gates

Complete-range whitespace, JSON, source-size, links and production-byte guards
must pass before publication and on actual published state. Exact remote SHA,
first runner checkout/CI and NEW independent whole-packet GO must be freshly
verified; no old F1 GO is reused for these new amendments. Raw local logs and
GitHub readbacks remain private; exact later publication receipts identify that
state independently of this local run.

No production source/runtime dependencies, existing public request/result schemas,
workflow/permission, historical journal or admission configuration is changed.
The sole dependency amendment is the pinned test-only format implementation;
its exact before/after line and baseline file hash are recorded in the manifest.
All original7/extended11 journal1 forms remain unchanged/non-replayable. Issue107
remains the separately tracked umask077 fixture problem; normal022 PASS is not
its remediation or qualification.

## Not performed

Final normative acceptance/integration, ADR accepted transitions, merge,
construction/deployment, protected bootstrap, actual storage/issuer/job/SSH/
FD/credential capability, S2 crash/quiescence/lifecycle witnesses, end-to-end
retention/publication, J20 all-writer drain/isolation, v2 claims, production ARM
and consumer/broker model invocation remain outside this mandate.

The next decision is separate owner normative integration only after a new
exact-packet GO. Production qualification remains a later distinct gate.
