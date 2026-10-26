---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "security-contract"
domain: "independent-review"
severity: "strict"
name: "Reviewer Independence Contract"
version: "0.1.1"
---

# Reviewer Independence Contract

## Required independence

A reviewer instance must not inherit the producing agent's conversation,
working tree, mutable configuration, local rules, or result. It receives only
the trusted mission, mandatory profile, immutable packet, output schema, and
minimum runtime metadata required for examination.

The v1 adapter uses `--ephemeral`, `--ignore-rules`, `--strict-config`, the
exact `review-broker` permission profile, exact model selection, and
schema-constrained output. It rejects any base user config and verifies the
profile bytes, ownership, mode, runtime home, and trusted workspace before
creating `attempt.json`.

The revised profile grants only Codex's minimal system read set and the exact
prepared packet directory. It explicitly denies the runtime home and trusted
workspace, network and writes, prevents login shells, and sets a fixed minimal
model-tool subprocess environment. It refuses packet roots overlapping either
privileged tree. The historical root-readable profile remains documented by
its original producer receipt; it is not accepted for the revised execution.
The runtime still has that installed historical profile until a controlled
migration. Profile mismatch stops execution rather than silently replacing it.
A direct non-secret probe of a temporary minimal-read configuration is producer
observation only: actual model-tool equivalence, parent-process interfaces,
hard-link behavior, and effective isolation remain independently unqualified.

## Credential ownership

The GitHub Actions token admits and publishes requests. A separately provisioned
Codespaces-control identity starts, views, transfers to, connects to, and stops
the dedicated runtime. The Codespace's runtime user owns the independent
ChatGPT session. The Codex process needs that session, but model-controlled tool
processes must be unable to read its credential material.

No ChatGPT credential is stored in GitHub, the broker repository, workflow
artifacts, packet directories, or evidence. No API key is accepted as fallback.
No credential from the Turnlock Review Lab Codespace is copied.

## Reviewer limitations

The reviewer can inspect only packet snapshots. It cannot modify an
authoritative source repository, publish its result, mutate the journal, or
select another model. The trusted workflow recovers output and an independent
validator publishes the result.

Effective model identity and reasoning effort are recorded as requested values.
They remain unattested unless the provider exposes independently verifiable
metadata. The broker never infers either from a CLI flag.

## Qualification gate

Before authenticated content is exposed, independently reviewed controlled
probes must demonstrate:

- the effective user and process tree, including accessible parent environment,
  inherited descriptors, and actual model-tool permissions;
- packet read access and write restrictions;
- denial of model-tool access to ChatGPT credential files;
- absence of GitHub and API-key credentials in the child environment;
- bounded network behavior and failed unauthorized exfiltration attempts;
- evidence recovery without credential material;
- cleanup after success, failure, cancellation, and control-plane interruption.

An external reviewer must examine the probe design and observations. The broker
cannot review itself into qualification. Until that gate passes, workflow
execution stops before Codespace startup with
`SECURITY_BOUNDARY_NOT_QUALIFIED`.
