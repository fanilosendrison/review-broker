---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "operations"
domain: "independent-review"
severity: "strict"
name: "Review Broker Authentication"
version: "0.1.1"
---

# Review Broker Authentication

## Trust boundaries

Three identities remain separate:

1. The workflow token admits requests and publishes bounded results.
2. A dedicated GitHub identity controls Codespace start, view, copy, SSH, and
   stop operations.
3. The Codespace runtime holds its independent ChatGPT subscription session for
   Codex.

The Actions default token is not assumed to control Codespaces and GitHub's
workflow permission vocabulary exposes no Codespaces permission. The dedicated
control credential must be minimally scoped and stored as
`REVIEW_BROKER_CODESPACE_TOKEN`. It needs only the permissions proven necessary
to view, start, connect to, copy to or from, and stop this private-repository
Codespace. It must not receive repository Contents write, Issues write, Project,
or administration permission.

Workflow journal and publication operations continue to use the job-scoped
`GITHUB_TOKEN`. The reconciler passes the dedicated credential only to
`CodespaceController` subprocesses. The credential is not passed to the remote
reviewer process.

ChatGPT credential files never enter Actions secrets, repository files,
artifacts, Issues, logs, or chat. API-key and access-token login modes are
forbidden.

## Current status

At `2026-10-26T08:31:37Z`, the dedicated Codespace reported Codex CLI `0.164.0`
and `Logged in using ChatGPT`. API-key overrides and GitHub token environment
variables were absent. The sanitized receipt is
`docs/qualification/receipts/authentication-receipt-v1.json`.

`AUTH_BOOTSTRAP_REQUIRED` is cleared. No account identifier or credential
content was observed or recorded.

## Post-authentication gate

Authentication does not qualify credential isolation. Both the original
built-in read-only profile and the historical named profile allowed reads
outside the packet. A revised named profile limits reads to minimal system
paths and the exact packet, but its direct non-secret producer probe does not
establish effective model-tool isolation. The installed historical profile
is not silently overwritten: migration requires an explicitly verified,
credential-preserving operation. Before a real model invocation, an external
security review must accept filesystem, process, environment, network, and
output-channel evidence in `docs/qualification/security-assessment.md`.

Only then may the repository variables `REVIEW_BROKER_SECURITY_QUALIFIED` and
`REVIEW_BROKER_SECURITY_EVIDENCE_ID` be set from independently preserved
evidence. The separate Codespaces-control transport gate passed T1–T6 in
Actions run `40304872558`; that result grants no security qualification.
