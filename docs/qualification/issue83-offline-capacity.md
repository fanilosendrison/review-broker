---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Issue 83 offline capacity and lossless rendering qualification"
version: "0.1.0"
---

# Issue 83 offline capacity and lossless rendering qualification

## Scope and exact subject

Baseline: `a3526c1a7620a8bc437e43511f354fdae2130ce5`.
Consumer: Proto-Scope PR #62, head `829d9ec772749bc0bdfa8e65e5bbc582e309b9e3`,
merge base `374addc871ad21a2d0dc3fa2fe5a314acf8dd442`.

The owner mandate authorizes repository implementation, offline qualification,
independent construction review and governed PR publication. It does not
activate admission, authorize authenticated reviewer inference, change any
credential, retry request #82 or modify the consumer PR/Issue #48.

The exact candidate SHA and tree are bound by the governed PR publication
receipt, not inferred from this authored report. The machine-readable
[offline receipt](receipts/issue83-pr62-offline-capacity.json) binds measured
packet identities and implementation-file hashes. It is not a ReviewResult.

## Reproduction and acquisition

The retained #82 packet verifies through the original legacy identity and
renderer. Recovered prompt/before/after SHA-256 values agree. The old packet is
`packet:sha256:870c8d3871785f680687688e3362185167c8ffebb25140cca0151e2a60bbc829`.

Read-only authenticated GitHub acquisition cloned the public consumer into a
bare repository without a checkout. Exact head/base commits were fetched.
Git blob reads reconstructed all 96 original images. The canonical API changed
set and Git's unheuristic path delta both contain 96 additions. The retained
internal Git diff is byte-identical to the independently regenerated diff.
No reviewed code, source filter or hook was executed.

The internal diff measures 713,785 Unicode scalar characters / 714,600 UTF-8
bytes, SHA-256 `95856307d70e33f1628e56f967f7296dd771f9facdbd26ab5f24d481ae3a168a`.
The supplied GitHub diff measurement of 826,368 characters is a diagnostic
reference, not substituted for these internal bytes. The internal diff has ten
similarity-copy headers from unchanged base paths. The canonical changes remain
added, not copied; their complete after images are all retained.

## Measured result

- Legacy input: 1,670,363 Unicode scalars, 1,670,363 UTF-16 units,
  1,672,247 UTF-8 bytes.
- Legacy input SHA-256:
  `44bc6b1c6e6d7231ad71d05f5cc891614b0a59c24d977b13bbc59a27fb154daf`.
- Compact input: 966,222 Unicode scalars, 966,222 UTF-16 units,
  967,291 UTF-8 bytes.
- Compact input SHA-256:
  `ae7780183c6657c20a8eb0607660346ade5e87e81147ebbfe20e4e2cc466d99b`.
- Compact packet:
  `packet:sha256:0f472ac0fc9981fb17db1f09b25c0ebfdeff720cd86af263e7c88f5429c15757`.
- Source manifest unchanged:
  `source-manifest:sha256:fcee2fa09ff3d89c6bccf0928cdf52711829a811c0274f8763ec1a20bba26ea8`.
- Complete images: 96; total original snapshot bytes: 779,115.
- Original mission, profile, request/subject identities, source entries,
  physical mappings, image bytes and diff bytes: unchanged.
- New format marker and mode table: explicitly packet-bound.
- Conservative capacity: 967,291 of 1,048,576 units; PASS offline only.
- Reviewer model invocations: zero. Journal mutations by qualification: zero.

No new compression, source truncation, summary, mission reduction or omitted
image was needed. The full diff is retained rather than redundantly presented.

## Offline regression evidence

The baseline full suite passed 521 tests after provisioning its exact CI-pinned
PR #72 fixture. An initial run without that fixture failed with
`PR72_TEST_FIXTURE_REQUIRED`; the environment was corrected without weakening
assertions. The new rendered-mode test was observed RED before implementation,
and the capacity test failed before its module existed.

The complete candidate suite passes 551 tests. New tests exercise real Git
repositories, byte/mode-preserving patch/index proofs, exact legacy/new PREPARED
reconstruction, copy heuristics, empty executable files, canonical mixed-scope
rejection, missing/reused images and path/commit/OID/diff/input mutations.

Capacity tests exercise real packet construction at below/exact/above limits,
non-ASCII conservative rejection, invalid UTF-8, receipt tampering, broker/packet
identity changes, mutation during journal binding, zero invocation reservation
on rejection, generic-CLI arm refusal, real reconciliation with no redispatch,
and frozen-memory transport through an injected runner. No synthetic outcome is
represented as a live reviewer verdict.

The policy extraction retains the exact Sol/xhigh/shell-disabled values and
public adapter aliases. Existing security, source-credential, publication,
Codespace, request v1/v2, evidence and historical receipt regressions remain
active. Public request/result schemas and the reviewer wire schema are unchanged.

Reproduce with the exact fixture declared by CI:

```bash
REVIEW_BROKER_PR72_TEST_CHECKOUT="<absolute-detached-fixture>" \
  .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src scripts
.venv/bin/python scripts/qualify-added-rendering.py \
  --legacy-packet "<retained-original-packet>" \
  --repository-root "<read-only-acquired-bare-repository>" \
  --output "<fresh-offline-output>" --report "<offline-receipt>"
git diff --check
```

## Remaining gates and immutability

Independent hostile construction review is still required on the exact final PR
head. No eligible separately authorized read-only reviewer is exposed to this
implementation session. The historically documented bootstrap mechanism is not
an admissible substitute. No production admission is enabled to self-review the
broker. The external review request accompanies the exact-head PR; no GO is
claimed here. CI and repository acceptance also remain publication gates.

The original #82 claim, STOPPED-after-INDETERMINATE history, count of one and
retained artifacts remain unchanged. A different rendered packet does not reset
that request, change its subject head or authorize another invocation. A future
consumer review requires separate owner authorization under the applicable v2
operation and admission. Proto-Scope PR #62 stays open; Issue #48 is not changed.
