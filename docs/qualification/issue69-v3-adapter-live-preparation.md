---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Issue 69 Real V3 Adapter Preparation"
version: "0.2.0"
---

# Issue 69 Real V3 Adapter Preparation

## Status and immutable subjects

This preparation provides an owner-gated controller and offline integration
verification. It does not establish live adapter qualification, requester
admission, Reviewer Packet readiness, or production v3 activation. Publication,
exact-SHA CI, independent review, and merge are separate acceptance gates.

- Starting dev: `e037db2cd2e32002b94586c560309d30fe634bff`.
- Unmodified, open draft PR 72: `e65e4db932cb59d7a0fcfbd442ba19e548fc141d`.
- Experimental tree: `420a18d006e421e197d23b8e93681376fbabc2db`.
- Dependencies: Python 3.11, jsonschema 4.26.0 and rfc8785 0.1.4.
- Existing source-App read run: `41361467061`, successful and not repeated.
- Existing read receipt:
  `2ac93f314c22b4b8a0aa4fa99f0b27dc1f98537b1fa7e95e2557401dfd6088b3`.
- Historical failed run `41359825355` remains a separate, unchanged fact.

The preserved extracted snapshot was compared with all 250 Git blobs of the
corrected tree, including the eight tracked symbolic links. It is not itself a
Git repository. Offline controller tests create separate detached temporary
checkouts from that same immutable commit; no existing branch is changed.

## Historical provenance finding and correction

The initial preparation stopped when both reference readers accepted a
substituted source-authorization evidence ID in non-qualification mode. Git-file,
Issue body and comment observations propagated that ID while claiming
`AUTHENTICATED_READ_ONLY`. The positive controls passed; three negative subtests
failed. The source authority was concrete, HTTP fixtures were injected, and no
live credential or source acquisition was involved.

The historical negative result was:

```text
rejected=False
qualification=AUTHENTICATED_READ_ONLY
bound_to_actual_authorization=False
propagated_supplied_identity=True
```

A separate correction on PR 72 now binds each emitted ID to the actual concrete
source authority's authorization. A subsequent string-subclass counterexample
required exact built-in string validation and emission of the locally captured,
verified immutable ID instead of rereading a mutable caller field. The original
failures are not retrospectively relabeled PASS.

The corrected SHA/tree above passed 787 tests and a fresh independent
`openai-codex-1/gpt-5.6-sol`, xhigh construction-review GO. The durable history is
[Issue 69's correction record][correction]. That prior review qualifies its exact
experimental correction, not this preparation or live adapter execution.

The two original harness test methods remain intact. Their positive controls
and substituted-ID rejection now pass against the corrected tree.

## Controller responsibility

The controller orchestrates the existing PR 72 implementations; it does not
implement a replacement source engine or invent a ReviewRequest. It verifies the
detached candidate SHA/tree, clean tracked bytes and safe symbolic links, pinned
dependency versions, and every imported `review_broker` module's candidate origin.

The actual source authority observes the singleton repository and supplies its
authorization. The actual PR observer checks PR 71, base, HEAD and complete file
inventory. The actual authenticated capture acquires Git objects without checking
out or executing reviewed source, validates merge-base and images, and obtains
the binary diff. Controller checks compare returned records and diff with local
Git, then finalize the PR observation and bind authenticated capture provenance.

The actual Git-file reader reads `AGENTS.md`; the actual Issue reader reads
Issue 43 and comment `6535094733` on Issue 51. Their repository, installation,
authorization, object identities, original-byte digests and canonical observation
evidence IDs are checked before reporting success. The fixed parent Issue ID is
`6106789428`; comment author ID is `30498238`.

The receipt contains curated metadata, evidence IDs, byte counts and hashes, not
source bodies, diff text, credentials or authorization headers. Its own digest
covers canonical receipt bytes before adding `receipt_sha256`. Failures emit only
a fixed incomplete marker at the CLI boundary. Private temporary capture storage
is removed on success and exception. The receipt is not a production packet.

## Offline verification

The tests use real candidate classes, injected GET responses and local temporary
Git repositories. Only the acquisition boundary is redirected to local Git. The
live entry point supplies no injection and retains the candidate's default
`gh` clone/fetch path. No network API or production credential is used by tests.

Coverage includes candidate SHA/tree and import origin; source repository,
installation and token identity; substituted and subclass provenance; PR number,
ID, initial/final HEAD and base; incomplete inventories; merge-base; exact
preimages/postimages, blob hashes and binary diff; Git-file and Issue/comment
reads; missing references, malformed bodies and ambiguous API results; coherent
sanitized receipt and cleanup after failure. Post-return corruption injections
explicitly test controller rejection, not defects attributed to PR 72.

Observed local results:

- Harness module: 7 test methods PASS, including positive and negative subcases.
- Credential-scope module: 16 tests PASS; exactly five classified mint sites.
- Dev regression: 518 tests PASS with the worktree's `src` on `PYTHONPATH`.
- Corrected PR 72 applicable adapter/provenance suites: 68 tests PASS, separately
  from dev. The historical 787-test result is not claimed as a new full run.

An initial dev discovery command without package-path setup failed with import
errors (`ModuleNotFoundError: review_broker`). The configured run passed; the
initial result is retained in local validation logs, not described as PASS.
The intermediate unclassified-fifth-site RED was repaired in the permitted guard.

These are offline functional results, not observations of effective live token
permissions, remote Git acquisition, an atomic GitHub snapshot, or requester
admission. Installation identity remains trusted mint context; the repository
listing does not independently attest it.

## Workflow and credential boundary

The only event is `repository_dispatch`, action
`review-broker-v3-source-adapter-qualification`. The job requires the canonical
repository and numeric ID, default branch `dev`, exact ref/event/action, sender
ID `30498238`, actor and triggering actor `fanilosendrison`, App ID `5529772`, and
nonempty `REVIEW_BROKER_V3_ADAPTER_QUALIFICATION_SHA` equal to the execution SHA.
No `client_payload` value selects executable code or authority.

Pinned checkout actions prepare the trusted execution SHA and exact experimental
commit. Tree verification, dependency preparation and credential-free import
preflight occur before the pinned token action receives the App key. The token
requests exactly Contents, Pull requests, Metadata and Issues read, restricted
to repository `review-broker`. Only the controller step receives its output.
Normal action post-job token revocation is retained.

Three legacy mint sites retain their exact three-read profile. The existing
App-read workflow and its guard hash are unchanged. A distinct full-file hash
guards the new adapter workflow. Static inventory rejects unexpected mint sites,
extra permissions, changed input serialization and unclassified consumers.
These checks do not establish platform-wide secret isolation.

## Publication and future owner gate

The preparation PR targets dev and must pass CI and fresh independent review at
its exact published SHA before normal merge. PR 71 and PR 72 remain unchanged;
Issue 69 remains open. The eventual accepted dev SHA, not a mutable branch or a
pre-merge candidate SHA, must receive separate owner authorization.

`REVIEW_BROKER_V3_ADAPTER_QUALIFICATION_SHA` has not been created or set by this
preparation. No new dispatch, App token, GitHub permission change, journal
mutation, Codespace operation, Review Broker invocation or model inference has
occurred. The successful earlier App-read run is not repeated or conflated with
adapter qualification.

The next owner gate is approval of the exact final dev SHA for one separately
bounded, read-only adapter qualification. Publication alone does not authorize
that execution or activate v3.

```text
LIVE_SOURCE_APP_READ_AUTHORITY=PASS
LIVE_V3_ADAPTER_QUALIFICATION=NOT_RUN
LIVE_SOURCE_AND_SUBJECT_AUTHORITY=BLOCKED
LIVE_REQUESTER_AUTHORITY=NOT_QUALIFIED
NEW_DISPATCH_COUNT=0
SOURCE_APP_TOKEN_MINT_COUNT=0
GITHUB_JOURNAL_MUTATIONS=0
CODESPACE_EFFECTS=0
REVIEW_BROKER_MODEL_INVOCATIONS=0
V3_PRODUCTION_ACTIVATION=NO
ISSUE69_CLOSED=NO
```

[correction]: https://github.com/fanilosendrison/review-broker/issues/69#issuecomment-6566591457
