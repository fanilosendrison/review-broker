---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Issue 69 Source App Read-Only Qualification Preparation"
version: "0.1.0"
---

# Issue 69 Source App Read-Only Qualification Preparation

## Scope and status

The starting accepted `dev` SHA is
`4b664feb9aaf5ddf47914c77ce0ef28096620d41`, the merge of PR #73.
The specification 0.7.1, private-source authorization 0.3.1 and threat model
0.3.1 establish the successor credential boundary. All three legacy mint sites
explicitly retain only Contents, Pull requests and Metadata reads.

The owner reports that the existing dedicated source-reader App's additional
Issues: read permission and installation approval have been completed. This is
owner-reported configuration, not an observed effective installation/token grant.
No App credential is used during implementation, tests, CI or construction review.

This preparation introduces an independent, narrow HTTP observation oracle. It
neither imports nor executes PR #72's adapters. It is not a production review
workflow, production Reviewer Packet v2, or qualification of packet/journal
`PREPARED`. PR #71 and #72 remain separate and unchanged.

```text
OWNER_REPORTED_APP_APPROVAL=YES
EFFECTIVE_ISSUES_READ_VERIFIED=NO
LIVE_QUALIFICATION=NOT_RUN_OWNER_EXECUTION_GATE
LIVE_SOURCE_APP_READ_AUTHORITY=NOT_YET_QUALIFIED
LIVE_V3_ADAPTER_QUALIFICATION=NOT_QUALIFIED
LIVE_SOURCE_AND_SUBJECT_AUTHORITY=BLOCKED
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
V3_PRODUCTION_ACTIVATION=NO
```

## Trusted workflow and pre-credential boundary

The workflow is `.github/workflows/v3-source-app-read-qualification.yml`.
Its only event is `repository_dispatch` with type
`review-broker-v3-source-app-read-qualification`.

GitHub's [repository dispatch event contract](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#repository_dispatch)
selects the default-branch workflow, ref and current commit. The
[workflow dispatch event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
instead accepts a caller-selected branch or tag. No dispatch payload selects
execution code, source target or permission profile here.

One job requires the canonical broker repository, numeric repository ID
1433701208, default branch `dev`, exact event/action, `refs/heads/dev`, numeric
sender ID 30498238, actor and triggering actor `fanilosendrison`. All conditions
are ANDed with a nonempty owner approval variable and event-SHA equality:
`REVIEW_BROKER_V3_SOURCE_QUALIFICATION_SHA`.

Absent or unequal approval skips the entire job before runner/secret-bearing
steps. This preparation does not set that variable or request a dispatch.
Approval must name the actual resulting default-branch executable SHA, not
merely a reviewed PR head. A later default-branch commit requires fresh approval.
Default-branch writers/admins remain a broader trust domain; this is not global
repository-secret isolation or protection from a compromised authorized owner.

Before token minting, pinned checkout selects `github.sha` with persisted
credentials disabled; pinned setup-python selects Python 3.11. A credential-free
preflight confronts checked-out Git HEAD, event SHA, approved SHA, ref and event,
script existence and absence of supplied source/GitHub credential environment
variables. It does not claim the Actions runner has no platform-internal tokens.
No dependency installation or executable download occurs in the read step.

## Exact token profile and handling

The pinned official token action requests `V3_REFERENCE_SOURCE_READ`:

```yaml
owner: fanilosendrison
repositories: review-broker
permission-contents: read
permission-pull-requests: read
permission-metadata: read
permission-issues: read
```

No other permission or write grant is requested. The
[official action contract](https://github.com/actions/create-github-app-token/tree/fee1f7d63c2ff003460e3d139729b119787bc349#permission-permission-name)
otherwise permits installation-permission inheritance when inputs are omitted;
all four repository workflow mint sites are explicitly classified by tests.
Normal post-job revocation remains enabled. App registration, installation
approval, requested token permissions and observed API access are separate facts.

Only the specific subsequent qualification step receives the minted source token,
App slug and installation ID. Its `GITHUB_TOKEN` is empty. It runs only
`python scripts/qualification/v3_source_app_read.py`; there is no broker runtime,
Git clone, reviewed-source execution, journal, model or Codespace operation.
The App key never enters the script. Tokens/bodies/blobs are not retained in
artifacts, logs, packets, prompts or results; original bytes exist transiently
in memory for validation and hashing only.

## Fixed targets and observations

- Private repository: `fanilosendrison/review-broker`, numeric ID 1433701208.
- Issue 43: numeric ID 6101161202, exact Issue type/number/API URL.
- Comment 6535094733: parent Issue 51 and author ID 30498238. Its exact parent
  Issue URL is confronted and Issue 51 is read to confirm its numeric number.
- PR 71: numeric ID 5101281733, nine changed files.
- Expected HEAD: `9258617056e9d2e20cce7f05e6be71ea82dfbd23`.
- Expected base: `83b02c1b9b5bad6c6f64af76affb140957fcbd38`.
- Fixed regular file: `AGENTS.md` at that HEAD, resolved through its root tree.

The exact twelve-GET sequence is installation repositories, repository, Issue 43,
comment, Issue 51, PR, compare, PR files, Git commit, root tree, blob, then PR
again. Dynamic tree/blob paths come only from previously validated Git identities.
Installation scope must be exactly one canonical repository/ID with no pagination
ambiguity. The installation ID is trusted mint-action metadata; the listing does
not independently attest which installation issued the token.

Issue/comment body digests cover decoded JSON strings' exact UTF-8 bytes. Null,
missing or malformed bodies fail closed; mutable bodies have no fabricated
historical expected digest. Their contents never enter the receipt.

PR object/base/HEAD/repository/count are fixed and rechecked. File inventory
requires exactly nine unique safe paths and supported statuses, with no Link
header. Compare base, terminal commit, count, status and merge-base consistency
are confronted. Its merge-base SHA is an authenticated API observation, not a
local Git-ancestry proof. The oracle has no locally recomputed Git merge-base.

The commit must identify the exact HEAD/root tree. The root tree must be complete
and contain exactly one regular-file `AGENTS.md` blob entry. Strict base64 decoding
permits GitHub's LF line wrapping only; declared sizes, blob SHA and the independent
`SHA1("blob " + decimal_length + NUL + original_bytes)` must agree. Original bytes
also receive SHA-256. This single blob does not qualify all PR before/after images.
No globally atomic GitHub snapshot is claimed.

## Transport and sanitized evidence

Standard-library urllib uses only `https://api.github.com`, REST version
`2022-11-28`, GitHub JSON Accept and the dedicated Bearer token. Proxies are
disabled; redirects, non-GET methods, non-allowlisted endpoints and any pagination
Link fail closed. Responses are bounded to 1 MiB. A 10-second socket timeout and
30-second POSIX real-time alarm bound each request, including slow trickle/header
cases; the entire Actions job is additionally bounded to 15 minutes.

Transport/identity failures emit fixed markers, never API response bodies,
Authorization headers or exception text containing untrusted content. Known
credential shapes and the actual source token are screened in raw/decoded JSON,
decoded blob bytes and final receipt. This bounded screening is not proof of
absence of every possible secret format.

The only success output is one deterministic JSON record, schema version 1.0.0:
execution SHA/run/attempt/job; trusted App slug/installation ID; requested
permission names; repository identity/count; Issue/comment identities and body
digests; PR identity/base/HEAD/observed merge-base/count; commit/tree/blob identities,
mode/type/encoding/size and original-byte digest; per-boundary PASS flags; and zero
GitHub mutations, Codespace effects and model invocations. The receipt SHA-256
covers sorted, compact, ASCII JSON before adding the `receipt_sha256` field.
It is scoped evidence, not production authority or a Reviewer Packet v2.

## Offline adversarial matrix

Injected tests require no credentials and make no network calls. Boundary-specific
markers cover:

- Missing source token, malformed App/installation metadata, execution metadata
  or repository configuration.
- Wrong repository name/numeric ID/private visibility, excess/duplicate scope,
  incomplete or malformed pagination and duplicate JSON keys.
- HTTP 401/403/404, redirect, unavailable transport, oversized body, deadline,
  malformed JSON and unapproved method/endpoint.
- Wrong Issue object/number, null/missing/malformed body, comment ID/parent/author.
- Wrong immutable PR identity, HEAD/base drift, missing/inconsistent compare data.
- Incomplete/duplicate file inventory, unsafe path or unsupported status.
- Missing/duplicate tree entry, truncated tree, wrong mode/type/commit/blob,
  invalid base64, size mismatch and independently mismatched blob object ID.
- Token-shaped material in response bodies or decoded blobs, escaped token text,
  and attempts to print original Issue/comment/source content.
- Workflow owner-SHA gate removal, alternate/manual triggers, repository-scope
  removal, missing Issues read, write grants, extra mints, action-pin changes,
  preflight/job secret placement and payload-controlled authority.

The existing three legacy scope guards and admission/prearm/runtime tests remain
required. Static workflow snapshots intentionally constrain exact structure and
execution order; they are not live GitHub enforcement observations.

## Publication, independent review and next owner action

Publication requires local tests, full regression, compilation, YAML/frontmatter
checks, exact-SHA CI and fresh independent construction-review GO using
`openai-codex-1/gpt-5.6-sol`, `xhigh`, with tools disabled or read-only. The final
commit/tree, actual test count, CI URLs, exact review verdict/report digest and
merged default-branch SHA are recorded in the publication PR and Issue 69 to avoid
self-referential commit evidence. This document does not preassert a review GO.

Only after reviewed publication may the owner separately set
`REVIEW_BROKER_V3_SOURCE_QUALIFICATION_SHA` to the approved actual default-branch
SHA and authorize one repository dispatch. That authorization must identify the
fixed repository/event/sender, Issue/comment targets and exact PR 71 HEAD above;
at most one App-token mint; zero GitHub mutations, Codespace effects and inference.
This task neither sets approval nor performs that dispatch.

Future success may qualify `LIVE_SOURCE_APP_READ_AUTHORITY` only. PR #72 adapter
execution and complete subject capture remain `LIVE_V3_ADAPTER_QUALIFICATION=
NOT_QUALIFIED` until separately reviewed and exercised. No requester authority,
packet/journal lifecycle, retention, model execution or production activation is
established by these reads. Issue 69 remains open and incomplete.
