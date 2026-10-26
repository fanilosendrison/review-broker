---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Private Source Authorization"
version: "0.1.0"
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

Private source acquisition requires a separately installed GitHub App with only
these repository permissions:

- Contents: read-only.
- Pull requests: read-only.
- Metadata: read-only.

The App installation must select only repositories authorized as Review Broker
consumers. It must have no Issues, Actions, administration, workflow, or
repository-write permission.

The workflow uses the pinned official `actions/create-github-app-token` action
to mint one short-lived installation token. Broker code removes the token from
its parent environment before any subprocess and supplies it only to exact
source-resolution, file-enumeration, clone, and fetch operations. Journal,
publication, and Codespaces subprocesses do not receive it.

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
