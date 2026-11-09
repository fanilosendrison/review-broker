---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "candidate-contract"
domain: "independent-review"
severity: "draft"
name: "RB91 F1 Execution and Storage Provenance Separation"
version: "0.1.1"
---

# RB91-F1 — Execution is not storage

**Candidate only; no normative adoption or operational implementation.**
The [2026-11-09 owner decision](https://github.com/fanilosendrison/review-broker/issues/91#issuecomment-6731259973)
selects conditional J-CH, keeps B/E as reconsideration alternatives, confirms
journal2/AtomicArm/j-ch-v1 direction, v2 S2 and the protected-host boundary,
and REQUIRES this correction rather than accepting the original-run-only limit.
Those choices are not reopened. J20 and operational admission remain separate.

The [old GO](https://github.com/fanilosendrison/review-broker/pull/112#issuecomment-6731118038)
remains valid ONLY for85149a17c6eda3e8f7cbc5f0f00c280f1b5ecdf9. Its F1 trace is
preserved: terminal evidence survives, original run ends before result upload,
a later run's result location fails RESULT_RUN. The new candidate replaces that
single conflated predicate with the following independent gates.

## A — Immutable execution provenance

The closed `execution` object binds request/ordinal1 attempt, subject, policy,
packet, broker numeric ID, original controller workflow ref/SHA/run/attempt,
AtomicArm commit A and canonical binding digest, exact terminal-capture receipt,
original evidence locator identity and exact validation artifact identity.

Every field matches an authenticated immutable execution/journal snapshot.
A is observed externally from the actual ARM commit and checked against its
binding/parent, never guessed from a caller's string or embedded recursively in
A. Original terminal locator/plan/run identities remain unchanged. The terminal
receipt and validation evidence IDs must be in their exact historical events;
count1, arm event, admission and binding remain immutable. A recovery does not
reinterpret INDETERMINATE as evidence of non-execution, nor invent terminal data.

The candidate's trusted execution context is obtained by the authenticated v2
journal reader under R1-style immutable/scope checks and monotone history
validation. It is NOT supplied by the packet, result reference, job input or
reviewer. Offline fixtures explicitly supply this trust root; they do not claim
to implement or qualify that production reader.

## B — Separately authenticated storage provenance

The closed `storage` object identifies mode `original` or `recovery`, actual
storage workflow ref/SHA, run/attempt, numeric job ID, fixed job name, actor and
triggering-actor login/numeric ID, and a closed authorization receipt plus its
artifact identity. `location` keeps repository, actual storage run/attempt,
Actions artifact numeric ID, archive digest/name and exact `review-result.json`
path. Its run/attempt equals STORAGE, not automatically EXECUTION.

- Original mode requires storage run/attempt/workflow to equal the original
  controller. It still requires independent storage authorization/observations.
- Recovery mode requires a distinct run/attempt pair and an explicitly admitted
  recovery workflow/job/source/actor. A later attempt of the same run may qualify
  as recovery; it cannot masquerade as the original attempt.
- Mode selection is data, not authentication or a model permission.

### Admission proof before any publication reservation

A trusted deployment policy, separate from the reference, pins repository/name
and numeric ID/owner ID/default ref, approved ORIGINAL and RECOVERY workflow
refs/source SHAs, fixed job/upload-step names, event types and authorized actor
IDs. Source pins authorize only their explicit storage role. No ambient default,
caller-provided workflow allowlist or arbitrary same-repository job suffices.
Actor IDs in the protected policy are strict positive integers, not booleans
or coerced numbers. The storage caller must also be independently authorized to recover this exact
request/attempt under the broker's existing requester/admission scope; the
trusted snapshot fixes that scope, it cannot be selected by an untrusted input.

The existing GitHub workload-identity verifier authenticates a TRANSIENT storage
proof. Its audience is:

```text
urn:review-broker:result-retention:v1:sha256:<SHA256(canonical statement)>
```

The statement is the COMPLETE closed result reference with only
`storage.authorization` and `storage.authorization_receipt_id` removed, avoiding
self-reference. It binds execution, bytes, location, mode, workflow, run/attempt,
job and actors. It is disjoint from every ARM audience and `j-ch-v1` execution
envelope. No JWT is stored in packet, result, journal, artifacts, logs, argv or
reviewer environment. This is authentication, NOT another consumption primitive.

The maintained shared `github_oidc.verify_github_identity` mechanism verifies
pinned issuer/discovery/JWKS, RS256/key identity, signature, exact audience,
strict numeric dates, maximum600-second lifetime and exact workload claims.
Standard JOSE thumbprints may be validated as metadata through its existing
option; they never select keys. Expected claims are repository/name and numeric
ID, owner/name and numeric ID, immutable repository subject, ref, workflow ref
and SHA, executing SHA, actual storage run/attempt and actor login/numeric ID.
No live proof mint occurs in this task.

In addition, fresh authenticated official GitHub observations must agree:

1. Repository metadata identifies the configured repository/ID.
2. Attempt-specific Actions run identifies exact run/attempt/repository, pinned
   source SHA/workflow path/default branch, allowed event, actor AND triggering
   actor. Provider actor objects are projected to login/ID, not compared as if
   all their incidental fields were part of the journal ABI.
3. A complete bounded attempt-specific job list has exactly one admitted fixed
   job name, matching numeric job ID, run/attempt/source and usable status
   (in-progress, or completed/success). Unknown, canceled, duplicate names,
   incomplete scans and missing job facts refuse.
4. Its unique configured upload step is completed/success. Artifact creation is
   within that step's observed start/completion interval. Independent artifact
   metadata identifies exact numeric ID, name, digest, unexpired state and actual
   storage run/source SHA. Unknown/missing/expired/contradictory data refuses.
5. Applicable source/run/repository assertions in EVERY artifact metadata read
   are confronted with the respective immutable original execution or authenticated
   storage context. Reusing an older download adapter cannot discard an explicit
   source contradiction or overlook drift on a later read.
6. The retained ZIP's actual digest/size, safe extraction, exact path and complete
   file inventory establish the exact result bytes, not merely desired metadata.

GitHub artifact REST metadata has a run ID, NOT independent job/run-attempt
attestation. OIDC binds run/attempt; attempt-specific jobs and upload observations
provide corroboration. Binding the upload outputs/job ID to the actual job still
relies on the pinned trusted workflow, which must derive its context from the
actual runner/runtime token, never dispatch input. Only the admitted job may
hold storage-purpose OIDC/upload authority in that workflow. The code/source
pin, job isolation and actual provider capability need separate operational
qualification. A nonce, job ID, actor string, filename, upload success flag or
OIDC signature by itself does NOT prove who uploaded an artifact.

### Durable non-secret receipt

After ALL gates pass, the trusted verifier produces exactly:
`schema_version=1`, `evidence_type=result-storage-authorization-v1`, pinned issuer,
`authority_policy_id` and `statement_sha256`. Policy ID is the existing artifact
identity over canonical policy basis+LF (repository/ID/owner/ref, approved
workflow map, sorted actor IDs and exact trusted recovery scope: request/attempt,
ARM commit and original terminal locator identity). Receipt ID is the existing artifact identity
over canonical receipt+LF. Both receipt and ID are embedded in the immutable
reserved intent. They contain NO token or reusable execution grant.

Matching receipt fields/hash is necessary but NOT authentication: the future
writer must perform the actual live verification before committing that receipt.
Readers later trust its immutable journal custody under the accepted trusted
writer boundary. They do not demand an old expired JWT, recreate a creator
capability from a receipt, or treat arbitrary externally supplied receipt bytes
as an accepted journal observation. Historical reads/recovery remain evidence-only.

If the original job died before committing an intent/authorization receipt, a
new authorized recovery may reconstruct and retain the same validated result
under its own job and fresh storage proof. Orphaned storage is not a model retry
or posting entitlement. No additional service, key store, ledger or database is
introduced; existing Actions artifacts, GitHub issuer and journal are used.

## C — Result and evidence content identity

The result reference is typed `application/json` / `review-result-v1`, with exact
artifact ID and byte length. Result ID remains the existing canonical semantic
result identity; raw artifact identity uses exact canonical JSON+LF bytes.
Location changes cannot change execution identity. Identical result bytes
re-stored by another job keep the SAME result/content IDs. Execution provenance,
validation and original evidence are never rewritten to make storage fit.

Before admission, download the ORIGINAL terminal archive through its original
locator. Verify metadata, expiry, archive hash/size, safe extraction and complete
inventory using accepted artifact rules. Validate the capture receipt, exact
request/attempt/packet and original controller context. Recompute independent
packet/terminal/credential/citation validation using the accepted evidence
validator; compare its canonical identity with the immutable VALIDATED event
and `execution.validation_id`. No precomputed success boolean can replace it.

Download result bytes through the STORAGE location. Require exact content
identity/length, canonical bytes, public result schema, request/attempt, subject,
policy, packet, complete resolved admission and exact recomputed validation.

Matching an EMBEDDED validation object is not enough: the result's execution/
evidence dimensions, verdict, examined sources, anchored findings and
uncertainties must faithfully project that reconstructed validation. Requested
reviewer identity comes from the exact retained attempt; effective identity flags
cannot be fabricated from a storage proof. The accepted result constructor is
reused as the projection oracle; all its normative fields are confronted, while
additional non-authoritative reviewer metadata permitted by public v1 remains
preserved. No result field is silently dropped or rewritten to make it pass.
Applicability is checked for consistency with its checked-head observation;
fresh source applicability remains the separate authenticated publication gate
under the accepted source-credential contract, not a claim made by storage alone.

Structured identity comparisons use exact canonical JSON bytes, including the
complete resolved admission and the projected provider actor identity. Language
coercion/equality such as Python `True == 1` cannot establish identity. The
ordinary credential veto remains mandatory. Missing or invalid terminal proof,
changed/cross-attempt content, expired artifacts or contradictory provider
observations blocks validation/publication, NEVER historical consumption.

## Publication ownership and interruption

All F1 gates precede a new publication-intent reservation. One expected-old CAS
from unreserved VALIDATED chooses one complete intent and its exact storage
reference. Only its positively acknowledged ORIGINAL live CAS creator receives
a single in-process POST continuation. Competing jobs may store copies but only
one may reserve. A lost reservation ACK is evidence-only, even if the intent is
later seen. Recovery cannot infer creator permission from a nonce, JWT, storage
mode, receipt or matching result. This is unchanged publication safety, not a
new durable mechanism.

A later attempt may repeat evidence-only work if no intent exists. Once reserved,
intent/reference/nonce/publisher/result identity are immutable. No relocation,
new storage proof or expired artifact resets the reservation or grants another
POST. Before POST, a complete exact actor/body/publication-ID comment scan may
observe an existing publication. Actor attribution compares the canonical
login/numeric-ID projection, not the entire extensible GitHub user object;
ordinary provider metadata cannot erase an otherwise exact observation. POST is attempted at most once by its live
creator; the attempt flag precedes transport. Any uncertain reply thereafter
allows observation only. Zero matches remains ambiguous, multiple matches is an
incident, one independently observed exact match permits REPORTED. Interrupted
recovery cannot create model permission or a second posting capability.

The bounded publication model is a verification oracle, not production code.
It reuses the real publisher's transport/pagination and intentionally restates
v2 ownership separately. Existing v1 publication machinery and its tests remain
unchanged. The accepted no-double-POST rule is NOT weakened to improve liveness.

## Adoption and remaining gates

The closed [result-reference schema](qualification/rb91-result-reference-v2.schema.json)
is consumed by candidate journal0.2.0; old candidate bytes remain at the old SHA,
not implicitly migrated. Public ReviewResult v1 bytes/schema are unchanged.
The candidate authorization receipt is closed, separate from the external raw
JOSE proof and trusted policy. The real storage-purpose OIDC role/source/job
configuration, upload output binding, exact Actions observations, credential
isolation, ZIP limits and provider behavior remain construction/operational
qualification obligations; no current workflow permission is modified.

The documentary transition is prepared, not executed:

| Accepted owner | Planned amendment at formal adoption |
| -------------- | ------------------------------------ |
| [Specification](../specification/review-broker-spec.md) | Conditional J-CH applicability, execution versus storage authority, and request-v2 implementation-status reconciliation |
| [Execution](../contracts/review-execution.md) | Journal2/AtomicArm/count1/history, strict dispatch, v2 S2 and preservation of v1 |
| [OIDC authority](../contracts/oidc-arm-authority.md) | Explicit coexistence with a versioned J-CH successor and disjoint storage-purpose authentication; preserve the original v1 contract |
| [Evidence](../contracts/review-evidence.md) | Original terminal/validation identities, typed storage observations, exact retention and token exclusion |
| [Result](../contracts/review-result.md) | Reference/receipt custody and content identity, retaining creator-only reservation and no ambiguous repost |
| [Recovery](../operations/recovery.md) | Authorized recovery storage, S2 quiescence/custody, no execution reauthorization or historical migration |
| [Components](component-boundaries.md) | Distinct journal, workload verifier, storage/evidence and publisher responsibilities |
| [Threat model](../security/threat-model.md) | Trusted workflow/job context, actor/source pins and residual provider/privileged-writer boundaries |
| [Independence](../security/reviewer-independence.md) | Storage proof and control credentials outside reviewer reach, without reopening maximal attestation |
| [Agent rules](../../AGENTS.md) | Versioned applicability/discovery and unchanged J20/admission gate authority |

Formal adoption also needs the repository-governed versioned architecture record,
accepted journal/result-reference/workload schemas and protected policy/profile
contracts. None is adopted or deployed here. No accepted document/ADR is changed. J20, production ARM and J-CH v2
admission remain closed. A NEW independent verdict on the revised SHA is required
for readiness for normative adoption; the earlier design GO is not reused.
