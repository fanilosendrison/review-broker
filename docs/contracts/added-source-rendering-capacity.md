---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "Added-source rendering and pre-arm input capacity"
version: "0.1.0"
---

# Added-source rendering and pre-arm input capacity

## Responsibility and authority

This implementation realizes the owner-approved Issue #83 design. It changes
packet presentation and trusted pre-arm checks, not Product Intent, request
semantics, reviewer policy, source authority or historical review outcomes.
Request, mission, subject and reviewer identities remain separate from a new
packet identity. No offline construction result is a reviewer verdict.

## Rendering selection

`added-source-images-v1` is an explicit `rendering_format` member in the packet
identity basis. New GitHub PR preparation selects it only for exclusively added
canonical changes with complete, one-to-one source coverage. Every change has
`status=added`, null `before_source_id` and `previous_path`, and exactly one
unique after image at the exact head/path. No image or changed path is missing
or reused. Source repositories agree. Git's actual raw tree delta with copy and
rename heuristics disabled independently supplies the exact added modes.

Modified, removed, copied, renamed, unsupported and mixed canonical change
sets do not select this mode. Their legacy rendering remains unchanged. An
unavailable image, encoding, scope or proof fails closed; it is not silently
summarized or admitted as complete.

The new prompt retains the full mission, mandatory profile instructions,
reviewer output contract, subject/request/packet identities, exact ordered change
metadata and image IDs, added modes, retained diff digest and byte length. It
explicitly declares that the full diff is retained in `changes.patch` but not
redundantly rendered. Each complete image is rendered once with its existing
physical-line anchors. Source snapshots, Git OIDs, SHA-256, encoding and physical
line mappings remain unchanged. The entire original diff remains unchanged.

Git may encode added paths as similarity copies from unchanged base paths even
when the canonical API change set and unheuristic tree delta are entirely added.
That does not turn a canonical `copied` change into an addition. The verifier
uses Git's standard index and patch operations: seed exact after-image objects
and modes, reconstruct the after index from the reverse patch, derive copy
context by reversal, remove canonical added paths from that context, then apply
the original patch forwards. The final index must equal the unchanged derived
context plus exactly the declared after images/modes. This validates byte and
mode correspondence without another source image, a checkout, source execution,
ambient Git configuration or credential propagation. Derived context is proof
material, not newly authenticated historical source evidence.

## Historical compatibility

A manifest without `rendering_format` is verified by the exact legacy renderer
and identity basis. A new marker is never inferred for historical bytes. Unknown
or null-present markers fail closed. Removing the marker or modes from a new
packet cannot preserve its identity. The raw diff digest/length and modes are
bound alongside the explicit new marker.

PREPARED recovery reconstructs candidate presentations offline and selects only
the exact immutable manifest evidence already in the journal. It does not
upgrade a prepared packet to a new rendering. No matching reconstruction means
`PREPARED_PACKET_EVIDENCE_MISMATCH`, never a rewritten claim.

## Pinned capacity policy

The observed Codex 0.164.0 turn-input limit is 1,048,576 characters. The
qualification policy is `codex-0.164.0-turn-input-v1`; it does not automatically
follow a future runtime upgrade. The exact final UTF-8 `input.txt` is measured
as Unicode scalar characters, UTF-16 code units and UTF-8 bytes, with SHA-256.
Invalid UTF-8 and surrogate encodings fail closed.

Because the transport's treatment of all non-ASCII inputs is not independently
established, `utf8-bytes-conservative-upper-bound-v1` enforces the maximum of
those three counts. For valid Unicode this is the UTF-8 byte count. It cannot
undercount any of the three representations; it may reject an input below a
scalar-character limit. This is deliberately conservative, not a claim of
provider attestation, effective model identity or a live non-ASCII boundary
qualification. ASCII at exactly the limit passes; one unit over fails.

## Pre-model rejection and armament

The workflow assesses capacity after prepared-packet preservation and before
Codespace lifecycle or any reviewer process. A canonical receipt binds request,
attempt, packet, input hash, executing broker SHA, counts and pinned policy.
The journal records it as immutable same-state `input_capacity` metadata on
PREPARED, with a canonical evidence identity. Historical records without this
member serialize exactly as before; no new null member is added.

A rejection remains PREPARED with `invocation_count=0`. It is explicitly
`REJECTED`, not model-capable INDETERMINATE, a successful review, or a new
journal state. Preparation and scheduling return `BLOCKED_INPUT_CAPACITY`.
Neither manual generic arm transitions nor automatic recovery bypass a recorded
rejection. Contradictory capacity/state/count metadata fails journal decoding
and recovery explicitly; it cannot conceal ARMED/STOPPED cleanup anomalies as
a pre-model block. No new attempt or automatic dispatch is allocated.

`internal-arm` requires the packet directory and executing broker SHA. It
reconstructs and coherently rereads the exact input, verifies the original
PREPARED manifest evidence, and binds the observation idempotently. It repeats
the observation after journal I/O immediately before durable ARM. Generic
`internal-transition --state ARMED` is forbidden. The existing legal state map
and at-most-once reservation/counting boundary otherwise remain unchanged.

The final adapter verifies the packet and positive capacity receipt again and
transmits the checked immutable bytes in memory, not a subsequently reopened
input pathname. Substitution detected before final snapshot acceptance is refused without
reviewer transport. A later filesystem change cannot substitute different bytes
into that memory snapshot; existing post-invocation checks still detect changed
input, even when transport of the original verified bytes has already occurred.
These bounded observations are not a hostile-host filesystem lock or a claim
that all future path states were observed. An already ARMED reservation is never
reset after a later execution-boundary failure.

## Operational separation

No new receipt activates production admission. Comprehensive and bounded
security checks, credential screening, immutable runtime verification,
publication attribution and observed Shutdown remain required. Old receipt
validation does not newly require capacity fields; new construction emits them,
and current armament enforces capacity independently of historical receipts.

A rendering change is not a subject-head change. It never authorizes another
invocation under a consumed request. Any future same-head or changed-head review
requires its own explicitly authorized v2 operation and applicable admission.
The original #82 INDETERMINATE/STOPPED attempt remains immutable.
