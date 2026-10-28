# Strict output wire-schema qualification

## Scope

Review Broker 0.4.6 separates the reviewer output contract used on the Codex
wire from the authoritative local validation contract. This qualification is
static and offline; it does not authorize or record an authenticated model
request.

## Finding

The full Draft 2020-12 schema contains `uniqueItems: true`. OpenAI strict
Structured Outputs does not support that keyword. The full schema also uses
string and collection constraints outside the documented strict-output subset.
Codex 0.164.0 forwards the selected output schema in strict mode rather than
removing those constraints.

This establishes a static compatibility defect. It does not prove that the
defect caused any particular historical `CODEX_APPLICATION_ERROR`.

## Remediation boundary

`reviewer-findings-v1.schema.json` remains byte-for-byte unchanged and remains
the authoritative local validator. Identity formats, source identifiers,
uniqueness, lengths, bounds, required fields, source coverage and citation
checks therefore remain enforced locally.

`reviewer-findings-v1.codex-wire.schema.json` is a conservative wire contract.
It retains the complete response hierarchy, closed objects, required property
sets, primitive types and categorical enumerations while omitting unsupported
or richer local constraints. Synthetic and production Codex invocation paths
select this wire artifact. The production gate remains closed.

Offline checks establish static strict-output compatibility, structural
coherence between both schemas, full local rejection behavior, call-site
selection and inclusion of both schemas in package data. They are not evidence
of provider acceptance.

## Preserved state

The four historical pilot failures and durable claims of RB-PILOT-01 through
RB-PILOT-04 remain unchanged and consumed. No new pilot or execution
authorization is introduced.
Codex 0.165.0 is not adopted; the runtime remains pinned to 0.164.0. The
intended reviewer target remains `gpt-5.6-sol` with `xhigh` reasoning effort.
Production security remains unqualified.
