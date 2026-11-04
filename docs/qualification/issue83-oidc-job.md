---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "Issue 83 nonproduction Actions OIDC qualification"
version: "0.1.0"
---

# Issue 83 nonproduction Actions OIDC qualification

## Scope

The owner authorized construction of a nonproduction OIDC path in the existing
review workflow, conditional dark deployment and one actual Actions issuance.
Source publication, construction review, conditional merge and actual job
qualification remain separate gates. No result is claimed by this procedure.

The [production authority contract](../contracts/oidc-arm-authority.md) remains
unchanged. No production request, journal operation, Codespace operation,
protected bootstrap, model execution or admission activation is permitted.
Neither a qualification token nor a sanitized receipt is arm authority.

## Workflow separation

`qualification_only` is a boolean manual-dispatch input, default false. Only
that explicit mode selects the qualification job. Issue events never select it.
The ordinary job explicitly excludes that mode; its existing permission, event,
admission, reservation, recovery and cleanup contracts remain unchanged.

The qualification job requires the expected broker repository, actual default
branch `dev`, `refs/heads/dev`, equal executing/workflow SHAs and an exact
`qualification_sha` pin supplied by the authorized dispatcher. The pin cannot
select checkout source: checkout uses only `github.sha` and verifies the actual
Git HEAD before installation or issuance. A moved source fails closed before
minting. The job has only Contents: read and ID-token: write, no source or
Codespaces-control secret, and the existing non-cancelling serialization group.

Manual ordinary review dispatch now requires a positive decimal `issue_number`
before checkout, source-token issuance or request admission. The optional input
exists only to permit a qualification dispatch without a ReviewRequest selector.

## Issuance and cryptographic verification

The fixed entry point is `python -m review_broker.oidc_qualification`. It imports
no request admission, journal, Codespace, execution adapter or broker CLI module.
It generates a fresh 256-bit qualification identity and hashes RFC 8785 canonical
bindings containing repository name/ID, source and workflow SHAs, workflow ref,
default-branch ref, run ID/attempt and that qualification identity. The audience
is `urn:review-broker:qualification:v1:sha256:<binding-digest>`, never the production
arm-authority namespace or a real request/packet/attempt identity.

There is one mint request and no retry. Its HTTPS endpoint and credential come
from the trusted Actions runtime, restricted to the Actions GitHub domain without
userinfo, alternate ports, fragments, redirects, proxies or a preexisting audience.
The production request facade retains its narrower original hostname restriction;
job qualification does not silently qualify or broaden that production policy.

The shared provider client pins GitHub's issuer and fixed discovery/JWKS URLs.
PyJWT with the declared cryptographic dependency verifies RS256, a unique matching
public RSA signing key of at least 2048 bits, exact issuer/audience, required
integer dates with no leeway and a positive lifetime of at most 600 seconds.
Token-controlled key URLs and unsupported headers fail closed. Qualification
alone accepts standard JOSE thumbprints as syntactically bounded, ignored
metadata, never key selection or trust. Production retains its original stricter
header whitelist. This job does not qualify production header compatibility.
Exact repository
name/ID, workflow ref/SHA, default-branch ref, subject, run ID and attempt are
compared with the trusted executing context. Production envelope, trust and
consumption checks remain separate and are not imported or invoked by this job.

## Sanitized evidence and acceptance

Only `oidc-qualification.json` is uploaded after successful verification. It
contains the source identity, fresh qualification identity, policy and audience
hashes, explicit verification outcomes and
`production_arm_authority_qualified: false`. JWT bytes are not written, printed,
returned in receipts or included in errors. A fixed token-response status is
emitted only after receipt, without token content. Failed entry points emit the
fixed `OIDC_QUALIFICATION_FAILED` diagnostic, optionally with a whitelisted static
client error code, and cannot upload a success artifact.

A successful exact-run receipt establishes `OIDC_JOB_QUALIFIED` only. It does not
establish production endpoint compatibility, exclusive reservation, protected
Codespace trust, durable consumption, lifecycle persistence, bundle stdin
transport, provider execution or a valid scientific ReviewResult. Those remain
separately owner-authorized gates. Issue #83 remains open; original #82 and all
claim refs remain immutable. The historical offline report and prior verdicts
are not rewritten by this procedure.

Before any conditional merge, reconcile the exact reviewed candidate and current
dev, successful CI and independent construction GO, disabled admission, unchanged
claims and consumed request, absent active operations and observed Shutdown.
Reconcile the repository's actual merge authority separately. This procedure
does not waive a governing pre-merge qualification requirement. Stop if such a
requirement applies without an accepted dark-deployment exception.
