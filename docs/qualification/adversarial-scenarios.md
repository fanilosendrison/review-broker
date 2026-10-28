---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-plan"
domain: "independent-review"
severity: "strict"
name: "Review Broker Adversarial Scenarios"
version: "0.1.0"
---

# Review Broker Adversarial Scenarios

Default tests use synthetic Git, GitHub, Codespace, and Codex transports. They
must not consume live ChatGPT quota.

1. **Duplicate request delivery.** Expected: one stable attempt identity and no
   second invocation authorization.
2. **Concurrent identical admission.** Expected: one atomic claim wins and all
   callers observe that attempt.
3. **Concurrent different requests.** Expected: both claims persist, but only
   one can enter the single-reviewer `ARMED` boundary.
4. **Invalid request schema.** Expected: admission rejects before source access
   or Codespace startup.
5. **Unauthorized requester.** Expected: `REQUESTER_UNAUTHORIZED` with no claim
   capable of execution.
6. **Unauthorized repository.** Expected: `REPOSITORY_UNAUTHORIZED` with no
   source acquisition.
7. **Incorrect PR head SHA.** Expected: `PR_HEAD_MISMATCH`; no redirect to the
   observed head.
8. **Candidate changed after admission.** Expected: historical result is
   preserved and current applicability becomes `SUPERSEDED`.
9. **Source missing from packet.** Expected: `INCOMPLETE_SCOPE`; no whole-subject
   coverage claim.
10. **Modified source bytes.** Expected: packet verification fails with source
    SHA-256 mismatch.
11. **Malformed Git blob identity.** Expected: packet verification fails with
    Git blob mismatch.
12. **CRLF source material.** Expected: original CRLF bytes and hash remain
    unchanged while citations use qualified physical-line text.
13. **Unicode and BOM handling.** Expected: UTF-8 BOM remains in original bytes,
    encoding is `utf-8-sig`, and first-line citation text excludes the BOM.
14. **Prompt injection in source documents.** Expected: injection remains
    delimited source data and cannot alter command or profile.
15. **Credential-access attempt from untrusted execution.** Expected: controlled
    probe cannot read credential material; any access blocks security
    qualification.
16. **Model unavailable.** Expected: `MODEL_UNAVAILABLE`; no substitution or
    retry.
17. **OAuth expired.** Expected: `OAUTH_EXPIRED`; no API-key fallback.
18. **ChatGPT usage quota exhausted.** Expected: `QUOTA_EXHAUSTED`; preserve the
    attempt and do not run another inference.
19. **Codex crash before terminal output.** Expected: explicit failure or
    indeterminate execution according to captured transport evidence.
20. **Lost terminal response after possible invocation.** Expected:
    `INDETERMINATE` and no retry.
21. **JSONL failure event.** Expected: `FAILED`, invalid evidence, and
    `UNDETERMINED` verdict.
22. **Incorrect citation.** Expected: evidence `INVALID`; no conversion to
    `NO_GO` or `GO`.
23. **Fabricated source line.** Expected: citation anchoring fails.
24. **Valid citations supporting an unsupported conclusion.** Expected:
    citation validation can pass while semantic correctness remains explicitly
    unvalidated.
25. **Missing review evidence.** Expected: missing artifact remains unavailable
    and validation cannot manufacture success.
26. **Failed result upload.** Expected: state remains `VALIDATED`; publication
    can resume without another inference.
27. **Stale result reused for a newer SHA.** Expected: applicability is
    `SUPERSEDED`; original verdict is unchanged.
28. **Codespace left running after interruption.** Expected: reconciler requests
    stop and requires observed `Shutdown`; unknown state is an incident.
29. **GitHub Actions event not delivered.** Expected: durable Issue/ref
    reconciliation discovers the request without assuming event delivery.
30. **Reviewer service attempting to qualify its own implementation.** Expected:
    `SELF_QUALIFICATION_FORBIDDEN`; external provenance remains required.

## Qualification boundary

Passing synthetic tests qualifies only the implemented contract behavior under
the fakes. Live Codespaces permissions, ChatGPT authentication, model
availability, credential isolation, connector event delivery, cancellation,
and external construction review require separately preserved observations.
