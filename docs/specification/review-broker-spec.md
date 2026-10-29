---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "specification"
domain: "independent-review"
severity: "strict"
name: "Review Broker v1 Specification"
version: "0.6.0"
---

# Review Broker v1 Specification

## Product intent

Review Broker enables an authorized human, agent, or system to request
independent examination of explicitly identified material. A request states the
subject, purpose, instructions, and criteria. The service applies one stable
execution protocol while preserving the requester's variable mission.

The protocol admits the request, resolves its immutable subject, constructs a
verifiable packet, invokes an independently instantiated reviewer once,
preserves execution evidence, validates response structure and citation
anchors, publishes a bounded result, and records interruption, uncertainty, or
supersession explicitly.

## Authority model

The requester owns substantive mission instructions and criteria. A selected
profile contributes mandatory behavior and minimum evidence requirements. A
custom mission may strengthen but never disable those requirements.

The broker owns request admission, exact identities, packet integrity,
execution control, evidence capture, structural validation, publication, and
recovery. It does not invent missing scientific, legal, architectural, or
normative premises.

The reviewer supplies findings, citations, uncertainty, and an explicit
verdict. The reviewer is not an authority. Valid citation anchors do not prove
semantic correctness.

The consumer owns admission, publication, merge, architectural adoption, and
scientific acceptance. A reviewer `GO` is evidence for the consumer's policy,
not authorization for any downstream action.

## Versioned request boundary

ReviewRequest v1 remains the only implemented request contract. Its logical
request stays stable while resolution records the exact head, base, merge base,
source manifest, policy, and mission identities. Its canonical bytes,
identities, claims, attempts, artifacts, journals, publication receipts, and
result retrieval remain unchanged.

The accepted ReviewRequest v2 contract separates a stable Review Intent from an
exact-head request and its single ordinal-1 execution attempt. Review Intent
binds the logical GitHub pull request, requester mission, selected policy, and
requested reviewer policy under the `review-intent:sha256:` identity domain. A
v2 request additionally binds the expected head and one explicit operation:
`initial`, `changed_head`, or `repeat_same_head`. Identical canonical request
bytes remain one deterministic claim. Changed-head and same-head repeat reviews
require distinct authorized requests; neither is automatic. See
`docs/contracts/review-request-v2.md`.

This publication selects normative semantics only. No v2 parser, executable
schema, admission path, claim, execution, recovery, or publication path is
active until separately implemented and qualified. Historical v1 requests are
never reinterpreted as v2.

The implemented subject kind is an explicitly authorized GitHub pull request.
Other subject kinds are extensibility points only and are not claimed as
supported. The initial reviewer backend is Codex CLI through an existing
ChatGPT subscription. The qualified target is model `gpt-5.6-sol`, reasoning
effort `xhigh`, read-only sandbox, schema-constrained final output, and JSONL
event capture. API-key fallback and model substitution are forbidden.

## Risk-proportionate security and staged v1 admission (2026-10-28)

Review Broker v1 prioritizes the original agent-to-reviewer-to-structured-report
workflow under security assurance proportionate to subject sensitivity.
Exhaustive attestation of every Codex policy, tool, plugin, alias and process
route is not a universal prerequisite for explicitly authorized low-sensitivity
use. Essential controls remain mandatory, residual risks remain disclosed, and
a directly observed material credential disclosure or unexpected privileged
capability blocks the affected path.

### Historical synthetic sequence

RB-PILOT-01 through RB-PILOT-05 are consumed and cannot be replayed. Their
outcomes remain distinct:

- RB01 was the initial fixed non-secret exception and did not qualify general
  production security.
- RB02 ended with `APPLICATION_ERROR_UNCLASSIFIED`; raw diagnostics were not
  retained before observed Shutdown.
- RB03 ended with `CODEX_APPLICATION_ERROR`, functional `FAIL`, valid failure
  receipts, complete private retention and observed Shutdown.
- RB04 ended with `CODEX_APPLICATION_ERROR`, functional `FAIL`, valid receipts,
  complete retention and observed Shutdown.
- RB05 completed the Sol/xhigh review with functional `PASS`, verdict `NO_GO`
  and valid receipts. Its original operational acceptance remains `FAIL`
  because raw diagnostic retention was `PARTIAL` (#26 comment `6480361923`).
  Byte-exact supplemental recovery from retained events passed without new
  inference and without rewriting that outcome (comment `6480916478`).

Review Broker 0.4.9 corrected staged-file permission normalization (comment
`6481195784`). A later bounded non-inference Codespaces qualification observed
one real transfer arrive as mode 0644, then pass the actual retention path as
mode 0600 with byte and hash identity, credential screening, cleanup and
observed Shutdown (comment `6481554872`). This qualifies that transfer-retention
mechanism only. It does not manufacture historical pilot acceptance or general
production-security certification.

```text
RB_PILOT_01_THROUGH_05=CONSUMED
RB_PILOT_05_FUNCTIONAL=PASS
RB_PILOT_05_ORIGINAL_ACCEPTANCE=FAIL
RB_PILOT_05_SUPPLEMENTAL_RECOVERY=PASS
V049_TRANSFER_RETENTION=PASS
PRODUCTION_SECURITY_QUALIFIED=NO
```

### Bounded low-sensitivity operational admission

The applicable v1 subject class is an explicitly authorized, non-secret or
low-sensitivity GitHub pull request in a repository independently verified as
public. Public visibility is necessary but not sufficient: the operator must
also list the repository in the dedicated low-sensitivity allowlist. The
requester and repository must remain in their existing authorization allowlists,
and the executing broker SHA must equal the separately admitted SHA.

This bounded path is separate from comprehensive security qualification and is
disabled by default. Its admission decision occurs before a journal claim,
packet preparation, Codespace lifecycle action or model-capable attempt.
Private, ambiguous and unavailable repository visibility fails closed.
Sensitive or high-assurance requests require a separately justified admission
path. No configuration variable is activated merely by publishing source.

All existing ReviewRequest, immutable-source, packet, credential-screening,
one-shot, evidence-validation and publication controls remain applicable. Before
armament, this mode records a separate low-sensitivity-v1 preflight bound to the
exact request, attempt, packet, profile, runtime and executing broker. It verifies
the approved runtime and installed profile identities, packet-tree integrity,
credential-separated environment request and declared shell disablement. It
does not execute the comprehensive direct sandbox probe and records effective
Codex policy attestation and comprehensive isolation as unavailable and
unqualified. Missing or cross-mode evidence fails closed.

The comprehensive admission path retains its strict direct sandbox probe and
original oracle. Historical hard-link readability, managed-policy overrides,
`/proc` uncertainty and unavailable effective-policy attestation remain
unchanged. A successful bounded preflight does not qualify comprehensive
isolation, while demonstrated credential exposure or unexpected privilege still
blocks the affected path.

### Bounded private-source operational admission

A distinct default-disabled path may admit one explicitly configured,
low-sensitivity private-repository pull request. It requires exact requester,
repository, pull-request number, expected head, and executing broker SHA
bindings. It is available only for ReviewRequest v2, whose canonical request
already binds the expected head.

Repository identity must be verified as private using the dedicated read-only
source-App credential. That credential's installation repository scope must be
verified as the exact admitted repository. Publication and Codespaces-control
credentials cannot substitute for source-read authority. Public-mode evidence
cannot satisfy this path, and private-mode evidence records
`public_repository_verified` as false.

The source token is limited to repository metadata, pull-request resolution,
file enumeration, clone, fetch, and publication applicability lookup. It is
removed before reviewer execution and is never transferred to the reviewer
runtime. This path preserves all canonical v1/v2 bytes, identities, one-attempt
semantics, packet integrity, publication, recovery, and uncertainty rules. Its
configuration does not authorize inference; exact operational activation and
model execution remain separate decisions.

The requester continues to own the variable mission and criteria. A reviewer
result is evidence only; it never authorizes merge, publication, source
modification or alteration of normative premises. See RB-PI-SEC-01 (#27).

## Required separations

The implementation maintains distinct boundaries for:

1. GitHub request admission.
2. Source acquisition and packet construction.
3. Codespace lifecycle control.
4. Codex invocation.
5. Evidence validation.
6. GitHub result publication.

Reviewed code is read as Git blob data. It is never executed in a context that
holds orchestration or reviewer credentials. The reviewer cannot publish its
own result.

## Status dimensions

Every result preserves three independent dimensions:

- `ExecutionStatus`: `COMPLETED`, `FAILED`, or `INDETERMINATE`.
- `EvidenceStatus`: `VALID`, `INVALID`, or `UNDETERMINED`.
- `ReviewVerdict`: `GO`, `NO_GO`, or `UNDETERMINED`.

Current applicability is separate. A verdict on a historical head is not a
verdict on a new head.

## Failure semantics

`ARMED` is durable before any call capable of model transport. Each admitted
attempt permits at most one Codex CLI process invocation. A crash after `ARMED`
without terminal evidence becomes `INDETERMINATE`; it is not retried
automatically. This does not claim stronger exactly-once provider inference.

Missing evidence remains missing. A desired Codespace state, zero process exit,
valid JSON, anchored citations, or an empty findings list cannot manufacture a
successful review.

All polling is bounded. Cleanup requires observed `Shutdown`. Failure to
confirm it is an infrastructure incident handled by the reconciler.

## Explicit non-goals

Review Broker does not modify reviewed material, merge pull requests,
automatically approve its own construction, reveal or claim access to hidden
reasoning, compete with a generic LLM-invocation product, duplicate generic
Proto-Ring governance, or transfer consumer-specific authority to Proto-Ring.
