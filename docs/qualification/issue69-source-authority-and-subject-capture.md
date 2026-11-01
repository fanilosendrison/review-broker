---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Issue 69 Source Authority and Subject Capture Qualification"
version: "0.1.0"
---

# Issue 69 Source Authority and Subject Capture Qualification

## Status

The exact baseline is `83b02c1b9b5bad6c6f64af76affb140957fcbd38`.
The implementation commit and tree are the Git objects containing this record;
their exact identities are published in the dedicated draft PR and Issue #69 report.

The production-compatible implementation and injected offline qualification are
complete. The credential-bearing stage was not run and is blocked because the
accepted private-source authorization permits Contents, Pull requests, and
Metadata reads but explicitly excludes Issues access. No App permission,
installation, secret, variable, or token was changed or exercised.

`LIVE_SOURCE_APP_PERMISSION=BLOCKED_OWNER_APPROVAL`
`LIVE_SOURCE_AND_SUBJECT_AUTHORITY=BLOCKED`

## Reused and new boundaries

The implementation reuses the fixed-origin bounded HTTP executor, v3 origin and
reference readers, preclaim authority interfaces, `GitSourceReader`,
`SourceRecord`, `SourceSpec`, packet-v2 construction, and existing change-scope
proof. New modules have one responsibility each:

- `github_source_authority_v3.py` observes complete installation-token repository
  scope and emits the existing source authorization receipt.
- `github_requester_authority_v3.py` binds one trusted numeric requester, broker
  Issue, and authenticated origin evidence.
- `github_pull_request_observation_v3.py` observes exact repository, PR,
  comparison, and complete changed-file identities.
- `github_subject_capture_v3.py` acquires bounded Git history and constructs exact
  authenticated before/after images and diff evidence.

Source authorization uses the documented
`GET /installation/repositories?per_page=100&page=N` endpoint. The trusted mint
boundary supplies App slug, installation ID, approved permissions, selected
repository, and the token. The API observation establishes the repositories
visible to that exercised token; it does not cryptographically attest the
installation ID. The credential-free scope evidence and the existing canonical
`SourceRepositoryAuthorizationV3` receipt remain distinct.

Requester authorization is separate from source read access. It requires exact
numeric requester and broker-Issue identities, exact origin evidence, and an
explicit trusted authorization decision. Login text and successful repository
access grant no requester authority.

## Permission and credential boundary

The offline authority requires `contents:read`, `pull_requests:read`,
`metadata:read`, and `issues:read` in trusted mint metadata. This validates the
adapter's fail-closed permission contract, not the installed App's effective
permissions. Effective Issues access remains unestablished.

The candidate manual workflow is `workflow_dispatch` only, requests exact
repository-scoped read permissions through the pinned official App-token action,
and requires an owner-protected environment plus an independently reviewed
exact SHA. It intentionally has no successful live qualification entry point in
this draft and was not dispatched.

Git acquisition uses an isolated HOME/config, no ambient publication,
Codespaces, or reviewer credential, no token-bearing remote URL, no checkout,
and no reviewed-code execution. `GIT_NO_REPLACE_OBJECTS=1`, disabled system and
global config, bounded subprocess time, filtered object transfer, and bounded
history deepening are preserved. Tests confront packet, prompt, Git config, and
sanitized failures for token absence.

## PR observation and Git proof

The observation performs repository reads before and after the PR scope,
requires canonical name and numeric ID, exact PR number and immutable object ID,
pinned HEAD, observed base, compare-base consistency, compare terminal HEAD,
and merge-base identity. Changed files are paged at 100 entries and confronted
with `changed_files`; duplicate, malformed, unsafe, truncated, capped, or
unsupported inventories fail closed. GitHub `patch` text is not authoritative.

A real temporary Git graph has a nontrivial divergence: the observed base and
HEAD share an earlier merge base. Local Git independently recomputes that merge
base, canonical name-status inventory, changed path set, exact binary diff,
blob OIDs, original bytes, SHA-256 digests, and physical lines. Required
preimages and postimages follow status semantics. A final authenticated PR read
rejects repository, PR, base, or HEAD drift.

No globally atomic GitHub snapshot is claimed. The evidence identifies the
exact observations and Git objects captured.

## Packet provenance

Authenticated captures use `AUTHENTICATED_SOURCE_READ_ONLY`; synthetic captures
retain `SYNTHETIC_OFFLINE_VERIFIED` with unchanged identity bases. The
authenticated capture evidence additionally binds source-authorization and PR-
observation evidence. Packet validation confronts both against the canonical
admission. A forged label, missing evidence, or mismatched receipt fails.

The packet technical-policy qualification remains
`SYNTHETIC_OFFLINE_ONLY`. Authenticated source bytes therefore do not promote
runtime policy, reviewer execution, ReviewResult, or production readiness.

## Scenario matrix

| Scenario | Status | Boundary exercised |
| -------- | ------ | ------------------ |
| I69-N01–N03 | PASS | Trusted mint scope, source receipt, and requester authorization. |
| I69-N04–N05 | PASS | Exact PR identity and complete paginated file inventory. |
| I69-N06–N08 | PASS | Real divergent Git graph, merge base, images, diff, and capture evidence. |
| I69-N09 | PASS | Authenticated packet provenance with synthetic technical policy. |
| I69-N10 | PASS | Existing synthetic packet behavior remains distinct. |
| I69-F01–F06 | PASS | Repository, installation, selection, pagination, and unavailable authority reject. |
| I69-F07–F10 | PASS | Requester, permission, and qualification-token confusion reject. |
| I69-F11–F15 | PASS | PR object, drift, compare, pagination, duplicate, and malformed scope reject. |
| I69-F16–F22 | PASS | Unsafe/type, ancestry, merge-base, image, object, diff, and size failures reject. |
| I69-F23–F28 | PASS | Ambiguity, role confusion, forged provenance, credential escape, and policy inflation reject. |
| I69-F29 | PASS | Synthetic packet and historical compatibility remain unchanged. |
| I69-F30 | PASS | Injected GitHub operations remain read-only; no model-capable effect exists. |
| Effective source-App Issues permission | BLOCKED | Separate owner approval and installation upgrade required. |
| Same-token live Issue/comment read | BLOCKED | Depends on approved effective Issues permission. |
| Live PR #71 qualification | BLOCKED | Depends on owner gate and reviewed default-branch workflow. |

## Validation and limitations

The draft PR records exact focused commands, complete regression result,
independent-review provenance, and exact-SHA CI. PR #68's test modules are not
present in the mandated independent PR #66 baseline and cannot be executed
without improperly stacking PR #71; compatibility is instead checked through
the unchanged synthetic packet suites and PR #71 remains an independent
integration prerequisite for #70.

The qualification does not establish effective production App permission,
production token behavior, live private-source access, workflow/run identity,
journal mutation authority, packet retention, trusted technical policy,
Codespace isolation, inference, ReviewResult publication, or production v3
activation.

## Required owner action

The owner must separately approve `Issues: read` for the dedicated source App,
approve the installation permission upgrade for only the selected repository,
and authorize one exact reviewed default-branch `workflow_dispatch` SHA against
PR #71 at `9258617056e9d2e20cce7f05e6be71ea82dfbd23`. Until then, #69 remains open
and #70 cannot treat live source authority as satisfied.
