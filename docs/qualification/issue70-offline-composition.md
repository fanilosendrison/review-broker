---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-report"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Offline Authenticated-Path Composition"
version: "0.1.0"
---

# Issue 70 — offline authenticated-path composition

## Scope and exact sources

This experimental composition targets **OFFLINE_INT03_COMPOSED** only.
It neither implements nor qualifies a real GitHub pre-model worker.
No operational permission derives from this report or from a future review GO.

```text
PR72_HEAD=e65e4db932cb59d7a0fcfbd442ba19e548fc141d
PR72_TREE=420a18d006e421e197d23b8e93681376fbabc2db
PR71_HEAD=9258617056e9d2e20cce7f05e6be71ea82dfbd23
PR71_TREE=35635d81c640ea4b798bf876772e1cc7b0c632e4
DEV=a3526c1a7620a8bc437e43511f354fdae2130ce5
PR55_PROTOCOL=d827df21b1ccd179408f0624709cc2446795e134
```

The base is PR72, not dev. All eight approved PR71 files were initially
imported byte-for-byte. Three are subsequently adapted under the supplemental
owner mandate: `packet_retention_v3.py`, `issue68_test_support.py`, and
`test_issue68_failures.py`. The preparation authority, historical report,
nominal tests, recovery tests and original reload probe remain byte-exact.
The shared PR72 packet fixture retains its authority override and authenticated
capture path; only deterministic PR71 Git commit dates are added.

Neither experimental source PR is merged or modified. Normative contracts,
schemas, production source readers, journal implementation, packet verifier,
provenance discriminator and workflows remain unchanged.

## Preserved RED evidence and correction

The first composition stopped at
`IMPORTED_INT01_REFERENCE_AUTHORITY_REALM_MISMATCH`.
Both original nominal methods failed with
`GIT_FILE_SOURCE_AUTHORITY_MISMATCH`, before retention reconstruction.
The legacy synthetic source authority and the concrete PR72 reference readers
used different authorization evidence. Changing an expected digest would not
resolve this disagreement.

The initial complete command log has SHA-256:

```text
8fa204c2158e95e6cb3eeb7ede823cdff62b1badd8c8e7e45ef02cc8c84bdcb1
```

The fixture correction creates one concrete `GitHubSourceAuthorityV3` using
PR72's injected `ScopeApi`, dummy token and installation 123. Git-file, Issue,
comment, subject capture and admission use that same instance. Fresh mutable
reference observations before PREPARED use new readers bound to that instance,
not cached Issue responses. F03–F07 have successful admissions before their
individual mutations; their exception expectations are narrowed, not widened.

With only this fixture correction, the two nominal methods reached the expected
cold-reconstruction RED: `RETAINED_SUBJECT_EVIDENCE_MISMATCH`. Six negative
methods that require completed preparation encountered the same reconstruction
failure. The F03–F07 construction negatives passed independently.
The intermediate nominal RED log has SHA-256:

```text
24313b22beb3c86a7052ba8b3aa2b9d5a501cca5da4a0a713fc56a3ba202b10e
```

The retained loader now passes validated `source_app_scope_evidence_id` into
the reconstructed admission by named argument. For the authenticated mode it
requires both manifest authority IDs as correctly formatted artifact strings,
reconstructs them, confronts the capture against validated source provenance
using the unchanged canonical provenance validator, recomputes the capture
identity, and calls the genuine Packet v2 verifier. The synthetic mode requires
absence of authenticated authority fields; unknown modes are rejected.
No scope ID is invented or substituted for an authorization ID.

## Component composition and authority limits

`AuthenticatedScenario` exercises real PR72 scope, PR observation, source
capture/binding, origin, requester and admission implementations. All external
responses are injected. Its final PR observation and requester authorization
are established before any journal claim. History and mutation/worker/writer
attestations remain explicitly injected test authorities.

The lifecycle remains:

```text
claim -> reserve_initial -> register_worker -> record_admission
      -> capture/verify/persist -> receipt -> prepare -> independent readback
```

`GitHubJournalV3` uses the injected expected-old/direct-parent CAS transport.
The dispatch count is local instrumentation, not an Actions dispatch. Packet
authority is the actual non-permissive `RetainedPacketAuthorityV3`, not an
always-true test double. A corrupted packet cannot authorize PREPARED.
A permanent refusal fences the previously retained preparation receipt.

Cold verification runs a new interpreter in an empty working directory with a
minimal environment, after removal of the acquisition checkout. Networking is
forbidden. Only serialized injected journal commits and private retained bytes
supply the reconstruction inputs. The retained tree uses directory mode 0700
and file mode 0600. This proves local retention, not remote artifact durability.

Distinct authority realms in the negative test mean different installation
and scope evidence, not Python object identity. Deterministic equivalent
observations are not falsely claimed to have unique per-instance identities.

The historical synthetic regime remains separately tested. It has no App scope
or authenticated authority IDs. Its capture and packet identities survive a
cold load of a historical-shape retained fixture. That fixture tests the loader;
it does not claim to qualify inline-only retention production. The original
PR71 four-reference packet identities remain historical facts on PR71, not
identities of this newly authenticated-path scenario.

## Observed injected example

These are test-fixture identifiers, not live GitHub evidence or signed receipts.
The technical policy remains `SYNTHETIC_OFFLINE_ONLY`.

```text
scope:
artifact:sha256:d3224f6833dba06aefe420bbb30ccfe2c9753706e53db73c9200d231136fd38e
source authorization:
artifact:sha256:df873b14bac55245f3b4c9f11f4f6e41efba8b9d2f3de7d1ef15f10342fd4f66
PR observation:
artifact:sha256:9962cfcb6960454b69264674dc256ff731a61d88765a17527d5dbc8f016d3f0b
capture:
artifact:sha256:09544d0eeaa9b976e1ad04e52715113b87b77a33608798266898652e1230c7c5
packet:
packet:sha256:9eda802d4ab56f6057ecbacc94fc93340c9a35e9fe54c34b5526b5672fcfae6b
packet evidence:
artifact:sha256:8b72676f940e6ad5f1d4eea20ac0a7fb1fdfab616b49afbf32604e34743def27
fake ADMITTED commit: dcf8b3733aa9378144412e78425ba59a41a1c296
fake PREPARED commit: 243fac5e75bbb40dc574ecb5e2a96901587a37f8
```

The two commit strings belong to the injected transport only. They were never
created as GitHub journal commits or refs.

## Tests and reproducibility

Python 3.11.9 local observations:

- Original preserved nominal RED: 2 errors in 2 methods.
- Fixture-only nominal RED: 2 reconstruction errors in 2 methods.
- Fixture-only negative run: 6 reconstruction errors in 11 methods.
- Corrected #68 nominal/failure/recovery: 16 tests, 38.176 seconds, OK.
- Initial #70 run: 10 passes and one test expectation error; the existing
  second-reservation API raises `INITIAL_RESERVATION_NOT_PERMITTED`, rather
  than returning an outcome. Only that new expectation was corrected.
- Final #70 run: 13 tests, 20.460 seconds, OK.
- Current focused #68/#69/#70 plus reference/origin readers: 106 tests,
  90.221 seconds, OK.
- Full discovery: **816 tests, 672.129 seconds, OK**. This count was observed,
  not calculated from prior totals. No interrupted run is classified as PASS.

The full discovery command log has SHA-256:

```text
053f2988552b242228e7232b76ad22ae92981a78ebe1b1227e5846f447ec1b03
```

Reproduction requires Python 3.11, Git and the declared package dependencies:

```bash
python -m pip install .
python -m unittest tests.test_issue68_nominal -v
python -m unittest tests.test_issue68_failures -v
python -m unittest tests.test_issue68_recovery -v
python -m unittest tests.test_issue70_offline_composition -v
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

No ignored virtualenv, pre-existing PR71 object or downloaded consumer content
is a test prerequisite. JSON, new-document frontmatter, whitespace and changed
source-size checks accompany publication. Exact-source CI and a fresh read-only
independent review remain separate publication gates; their eventual receipts
belong in the PR/handoff, without rewriting this local evidence.

## Boundaries A–G for a later real workflow

| Gate | Offline evidence | Unqualified live boundary |
| ---- | ---------------- | ------------------------- |
| A | Injected admission | Real request/history authority |
| B | Injected CAS/counter | Controller, dispatch and ambiguity |
| C | Injected fencing | Authenticated Actions worker coverage |
| D | Injected HTTP/Git | Authorized credentials and real capture |
| E | Packet verifier | Production technical-policy readiness |
| F | Private local reload | Durable private remote retention |
| G | Injected CAS/readback | Authorized GitHub mutation/readback |

The bounded real source/requester qualification accepted for #69 remains
separate prior evidence. This exercise neither repeats it nor upgrades it into
an integrated real worker qualification. The #68 historical report is unchanged.
The absence of #70 from the declared Project 17 was observed during inspection;
no Project item was created, changed or used as technical authority.

## PM01–PM35 confrontation

The source is PR55's pinned non-normative pre-model protocol annex. PASS below
is limited to offline semantics. BLOCKED preserves missing real orchestration
or an incomplete combined obligation. OUT_OF_SCOPE excludes later effects;
it does not waive their eventual qualification. There is no live PASS.

| Case | Status | Evidence / limit |
| ---- | ------ | ---------------- |
| PM01 | BLOCKED | I68 F15–F16; no live discovery controller. |
| PM02 | BLOCKED | I68 F15–F16; no live reconciler race. |
| PM03 | BLOCKED | External dispatch acknowledgment absent. |
| PM04 | OUT_OF_SCOPE | Generation 2 and ARMED excluded. |
| PM05 | BLOCKED | I70 F09; real in-flight acquisition untested. |
| PM06 | BLOCKED | Local refusal guards; live competing CAS absent. |
| PM07 | OUT_OF_SCOPE | Terminal no-access proof processing. |
| PM08 | OUT_OF_SCOPE | Codespace acquisition and terminal proofs. |
| PM09 | OUT_OF_SCOPE | Specialized STOPPED/no-access receipts. |
| PM10 | BLOCKED | Transient recovery generation absent. |
| PM11 | BLOCKED | I68 F05–F06; real dispatch ownership absent. |
| PM12 | BLOCKED | No redispatch claim; real controller absent. |
| PM13 | BLOCKED | I68 F13–F14; no real run race. |
| PM14 | PASS | I68 F21–F24/I70 F08: no offline post-PREPARED refresh. |
| PM15 | OUT_OF_SCOPE | ARMED/inference indeterminacy. |
| PM16 | OUT_OF_SCOPE | Owner recovery nonce/generation 2. |
| PM17 | PASS | 816 tests retain historical v1/v2 coverage. |
| PM18 | BLOCKED | Receipt negatives; terminal disposition excluded. |
| PM19 | OUT_OF_SCOPE | Duplicate STOPPED refusal. |
| PM20 | BLOCKED | I68 F19–F20; no live failure-write authority. |
| PM21 | PASS | Strict decoder, canonical/history negatives. |
| PM22 | OUT_OF_SCOPE | Cross-request Codespace ownership. |
| PM23 | BLOCKED | Issue-opening/reconciler workflow absent. |
| PM24 | BLOCKED | I68 F13–F14; live worker/ARMED coverage absent. |
| PM25 | OUT_OF_SCOPE | Generation advance and cleanup. |
| PM26 | OUT_OF_SCOPE | No-access STOPPED specialization. |
| PM27 | OUT_OF_SCOPE | Shared Codespace operation. |
| PM28 | OUT_OF_SCOPE | Universal preventive-gate qualification. |
| PM29 | OUT_OF_SCOPE | Codespace observation/ambiguity. |
| PM30 | OUT_OF_SCOPE | Start-gate operations. |
| PM31 | OUT_OF_SCOPE | Terminal non-acquisition shortcut. |
| PM32 | OUT_OF_SCOPE | Terminal receipt resource binding. |
| PM33 | OUT_OF_SCOPE | Refusal run-evidence/cleanup. |
| PM34 | OUT_OF_SCOPE | Dispatch/run trace and gate proof. |
| PM35 | OUT_OF_SCOPE | Terminal receipt CAS/replay. |

## Disposition

Local offline component composition passes. Final offline acceptance additionally
requires exact-source CI and independent GO. No acceptance closes #70 or #67.
No new ReviewRequest, dispatch, journal ref, source credential or permission
change, Codespace operation, reviewer invocation or v3 activation is authorized.
The separate construction review is not a Review Broker model invocation.

```text
LIVE_PREMODEL_PREPARED=NOT_QUALIFIED
GITHUB_JOURNAL_MUTATIONS=0
CODESPACE_EFFECTS=0
REVIEW_BROKER_MODEL_INVOCATIONS=0
V3_PRODUCTION_ACTIVATION=NO
NORMATIVE_ADOPTION=NO
```
