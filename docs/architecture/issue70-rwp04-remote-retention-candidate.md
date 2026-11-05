---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "design-proposal"
domain: "independent-review"
severity: "draft"
name: "Issue 70 RWP-04 Remote Retention Candidate"
version: "0.1.0"
---

# Issue 70 RWP-04 — Remote retention candidate

## Status and exact base

This experimental candidate records the owner-selected RWP-04 design. It does
not adopt a normative v3 contract or authorize operational execution.
The base is PR #87, SHA `65e38e3546fc92d99880eb315729c13c95590f65`, tree
`29b2a85da15bbdcfbf9dd4b20e3af276c49325ff`. RWP-01/02/03 acceptance applies
to that exact historical candidate, not to this successor.

## Authority and responsibilities

`remote_prepared_receipt_v3.py` owns the closed pure remote receipt, canonical
bytes followed by one LF, identity, and links. The original offline receipt is
computed from authenticated ADMITTED A, the verified manifest and the unchanged
ordered retained inventory before upload. Neither receipt is inserted into the
packet or archive.

`github_prepared_artifact_v3.py` owns authenticated metadata observations and
exact remote ZIP download through explicitly injected transports. Separate
responsibilities own strict budgets, complete scoped pagination, the historical
Actions attempt reader, and bounded private ZIP extraction. No fallback network
transport or invented REST upload endpoint exists. The upload boundary represents
the official Actions artifact mechanism; its actual operational connection is
not qualified here. Retention targets 30 days, bounded by observed expiration.

`prepared_packet_readback_v3.py` authenticates PREPARED P and its exact parent A
using existing journal origin authorities and Git reads. Canonical transition
bytes come from the existing transition function. A closed historical policy
verification context checks original source and selection authority, keeping the
selection bound to A, not P. It offers no permission to capture, select, build,
persist, upload or mutate. Cold reconstruction uses loaders and the real Packet
v2 verifier, never the packet builder or archive-owned assertions as trust roots.

`pre_model_remote_retention_v3.py` owns one active continuation from an attributed
RWP-03 handoff. It derives the retained path from the claim, reverifies all bytes,
authorities and inventory, computes the offline receipt, uploads once, observes
and downloads the archive, reconstructs the packet, computes the remote receipt,
and supplies a narrowly bound remote authority to the existing PREPARED CAS.
Actual internal reads, writes, archive steps, transport calls and the CAS request
are guarded against journal movement. These checks are not a cross-service
transaction and cannot cancel an already launched effect.

## Remote receipt

The only top-level fields are `schema_version`, `evidence_type`,
`offline_preparation_receipt_id` and `storage`. Schema version is integer 1;
the evidence type is `remote-v3-prepared-packet-binding`. Storage contains exactly
backend, repository, repository_id, workflow_run_id, workflow_run_attempt,
workflow_id, workflow_path, execution_ref, executable_sha,
verified_worker_job_id, artifact_id, artifact_name, artifact_digest,
artifact_size_in_bytes, created_at and expires_at. Backend is
`github-actions-artifact`, attempt is integer 1, workflow path is
`.github/workflows/v3-pre-model-worker.yml`. Numeric JSON values are exact
positive integers no greater than 9007199254740991. Artifact and job IDs are
canonical positive decimal strings, converted directly from integer API values.
Timestamp strings are authenticated, parsed and ordered without rewriting.
Availability is checked separately against current time and expiration.

The name is `rb-v3-prepared-<claim-digest>-<run-id>-<run-attempt>`.
The receipt excludes its own identity, P's SHA, signed URLs, credentials,
observation times, mutable job status and conclusions. Its identity is
`artifact_identity(canonical_bytes(receipt) + LF)`. A metadata change cannot
silently create a replacement historical commitment.

## Historical Worker observation

The original ACK and binding in authenticated A remain the durable authorities.
The old binding observation's timestamped preimage is not reconstructible and
is never claimed to be reconstructed. A separate reader observes the exact
`/actions/runs/{run_id}/attempts/{attempt_number}` and its complete jobs listing,
not latest. Exactly one approved Worker job must match workflow and executable.
Active preparation additionally confronts the independently authenticated runtime
job. The job ID does not attest that this job uploaded the artifact. Upload
permission originates exclusively from the active continuation.

## Transport and archive boundaries

Each adapter requires explicit positive budgets for archive bytes, uncompressed
bytes, members, metadata pages and metadata response bytes. Packet prompt limits
are unchanged and are not reused for transport objects. Complete listings reject
scope drift, invalid links, count disagreement, duplicate IDs or multiple names.
A complete final page may contain only first/previous links.

The authenticated GitHub download-resolution request and the HTTPS storage
request are separate. Only a validated redirect from that response can select a
storage destination. GitHub Authorization and cookies never cross this boundary.
Signed URLs are neither durable evidence nor diagnostic output. ZIP digest and
length are checked over exact streamed remote bytes, not recompressed content.

Extraction creates a fresh private root, directories at 0700 and files at 0600
before data writes. It rejects ambiguous names, traversal, backslashes,
symlinks, special members, duplicates and file/directory collisions. Advertised
and actual byte budgets both apply. Only packet/ and evidence/ are allowed;
complete packet/inventory verification closes their members. Structural empty
`evidence/admitted-references/` is restored when required; no absent file is
fabricated. Retained content is never executed.

## One-shot effects and uncertainty

Upload is one logical operation, without overwrite or cleanup. ACK, established
refusal and unknown outcome remain distinct. Lost responses may be reconciled
by bounded reads during the same still-authorized continuation; no second upload
is permitted. If no PREPARED CAS has been emitted, the original CAS can follow
successful exact-object reconstruction. After CAS emission, reconciliation is
read-only; matching PREPARED bytes without recognized write attribution do not
establish this operation's COMMITTED outcome. Orphan artifacts are not deleted.
A new process is an observer even when it reads ADMITTED.

After confirmed PREPARED, retention loss leaves the journal COMMITTED/PREPARED
and reports remote reconstruction UNAVAILABLE. It never recaptures sources,
changes policy selection, replaces artifacts, rewinds the journal or dispatches
another Worker. Journal outcome, retention availability and decision reason are
separate result dimensions.

## Qualification and exclusions

Required evidence includes Q01–Q24 of the owner mandate: independent original
identity oracles, four-reference and empty-reference paths, schema/identity
falsifications, complete pagination, exact-attempt observation, safe redirect,
ZIP byte and extraction adversaries, each budget, independent authority loss,
downgrade rejection, internal freshness races, historical parent/write faults,
active/historical separation, upload/CAS crash ambiguity, observer-only restart,
post-commit availability loss, immutable snapshots and v1/v2/RWP regressions.
Cold verification is a distinct interpreter without producer state; Linux
reconstruction retains the existing effective seccomp network boundary. Simulated
download and observation authentication occur outside that isolated process.

Qualification remains offline only. Actual Worker dispatch, source acquisition,
artifact upload, operational journal mutation, Codespace, ARMED, broker model
inference, ReviewResult, generation 2, BLOCKED/RWP-05 implementation, production
activation, normative adoption, merge, Issue closure and changes to #83 are
excluded. Construction-review and governed-publisher model calls are not broker
reviewer invocations. Final CI and independent review qualify only their exact
source tree; publication as draft is not acceptance.
