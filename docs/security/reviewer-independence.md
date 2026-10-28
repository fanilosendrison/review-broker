---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "security-contract"
domain: "independent-review"
severity: "strict"
name: "Reviewer Independence Contract"
version: "0.2.1"
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
Complete effective-policy attestation remains unavailable. RB-PILOT-01 through
RB-PILOT-05 are consumed historical exceptions and none may be replayed. RB05
established functional Sol/xhigh behavior but retained its original operational
`FAIL`; supplemental recovery and the later 0.4.9 transfer-retention PASS are
additive evidence, not comprehensive policy attestation.

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

RB-PILOT-01 through RB-PILOT-05 (#26) are consumed and cannot be admitted
again. The bounded operational policy for future ordinary reviews is a distinct,
default-disabled path restricted to explicitly allowlisted public repositories,
a separately admitted exact broker SHA, and existing requester/repository
authorization. Preparing that path is not consent to inference or activation.

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

## Admission and qualification scopes

### Comprehensive security qualification

The comprehensive path retains its independent qualification variable and
evidence identifier. Its controlled probes seek effective process, tool,
filesystem, environment, network, credential, recovery and cleanup assurance.
Historical NO-GO, PARTIAL and UNDETERMINED observations remain applicable. The
broker cannot review itself into comprehensive qualification, and this path
remains unavailable unless its exact existing gate is explicitly satisfied.

### Bounded low-sensitivity v1 admission

The separate bounded path accepts the documented residual risks for an
explicitly authorized non-secret or low-sensitivity pull request. It requires a
dedicated exact enable value, exact executing-SHA admission, a nonempty
low-sensitivity repository allowlist, both existing authorization allowlists,
and authoritative public repository visibility. Unknown visibility and private
repositories fail closed. Admission occurs before journal claim, packet
construction, Codespace startup or model-capable execution.

This bounded scope does not assert effective model identity, reasoning effort,
universal filesystem isolation, complete tool isolation or comprehensive
security qualification. It preserves the verified runtime identity, requested
Sol/xhigh policy, shell-disable request, packet guards, credential quarantine,
one-shot execution and independent evidence validation as defense in depth.
No reviewer can merge, publish its own result or elevate its findings into
normative authority.
