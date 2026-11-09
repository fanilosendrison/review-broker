---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-plan"
domain: "independent-review"
severity: "draft"
name: "RB91 J20 Reject-Before-Publish Preparation"
version: "0.1.0"
---

# RB91 — J20 preparation, NOT execution

## Read-only inventory — 2026-11-09

Pinned source: `dev` `3057192a6ad4e80663b3b8168cbaa52657c3db27`.
[Machine-readable snapshot](rb91-j20-readonly-inventory.json) records four
paginated Actions run responses: reported/observed **380 runs**, **87** runs for
the three legacy writer workflows across **16** distinct head SHAs. No
noncompleted run was observed in that snapshot. This does not prove none can
start after the observation, or that every historical run is rerunnable now.

Current tree has **11** workflow files. API lists **18** registered workflows,
all `active`, including seven paths absent from current dev: two Q3 workflows
and five historical v3 qualification workflows. Registered active does NOT
prove a currently dispatchable source or present write credential; absent file
does NOT revoke historical rerun authority. Original Q1 nine-workflow inventory
remains a historical fact, not today's complete census.

| Surface | Verified source/read fact | Remaining operational obligation |
| ------- | ------------------------- | -------------------------------- |
| review-request | Current source installs local checked-out package, builds exact transferred wheel; writer job declares contents/issues write and id-token write | Bind actual run/checkout/wheel/workflow SHA, drain historical jobs and all rerun-eligible old SHAs |
| review-reconciler | contents/issues write, hourly/manual, `pip install .`; reads Issues AND claim refs, can claim/transition/dispatch/stop | Strict version rejection before any effect; complete bounded scan; drain old source and test real token capability |
| publication-recovery | contents/issues write, manual, currently historical-Issue constrained; shared journal/artifact/result APIs | Unknown version must block before reservation/receipt/ref writes; old pinned source remains distinct |
| three writer workflows | Same review-broker-single-reviewer scheduling key, no cancel-in-progress | Not a durable remote-process fence; all lifecycle mutators must share custody for D06 |
| codespace-control qualification | Different scheduling key, independent start/stop/always cleanup | Future resource custody change requires separate mandate; no group changed here |
| v3 controller/worker | Current source job `if:false` | API registered active is not execution admission; old branch source/runs need separate census |
| GitHubRefJournal/AttemptRecord | Current integrated R1/R2 fail-closed source; current CLI and all writer APIs use shared reader | Actual deployed packages and effective credential availability not inferred from source |
| manual reviewctl/direct API | Read/claim/transition/capacity/invocation/terminal/locator/publication/cleanup paths remain callable by privileged operators | Owner/admin enumerate actual installations, credentials and scripts; repository does not enumerate them |
| remote wheel/tools | Source verifies wheel transfer hash and installs exact wheel for each run | No remote inspection performed; old wheel installation/path/import or privileged bypass is UNKNOWN |
| historical reruns | Snapshot records actual run IDs and head SHAs, including pre-R1/pre-R2 source | Determine current rerun eligibility, original actor permissions and all source/ref guards; list is not a denial proof |

Read APIs observed Actions enabled, allowed_actions=all, sha_pinning_required=false;
workflow default token permission `read` and no PR-review approval capability.
These are repository defaults, NOT effective job grants: current writer jobs
explicitly request contents write. Q3's real scoped token established only its
bounded expected-old mutation; R1's new absence/identity probes have not been
qualified with the intended live Actions token. Local injected tests are not
such evidence.

No App private keys, tokens, credential files or values were inspected. Full
App/PAT/admin/bypass installation census, external manual tooling and remote
package inventory are **NOT AVAILABLE from this source/run inventory**. No
claim that unavailable administrative observation is a verified absence.

## Proposed reject-before-publish sequence

No step below is authorized for execution by this dossier.

1. Obtain owner adoption of exact journal/OIDC/recovery candidate and a separate
   implementation mandate. Implement v2 while keeping admission disabled.
2. Freeze the intended deployment and exact request/journal/OIDC protocol map.
   Record immutable approved SHA, wheel hash, workflow source, package imports,
   launcher/protected trust, selected ref namespace and recovery/discovery rules.
3. Enumerate all effective writers, current/in-flight and historical rerunnable
   workflows, branch-only qualification sources, Actions actors, manually deployed
   tools/wheels and direct API holders. Verify actual credential scope without
   revealing credential values. Stop on incomplete enumeration.
4. Deploy qualified v1 strict refusal everywhere that can encounter v2, preserving
   both historical wire profiles. Drain or deny old source jobs/reruns/tools by
   approved operational controls. Source merge alone is insufficient. Test
   refusal at every reader/writer entry point before the first v2 authority exists.
5. Prove old executables cannot read AND mutate v2 authority they do not understand;
   record effective deny/isolation receipts, not merely patched source receipts.
   Qualify R1 absence/identity observations with actual intended scoped tokens.
6. Qualify v2 adapter, specialized transitions, exact GraphQL outcome handling,
   OIDC ordering and original-session launcher. All lifecycle mutators participate
   in the D06 custody path. No old `internal-invoke` fallback can bypass binding.
7. Reinspect from a fresh administrative/read context after the drain. Require
   no old effective writer, no incompatible in-flight operation, all known old
   reader refusal controls, complete discovery and historical head preservation.
8. Only a separately authorized bounded non-inference qualification may create
   the FIRST future claim2 in the expressly approved namespace. Verify initial
   journal2/j-ch-v1/count0/null, exact admitted request/ordinal1/subject, closed
   nested fields, exact creator/executable and canonical bytes. Observe old
   writer refusal with zero mutation before any ARM test; preserve fail receipts.
9. Later operational admission still requires a separate exact owner grant,
   deployment receipts and all applicable execution/isolation/evidence/Shutdown
   gates. Neither initial claim2 nor offline PASS activates it.

A gate failure leaves admission disabled. No destructive rollback, reset of an
attempt, revocation, permission mutation, workflow disabling, bootstrap, claim2
or live experiment is performed here.

## If a disjoint ref namespace is proposed later

This dossier selects NO alternate namespace. A mere name separation is not
access control against repository-wide Contents-write credentials. A separate
proposal must define deterministic mapping from the same canonical request,
claim collision/exclusivity across namespaces, protocol selection BEFORE scan,
complete discovery for reconciliation/status/results/predecessors/publication,
legacy refusal, all direct writer privileges, retention and no-delete custody,
terminal artifact retrieval and shutdown ownership. Cross-namespace duplicates
must never allocate another ordinal-1 execution permission for one request.
Unknown/missing namespace observations fail closed. Operational credential
isolation still needs actual enforcement; a new prefix alone cannot satisfy J20.

## Future real non-inference protocol and risk budget

If conceptual adoption is accepted, the minimum live supplement is one separately
mandated disposable environment, fake child only, exact pinned source/issuer and
independently retained external process-start witness. No historical #82 or
consumer PR; no production trust state; no real model. Budget: one preapproved
Codespace allocation, bounded lifecycle, bounded synthetic claim set and scenario
matrix, named cleanup owner, exact Shutdown/deletion receipts. Numeric duration,
cost ceiling, allocated identities and credential grants must be fixed by that
separate mandate, not invented as authority here.

Cases: abrupt SSH/controller death before/after proof; ACK lost at each actual
submission/readback/mint/delivery boundary; duplicate proof and launch reentry;
fresh process/recipient; cancellation transit/ACK; delayed child start; actual
Shutdown competing with continuation; terminal evidence appearing during R's
fresh-head check; real capability/permission denial and legacy-writer refusal.
External witness distinguishes zero starts, one start and unknown lost evidence.

Immediate stop: unexpected model-capable binary, unknown recipient/source,
credential disclosure, unexpected privilege, extra start, ambiguous resource
custody, production ref touched, failed durable evidence upload, unbounded wait
or unobserved Shutdown. Consumed uncertainty never authorizes a retry. Preserve
all negative receipts; cleanup is not proof of zero prior model transport.

**J20_CUTOVER=NOT_EXECUTED.** Implementation/qualification/admission remain
separate from conceptual owner selection.
