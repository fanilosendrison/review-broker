---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "strict"
name: "Issue70 Initial-History Provider Conformance Correction"
version: "0.1.0"
---

# Issue70 initial-history provider conformance correction

## Historical boundary

The [historical STOP](https://github.com/fanilosendrison/review-broker/issues/70#issuecomment-6708310164)
remains STOPPED / INITIAL_HISTORY_REF_INVALID / live PREPARED BLOCKED / review
NO_GO on candidate 215d00be6d6c7e354e4dc40b6d65009b0b041bd1. It created no
ReviewRequest Issue, temporary gate, dispatch, source mint, claim, journal write
or Artifact. No runtime attempt was consumed; no automatic resumption follows.

The correction and the operator evidence incident are distinct non-normative
findings. Neither changes a product contract or historical qualification.

## Provider-conformance discovery

Statement: the old initial-history adapter rejects GitHub's real deep-refPrefix
relative node names. Before source correction, independent read-only GraphQL and
REST observations agreed on ten complete qualification ref/OID pairs. The first
GraphQL name was qualification-20261030T200256Z-513925f0bf09, without the queried
refs/heads/review-claims-v3/ prefix. Both provider-shaped acceptance tests then
reproduced INITIAL_HISTORY_REF_INVALID on the unchanged source; their RED log is
retained privately.

Authority: the owner correction mandate requires interpreting names relative to
one exact query namespace while preserving complete, twice-confronted history.
Disposition: no-normative-impact. Affected layers: implementation/provider
conformance and qualification evidence. Required authority for this correction
is supplied by that mandate, not by the failed live observation alone.

The sole runtime-source change is github_initial_history_v3.py. Its one
INITIAL_CLAIM_NAMESPACE constant supplies the query, reconstruction, namespace
check and exact 64-hex claim filter. Safe relative names are appended to the
whole namespace, never to refs/heads/ separately. Full refs and ambiguous or
Git-invalid relative names fail closed without shell/Git validation or alternate
representation heuristics. Qualification refs remain in inventory and drift
comparison, but only exact direct 64-hex claims are decoded for intent history.
Repository identity, Commit/OID checks, pagination/count, duplicate rejection,
100-page budget and second-inventory confrontation remain required.

## Evidence-handling discovery

Statement: an earlier operator archived an unnecessary complete repository API
object containing a provider-generated temp_clone_token, which entered a
reviewer read trace. This is QUALIFICATION_EVIDENCE_CREDENTIAL_RETENTION, not an
established broker-runtime credential leak. Provider revocation/retention remain
NOT_ATTESTED. No historical credential value is needed or retrieved here.

Disposition: no-normative-impact. Affected layers: operator procedure and
qualification evidence. The separate [evidence hygiene procedure](qualification-evidence-hygiene.md)
and operator-only admission tool establish projection-before-persistence and
fail-closed corpus checks. They do not modify the product execution pipeline.
The historical incident receipt contains only file identifiers, already-known
hashes, redaction counts, field names and reason; unsafe originals are excluded.

## Regression oracles

`tests/test_github_initial_history_v3.py` contains the independent H01–H15
oracles: relative qualification/claim reconstruction; inventory-only qualifiers;
real journal decoding for intent matches; full-ref/duplicate/target refusals;
complete pagination, count drift and finite budget; second-inventory drift;
exact prior request with no matches; matching intent preservation; unrelated
qualification filtering; and provider-shaped GraphQL/REST equality. The two
fixtures in tests/fixtures/initial-history contain only bounded projected
observations, never a complete repository object.

`tests/test_qualification_evidence.py` exercises nested case-insensitive sensitive
fields, explicit typed safe counters, minimized jq projection, log/serialized
JSON/header screening, private exclusive persistence and refusal without leaking
values in diagnostics. Fixtures are inert strings, not historical credentials.

The corrected real read-only preflight for the unchanged local request returned
complete=true and no matching request IDs. Its two complete GraphQL observations
agreed with REST; the exact claim remained absent. This is preflight evidence,
not admission, a runtime reservation or live PREPARED qualification.

## Qualification and reuse limits

Exact final-SHA CI/tree equality, complete regression results and fresh independent
provider-conformance/evidence-hygiene reviews are supplied by the later PR93
receipt and Issue70 handoff. This pre-publication report does not claim those
not-yet-observed gates passed.

The existing subject PR98 and reference Issue99/comment6708178500 remain closed
and unmodified. Reuse readiness requires fresh exact IDs/bytes, canonical request
identities, absent claim/request Issue and absent temporary gates. It grants no
permission to reopen fixtures or execute the pipeline.

PR93 remains draft/unmerged. Installed PR92 stubs, dev, source-App configuration,
secrets/variables, Issues83/91 and unrelated runtime modules are outside this
correction. Issues70/67 remain open; Project state is unchanged. Live PREPARED
remains BLOCKED. A separate future owner mandate is required for the bounded
resumption; no next task executes automatically.
