---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-plan"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Future Bounded Live PREPARED Specimen Plan"
version: "0.1.0"
---

# Issue 70 — Future bounded live PREPARED specimen

## Status and prerequisites

This document creates no GitHub object and authorizes no live effect. The current
construction is PARTIAL because LP-01 in the
[adapter candidate](../architecture/issue70-live-prep-operational-adapters-candidate.md)
blocks the Controller/admission ordering. This plan is not executable until that
owner decision, complete implementation, exact CI and fresh independent GO exist.
A separate owner live-effect mandate is required even after all construction gates.

The future subject and references are fixtures, not authority to adopt a v3
contract. Issue #76 and historical requests must not be reused. No intentional
failure is injected in the first live qualification. Generation 1 only; STOP at
PREPARED, or preserve refusal/uncertainty without retry. No ARMED or inference.

## Exact subject fixture

Repository: `fanilosendrison/review-broker`, numeric ID `1433701208`.
A new dedicated branch is created later from the exact dev SHA/tree freshly
observed under the future mandate. Its sole change is the new non-executable file
`qualification/issue70-live-prepared-subject.txt`, mode 100644, containing these
UTF-8 bytes with LF line endings and one final LF:

```text
Review Broker v3 bounded live PREPARED qualification fixture.
schema=1
purpose=pre-model-only
model-invocation=forbidden
```

One dedicated subject PR remains unmerged. Authenticated readback freezes its
numeric PR ID/number, repository ID, exact HEAD/base/tree and unique file diff.
No other source path changes and no reviewed code is executed.

## Exact reference Issue fixture

One new dedicated reference Issue is created later in the same repository.
Its body is exactly the following UTF-8/LF bytes with one final LF:

```text
Review Broker v3 bounded live PREPARED reference body.
schema=1
authority=qualification-fixture-only
```

One comment contains exactly these UTF-8/LF bytes with one final LF:

```text
Review Broker v3 bounded live PREPARED reference comment.
schema=1
```

Readback freezes Issue number/numeric ID, comment numeric ID, parent identity,
author numeric ID, original body/comment bytes and their SHA-256 digests. No
mutation occurs during qualification. After the attempt is fully accounted for,
the fixture Issue may be closed under its separate cleanup authority, without
rewriting its body or comment. It is never deleted or repurposed.

## Four ordered references

The future canonical request has exactly four references, in this order:

1. ID `inline-fixture`, kind `inline`, required true. Text is exactly
   `Review Broker v3 bounded live PREPARED inline reference.\nschema=1\n`.
2. ID `specification`, kind `git_file`, required true. Repository is the exact
   broker repository; path is `docs/specification/review-broker-spec.md`. The
   source commit is chosen and frozen during the future live preflight. Original
   bytes, Git blob OID and expected SHA-256 are read back before request creation.
3. ID `reference-body`, kind `github_issue_body`, required true. Repository and
   Issue number are the exact new reference fixture, with its expected body hash.
4. ID `reference-comment`, kind `github_issue_comment`, required true. Repository
   and comment ID are the exact new comment, with its expected comment hash.

`atomicity` is false; independent observations do not claim a globally atomic
cut. No extra reference, path alias, moving git ref or historical fixture is used.

## Canonical ReviewRequest Issue and owner decision

A third distinct object, the new ReviewRequest Issue, is created only after all
subject/reference object IDs, byte hashes and exact subject HEAD are frozen.
The body is only the v3 envelope emitted by the candidate's real
`build_issue_envelope_v3()` after the real request constructor/schema validation;
`parse_issue_envelope_v3()` must round-trip it exactly. There is no v1/v2 marker,
external ID annotation, title-derived authority or prose outside the envelope.
The broker-owned expected technical policy still determines the request's
reviewer fields; independent construction-review model settings do not replace it.

Before Issue creation, the independent owner decision binds:

- Requester numeric ID `30498238` and repository ID `1433701208`.
- Exact new subject PR numeric ID/number and expected subject HEAD.
- Exact canonical request ID and exact envelope/body SHA-256.
- Initial operation only, qualification-only, one Controller dispatch and at most
  one attributable initial Worker dispatch.
- The reviewed executing candidate SHA and exact protected workflow branch.
- No model invocation, Codespace, ARMED, result publication or activation.

The future mandate authorizes later object creation from these exact contents,
not guessed IDs. After creating the ReviewRequest Issue, readback freezes its
numeric ID/number, author, original bytes/hash and Issue origin. The decision
must be bound to that actual origin before any Controller dispatch.

Only then may a separately authorized operator install the four owner variables:
`REVIEW_BROKER_V3_LIVE_PREP_SHA`, `REVIEW_BROKER_V3_LIVE_REQUEST_ID`,
`REVIEW_BROKER_V3_LIVE_REQUEST_ISSUE`,
`REVIEW_BROKER_V3_LIVE_REQUEST_BODY_SHA256`. Presence alone supplies no authority;
workflow/run/job/ref/SHA/actor and Issue observations must confront all values.
No such variables are installed by this construction.

## Future deployment and stop sequence

The future mandate must separately authorize installation of the reviewed inert
registration stubs, freeze workflow IDs and the exact active qualification branch,
and reconfirm that dev/default-branch and all gates remain as approved. Neither
draft PR in this construction is merged. An inert registration does not activate
a live workflow. Both live workflows remain workflow_dispatch-only.

The single authorized Controller must claim/reserve once, dispatch once and
independently authenticate the ACK. The original bound Worker must record
ADMITTED, use its distinct source-App token, retain the original authorized
packet through one direct upload, authenticate REST metadata and remote bytes,
commit the sole PREPARED-or-BLOCKED CAS and perform independent historical
reconstruction. A restarted process is an observer, never a continuation.

The full future effect budget is in [the budget document](issue70-live-effect-budget.md).
The attempt stops before ARMED. Lost responses cause bounded reads only, never
automatic redispatch, upload replacement, ref repair, deletion or generation 2.
Evidence and journal outcome remain separate from Artifact availability.

After terminal accounting, the future operator removes only the four temporary
approval variables and verifies their absence. Fixture/request closure is
containment, not review completion; exact cleanup authority must be included in
the separate live mandate. No next-stage effect is authorized by this plan.
