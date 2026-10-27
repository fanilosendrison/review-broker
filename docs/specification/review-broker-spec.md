---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "specification"
domain: "independent-review"
severity: "strict"
name: "Review Broker v1 Specification"
version: "0.2.0"
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

## Supported v1 boundary

The implemented subject kind is an explicitly authorized GitHub pull request.
The logical request remains stable while resolution records the exact head,
base, merge base, source manifest, policy, and mission identities. Other
subject kinds are extensibility points only and are not claimed as supported.

The initial reviewer backend is Codex CLI through an existing ChatGPT
subscription. The qualified target is model `gpt-5.6-sol`, reasoning effort
`xhigh`, read-only sandbox, schema-constrained final output, and JSONL event
capture. API-key fallback and model substitution are forbidden.

## Risk-proportionate security and staged v1 admission (2026-10-26)

Review Broker v1 prioritizes the original agent-to-reviewer-to-structured-report
workflow under security assurance proportionate to the sensitivity of the
subject. Exhaustive attestation of all Codex internal policies, model-visible
tools, plugins, aliases and process mechanisms is NOT a universal launch
prerequisite for bounded, authorized low-sensitivity use. Review Broker must
instead retain its essential controls, declare actual residual risks honestly,
and refuse any path with observed material credential disclosure.

RB-PILOT-01 (#26) was the only authenticated exception to the production gate.
Its identity is consumed and permanently closed. RB-PILOT-02 is prepared as a
separate, explicitly acknowledged, fixed non-secret synthetic fixture with no
consumer PR, repository source execution, GitHub publication, or automatic
retry. Its executable entry point does not authorize inference:
`RB-PILOT-02_INFERENCE_AUTHORIZED=NO`. A future mandate must authorize exactly
one invocation after independent code-identity and operating-condition checks.
A local validation receipt is not production EvidenceStatus VALID. The pilot
retains the pinned native Codex executable and requested policy while exhaustive
internal policy attestations remain unavailable; no claim of comprehensive
credential isolation follows.

After a successful pilot, ordinary authorized non-secret or low-sensitivity PR
reviews may be admitted only by a separately versioned and tested operational
admission policy. Until that implementation exists, the real-PR production gate
remains closed. Sensitive/high-assurance requests require their own stronger
authorization and evidence. Review reports never carry automatic merge or
normative decision authority. See RB-PI-SEC-01 (#27).

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
