---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "security-model"
domain: "independent-review"
severity: "strict"
name: "Review Broker Threat Model"
version: "0.4.0"
adoption_status: "accepted"
---

# Review Broker Threat Model

## Ordinary J-CH assurance supplement

The owner-selected ordinary J-CH profile trusts GitHub/issuer, approved qualified
writers/workflows and protected host within their responsibilities. Arbitrary
fully privileged history falsification or memory cloning is outside that
adversarial claim, not defeated by hashes/nonce/PID/CAS. Ordinary bugs, replay,
wrong transitions, unknown observations, credential leakage, excessive capability,
fork/reentry/relaunch/bypass and ineffective Shutdown remain defects and gates.
B/E remain nonpreferred reconsideration options if an in-scope invariant fails.

The [versioned J-CH contracts](../adoption/jch-normative-adoption.md) require
irreversible AtomicArm in GitHub, original live controller/launcher, strict
version coexistence/J20 and S2 quiescence/custody. F1 separates execution,
authenticated actual storage and exact faithful result content. A workload
signature does not establish original result truth, upload-job custody, process
identity, provider exactly-once inference or permission to post again.

Storage-purpose OIDC is disjoint and transient; no raw proof/control credential
reaches reviewer, packet, argv/environment, result or retained evidence. Only
verified non-secret authorization receipts enter immutable journal custody.
Actual source/job/policy/bootstrap/credential and all-mutator isolation must be
qualified separately. Decision27's bounded risk policy is retained; no blanket
maximal Codex-internals prerequisite is reopened. This supplement takes normative effect upon integration into dev, grants no runtime
admission and does not rewrite historical exposures or qualifications below.

## Protected assets

Protected assets include ChatGPT session material, the dedicated Codespaces
control credential, trusted broker source, request and attempt journals,
immutable packets, recovered evidence, publication credentials, and consumer
repository integrity.

## Trust zones

GitHub Issue bodies, pull-request descriptions, source repositories, source
files, reviewer output, and transferred packets are untrusted data. Broker code
on the default branch, versioned schemas and profiles, admission policy, the
atomic journal, and independent validators are trusted only within their
qualified responsibilities.

The GitHub Actions journal/publication credential, dedicated Codespaces
lifecycle credential, and source-reader GitHub App authority remain separate.
One installed source App may support two explicitly restricted installation-token
profiles: `LEGACY_SOURCE_READ` requests only Contents, Pull requests, and Metadata
reads; candidate `V3_REFERENCE_SOURCE_READ` additionally requests Issues: read
for separately authorized source-reference acquisition. Legacy tokens never
inherit Issues access from a broader installation. App registered permissions,
installation approval, and effective issued-token grants are distinct facts;
proposed Issues permission is not evidence of an approved effective grant.

Both source tokens derive from the same App private key. They are separately
scoped tokens, not independent App-private-key compromise domains. A compromised
App private key could mint tokens within the installation's approved authority;
token restriction does not remove that shared risk. App expansion therefore
requires accepted contract publication, verified legacy restrictions, separate
owner App/installation approval, and separately approved live qualification.

The source-token authority, trusted broker orchestrator process, isolated
source-read subprocesses, journal/result mutation authority, Codespaces lifecycle
authority, and independent reviewer execution environment are distinct trust
roles. Separate GitHub credential permissions do not imply separate OS processes.
The trusted publication command may possess a source token for read-only
current-source-PR applicability lookup alongside its journal/publication
credential. The trusted reconciler may temporarily possess source, journal,
and Codespaces-control credentials within the same process.

Controls restrict credential use and subprocess propagation: source-read
operations receive the source token, including applicable isolated Git
subprocesses and separately authorized candidate v3 Issue/comment reads.
Journal/result mutations and Codespaces lifecycle operations use their separately
authorized credentials. Requester admission remains independent. Neither source
profile permits writes, Actions, workflow, administration, journal mutation,
result publication, Codespaces control, or reviewer-model authority.
Publication-applicability lookup does not make the source token a writer.

Credential permission separation is supported; complete process-level possession
isolation is not established. A compromised trusted broker process could
potentially access co-resident credentials and cross these logical boundaries.
This is an existing architectural exposure and residual risk, not evidence of
an experimentally demonstrated compromise. The original risk-proportionate
security policy remains applicable; no exhaustive Codex-internals attestation
requirement is introduced.

No source, journal, publication, or Codespaces-control credential is intentionally
transferred into the independent reviewer execution environment or Codespace
reviewer process. Those credentials must remain outside that environment,
model prompts, retained packets, public logs, and ReviewResults. The Codex
ChatGPT session exists only in the dedicated Codespace.

## Threats and controls

### Malicious reviewed content and prompt injection

Source bytes are acquired with Git object commands and never executed. Packet
boundaries label source text as untrusted data. Verification reconstructs every
prompt byte from packet-bound mission, policy, and exact source snapshots; a
mutable prompt hash cannot bless changed instructions. Shell commands use
argument vectors, fixed remote paths, and validated identities. Source
instructions cannot alter the profile, request, command, schema, or evidence
destination.

### Malicious Issue content and unauthorized requests

Only one canonical marker envelope is accepted. RFC 8785 bytes are validated
against ReviewRequest v1. The Issue author and subject repository must appear in
explicit allowlists. Text outside the envelope has no request semantics.

### Forged, replayed, or substituted identity

Resolution records repository identity, pull request, head, base, merge base,
mission, policy, and source manifest. Source snapshots retain Git blob OIDs,
SHA-256, original byte lengths, and physical line maps. Request, subject,
packet, attempt, and artifact identities use separate domains. Current head is
checked again before publication.

### Duplicate or concurrent execution

A deterministic Git ref is created atomically for each request identity. The
winning ref contains the attempt journal. Readers retrieve state from the exact
observed commit, while fast-forward-only updates and one global Actions
concurrency group supplement the durable claim. Duplicate Issue delivery cannot
authorize a second attempt.

### Credential exposure and network exfiltration

API-key, GitHub token, base URL, organization, and project overrides are removed
from the Codex child environment. Known credential-shaped patterns are screened
before each ordinary artifact upload and result publication. Detected raw runner
evidence is replaced with a
sanitized incident; contaminated results and findings cannot be published.
This bounded detection is not proof that all secrets are absent. The ChatGPT
credential file is never intentionally copied, logged, committed, or placed in
Actions secrets.

The built-in Codex `:read-only` profile was proven insufficient because it
allowed reads from filesystem root. The reviewed named profile denied the
runtime home and trusted workspace but still allowed reads elsewhere at
filesystem root. A direct non-secret Codex
`0.164.0` probe independently observed an outside-tree canary readable. The
revised profile instead grants Codex's minimal system paths plus only the exact
packet directory, explicitly denies the home and workspace, denies writes and
network access, prevents login shells, and supplies a fixed minimal subprocess
environment. Controlled producer probes must pass immediately before invocation.

These producer controls are not sufficient comprehensive qualification by
themselves. The comprehensive path retains the direct sandbox probe and strict
oracle. The separately accepted low-sensitivity-v1 path uses a non-probing
pre-arm record for exact runtime/profile identity, packet-tree integrity,
sanitized environment and declared shell-disable configuration. That bounded
record explicitly leaves effective-policy attestation unavailable and
comprehensive isolation unqualified; it does not erase any probe counterexample.

### Persistent Codespace compromise

Exactly one dedicated private-repository Codespace is used. It does not reuse
the historical Review Lab Codespace. Packet transfer is bounded. The workflow
builds a broker wheel from its exact default-branch event SHA, transfers and
verifies its SHA-256, force-installs that wheel, disables unsafe Python import
paths, and records the wheel identity in attempt evidence. Untrusted repository
code is not checked out for execution, and each workflow binds actual
`Shutdown` or records an incident. The scheduled reconciler independently
detects nonterminal attempts and stranded runtime state.

### Policy and workflow modification

Only the exact default-branch event SHA executes. Privileged manual dispatches
from any other ref are rejected before secrets are exposed. Pull-request code is
not selected by a review event. Schemas, profiles, workflows, trusted broker
wheels, and reviewer distribution versions are versioned and reviewed. The
Codex launcher/package mapping and native executable must match the versioned
npm release trust record, and model transport uses a root-owned non-writable
package-layout copy rather than a second PATH lookup. Profiles cannot be weakened
by mission text.

### Incomplete evidence or false success

Execution, evidence, verdict, applicability, and semantic correctness remain
separate. Terminal JSONL events, final-message equality, prompt hashes, response
schema, source IDs, physical lines, and exact quote anchors are checked.
Failures and missing artifacts produce invalid or indeterminate states.
Terminal evidence is uploaded under a journaled plan and finalized with exact
Actions run, artifact, archive, and file identities. Publication requires one
nonce-bearing journal intent and exactly one independently observed comment from
the expected GitHub actor. Artifact expiry, response loss, or duplicate comments
cannot create false terminal state.

## Proportional-security product decision and local synthetic pilot

The October 26 product decision in #27 retires exhaustive Codex-internal
attestation as a blanket prerequisite to bounded low-sensitivity v1. It does
NOT nullify the historical producer probe, the hard-link read, managed-policy
fallback, /proc visibility, or uncertainties about surviving tools. All are
recorded as residual risks rather than quietly reclassified as PASS.

RB-PILOT-01 (#26) is a one-off, fixed, non-secret synthetic experiment outside
GitHub Actions, with no GitHub/App/Actions tokens or publication capabilities in
its own execution path. Only existing Codex OAuth is an intended credential.
The caller must launch it under a scrubbed environment; unexpected ambient
credential-related keys cause preflight refusal. The pilot keeps the published
runtime hash and profile checks, disallows arbitrary mission/source inputs,
records a durable attempt marker, and never retries automatically. Any detected
credential-shaped output is quarantined locally. It does not establish general
credential isolation or satisfy production cleanup/recovery qualification.

Low-sensitivity public PR review uses a separate default-disabled operational
gate. It requires exact enablement and executing-SHA binding, dedicated and
general repository allowlists, requester authorization, and authoritative
public visibility before any claim or execution side effect. Public visibility
does not itself classify a repository as low sensitivity.

Bounded private-source review is a distinct default-disabled gate. It requires
ReviewRequest v2 plus exact requester, private repository, PR, expected head,
and executing-SHA bindings. Trusted code verifies private identity and exact
installation-repository scope with the dedicated read-only source-App token.
The publication and Codespaces tokens cannot satisfy this check. The source
token is never transferred to the reviewer environment. A false public proof,
wrong token scope, missing token, or public/private receipt substitution fails
before armament.

Before armament, trusted workflow code must produce a mode-specific bounded
preflight receipt tied to the exact immutable packet and installed
runtime/profile identities. Reviewed content cannot select either mode. The
comprehensive high-assurance qualification variable remains separate and unset.

## Residual risks and comprehensive blocker

ChatGPT authentication is verified. The dedicated Codespaces-control transport
passed T1–T6 in Actions run `40304872558`. The historical root-readable profile
passed its limited producer canaries but failed an outside-tree canary. A
temporary minimal-read direct-sandbox probe
observed denial of that outside canary, but did not test an authenticated
model-tool invocation or establish parent-process, descriptor, hard-link, and
output-channel safety. The installed historical profile is not silently
upgraded: the revised installer fails closed on mismatch. Managed-policy
overrides, filesystem aliases, inherited process capabilities, `/proc` and
descriptor visibility, and unobserved effective tool routes remain
real residual risks. They remain blockers for the comprehensive qualification
claim, not silently reclassified PASS. The comprehensive security variable must
remain unset until its independent qualification accepts the required exact
observations. The separate low-sensitivity path may be activated only by an
explicit operator decision satisfying its own exact-SHA and public allowlist
gate; source preparation does not activate it.

Official npm artifact provenance now binds the requested Codex release, but does
not establish upstream-source reproducibility. Synthetic managed-requirement
probes also demonstrated that Codex can replace `shell_tool=false`, the named
profile, `approval_policy=never`, and network denial. No supported interface was
found that exposes all final values from the same `codex exec` process before
model transport. Effective-policy attestation is therefore blocked for the
original complete production qualification gate, which remains closed. The fixed
synthetic pilot
is the narrowly scoped, explicit exception described above.
