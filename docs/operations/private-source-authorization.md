---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Private Source Authorization"
version: "0.3.0"
---

# Private Source Authorization

## Boundary

The job-scoped repository token remains responsible for Review Broker Issues,
claim refs, workflow artifacts, and result comments. The Codespaces-control
token remains responsible only for Codespace lifecycle and transport. Neither
credential is authorized to read a private consumer repository.

Public consumer repositories continue through the ordinary GitHub API and Git
path without a private-source credential.

## Required private-repository authority

Private source acquisition requires the dedicated source-reader GitHub App,
separate from journal, publication, Codespaces-control, and reviewer credentials.
One App may support both legacy v1/v2 and candidate v3 through two explicitly
restricted read-only installation-token profiles. These policy profile identifiers
do not introduce runtime schema fields.

The legacy App setup uses Contents: read, Pull requests: read, and Metadata:
read. After contract publication, legacy hardening, and separate owner approval,
the App may request exactly those permissions plus Issues: read for the
successor boundary. The installation must select only authorized consumer
repositories. No profile permits repository-write, Issues-write, Actions,
workflow, administration, Codespaces-control, publication, or reviewer-model
authority.

App registered permissions, installation-approved permissions, and each issued
token's effective permissions are distinct facts. Registered App configuration
does not prove installation approval or effective token permission. Two tokens
from one App share its private-key authority; they are not independent security
principals at the App-private-key level.

### Explicit installation-token profiles

Every source token must explicitly request its use-case subset with the pinned
`actions/create-github-app-token` action. Tokens must not silently substitute
across protocols. `LEGACY_SOURCE_READ` applies to v1/v2, including private-source
qualification, and has exactly these permission inputs:

```yaml
permission-contents: read
permission-pull-requests: read
permission-metadata: read
```

There is no `permission-issues` input in a legacy mint step. Approval of Issues
on the parent installation must not broaden legacy tokens.

`V3_REFERENCE_SOURCE_READ` is reserved for separately authorized candidate v3
source-reference acquisition and has exactly these permission inputs:

```yaml
permission-contents: read
permission-pull-requests: read
permission-metadata: read
permission-issues: read
```

V3 Issue-body/comment reads and source acquisition use that same source token
under verified installation and repository authority. App source access does not
authorize a requester. Original broker Issue admission, reference acquisition,
journal mutation, and result publication remain separate boundaries. Missing
permissions, ambiguous API failures, unauthorized installations, or repository
mismatches fail closed.

Explicit repository selection through the action's `repositories` input is
mandatory for bounded v3 qualification, together with the authorized `owner`.
Specifying `owner` without a restricted repository selection can expose all
repositories available to that owner's installation; that is not the v3
qualification scope. The legacy workflows' existing repository selection is
unchanged, including bounded admission's exact repository-scope verification.

The action's [official permission-input contract](https://github.com/actions/create-github-app-token/tree/fee1f7d63c2ff003460e3d139729b119787bc349#permission-permission-name)
states that omitted permission inputs inherit all installation permissions.
Thus every active legacy mint path must be constrained before App expansion.

### Token lifetime and disposal

The workflow uses the pinned official `actions/create-github-app-token` action
to mint a short-lived installation token, expiring after one hour. Default
post-job revocation must remain enabled; `skip-token-revoke` must not bypass it.
Token use is bounded to the authorized acquisition, with transient environments
and temporary credential-bearing state disposed after use. Credential bytes
must never enter logs, retained packets, artifacts, Codespaces, reviewer
runtime, or the publication mechanism. Publication-applicability lookup is a
source read only; the separate publication credential performs mutations.
Broker code removes the token from its parent environment before any subprocess
and supplies it only to exact
source-resolution, file-enumeration, clone, fetch, and publication-applicability
operations. Journal, publication, Codespaces, and reviewer subprocesses do not
receive it.

Bounded private admission additionally verifies that the token can observe the
configured repository as private and that its installation repository listing
contains exactly that repository. It binds one configured requester, repository,
PR, expected head, and broker SHA. The mode requires ReviewRequest v2 and remains
disabled unless `REVIEW_BROKER_BOUNDED_PRIVATE_V1_ENABLED` is exactly `true`.
Its private preflight evidence is distinct from public low-sensitivity evidence
and records `public_repository_verified` as false.

## Successor owner approval sequence

The candidate v3 boundary does not activate v3, accept ReviewRequest v3 or
Reviewer Packet v2 as a whole, or authorize live qualification. The required
sequence is:

1. The successor contract is accepted and published.
2. All legacy token-minting paths are constrained and verified.
3. The owner authorizes the App permission change.
4. The owner approves the changed installation permission.
5. The owner authorizes one exact reviewed live-qualification workflow SHA and
   subject PR/head, with its trusted workflow published on the default branch.
6. Trusted qualification requests the four-permission v3 token for the explicitly
   authorized repository.
7. Actual read-only behavior and token boundaries are observed.
8. Only then may Issue #69's live exit gate be evaluated.

Until approval and observation occur, effective Issues access remains unverified
and live use remains blocked. No branch override, PR event, or arbitrary
`GITHUB_SHA` substitutes for trusted workflow publication and approved executable
identity. Production activation requires its own qualification and owner approval.

## Bounded owner setup action

An owner must complete these administrative steps outside review execution:

1. Create or select the dedicated read-only GitHub App with the permissions
   above and install it only on approved private consumer repositories.
2. Set repository variable `REVIEW_BROKER_SOURCE_APP_ID` to the App ID.
3. Set repository variable `REVIEW_BROKER_PRIVATE_SOURCE_REPOSITORIES` to the
   comma-separated exact `owner/repository` allowlist requiring private access.
4. Store the App private key as Actions secret
   `REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY`.
5. Dispatch a non-model source-acquisition qualification and preserve only App,
   installation, repository, permission, commit, and file identity metadata.

The secret value must not be requested, printed, copied into an Issue, inspected
locally, or reused for another boundary. Until setup and qualification are
complete, an authorized private request fails as
`PRIVATE_SOURCE_CREDENTIAL_REQUIRED` before claim creation or source access.
