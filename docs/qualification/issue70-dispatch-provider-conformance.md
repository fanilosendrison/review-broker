---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "strict"
name: "Issue70 Dispatch Provider Conformance and Consumed Request Disposition"
version: "0.1.0"
---

# Issue70 dispatch provider conformance

## Permanent owner disposition of Request101

The [historical live handoff](https://github.com/fanilosendrison/review-broker/issues/70#issuecomment-6710960045)
remains PARTIAL / DISPATCH_ACK_UNCONFIRMED_NO_RETRY / live PREPARED UNRESOLVED.
The owner now permanently disposes Request101 as CONSUMED_UNRESOLVED, no retry.
The claim and reservation remain retained, not deleted or reused. Generation1
retry, Worker redispatch and generation2 are forbidden. No future task may
silently revive that reservation.

Fresh pre-change observation confirms Issue101 CLOSED/not_planned, exact body,
claim head659b84580d28cfed162f5cc1dde90b092dd29805, REQUESTED/RESERVED,
generation1, worker/failure receipt null, invocation0 and no ACK, ADMITTED,
PREPARED or ARMED. Controller42395553604/job128472047067 remains attempt1,
terminal failure; no attributable historical Worker or rerun is observed.

Historical Worker HTTP emission remains unresolved0-or-1. Historical HTTP
status is NOT_ATTESTED, response body NOT_RETAINED and root cause NOT_PROVEN.
Current compatibility evidence must not be relabeled as historical HTTP422,
number-input rejection, timeout or provider failure.

## Two implementation findings, no product-contract change

The current owner mandate authorizes the REST-only wire correction and bounded
provider diagnostics. These are no-normative-impact implementation/provider and
qualification-evidence findings, not new dispatch, ACK or retry semantics.

The concrete adapter previously serialized generation as JSON number1. The
corrected provider helper serializes all workflow inputs as exact strings;
internal generation remains exact integer1. The active Worker still declares a
number input, checks inputs.generation==1 and retains the original Node/Python
mapping. The endpoint parameter return_run_details remains boolean true.

The old adapter also discarded non-200/204 response distinctions and transport
failure information. The new closed immutable diagnostic records only bounded
context, outcome/status, body digest/length, recognized candidate run ID and a
closed error class. No raw body, error message, arbitrary URL, exception text,
header, cookie or credential is retained. The existing live executor bounds
received bytes; RFC8785 bounds diagnostic JSON numbers. Transport wrappers may
expose only TRANSPORT_UNAVAILABLE rather than an underlying timeout subtype;
no underlying cause is invented.

The original adapter still consumes before emission and refuses a second call.
Only its actual response/result binding participates in the existing independent
ACK recognition. The diagnostic has no authentication, retry or mutation API.
A reporting sink cannot change the consumed opportunity or outcome; the concrete
CLI prints its screened projection without adding it to any journal or packet.
The injected domain dispatch protocol, WorkerInputsV3 and journal bytes are
unchanged. No cancellation, late binding, ACK or BLOCKED write is made for101.

## Authoritative provider confrontation

The current [REST workflow dispatch endpoint](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
and official github/rest-api-description operation actions/create-workflow-dispatch
support workflow_dispatch, ref selection, boolean return_run_details, HTTP200
with workflow_run_id/run_url/html_url and the historical HTTP204 no-ID response.
The current OpenAPI inputs object has additionalProperties=true; it does not by
itself prove that a historical numeric input was rejected.

The [official CLI source](https://github.com/cli/cli/blob/736c68f674113337685e3eb1f908602a03b8f99b/pkg/cmd/workflow/run/run.go)
uses map[string]string for manually supplied, prompted and JSON workflow inputs,
then constructs the dispatch request. This maintained provider representation is
the compatibility oracle for the string wire, not a new internal generation type.

The [GitHub App permission table](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps#repository-permissions-for-actions)
requires Actions write for POST workflow dispatch. GitHub's
[workflow triggering documentation](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow)
explicitly exempts workflow_dispatch/repository_dispatch from the normal
GITHUB_TOKEN recursive-trigger suppression. A job-scoped GITHUB_TOKEN with
actions:write can therefore exercise this endpoint. Concrete provider receipts
remain necessary; documentation is not a substitute for the bounded probe.

Selected official source/schema/documentation projections and immutable source
identities are retained privately. No complete external repository API object
is retained for this confrontation.

## RED, regression and diagnostic oracles

The new actual-Controller wire oracle reproduced RED on unchanged source: the
serialized generation was a number instead of string1. The private RED log is
preserved. DP01–DP03 verify exact payload, internal integer generation and boolean
return_run_details. DP04–DP13 cover valid/malformed200,204,400/403/404/409/422,
5xx and closed transport errors. DP14–DP17 verify bounded immutable diagnostic
fields, absence of raw material, genuine ACK positive control versus diagnostic
rejection, second-call refusal and no permission reset after diagnostic changes.
CLI serialization and reporting-sink failures have separate tests.

DP18 preserves the historical synthetic RWP dispatch/ACK/journal tests. The
existing concrete REST-wire assertion in test_live_prep_dispatch_authorities.py
changes only its exact expected generation value from1 to string1, as required by
the new wire contract; no count, guard, expected ACK or other assertion weakens.
The new tests exercise real Controller/admission/journal code with external
provider/Git doubles, not patched domain decisions. The isolated CLI-format test
mocks composition only to test its output consumer; it does not claim authority
qualification from that mock.

## One independent inert provider probe

The smallest design reuses the already installed inert Controller registration
as a provider-only caller on an isolated qualification branch. No new default
workflow, registration PR or merge is needed. Default Controller and Worker
stubs remain their exact qualified PR92 bytes. The fixture
`tests/fixtures/dispatch-provider/probe-controller-active.yml` is not a registered
workflow; its exact bytes are published only as the active counterpart on the
isolated caller branch after the corrected candidate is qualified.

The caller run-name is v3 dispatch provider-only qualification and it has only
job `dispatch-provider-probe`, not controller. The registered workflow name stays
unchanged. It preserves the registration's input
names/types for provider compatibility: request_id carries the exact caller SHA,
not a ReviewRequest identity; request_issue_number must be zero and is never an
Issue lookup. Branch, SHA, owner, event and attempt1 are constrained. The job has
only actions:write and contents:read, with the credential mapped solely from
github.token. No secret, source-App credential, live approval variable or broker
command is referenced.

The caller invokes `scripts/qualify-dispatch-provider.py`. The script verifies
its authenticated current run/job, default dev identity, registered Worker path
and the exact inert stub bytes twice before its one POST. Its shared production
wire helper emits only the dev ref, qualification-only non-broker request and
reservation strings, generation string1 and return_run_details=true. No valid
claim or Request101 value is used. It emits only the bounded diagnostic and
approved identity facts, never a raw provider response.

The budget is one caller run and one Worker-stub dispatch. No alternate payload
or optional second probe is selected. After terminal evidence is retained, an
ordinary successor commit restores the probe branch's Controller file to the
exact inert registration stub; no rerun follows and the active probe commit
remains retained by published history. Errors produce evidence and STOP, never
retry. The target must be workflow410394071 on dev, attempt1, skipped job under
if=false/empty permissions, with no source mint, journal, claim, packet, Artifact,
ARMED, Codespace or model. Independent provider readbacks verify one new target
run and exact response/run identity; no diagnostic alone authenticates a Worker.

Registration reuse cannot recognize this run as the historical or corrected
broker Controller: its SHA/ref and job identity differ, and it
holds no broker request/reservation. No Request101 gate is installed or reused.

## Qualification and next boundary

This pre-publication document defines the correction and exact finite probe
plan. Later exact-tree Ubuntu CI, provider run receipts, final claim readbacks
and a fresh independent correctness/provider-conformance review are supplied by
the Issue70 handoff. Planned gates are not represented here as already passed.

Both review verdicts must be GO. Even a successful probe establishes only
provider dispatch conformance against an inert target, not a broker Worker,
PREPARED, model or security qualification. Historical cause remains UNRESOLVED;
workflow input wire representation remains a likely compatibility finding only.

Issue70 and parent67 remain open; Project state is unchanged, PR93 unmerged and
live PREPARED UNRESOLVED. A later separately authorized live qualification must
use a genuinely new subject fixture, new review intent/request/claim and initial
attempt, never an artificial nonce or reuse of101. No next task executes here.
