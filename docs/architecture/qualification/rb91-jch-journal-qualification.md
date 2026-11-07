---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "RB91 J-CH Journal v2 Core Qualification — Evidence and Cutover Blockers"
version: "0.1.0"
---

# RB91 — J-CH journal v2: core contract qualification (Q4 / offline)

**Qualification disposition: PARTIAL / CORE PASS, FULL CONTRACT AND ACTIVATION NO-GO.**
**Scope:** proposed J-CH v2 **claim/pre-arm/AtomicArm authority core**, not approved journal ABI, full operational record, trusted launcher, or model permission.
This report is **non-normative**, tied to [issue #91](https://github.com/fanilosendrison/review-broker/issues/91) and [draft PR #94](https://github.com/fanilosendrison/review-broker/pull/94). The v1 contract, production source, operational workflows and all historical claim refs remain unchanged.

## Reproducible inputs and run

- Draft source: [`jch-journal-contract-proposal.md`](../jch-journal-contract-proposal.md) v0.1.1; overarching [`arm-challenge-authority-proposal.md`](../arm-challenge-authority-proposal.md), originally v0.1.2.
- Candidate (NOT accepted) JSON Schema: [`rb91-jch-journal-v2-core.schema.json`](rb91-jch-journal-v2-core.schema.json) — JSON Schema Draft 2020-12, **only 14 top-level core fields**, closed 20-key `arm_binding`, closed synthetic capacity receipt and history events. Deliberately refuses unqualified embedded business objects.
- Offline model: [`tests/rb91_jch_contract_model.py`](../../../tests/rb91_jch_contract_model.py). Test suite: [`tests/test_rb91_jch_contract_qualification.py`](../../../tests/test_rb91_jch_contract_qualification.py).
- Local command: `python -m unittest discover -s tests -p 'test_rb91_jch_contract_qualification.py' -v` from repo root with `.[test]` installed; in GitHub Actions the normal `python -m unittest discover -s tests -v` runs this against the **real pinned `review_broker` modules**.
- Local container without `rfc8785` executes an explicitly limited string/integer fixture fallback; its three project-dependent checks are skipped. **Do not cite local PASS as a real RFC8785 or old-code qualification.** The real CI execution, using the repo dependencies, is authoritative for those three checks.

## Falsification matrix — exact scope

| Proposed requirements | Evidence and disposition | Limit |
| --- | --- | --- |
| J01–J03 schema dispatch/core closure | Tests reject absent/future/bool version, unknown root and binding keys, missing binding properties, wrong field types; canonical and duplicate-key raw JSON. **PASS core** | Full admission, artifacts, publication and nested metadata **not yet represented** |
| J04 identity/capacity cross-check | Attempt ordinal-1 derivation; v1 input capacity receipt validated with actual repo implementation in CI; packet and input SHA/binding checks. **PASS synthetic** | A real ReviewRequest source, GitHub commit, policy/runtime and recipient must be independently bound |
| J05–J09 binding/consumption | Only PREPARED/capacity-PASS/count0/null-binding may become ARMED/count1; one arm event and bound parent SHA; rebind/split/count rollback refused. **PASS core** | No true Git commit creation, live launcher, or OIDC mint |
| J08/J10 pre-ARM terminal histories | **DISCOVERED CONTRACT CORRECTION**: `INDETERMINATE` and `STOPPED` may be reached pre-ARM at count0/null binding, or post-ARM at count1/immutable binding. History disambiguates. Tests both paths. **PASS core** | Existing specialized shutdown/evidence receipts were not qualified |
| J11–J13 history and recovery | Prefix-preserving event/evidence lists, exactly one append, no-op and re-arm refusal, correct capacity-PASS and valid REJECTED capacity (pre-ARM only). **PASS core** | Publication/retention changes are intentionally out of core-slice |
| J14/J17 error classification | Mock 404 authenticated vs 401/403/429/5xx/unknown; ambiguous GraphQL/silent lost response → no mint/retry. **PASS mock** | Real generic GitHub errors already recorded separately by Q3; no fault-injected live J-CH controller |
| J15/J16/J18/J19 GitHub/SSH/OIDC ownership | Q3 establishes bounded real `updateRefs(beforeOid)` behavior; Q2 bounded real synthetic full-duplex SSH. **PARTIAL across separate experiments** | Not integrated with an actual atomic v2 record and real issuer; process cloning/reentry/cancellation cuts open |
| J20 compatibility cutover | **FAIL / BLOCKER:** current `AttemptRecord.from_dict()` accepts a synthetic, schema-valid v2 ARM record, and `as_dict()` re-encodes it as v1 while **dropping `protocol_id` and `arm_binding`**. CI confirms this through an actual-source test; future required reject check is marked *expected failure*. | Cannot admit any v2 claim before all old readers/writers fail closed, or isolation is separately specified and accepted |
| J21 historical non-replay | Candidate v2 decoder rejects v1 record; no historical migration operation tested. **PARTIAL** | Must retain actual historical #82 and v1 identities in production without replay |
| J22–J23 trust and acceptance | Owner GitHub writer trust boundary accepted; publication and actual implementation remain absent. **DESIGN ONLY** | Independent hostile review, full writer/version inventory, normative owner adoption missing |

## Exact writer entrypoints inspected (source inventory, not operational exhaustion)

| Existing owner | Writer-capable paths | Cutover implication |
| --- | --- | --- |
| `.github/workflows/review-request.yml` (`contents:write`) | `internal-prepare`, capacity/ARM, terminal capture, artifact metadata, `internal-transition`, `internal-publish`, stop and indeterminate; mediated by `GitHubRefJournal` | Needs strict pre-existing v1/v2 version dispatch, verified pinned executable SHA, and a fully drained old workflow |
| `.github/workflows/review-reconciler.yml` (`contents:write`) | `internal-reconcile` invoking `reconciliation.py` which calls `claim`, `transition`, recovery and `record_stopped` | May create/update records independently of review-request; must reject unsupported v2 and use legal transition-only paths |
| `.github/workflows/publication-recovery.yml` (`contents:write`) | `internal-recover-publication` and publication-specific evidence operations | Post-ARM publication/recovery writer must reject unsupported v2 until a lossless v2 adapter is qualified |
| `src/review_broker/github_journal.py` + `queue.py` | Shared `claim`, `_read`, `transition`, `record_invocation`, metadata/publication/stopped and `AttemptRecord.from_dict/as_dict`; manually callable CLI paths | **Current concrete loss-of-binding failure**; `_read` also returns `None` for *every* nonzero GitHub GET, not just 404 |
| Other workflows / old pinned commits / human-authored tools | Not exhaustively enumerated by this source inspection | Check currently runnable workflow SHAs, permissions, direct CLI/script access and unexpired jobs **before cutover**. This inventory is NOT a proof that no other privileged writer exists |

**Required order for a possible migration:** (1) implement **strict v1 decode rejection of v2 and unknown fields** without changing valid v1 behavior; (2) test every entrypoint above under its actual effective permissions, including legacy worktree/workflow SHA; (3) drain/disable old runs, qualify fallback/recovery behavior; (4) only then enable new schema-v2 claim-time admission under its own explicit owner gate. If this is unprovable, STOP or propose a separately accepted disjoint ref namespace (with source discovery and recovery specification). **No v2 claim was created by this qualification.**

## Findings and exact disposition

1. **RB91-JQ-001 — BLOCKING**: Legacy `AttemptRecord.from_dict()` ignores `schema_version` and silently drops v2 authority fields on reserialization. Required J20 reject-before-publish gate **not implemented**.
2. **RB91-JQ-002 — CONTRACT CORRECTED**: Pre-ARM `INDETERMINATE/STOPPED` cannot be forced to count-one; the history-based pre/post-ARM distinction is now explicit in journal proposal v0.1.1.
3. **RB91-JQ-003 — BLOCKING FOR FULL ABI**: The core schema deliberately rejects non-null `admission`/evidence/publication data. It does not implement J03/J20 as a complete production record; embedded objects and semantic validators require complete typed specification and separate tests.
4. **RB91-JQ-004 — OPEN**: Current journal `_read()` interprets *any* failed ref GET as absent; a v2 reader needs a real three-outcome transport that preserves HTTP/GraphQL authority and distinguishes unknown from 404.
5. **RB91-JQ-005 — OPEN**: GitHub GraphQL errors, lost ACK, controller ownership, direct-child Git observation, OIDC, launcher reentry and reconciler race cuts are specified or separately observed in bounded tests, **not qualified together**.
6. **RB91-JQ-006 — OPEN**: Static code inspection does not enumerate every historical Actions SHA/privileged writer still runnable. A complete credential/permission and old-job drain audit remains mandatory.

This is **successful falsification/qualification of the bounded core model**, plus a confirmed cutover blocker — **not** a GO to integrate or deploy. The sole historical request #82 is not touched or revived. No J-CH ARM, JWT, Codespace, real Codex or external-model invocation occurred.

```text
TASK=RB91_JCH_JOURNAL_CORE_OFFLINE_QUALIFICATION
RESULT=PARTIAL_CORE_PASS_FULL_CUTOVER_NO_GO
SCOPE=NON_NORMATIVE_ATOMIC_ARM_CORE_ONLY
CANDIDATE_SCHEMA_VERSION=2_NOT_ACCEPTED
LEGACY_WRITER_V2_REJECTION=FAIL_EXPECTED
FULL_EMBEDDED_BUSINESS_SCHEMAS=NOT_QUALIFIED
REAL_JOURNAL_GRAPHQL_OIDC_CHAIN=NOT_TESTED
PRODUCTION_REF_MUTATIONS=0
OIDC_MINTS=0
REAL_MODEL_INVOCATIONS=0
PR94=OPEN_DRAFT
ISSUE91=OPEN
```