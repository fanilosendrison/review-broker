---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-plan"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Future Live Effect Budget"
version: "0.2.0"
---

# Issue 70 — Future live effect budget

## Authority boundary

This is a ceiling for a **future separately authorized** qualification, not an
allocation of effects to the current task. The original PARTIAL candidate at
5041cc2 used a single future source mint and stopped on LP-01. The explicit owner
resumption decision resolves that premise with two separately minted credentials;
it does not authorize any current live effect. All current real operational
counters are zero. Draft branches/PRs, normal CI and construction
review are separate permitted construction effects.

## Future single-attempt ceilings

```text
QUALIFICATION_REQUESTS_MAX=1
CONTROLLER_DISPATCHES_MAX=1
WORKER_DISPATCHES_MAX=1

CLAIM_REF_CREATIONS_MAX=1

JOURNAL_UPDATE_REFS_MAX=5
  reservation         <=1
  dispatch_ack        <=1
  worker_binding      <=1
  admitted            <=1
  prepared_or_blocked <=1

SOURCE_APP_TOKEN_MINTS_MAX=2
CONTROLLER_SOURCE_APP_TOKEN_MINTS_MAX=1
WORKER_SOURCE_APP_TOKEN_MINTS_MAX=1
SOURCE_TOKEN_TRANSFER_CONTROLLER_TO_WORKER=0
SOURCE_TOKEN_REUSE_ACROSS_RUNS=0

PREPARED_ARTIFACT_UPLOADS_MAX=1
FAILURE_OBSERVATION_UPLOADS_MAX=1

BROKER_ARTIFACT_HELPER_SPAWNS:
  PREPARED <=1
  FAILURE  <=1 only if a catalog-qualified failure actually occurs

CODESPACE_EFFECTS=0
MODEL_INVOCATIONS=0
ARMED_TRANSITIONS=0
REVIEW_RESULTS=0

AUTOMATIC_MUTATION_RETRIES=0
AUTOMATIC_WORKFLOW_REDISPATCHES=0
```

A nominal success expects PREPARED_ARTIFACT_UPLOADS=1 and
FAILURE_OBSERVATION_UPLOADS=0. No failure is intentionally injected during the
first real qualification. BLOCKED requires the original ticket, independently
recognized catalog evidence, retained exact bytes, current Worker and sole CAS.
If failure retention is unavailable, no BLOCKED CAS may be invented.

## Provider retries and non-atomic boundaries

BROKER_UPLOAD_INVOCATIONS_MAX=1 per lane. Broker retries, respawn, overwrite and
delete are forbidden. Provider-internal retries are allowed only inside the
single pinned official child already launched. They create no new Review Broker
authorization. The current authority is checked immediately before spawn and
after return; an orphan may remain without any subsequent journal write.

The five updateRefs slots are not reusable. A lost ACK consumes the attempted
slot; equal readback cannot manufacture attribution. Blob/tree/commit preparation
uses the existing journal writer and does not expand the ref/CAS budget. No
cross-service transaction between Actions, source App, Artifact storage and Git
is assumed. An effect already started can finish after authority movement; it
cannot authorize another effect.

## Remaining prerequisites

The separate live mandate must freeze concrete repo/workflow IDs, branch/SHA,
request/body/object IDs, original owner authorization, exact source-App scope,
Artifact retention and transport bounds, actor principals, cleanup, evidence
retention and no-retry accounting. The dual-phase owner decision and Node24
bridge must have complete new exact-tree CI and fresh independent GO before a
live-effect mandate can be considered. The ACK start gate's thirty read-only
observations, at two-second intervals, create no mutation/retry allowance.
Controller provenance discovery is also finitely bounded read-only observation,
never another Worker dispatch. Standard conditional GET validation and immutable
Git-data reuse create no permission and no extra mutation budget. No live quota,
latency, availability or perpetual-retention guarantee follows from offline tests.
This document supplies none of the missing live approvals and never authorizes
production activation.
