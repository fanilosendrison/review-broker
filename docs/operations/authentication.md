---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Authentication"
version: "0.1.0"
---

# Review Broker Authentication

## Trust boundaries

Three identities remain separate:

1. The workflow token admits requests and publishes bounded results.
2. A dedicated GitHub identity controls Codespace start, view, copy, SSH, and
   stop operations.
3. The Codespace runtime holds its independent ChatGPT subscription session for
   Codex.

The Actions default token is not assumed to control Codespaces. The dedicated
control credential must be minimally scoped and stored as
`REVIEW_BROKER_CODESPACE_TOKEN`. Its actual permissions must be qualified before
use. It is not passed to the remote reviewer process.

ChatGPT credential files never enter Actions secrets, repository files,
artifacts, Issues, logs, or chat. API-key and access-token login modes are
forbidden.

## Current status

The observed command `codex login status` returned `Not logged in`. This is the
explicit `AUTH_BOOTSTRAP_REQUIRED` gate.

## Minimum safe user action

Start the named broker Codespace from the GitHub Codespaces interface or with an
authorized local GitHub CLI. Open a terminal in that Codespace and run:

```bash
codex login --device-auth
```

Follow the displayed device flow directly with ChatGPT. Do not paste a code,
token, refresh token, session cookie, or `auth.json` into chat, an Issue, a log,
or the repository.

After the browser flow completes, run only:

```bash
codex login status
```

The required observation is `Logged in using ChatGPT`. Stop the Codespace when
finished and report only that authentication completed; do not report
credential material.

## Post-authentication gate

Authentication does not qualify credential isolation. Before a real packet is
transferred, an external security review must verify filesystem, process,
environment, and network boundaries. Only then may the repository variables
`REVIEW_BROKER_SECURITY_QUALIFIED` and
`REVIEW_BROKER_SECURITY_EVIDENCE_ID` be set from independently preserved
evidence.
