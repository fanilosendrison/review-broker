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
validation.json
```

A missing final response is represented by an empty captured artifact and an
invalid or indeterminate validation outcome, not a manufactured response.
Artifacts remain outside the reviewed repository.

## Validation boundary

Validation checks exact request, subject, packet, and prompt identities; prompt
before/after equality; one started and one completed terminal sequence; absence
of failure events; final-message equality; ReviewerFindings v1 schema; complete
source IDs; valid line numbers; and exact quote substrings.

Credential-shaped material invalidates publication handling and requires
incident review. Credential values are never included in validation output.

Anchoring proves only that the quote exists on the identified physical line. It
does not validate the finding's logic, completeness, materiality, or verdict.
