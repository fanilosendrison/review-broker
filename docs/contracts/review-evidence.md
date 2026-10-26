---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "contract"
domain: "independent-review"
severity: "strict"
name: "Review Evidence v1 Contract"
version: "0.1.0"
---

# Review Evidence v1 Contract

## Source packet

Each packet source records repository, exact commit, path, Git blob OID,
SHA-256 of original bytes, original byte length, declared encoding, snapshot
path, and physical line mapping. The source snapshot stores unchanged bytes.
No truncation is permitted.

Line mapping records byte start, content start, content end, line end, and the
physical ending `LF`, `CRLF`, `CR`, or `NONE`. A UTF-8 byte-order mark remains in
the snapshot and hash but is excluded from first-line citation text under the
declared `utf-8-sig` encoding.

The review prompt renders decoded line content with stable `L000001|` prefixes.
CRLF and other physical endings are not inserted into rendered line text.
Citation validation checks the rendered physical line while packet validation
checks the untouched original bytes and mapping. This distinction permits CRLF
review without source normalization.

## Attempt artifacts

Every attempted invocation preserves:

```text
attempt.json
input-manifest.json
prompt.sha256
codex-events.jsonl
codex-stderr.txt
codex-final.json
codex-exit-code.txt
input-before.sha256
input-after.sha256
reviewer-security-probe.json
validation.json
```

`attempt.json` binds the exact trusted broker wheel SHA-256 used by the remote
process. `reviewer-security-probe.json` binds the exact permission-profile
SHA-256 to controlled non-secret filesystem, environment, write, and network
observations. A missing or mismatched identity invalidates the evidence; a
passing producer receipt does not replace independent security review.

Attempted recovery writes `recovery-manifest.json` with a success or sanitized
failure record for every required runtime artifact. Partial recovery is
preserved but is not terminal evidence. `terminal-capture.json` binds exact
artifact hashes only after required files, attempt and packet identities, and a
single started-plus-terminal event sequence are established.

Cleanup writes either `shutdown-observation.json` or
`shutdown-incident.json`. Only the observation receipt can support `STOPPED`;
it binds actual `Shutdown`, Codespace identity, request identity, attempt
identity, observation time, and workflow context.

A missing final response is represented by an empty captured artifact and an
invalid or indeterminate validation outcome, not a manufactured response.
Artifacts remain outside the reviewed repository.

## Validation boundary

Validation checks exact request, subject, packet, broker-wheel, and prompt
identities; prompt before/after equality; one started event and one
non-contradictory terminal event; absence of failure events for a completed
execution; final-message equality; ReviewerFindings v1 schema; complete
source IDs; valid line numbers; and exact quote substrings.

Credential-shaped material invalidates publication handling and requires
incident review. Credential values are never included in validation output.

Anchoring proves only that the quote exists on the identified physical line. It
does not validate the finding's logic, completeness, materiality, or verdict.
