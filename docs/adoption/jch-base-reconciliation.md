---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "J-CH Upstream PREPARED Reconciliation"
version: "0.1.0"
adoption_status: "proposed"
---

# J-CH upstream PREPARED reconciliation

## Exact inputs and authority

Historical J-CH base remains3057192a6ad4e80663b3b8168cbaa52657c3db27.
Published proposal parent is7a740e5550e3739c98356200ff9f4a2e490ce9a2.
The owner-authorized ascending integration takes the exact dev commit
**a47e42c9437357b18d79fb3e68776063f894b8ea** as second parent, including
PR131'sd8db161e9a4bd986804dbf04adb89c3ac2282c28 and the subsequent PR133.
No rebase, force publication or implicit replacement of historical identities is
permitted. This report does not authorize final normative acceptance or merge of
PR113; the prepared ascending merge is within its task branch only.

PR131 changes260 paths, none of which intersects the66 published J-CH paths.
That observation alone does not establish semantic compatibility. The comparison
also examined specification/contracts, dependency metadata, CI and the actual
v3 Controller/Worker, journal, dispatch, source and retention boundaries.

## Compatibility assessment

- The primary product specification and accepted contract/security documents are
  unchanged by PR131. New implementation and qualification reports cannot adopt
  the proposed J-CH ADRs/contracts or confer runtime permission.
- The integrated v3 path ends at PREPARED/count0 and STOP_BEFORE_ARMED. Its
  generation/reservation/dispatch/ACK/source/packet/retention authority is not
  J-CH AtomicArm or an original model-capable continuation. Similar schema or
  journal version numbers do not merge those protocol domains.
- J-CH remains a proposed future journal2/j-ch-v1 execution protocol with its own
  disjoint workload audience, one irreversible AtomicArm and original launcher
  ownership. No v3 PREPARED object, receipt, source credential, dispatch result,
  process restart or historical reconstruction supplies that continuation.
- V3 original-instance and exact-effect guards, lost-ACK refusal and immutable
  provenance reinforce PREPARED construction; they do not authorize replay or
  change v1/v2 request identity. Legacy modules retain their lazy/provider
  isolation boundary and original execution/local-consumption contracts.
- Source A/B acquisition credentials, journal/control credentials and Artifact
  runtime credentials remain purpose-separated. The shared Git provider/facade
  refactoring adds no J-CH token exposure, claim or new issuer capability.
- Runtime dependencies, package version and entry points remain unchanged from
  the historical base. The sole J-CH dependency delta stays the already recorded
  test-only RFC3339 validator. CI inherits PR131's45-minute budget, Node24 setup
  and exact public Artifact-helper fixture. No operational workflow permission
  is introduced by this reconciliation.
- Accepted v3 source-reader credential boundaries remain as specified; the full
  v3 request/packet construction does not become normative acceptance by
  integration. J20 remains a distinct future all-writer isolation gate, now
  necessarily including the newly integrated v3 paths and their credentials.

These are construction/authority comparisons, not actual runtime isolation,
provider custody, live issuer, Shutdown or end-to-end operational qualification.
No new transition rule or owner architecture decision is selected.

## Byte preservation without rewriting history

The original [historical manifest](jch-baseline-preservation.json) and sixteen
[frozen qualified inputs](jch-qualified-inputs.json) remain unchanged. The new
[upstream manifest](jch-upstream-preservation.json) records all260 inherited paths
against actual native Git blobs/modes at d8db161. The final manifest additionally
includes PR133's three paths, for263 distinct inherited paths at a47e42c. Current inherited bytes must
match those identities, including additions and deletions; the merge is not
permission to modify upstream implementation.

Four original protected paths were legitimately changed by PR131, and two more
by PR133. Their old
hashes remain in the historical manifest, while the reconciliation manifest
records each old/new pair explicitly. The preservation test requires the exact
intersection of upstream paths and protected historical entries, then confronts
current bytes with the upstream identity for those six paths only. Every other
historical protected entry retains its original hash. This is not a global
rebaseline, omitted check or source-derived self-oracle.

The unchanged historical test initially produced four expected preservation
failures after integration. That output is retained separately. The corrected
layered preservation checks pass against the actual upstream bytes; complete
new-context tests/CI and independent review remain required before qualification.
A private Git index preserved the staged task patch while Git prepared the
upstream merge; the original patch/tree and final proposed index are distinct
retained evidence. Only the canonical prepared-merge publisher may commit the
validated two-parent result.

## Concurrent PR133 and final ascending parent

While the first complete local suite was running, PR133 advanced dev from d8db161
to a47e42c9437357b18d79fb3e68776063f894b8ea. Its three-file delta extracts the
existing attributable comment predicate (exact body and publisher projection)
into a shared function and applies it before ambiguity checks in verified-result
retrieval. The accepted renderer, canonical identities, receipt fields and
publication at-most-once ownership do not change. Additional tests confront
unattributable public marker copies and exact receipt/comment identity.

This implements the existing authenticated-publication contract rather than
selecting new J-CH/F1 semantics. F1 remains separately responsible for canonical
typed result/reference/provenance comparisons and creator-only POST. The inherited
runtime bytes are preserved exactly, not repaired by this task. The complete
new-context qualification must include the added publication tests and frozen
F1 models using the inherited publisher. No accepted contract or new authority
transition is selected by this source integration.

The intermediate d8db161 prepared merge and its full local results are retained
in the original task worktree. A separate linked publication worktree starts at
the same published7a740e5 parent, merges a47e42c without committing, then applies
only the preserved task delta. This avoids rewriting the intermediate evidence
or losing staged work. It is an ascending two-parent merge, not rebase/force.

## Supported-platform result disclosure

The complete intermediate run finished1564 tests in6157.053s, with one error and
12 Linux-only skips. It is explicitly NOT_PASS. The error is the known Darwin
Artifact-child output-overflow `killpg` PermissionError from
[Issue115's accepted environment disposition](https://github.com/fanilosendrison/review-broker/issues/115#issuecomment-6769546618).
Both source/test blobs still match that disposition exactly:
8921f85af1561b7336bd6031eafb90b9068718af and
3e463c07e3f0746d460285fff29c87015ae03c4b. No runtime repair, exception suppression,
retry-until-green, test deletion or general Darwin-support waiver is introduced.
The required runtime witness is Ubuntu24.04/Python3.11; final literal-SHA Linux
CI must execute it and all12 Linux-isolation witnesses. The local error remains
visible regardless of later Linux success. A prior3600s envelope timeout is also
retained as incomplete, not counted as a completed suite or a source hang proof.

## Completed local new-context observations and inherited static debt

The full final current-dev attempt completed **1568 tests in4914.122s**, exit0,
with12 explicitly Linux-only skips. It is not1568 executed passing witnesses;
the twelve require final Linux CI. This is a distinct complete invocation, not
resumption or relabeling of the failed1564-test intermediate run. No test was
removed, skipped by a new filter or retried solely to hide the Darwin witness.

The full historical3057192-to-candidate whitespace check reports exactly the
three unchanged PR131 blank-line findings tracked in
[Issue114](https://github.com/fanilosendrison/review-broker/issues/114).
The same four path/blob identities include its inherited404-line admission
module. They are preserved upstream debt, not introduced or repaired here and
not a blanket extension of Issue111's old exceptions. The current task delta
relative to both d8db161 and a47e42c passes ordinary whitespace; all new/changed
handwritten J-CH modules are within400 lines. Historical-range failure remains
disclosed, while upstream preservation prevents unauthorized cleanup. Neither
this report nor an audit-success count claims those historical blobs conform.

The unrelated known issues were freshly read and reused, not reopened or
replaced by speculative duplicate defects. Exact Linux CI and independent review
must still verify that this scoped disposition preserves required guarantees.

## Required new-context qualification

The old824-test result is historical and cannot qualify this tree. New-context
validation must include the complete inherited suite, local J-CH dialect audit,
NR01–NR05, challenge/relocation/frozen-input tests, v3 PREPARED and source-boundary
regressions, ADR/index, compile, JSON/links and full-range whitespace. Linux-only
isolation witnesses require actual Linux execution in literal-SHA CI; a Darwin
skip is disclosed as unexecuted locally, never counted as a passing witness.

The official public Artifact helper is checked out at
cf430e030ddbb5b0abf93d22962f4752f3646cd9 for source/blob verification only; its
upload code is never executed by this mandate. No live dispatch, source token
mint, Artifact upload, claim mutation, Codespace, OIDC, ARM or broker inference
is authorized. A new exact whole-packet independent GO is required separately.
