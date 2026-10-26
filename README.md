---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "readme"
domain: "independent-review"
severity: "guideline"
name: "Review Broker"
version: "0.1.0"
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

## Development

```bash
python -m pip install .
python -m unittest discover -s tests -v
python -m compileall -q src
```

Tests use synthetic transports and do not consume ChatGPT quota by default.
