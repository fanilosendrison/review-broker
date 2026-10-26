---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "security-model"
domain: "independent-review"
severity: "strict"
name: "Review Broker Threat Model"
version: "0.1.1"
---

# Review Broker Threat Model

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

The GitHub Actions publication token, dedicated Codespaces lifecycle token, and
short-lived private-source read token are separate. The source token is minted
from a read-only GitHub App and is passed only to source-resolution and Git
acquisition subprocesses. The Codex ChatGPT session exists only in the dedicated
Codespace. No reviewer process receives source, repository-write, lifecycle, or
publication credentials.

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
from the Codex child environment. Known credential-shaped patterns are screened before each ordinary artifact
upload and result publication. Detected raw runner evidence is replaced with a
sanitized incident; contaminated results and findings cannot be published.
This bounded detection is not proof that all secrets are absent. The ChatGPT
credential file is never intentionally copied, logged, committed, or placed in
Actions secrets.

The built-in Codex `:read-only` profile was proven insufficient because it
allowed reads from filesystem root. The reviewed named profile denied the runtime home and trusted workspace but
still allowed reads elsewhere at filesystem root. A direct non-secret Codex
`0.164.0` probe independently observed an outside-tree canary readable. The
revised profile instead grants Codex's minimal system paths plus only the exact
packet directory, explicitly denies the home and workspace, denies writes and
network access, prevents login shells, and supplies a fixed minimal subprocess
environment. Controlled producer probes must pass immediately before invocation.

These producer controls are not sufficient qualification by themselves.
Authenticated model execution remains disabled until an independent reviewer
challenges the profile, alternate credential paths, process visibility, and
probe evidence.

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
wheels, and reviewer distribution versions are versioned and reviewed. Profiles
cannot be weakened by mission text.

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

## Residual blocker

ChatGPT authentication is verified. The dedicated Codespaces-control transport
passed T1–T6 in Actions run `40304872558`. The historical root-readable profile passed its limited producer canaries but
failed an outside-tree canary. A temporary minimal-read direct-sandbox probe
observed denial of that outside canary, but did not test an authenticated
model-tool invocation or establish parent-process, descriptor, hard-link, and
output-channel safety. The installed historical profile is not silently
upgraded: the revised installer fails closed on mismatch. The repository
variable that enables authenticated execution must remain unset until
independent qualification accepts the exact filesystem, process, environment,
network, and output-channel observations and the profile migration is verified.
