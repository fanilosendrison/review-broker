---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "readme"
domain: "independent-review"
severity: "guideline"
name: "Review Broker"
version: "0.2.0"
---

# Review Broker

Review Broker is a private GitHub-driven service for evidence-bound independent
review of explicitly identified material. The requester owns the mission, the
broker owns execution and evidence, and the consuming repository owns admission
of the result.

## Qualification status

The implementation is a construction candidate. It is **not production
qualified**. Independent ChatGPT authentication is verified and the corrected
reviewer profile passes a producer-run non-secret isolation probe. Independent
security and construction reviews, a dedicated Codespaces-control credential,
and live execution qualification remain incomplete. Automatic workflows fail
closed until external security evidence is registered.

## Install the requester CLI

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/reviewctl --help
```

The requester installation does not install or run Codex. Reviewer credentials
remain in the dedicated service Codespace.

## Request a review

```bash
reviewctl request \
  --repo fanilosendrison/proto-scope \
  --pr 57 \
  --profile publication \
  --mission-file mission.json
```

```bash
reviewctl status --request request:sha256:<digest>
reviewctl result --request request:sha256:<digest> --json
```

The same canonical ReviewRequest JSON can be placed in an Issue using the
envelope documented in
[consumer integration](docs/operations/consumer-integration.md).

## Guarantees and limits

Review Broker preserves exact source, packet, attempt, and evidence identities.
Execution status, evidence status, reviewer verdict, and current applicability
remain independent. Citation validation proves only that quoted text is
anchored to the preserved source line; it does not prove a conclusion correct.

The broker never merges a pull request, changes reviewed material, retries an
indeterminate model attempt automatically, substitutes a model, or grants
normative authority to a review result.

## Added-file rendering and input capacity

The 0.6.0 construction candidate adds an explicitly versioned, non-duplicating
presentation for complete additions-only PRs. Every source image remains intact
and line-addressed; the original full diff remains in `changes.patch` with its
exact identity. Mixed or other canonical change kinds keep legacy presentation.
Old packet identities and reviewer/request contracts remain unchanged.

A pinned Codex 0.164.0 capacity check records Unicode scalar characters, UTF-16
units, UTF-8 bytes and the exact input hash before lifecycle and final armament.
The conservative UTF-8 upper bound rejects oversized input before a reviewer
invocation is reserved. Such a rejection stays PREPARED, distinct from an
ARMED execution becoming INDETERMINATE. This does not enable admission or
qualify a provider/model. See the
[implementation contract](docs/contracts/added-source-rendering-capacity.md) and
[offline qualification](docs/qualification/issue83-offline-capacity.md).

## Development

```bash
python -m pip install .
REVIEW_BROKER_PR72_TEST_CHECKOUT="<absolute-detached-fixture>" \
  python -m unittest discover -s tests -v
python -m compileall -q src
```

The complete suite requires the exact detached PR #72 Git fixture declared in
[CI](.github/workflows/ci.yml); a missing or wrong fixture fails closed.
Tests use synthetic transports and do not consume ChatGPT quota by default.
