---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "adoption-proposal"
domain: "independent-review"
severity: "draft"
name: "J-CH Governed Normative Adoption Packet"
version: "0.1.0"
adoption_status: "proposed"
---

# J-CH — Governed normative adoption packet

**PROPOSED AMENDMENTS ONLY. No final adoption, merge, construction or activation.**
This packet prepares the exact versioned authority changes selected by the owner.
A separate explicit owner integration mandate is required. Nothing in a Draft,
a schema validation result, ADR severity or independent GO activates execution.

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

## Proposed authority owners

- [ADR profile and proposed records](../adr/README.md): distinct decision scopes,
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
- Versioned resources in `schemas/`: proposed machine contracts, never runtime
  admission switches. Current v1 public schemas and production source stay exact.

Specification, existing execution/evidence/result/recovery/security/component
owners receive scoped amendments pointing to these protocol-specific contracts.
Legacy v1 remains under its own authority. Severity is not precedence; the
repository's existing specification→public schemas→accepted documents→code order
is retained. Proposed records do not become accepted merely by appearing here.

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

The amendment is still proposed until the separate formal integration decision.
No historical observation or accepted ADR body is rewritten.

## Validation and adoption boundary

Qualified candidate schemas and all qualified verification modules are retained
byte-identically as construction references. Proposed normative journal/result
resources must have exactly equivalent constraints after an explicit fixed
$id/$ref/annotation relocation; no F1 semantic rule is loosened. New workload/
message resources express the already selected bindings, with independent
positive/negative conformance tests. Tests are offline and not runtime adapters.

A new exact-packet independent review and CI are required. The old source GO is
provenance only, not a GO for these amendments. Final owner integration must
explicitly accept the proposed ADR/profile/contract versions and reconcile any
required lifecycle metadata; publication alone performs none of that.

After formal adoption, separate mandates are still required for construction,
actual workflow/job/issuer/credential capabilities, launcher isolation and bypass
qualification, crash/SSH/quiescence witnesses, artifact limits, end-to-end
retention/publication and J20 all-writer drain/isolation. No Codespace, live OIDC,
claim2, consumer review, historical journal mutation or operational activation
is authorized by this packet. Issue91 remains open.
