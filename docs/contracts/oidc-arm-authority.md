---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "OIDC-bound Arm Authority v1"
version: "0.2.0"
adoption_status: "accepted"
---

# OIDC-bound Arm Authority v1

## Protocol coexistence

All legacy-v1 requirements below remain unchanged, including its exact envelope,
audience, protected trust/local consumed store and original two-write journal
ordering. Historical records and tokens do not acquire J-CH eligibility.

The separately accepted [J-CH workload contract](jch-workload-authority.md) and
[execution contract](jch-execution-authority.md) define a distinct j-ch-v1
protocol, not an extension accepted by the v1 parser. Its one AtomicArm and
original live challenge/continuation replace local durable history ONLY for
new separately admitted journal2 claims after formal adoption, construction,
J20 and operational qualification. No legacy guard is removed here.

A storage-purpose workload proof authenticates retention facts only, never ARM
or invocation. Its audience/statement/receipt are disjoint. No JWT is retained
as evidence. This amendment takes normative effect upon integration into dev and authorizes
no bootstrap, mint or activation.

## Accepted decision and scope

The owner approved GitHub Actions OIDC delegation for Issue #83. GitHub is the
trusted issuer. The exact pinned controller workflow is trusted to observe a
successful exclusive journal reservation before obtaining workload identity.
Only the provisioned dedicated Codespace consumes that delegation. Durable
local consumption limits invocation under that controlled substrate, not under
arbitrary compromised hosts or loss of trusted durable state. No provider
exactly-once inference or production-security qualification follows.

Job identity does not independently prove journal state. The trusted workflow
and controller enforce that relationship. No source token, journal/publication
token or Codespaces-control token is transferred to Codex. No new static signing
key, App, reader token, credential store or external service is introduced.

## Envelope and audience

The closed Draft 2020-12 envelope schema and binding validator are canonical in
`arm_authority_contract.py`. Version 1 binds repository name and numeric ID,
executing SHA, exact workflow ref and SHA, default branch ref, workflow run ID
and attempt, immutable reservation commit, request/ordinal-1 attempt/packet,
input SHA-256, complete capacity receipt and reviewer policy, canonical broker
metadata digest, dedicated Codespace name/ID and random authorization identity.

RFC 8785 canonical envelope bytes determine the audience:
`urn:review-broker:arm-authority:v1:sha256:<complete-envelope-sha256>`.
The envelope is never sufficient authority by itself. Its identifier is not an
execution retry nonce and cannot reset an attempt.

## Controller ordering

`internal-arm-authorize` performs the existing final capacity assessment and
exclusive journal ARM/count-one operations in the same process. It reads back
the exact immutable authoritative ref/record and compares ARMED/count one,
capacity, packet evidence and executing SHA before requesting OIDC. A losing
CAS proposal cannot request a token. A different process cannot mint authority
merely by reading somebody else's count-one reservation.

The job has narrowly scoped `id-token: write`. Its workflow identity is
`.github/workflows/review-request.yml@refs/heads/dev`; only the separately pinned
executing workflow SHA is trusted remotely. The controller requests the
purpose-bound audience through the runner's OIDC endpoint without redirects or
ambient proxies, rechecks the reservation after issuance, and writes a private
exclusive temporary bundle outside packet/evidence. The existing authenticated
Codespaces SSH channel forwards that bundle on stdin. Neither JWT nor envelope
is put in reviewer argv, environment, packet or uploaded evidence.

Failure after ARM never resets invocation count, removes a claim or authorizes
a new request. Missing or partial authorization output fails closed. Existing
INDETERMINATE and observed-cleanup semantics remain applicable.

## Issuer and remote verification

The only issuer is `https://token.actions.githubusercontent.com`. Discovery and
JWKS use that issuer's fixed well-known HTTPS endpoints. Redirects, ambient
proxies, token-supplied key URLs, non-RS256 algorithms, ambiguous/unknown key IDs,
invalid signatures and noncanonical envelopes fail closed. PyJWT performs
signature, exact issuer/audience and time validation. Numeric dates are strict
integers; no clock leeway is granted; token lifetime is at most 600 seconds.

Exact repository identity, workflow ref/SHA, branch ref, run ID/attempt and
subject are checked against the envelope and protected deployment configuration.
The envelope is checked against the actual packet, exact input bytes, canonical
complete broker metadata and exact PASS capacity receipt. The actual Codespace
name must also match its provisioned identity. This is not a claim of remote
host attestation against a compromised runtime administrator.

## Protected bootstrap and durable consumption

Deployment configuration is a root-owned, singly linked, canonical regular file
at `/var/lib/review-broker/arm-authority-v1/trust.json`, mode 0444. Its ancestors
must be root-owned directories without group/other write permission or aliases.
The complete configuration is closed and includes the pinned broker/workflow,
repository and Codespace identities, the consumption directory owner and its
physical device/inode identity. The allowed state directory is the sibling
`arm-authority-state-v1` under `/var/lib/review-broker`.

A separately authorized bootstrap must create that state directory as a private
0700 directory owned by the trusted invocation user, then bind its actual
identity in the protected configuration. No runtime command initializes,
repairs, recreates, migrates or clears either trust or consumption state.
Missing or replaced state fails closed. This deployment is not performed or
claimed qualified by offline construction.

The verifier creates an exclusive no-follow 0600 consumption record keyed by
attempt identity, outside packet, reviewer home, workspace and model-visible
evidence. Both authority and state roots are explicitly denied by the requested
reviewer profile. The record contains no JWT or credential. Every existing entry,
including an empty, corrupt or aliased record, refuses another invocation.
Record bytes and directory entry are fsynced and rechecked before model-capable
transport. No failed persistence operation rolls back its exclusive marker.

Interruption before durable consumption cannot start a model. Interruption after
consumption, including before model startup, permanently consumes the local
attempt. A second run, authorization identity or packet directory cannot reuse
it. These controls depend on the qualified filesystem honoring exclusive create
and fsync and on retention of trusted state. They do not detect arbitrary removal
of individual records by a compromised administrator or catastrophic state loss.

## Qualification and publication boundary

Synthetic issuer keys/JWTs qualify signature and claim failure paths offline.
Local POSIX fixtures qualify the algorithm under their own filesystem semantics,
including concurrent processes and explicit persistence interruption. Simulated
protected-root metadata is not evidence of a provisioned live Codespace.

A separate owner-authorized non-inference qualification must establish actual
Actions OIDC availability/claims, protected bootstrap ownership and identity,
filesystem persistence across the intended Codespace lifecycle, stdin delivery,
credential non-disclosure and fail-closed replay on that exact deployment.
No live token mint, Codespace startup, activation or consumer review is authorized
by these offline results. PR #85 and Issue #83 cannot claim full operational
acceptance until their applicable remaining gates actually pass.

Historical ReviewRequests, packet bytes/IDs, journal records, evidence validation
and the original independent NO_GO remain immutable. Old evidence validation
never authorizes a new historical execution. Original #82 remains consumed.
