---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "J-CH Workload and Stream Authority"
version: "0.1.1"
adoption_status: "accepted"
---

# J-CH Workload and Stream Authority

**Owner-accepted normative contract; effective only upon integration into dev.**
No proof mint, bootstrap or invocation is authorized.
This defines the disjoint future j-ch-v1 domain. Accepted legacy ARM v1 envelope,
audience, protected local-consumption configuration and historical bytes remain
unchanged and cannot be upgraded by interpreting a new field or boolean.

## Closed execution envelope and domains

The [ARM envelope](../../schemas/jch-arm-envelope-v1.schema.json) has its OWN
strict integer schema_version1 plus literal protocol_id=j-ch-v1. It is not the
legacy ARM-v1 schema merely because both use integer1. Its closed fields are:

- authorization_id: fresh256-bit lowercase hex identity, not a retry nonce;
- broker repository/name, numeric owner ID and exact admitted default ref;
- externally observed exact ARM commit A;
- complete closed original journal arm_binding, including prepared parent P,
  request/attempt/packet/subject/input/capacity, original workflow/run/recipient,
  challenge, launcher, policy/executable and preflight identities;
- exact canonical broker-metadata digest, complete accepted PASS capacity receipt
  and closed pinned reviewer command policy.

The binding's workflow_sha is the admitted executing broker AND workflow SHA.
workflow_ref equals broker repository plus the admitted review-request path and
ref. Request/attempt/packet/input/executing SHA agree with capacity; attempt is
ordinal1. Binding.subject agrees with immutable admission. Capacity receipt ID
is the accepted artifact identity over canonical complete receipt+LF.

`reviewer_policy_sha256` commits canonical RFC8785 bytes of the complete reviewer
command policy object in the envelope. The requested per-attempt OS permission
profile and exact installed profile digest remain separately bound in the
verified preflight/runtime observations, HELLO runtime identity and protected
deployment policy. They are NOT fields in the preserved closed broker-metadata
preimage. That metadata separately commits original admission/Issue/source
context; its digest cannot stand in for the profile bindings. Reviewer command
policy and installed OS profile digests do not substitute for one another.
The native executable digest matches the protected runtime and binding. No PATH re-resolution or weaker fallback.

Execution audience is exactly:

```text
urn:review-broker:j-ch-v1:arm-authority:sha256:<SHA256(canonical complete envelope)>
```

The closed [broker-metadata resource](../../schemas/jch-broker-metadata-v1.schema.json)
defines the exact original metadata hash preimage: version, broker/Issue,
request/attempt, admission mode, executing SHA, authenticated requester, subject
repository and mode-specific admission checks. It matches the established v1
metadata domain, not a new execution grant. Its IDs/mode/source must agree with
immutable admission/binding; Issue/publisher scope comes from independently
authorized original request context, not an input selecting a destination.

Canonical envelope hash bytes have no LF; transported JSON objects use the
explicit stream framing below. The exact original controller constructs the
complete envelope only AFTER positively acknowledged AtomicArm/readback, while
holding its original launcher stream. It rechecks authority after issuance and
before delivery. Another job or a matching later head cannot reconstruct that
ordering or ownership. A must not be embedded in its own journal commit.

Storage authentication has the separate already-qualified domain:

```text
urn:review-broker:result-retention:v1:sha256:<SHA256(canonical storage statement)>
```

[The retention contract](jch-result-retention.md) owns the complete statement,
authority basis, non-secret receipt and actual job/artifact observations.
The [authority-basis schema](../../schemas/jch-storage-authority-basis-v1.schema.json)
is the exact hash-preimage type, selected by result-retention:v1, not a caller-
selected configuration file. Its existing preimage has no injected version key;
adding one silently would change qualified policy identity.

Neither audience matches legacy `urn:review-broker:arm-authority:v1:sha256:`.
No envelope/JWT from another domain, version, process/challenge, job, recipient,
request/attempt or execution commit can delegate model authority here.

## Pinned issuer and trusted deployment

Issuer is ONLY https://token.actions.githubusercontent.com with its fixed
well-known discovery/JWKS endpoints. Reject redirects, ambient proxies,
token-supplied key URLs, non-RS256 algorithms, ambiguous/unknown kid, malformed
keys, private key material, invalid signatures and insufficient RSA key size.
Use maintained JOSE validation, including exact audience, issuer and strict
integer iat/nbf/exp; maximum lifetime600seconds and no clock leeway. Standard
thumbprints are validated metadata only, never a key selector or trust anchor.

Exact expected workload claims bind repository/name and numeric ID, owner/name
and numeric ID, immutable repository subject, ref, workflow ref/SHA, executing
SHA and original run ID/attempt. Derive them from verified binding plus protected
policy, NOT from token-provided claims. OIDC attests workload/audience, not journal
success, OS process identity or one-use continuation. Those relationships rely
on the qualified original controller and protected launcher.

The [deployment-policy schema](../../schemas/jch-deployment-policy-v1.schema.json)
defines the closed protected bootstrap context. Its configured repository,
owner, default ref, admitted source/workflow/launcher/runtime/profile and exact
recipient are independently verified. The root-owned single-link regular trust
file is canonical, mode0444, beneath root-owned non-writable canonical ancestors;
no aliases, symlinks, writable import/config/runtime paths or unknown fields.
A separately authorized bootstrap owns path/allocation selection and exact byte/
ownership observations. No runtime command initializes, repairs, clears or
reconstructs missing trust or historical consumption.

J-CH does not require a new durable local consumed-history store: GitHub is the
durable authority, with the original process's ephemeral one-shot fence. Legacy
v1 still requires its separately bound local state. Sharing or reconstructing
legacy trust does not make any past attempt newly eligible.

## Bounded single-stream interface

One authenticated non-TTY command owns binary stdin/stdout and separate bounded
stderr diagnostics. Each frame is four-byte network-order length followed by
exactly that many canonical UTF-8 RFC8785 JSON bytes, WITHOUT a trailing LF.
This differs deliberately from journal/artifact JSON document+LF serialization.
No banners, stdout diagnostics, duplicate members, BOM, CRLF normalization,
nonfinite values, partial frames, concatenated objects or silent truncation.

[The closed message schema](../../schemas/jch-launcher-message-v1.schema.json)
discriminates HELLO, PROOF and DONE, each j-ch-v1 with exact handshake major1 /
minor0. Unsupported version/type refuses without downgrade. HELLO comes from
the original process before ARM. PROOF includes the exact new envelope and JWT;
DONE is bounded outcome/evidence-reference data, never another grant or proof
of absent model transport after ambiguity.

Maximum HELLO and DONE payloads are16384bytes each; maximum PROOF is100000bytes,
including the complete canonical wrapper, envelope and JWT. JWT is at most32768
ASCII characters. Before ARM, construct/measure the envelope and the complete
worst-case JWT/wrapper budget; refuse if it cannot fit. No16KiB synthetic-proof
assumption, split/reassembled bearer grant or post-ARM size renegotiation.

The passive launcher's wait deadline is120 monotonic seconds from challenge
creation. Proof must arrive completely within that same original deadline and
satisfy issuer time checks. A timeout/EOF/error abandons the process/continuation;
it never establishes that an already started child stopped. Post-ARM uncertainty
forfeits execution, not durable consumption. No new connection or challenge.

Control JWT/envelope/stream state never enters child stdin, argv, environment,
packet, logs, result or retained evidence. Only exact verified prompt bytes and
approved isolated runtime context reach the child. A frame or DONE receipt is
not terminal evidence; accepted capture/validation and S2 gates remain separate.

## Qualification boundary

The new resources are accepted public contracts effective upon integration into
dev, not runtime loaders. Known
closed fields/types/canonicalization and cross-bindings must be independently
tested offline. Actual GitHub issuer/job/SSH/FD/bootstrap/credential capabilities,
source pins, original-session ownership, reentry/bypass/fork and failure cuts
require separate exact-deployment qualification. Passing a schema does not mint
or authorize anything. J20 and owner operational admission remain mandatory.
