---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-procedure"
domain: "independent-review"
severity: "strict"
name: "Qualification Evidence Minimization and Admission"
version: "0.1.0"
---

# Qualification evidence minimization and admission

## Responsibility and limits

Apply this operator procedure before retaining provider-derived evidence or
supplying it to a construction reviewer. Keep it separate from runtime source
credential handling. The operator-only `scripts/qualification-evidence.py` is
not imported by the broker, does not grant effect authority and does not modify
Controller, Worker, journal or Artifact behavior.

Treat a clean scan as a bounded pattern check, not universal secret detection.
Do not use it to justify retaining unnecessary data. Never archive an entire
external object merely because its current fields appear harmless.

## Project before persistence

Select only the exact fields needed by the gate. Use maintained jq projections,
not a second custom provider-object format. Receive the raw provider response
only in ephemeral process memory or a pipe. Do not tee it to disk or print it.

For repository identity, select only needed ID, full name, node ID, visibility,
default branch or exact object identities. For Actions, select needed workflow,
run, job, attempt, actor, state, conclusion and timestamp fields. Do not copy
arbitrary nested repository objects from run or PR responses.

For the initial-history query retain only repository databaseId/nameWithOwner,
refs totalCount, nodes name/target oid/typename, and pageInfo. Retain only
ref/object sha/type for the independent REST inventory. Preserve every page and
reconfront complete inventories; projection does not excuse incomplete reads.

Pass an explicit object/array jq filter to the evidence admission tool:

```sh
gh api repos/OWNER/REPOSITORY --jq '{id,full_name}' |
  python scripts/qualification-evidence.py project \
    --filter '{id,full_name}' --output repository-identity.json
```

Use an existing private evidence directory. The tool checks the projection before
opening an exclusive mode-0600 output; it refuses overwriting earlier evidence.
Keep raw inputs, credential values and external-program error text out of error
messages. The CLI requires jq and Python; it performs no network operation.

## Structured-field and text admission

Reject nonempty case-insensitive credential-like fields, including token,
authorization, password, private-key, secret, cookie and credential forms.
Normalize separators only for field-name classification, never provider
identities. Allow only the two explicitly typed nonnegative integer counters
SOURCE_APP_TOKEN_MINTS and token_mint_count. Do not infer that another field is
safe merely because its name includes count. Allow empty fields and the exact
sanitized markers documented by the tool, never a credential-bearing value.

Generate logs and reviewer input from projected evidence. Check JSON, nested
serialized JSON, quoted structured fragments and Authorization header forms
before admission. Scan each final log, reviewer input and reviewer trace:

```sh
python scripts/qualification-evidence.py scan \
  repository-identity.json review-input.txt reviewer-trace.jsonl
```

Keep unadmitted command/reviewer output in private staging outside the admitted
corpus. Do not provide staged unsafe material to a reviewer. If any scan refuses,
mark evidence hygiene FAIL and stop archive admission. A reviewer GO does not
supersede this gate. Produce an explicitly sanitized derivative and a non-secret
incident receipt before admitting anything from an unsafe trace. Never silently
replace history or claim byte-exact retention of unsafe originals.

## Historical incident handling

Preserve the Issue70 STOP and its independent NO_GO as historical facts. Record
only already-known unsafe file identifiers, original file hashes, sanitized
hashes, redaction counts, field names, reason and historical trace identifier.
Do not retrieve, print, validate, compare or reuse the former temp_clone_token.
Do not include unsafe original response/trace bytes in a new reviewer corpus or
archive. If such originals remain, quarantine them outside the retained corpus
without reading their credential contents; record the intentional omission.

Classify this incident as QUALIFICATION_EVIDENCE_CREDENTIAL_RETENTION. Record
BROKER_RUNTIME_CREDENTIAL_LEAK=NOT_ESTABLISHED and provider-side revocation and
retention as NOT_ATTESTED. The historical preflight minted zero source-App
credentials; do not relabel the incidental provider value as source token A/B,
GITHUB_TOKEN or the source-App private key. Local sanitization neither revokes a
provider credential nor erases material already received by a reviewer provider.

## Archive and reviewer boundary

Give the reviewer only sanitized projections, exact source/diff/tests, qualified
CI output and the non-secret incident receipt. Do not give it historical raw
corpora, credentials or credential-store access. Restrict tools to read, grep,
find and ls in a new session with the owner-selected model configuration.

After completion, scan the trace before copying it into the admitted corpus.
Record source and evidence digests, scanner outcome, reviewer configuration and
retained trace digest. Build the private archive only from admitted files and
verify its member bytes. Report archive path, file count, byte length and digest;
do not publish raw private logs or provider responses to Issues.
