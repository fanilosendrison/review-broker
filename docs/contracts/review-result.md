---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "ReviewResult v1 Contract"
version: "0.1.2"
---

# ReviewResult v1 Contract

ReviewResult v1 is defined by `schemas/review-result-v1.schema.json`. It binds the
logical request, exact subject, policy, packet, attempt, requested reviewer,
sources examined, findings, uncertainties, validation evidence, and current
applicability.

## Independent dimensions

`execution_status` records only observed process execution:

- `COMPLETED`: one valid terminal completion sequence was captured.
- `FAILED`: an explicit process failure, nonzero terminal outcome, or failure
  event was captured.
- `INDETERMINATE`: actual execution or terminal outcome cannot be established.

`evidence_status` records structural and identity validation:

- `VALID`: required evidence and exact bindings pass.
- `INVALID`: an observed artifact violates the contract.
- `UNDETERMINED`: available evidence cannot establish validity.

`review_verdict` records only an evidence-valid reviewer response: `GO`,
`NO_GO`, or `UNDETERMINED`.

No dimension is inferred from another. A completed process may have invalid
evidence. Valid citations may support an incorrect conclusion. An empty finding
list does not create `GO`; only an explicit evidence-valid verdict can carry
that value.

## Reviewer metadata

The result records requested backend, model, and reasoning effort. Effective
model identity and effective reasoning effort remain unverified unless an
independent provider attestation is available. The current CLI flags are not
such an attestation.

## Applicability

The original verdict is immutable. Publication re-resolves the pull-request head
and records `CURRENT`, `SUPERSEDED`, or `UNDETERMINED` separately. A historical
`GO` cannot authorize a new SHA.

A changed-head or same-head repeat request has its own result. A newer result
does not mutate, validate, invalidate, or automatically override a predecessor
result and does not authorize consumer action. In particular, a prior invalid
result does not become valid because a subsequent review succeeds. These rules
preserve the existing independent execution, evidence, verdict, and
applicability dimensions for v1 and future v2 results.

## Publication evidence

Before a result comment can be posted, the journal atomically reserves one
publication intent containing a fresh nonce, exact canonical result and its
identity, Issue, and expected GitHub actor. The comment carries that publication
identity. `reviewctl result` retrieves only the exact journaled receipt's
comment ID and rechecks its issue, actor, canonical body, publication marker,
result identity, and complete comment pagination; a result-shaped comment
without that attribution is not an authoritative CLI result. A
successful or lost-response history reaches `REPORTED` only after complete
comment pagination independently observes exactly one matching body from the
bound actor and records immutable comment metadata.

A concurrent caller that did not create the reservation may observe but never
post. Zero observed comments after a reserved post attempt is
`PUBLICATION_OUTCOME_INDETERMINATE`; multiple matches are a duplicate-publication
incident. Desired comment text alone is not historical publication proof.

## Authority

A result is bounded evidence. The consuming repository decides whether its own
admission, publication, or merge conditions are satisfied. The broker does not
merge or modify the subject.
