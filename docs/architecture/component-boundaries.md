---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "architecture"
domain: "independent-review"
severity: "strict"
name: "Review Broker Component Boundaries"
version: "0.2.0"
adoption_status: "proposed-jch-amendment"
---

# Review Broker Component Boundaries

## Proposed J-CH responsibility supplement

This scoped proposal does not change current executable boundaries. Future
journal2 uses separate contract owners for [history/AtomicArm](../contracts/jch-journal-v2.md),
[original execution](../contracts/jch-execution-authority.md),
[workload/stream identity](../contracts/jch-workload-authority.md),
[result retention/publication](../contracts/jch-result-retention.md) and
[S2 recovery](../contracts/jch-recovery-s2.md). The [adoption packet](../adoption/jch-normative-adoption.md)
keeps formal integration, construction, qualification and admission separate.

The journal owner alone validates versions/monotone parent-child operations and
expected-old authority; workload identity never proves that operation by itself.
The controller retains original live session/ACK ownership; the protected
launcher owns one in-process start continuation; lifecycle custody/quiescence
is a distinct recovery responsibility. Artifact storage cannot grant invocation.

The retention authority verifies exact original evidence/validation and faithful
result projection, independently authenticated actual storage job/source/actor
and every relevant artifact observation. The publisher owns actual actor/Issue
scope, one reservation creator, exact comment/receipt observation and no repost.
Source applicability uses its separate admitted source-read authority. None of
these new contracts is a runtime implementation or qualification claim.

## Domain contracts

`request.py` validates ReviewRequest v1 and owns the GitHub Issue envelope.
`identity.py` owns RFC 8785 canonical bytes and domain-separated SHA-256
identities. `admission.py` owns requester/repository authorization and immutable
pull-request resolution. Packet preparation rechecks the PR head after complete
file enumeration and rejects a subject change before source acquisition.

## Material acquisition

`packets.py` reads Git blobs without checkout or execution. It preserves original
bytes, Git object identity, SHA-256, encoding, physical line offsets, and a
separate normalized line-addressed rendering. It rejects partial-scope claims,
mutation, unsafe paths, and transport-size overflow.

## Durable execution control

`queue.py` owns legal state transitions, specialized evidence-gated terminal
transitions, invocation count, and in-memory reviewer serialization.
`github_journal.py` owns atomic Git-ref claims, exact-commit reads, and
fast-forward-only compare-and-swap behavior. GitHub Actions concurrency is
supplemental only.

`recovery.py` maps durable state plus observed Codespace state to bounded
recovery actions. `execution_recovery.py` owns partial runtime recovery,
terminal-capture receipts, artifact-plan recording, shutdown observations,
incidents, and their durable transitions. `artifact_locator.py` owns exact
Actions artifact identity, metadata observation, safe extraction, and byte
verification. `artifact_resume.py` owns post-model reconstruction from those
bytes. `reconciliation.py` owns complete bounded Issue and claim scans,
lost-event dispatch, and executable recovery actions. None infers whether
provider inference happened after an inconclusive `ARMED` transition.

## Runtime infrastructure

`codespace.py` owns bounded start, state polling, transfer, SSH, recovery, stop,
and observed `Shutdown`. `reviewer_profile.py` owns the exact credential-denying
Codex permission profile. `security_probe.py` owns controlled non-secret
verification of its effective filesystem, environment, and network boundary.
`codex.py` owns the pinned one-shot command, profile verification, parent-process
environment reduction, prompt before/after hashes, exit capture, and explicit
failure classification.

Neither module owns request semantics, evidence validity, or publication.

## Evidence and publication

`evidence.py` inventories exact artifacts and detects credential-shaped material.
`validation.py` checks packet integrity, JSONL terminal sequence, final-message
binding, response schema, identities, source coverage, and citation anchors. It
sets semantic correctness validation to false.

`publication.py` constructs ReviewResult v1, precommits unique publication
intent, completely observes exact actor-bound comments, and produces publication
receipts. Reviewer output cannot call it.

## Interfaces and orchestration

`cli.py` exposes the requester commands and narrow trusted workflow entry
points. `orchestration.py` composes admission, source acquisition, packet
preparation, and publication without absorbing their invariants. Privileged
workflows run only from the exact default-branch event SHA. Remote broker code
is an exact transferred wheel, verified before installation and invoked with
unsafe Python import paths disabled.

The requester installation has no Codex dependency. The authenticated reviewer
runs only in the dedicated Codespace.
