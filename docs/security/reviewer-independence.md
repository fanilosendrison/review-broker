---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "security-contract"
domain: "independent-review"
severity: "strict"
name: "Reviewer Independence Contract"
version: "0.2.0"
---

# Reviewer Independence Contract

## Required independence

A reviewer instance must not inherit the producing agent's conversation,
working tree, mutable configuration, local rules, or result. It receives only
the trusted mission, mandatory profile, immutable packet, output schema, and
minimum runtime metadata required for examination. For the bounded v1
reviewer, model-controlled shell execution is intentionally unavailable:
the broker sends the complete verified packet and instructions through stdin
and explicitly selects `features.shell_tool=false`. The existing named
permission sandbox remains defense in depth. Other independently registered
model tools have distinct privilege implications and are not disabled or
qualified by this shell setting. See
[`reviewer-tool-surface.md`](../qualification/reviewer-tool-surface.md).

The v1 adapter uses `--ephemeral`, `--ignore-rules`, `--strict-config`, the
attempt-bound `review-broker-<packet-path-sha256>` permission profile, exact
model selection, and schema-constrained output. It rejects any base user config
and verifies profile bytes, owner, mode, runtime home, and trusted workspace
before creating `attempt.json`. Installation uses exclusive creation and never
replaces another attempt's profile; a partial or conflicting file blocks
execution.

The adapter now binds the PATH-selected npm launcher, root package, Linux x64
alias package and native executable to a versioned official-registry trust
record. It re-verifies a root-owned, non-writable package-layout copy at the
invocation boundary and executes that absolute native path directly, excluding
Node and mutable launcher lookup from model transport. The trust record is
producer-authored evidence pending independent review; npm artifact integrity
does not establish reproducible equivalence to the pinned upstream source.

Codex `0.164.0` exposes managed requirements that can override the requested
shell feature, permission profile, approval policy and network policy. Supported
non-inference diagnostics are separate processes or expose only requirements;
`codex exec --json` does not emit the required effective values before turn
transport. The broker therefore records effective policy attestation as
`UNAVAILABLE` rather than claiming that the requested profile became effective.
The authenticated production reviewer path remains disabled. The historical
fixed-fixture RB-PILOT-01 exception is consumed. RB-PILOT-02 is a separately
prepared non-production path that retains all existing requested controls but
has no inference authorization and does not claim attested effective Codex
policy.

The revised profile grants only Codex's minimal system read set and the exact
prepared packet directory. It explicitly denies the runtime home and trusted
workspace, network and writes, prevents login shells, and sets a fixed minimal
model-tool subprocess environment. It refuses packet roots overlapping either
privileged tree. The historical root-readable profile remains documented by
its original producer receipt; it is not accepted for the revised execution.
The runtime retains the historical installed profile. Distinct attempt-bound
profiles do not overwrite it. A direct non-secret Codex `0.164.0` probe of
installed attempt-bound profiles found that a controlled hard link to an
outside-packet file **was readable through the allowed packet path**. The
trusted packet-tree guard rejects multi-linked files before model invocation;
that guard has not been exercised in an actual model-tool session. The direct
probe also observed an accessible parent `/proc` environment interface without
synthetic parent-canary disclosure. Effective isolation remains unqualified.

## Proportionate v1 assurance and residual risks

The product owner explicitly retired exhaustive proof of Codex internals as a
blanket admission prerequisite for low-sensitivity v1 (RB-PI-SEC-01 #27).
The existing hard-link counterexample, observed managed-profile fallback and
unavailable same-process attestation remain truthful recorded risks; they are
not converted into passing controls. Protected materials are never intentionally
placed in model input or evidence. A demonstrated credential disclosure or
unexpected privileged capability blocks the affected path and requires a
specific mitigation.

RB-PILOT-01 (#26) is consumed and cannot be admitted again. RB-PILOT-02 is
prepared outside the production workflow with fixed synthetic data, no
privileged orchestration credentials, no GitHub publishing, and local evidence
only. Preparation is not consent to inference. A separate future mandate must
grant explicit one-shot consent. This remains a residual-risk experiment, not
a certification of Codex. Subsequent ordinary reviews require a distinct
bounded operational admission decision.

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
  inherited descriptors, effective tool inventory, and actual model-tool permissions;
- packet read access and write restrictions;
- denial of model-tool access to ChatGPT credential files;
- absence of GitHub and API-key credentials in the child environment;
- bounded network behavior and failed unauthorized exfiltration attempts;
- evidence recovery without credential material;
- cleanup after success, failure, cancellation, and control-plane interruption.

An external reviewer must examine the probe design and observations. The broker
cannot review itself into comprehensive qualification. Until the production
gate passes, the normal GitHub Actions review workflow stops before Codespace
startup with `SECURITY_BOUNDARY_NOT_QUALIFIED`. The consumed RB-PILOT-01 and prepared-but-unauthorized RB-PILOT-02 local paths
are not this workflow and cannot set the production gate.
