---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "J-CH Normative Adoption Preparation Validation"
version: "0.1.1"
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
exactly equivalent constraints under explicit $id/$ref/root-annotation relocation;
tests do not silently discard unknown schema keywords or widen the ABI.

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
