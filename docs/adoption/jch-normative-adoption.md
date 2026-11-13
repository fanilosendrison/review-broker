---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "adoption-record"
domain: "independent-review"
severity: "draft"
name: "J-CH Governed Normative Adoption Packet"
version: "0.1.2"
adoption_status: "accepted"
---

# J-CH — Governed normative adoption packet

**Owner-accepted normative integration proposal; effective only after merge into dev.**
The RB91 owner mandate accepts the five ADR decisions, their repository profile,
the five J-CH contracts, eight versioned public schema resources and scoped
amendments on the qualified source
`f5838b6acb7d061ff6a0514b4d955d7c71d9cea1` (tree
`71d1e3dbe5bc7028b80a659340399a9464ca9697`). This includes NR-01 through NR-05,
Issue130 and Issue132 within their declared limits. B/E remain nonpreferred
reconsideration options if required J-CH qualifications fail.

Accepted lifecycle metadata on the PR branch is an integration proposal, not
effective authority before merge into `dev`. The changed exact SHA requires its
own CI and independent adoption GO. Merge additionally requires a verified dev
ruleset or a distinct owner decision explicitly accepting integration without
native protection; no such exception is inferred from an unprotected branch.
No construction, J20 qualification, claim2, proof mint or activation is authorized.

The five ADR transitions change only `status: proposed` to `status: accepted`.
Their decision bodies, dates, identities, relationships, governing scopes and
hashes are preserved. No acceptance-date field or precedence rule is introduced.
The profile lifecycle and pinned schemas remain unchanged; its status and
activation condition record this governed transition. Contract/schema changes
are applicability prose and annotations only, not field-domain or protocol edits.
The generated index and maintained governance assertions follow that transition.

The sections below retain preparation provenance and its historical source
qualification boundaries. Mentions of prior proposals, mandates still pending
at those earlier stages, and historical verdicts do not override this current
adoption boundary. Historical reports, frozen resources and manifests remain
unchanged.

## Provenance and fixed decisions

- Fresh base dev:3057192a6ad4e80663b3b8168cbaa52657c3db27.
- Qualified source:PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce.
- [Owner direction](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973).
- [Exact qualified-source GO](https://github.com/fanilosendrison/review-broker/pull/112#issuecomment-6737001033).

The owner has already selected conditional J-CH; B/E remain nonpreferred
reconsideration options. Strict claim-time journal2, one AtomicArm, disjoint
j-ch-v1 workload binding, v2 S2, the protected-host boundary with ordinary defects
in scope, and F1 provenance separation are not reopened. No second authority is
introduced solely to withstand a fully malicious GitHub writer/administrator.

PR94 and PR112 remain unchanged and preserved. Historical NoGo/Go/RED records
retain their original exact-source scope. The F1 investigation is complete;
this packet reuses its qualified artifacts rather than restarting it.

## Accepted authority owners

- [ADR profile and accepted records](../adr/README.md): distinct decision scopes,
  provenance, lifecycle and immutable accepted-record policy.
- [Journal v2](../contracts/jch-journal-v2.md): closed record/identity/history and
  AtomicArm consumption semantics.
- [Execution authority](../contracts/jch-execution-authority.md): original live
  launcher/controller and one protected continuation.
- [Workload authority](../contracts/jch-workload-authority.md): disjoint versioned
  ARM and storage proof domains, closed wire resources and issuer checks.
- [Result retention](../contracts/jch-result-retention.md): immutable execution,
  independently authenticated storage, faithful exact result and one publication.
- [S2 recovery](../contracts/jch-recovery-s2.md): custody/quiescence priority and
  evidence-only recovery with no post-consumption grant.
- Versioned resources in `schemas/`: accepted machine contracts effective upon
  integration into dev, never runtime
  admission switches. Current v1 public schemas and production source stay exact.

Specification, existing execution/evidence/result/recovery/security/component
owners receive scoped amendments pointing to these protocol-specific contracts.
Legacy v1 remains under its own authority. Severity is not precedence; the
repository's existing specification→public schemas→accepted documents→code order
is retained. The owner mandate, not file presence or severity, authorizes the
accepted lifecycle transitions; normative effect awaits merge into dev.

## ED04 — governed status reconciliation

The prior discrepancy is resolved as an implementation-status correction, NOT
by selecting new request semantics or treating executable behavior as authority.
The product already accepts ReviewRequest v2 intent/exact-head/ordinal1 semantics;
its contract0.1.1 records the construction delivered in version0.4.17.

Native Git and PR41 establish integration at
50b89e4ed46963e11846e0159975bdebc0a30f40, including the versioned public schema,
parser and predecessor/admission integration. That merge precedes the pinned dev.
The current accepted request-v2 contract and maintained tests corroborate the
construction status. They do not establish operational admission or qualification.

The proposed specification/execution amendments therefore say that v1/v2 request
construction exists and remains default-disabled for real operation. Journal2 /
J-CH is a DISTINCT version domain and remains unimplemented operationally.
Historical request1 bytes, identities and evidence remain unchanged.

Disposition records:

- **ED04-FACT:** implementation exists in the integrated source; evidence above;
  `no-normative-impact`, verification/conformance/documentation layers. No new
  product meaning is inferred from source.
- **ED04-AMENDMENT:** correct the primary specification status and downstream
  execution prose together under this explicitly authorized preparation scope;
  `no-normative-impact`, repository documentation/conformance. The accepted
  request contract owns semantics; operational status stays separate.

The owner mandate accepts this status correction, effective upon merge into dev.
No historical observation or ADR decision body is rewritten.

## Issue130 — explicitly authorized challenge-domain exception

The owner's bounded Issue130 correction mandate authorizes exactly this proposed
schema delta relative to the qualified candidate, beyond the existing fixed
URI/root-annotation relocation:

- Resource: `schemas/jch-journal-v2.schema.json`.
- JSON Pointer: `/$defs/binding/properties/challenge`.
- Original constraints remain `type: string` and `pattern: ^[0-9a-f]{64}$`.
- Add exactly `minLength: 64` and `maxLength: 64` at that pointer.
- No other constraint, field, location, value or resource is excepted.

The resulting challenge domain is exactly64 ASCII lowercase hexadecimal
characters, with no prefix/suffix or extra character. The ARM envelope inherits
the binding through its unchanged reference to the journal resource. HELLO's
existing64-character maximum and the same64-character pattern already define
that domain; its minimum1 does not broaden it. No string or digest is normalized.
The original CSPRNG challenge origin, lifetime, controller/launcher ownership and
AtomicArm binding semantics are unchanged.

The complete relocation equality oracle adds only these two explicit expected
constraints at this exact pointer, then compares the entire resources. Negative
sensitivity controls cover absent, misplaced and changed lengths and unrelated
journal/result-resource changes. It is not a global waiver or a field-stripping
comparison. All16 qualified historical inputs retain their exact original bytes
and hashes, including the research model which accepts the old LF witness.
That historical model is not retroactively qualified against this corrected
proposed lexical contract. The new real-resource controls own this correction.

The [bounded lexical audit](jch-lexical-audit.json) is observational evidence,
not authority to redefine other fields. The later Issue132 mandate corrects the
local evaluation engine for the26 existing ECMA-262 expressions, not128 schema
occurrences. Current qualification and historical Python-engine results are
separate columns. Unknown patterns/dialects refuse. No additional proposed-schema
constraint is changed. Final integration remains owner-locked.

## Issue132 — dialect fidelity and ascending base reconciliation

JSON Schema Draft2020-12 pattern semantics select ECMA-262 and search matching,
not Python regex quirks. Every inventoried J-CH expression is anchored at both
ends. For this closed catalogue, the local conformance validator uses complete
matching and preserves ECMAScript wildcard line-terminator behavior. It never
normalizes a value or silently accepts a new expression. The unchanged historical
research models retain their original engine and are not retroactively qualified.
[Validation details](jch-validation.md#issue132--local-ecma-262-conformance) specify
scope, positive-domain preservation, native-engine comparison and limitations.

The owner's explicit reconciliation mandate also takes dev commit
a47e42c9437357b18d79fb3e68776063f894b8ea as the second parent of an ascending
merge into this proposal branch, preserving published7a740e5 ancestry and the
mandate'sd8db161/PR131 input as an ancestor. The
[compatibility assessment](jch-base-reconciliation.md) separates v3 PREPARED
construction from future J-CH execution authority and records all263 inherited
paths byte-exactly, including PR133's later three-file publication correction. The historical3057192 base and every original evidence/NO_GO
identity remain historical, not rewritten. No merge of PR113 into dev follows.

## Validation and adoption boundary

The following preparation requirements remain qualification and preservation
obligations under the owner adoption mandate; they do not claim the new SHA has
already passed or that any integration or operational gate has completed.

Qualified candidate schemas and all qualified verification modules are retained
byte-identically as construction references. Proposed normative journal/result
resources must have exactly equivalent constraints after an explicit fixed
$id/$ref/annotation relocation, except ONLY the owner-authorized Issue130 delta
specified below; no F1 semantic rule is loosened. New workload/
message resources express the already selected bindings, with independent
positive/negative conformance tests. Tests are offline and not runtime adapters.

A new exact-packet independent adoption review and CI are required. The source
GO on f5838b6 is provenance only, not a GO for these changed bytes. The owner
mandate authorizes the ADR/profile/contract lifecycle transitions; branch
publication alone does not make them effective before integration into dev.

After formal adoption, separate mandates are still required for construction,
actual workflow/job/issuer/credential capabilities, launcher isolation and bypass
qualification, crash/SSH/quiescence witnesses, artifact limits, end-to-end
retention/publication and J20 all-writer drain/isolation. No Codespace, live OIDC,
claim2, consumer review, historical journal mutation or operational activation
is authorized by this packet. Issue91 remains open.
