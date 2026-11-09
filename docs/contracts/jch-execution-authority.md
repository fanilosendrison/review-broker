---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "implementation-contract"
domain: "independent-review"
severity: "strict"
name: "J-CH Execution Authority"
version: "0.1.0"
adoption_status: "proposed"
---

# J-CH Execution Authority

**Proposed normative contract. No operational implementation or admission.**
This is a separate protocol from accepted OIDC ARM v1/local consumption. It
becomes authority only through the separate owner normative-integration mandate.
Its runtime still requires construction, qualification, J20 and exact admission.

## Goal and trusted actors

For each admitted exact attempt, at most one broker-authorized Codex process
start is permitted. No provider-side exactly-once inference, liveness or
instantaneous remote revocation is promised. Consumed-without-start is valid.

GitHub, issuer, admitted workflow/controller and protected host are trusted
within qualified responsibilities. Fully compromised privileged GitHub history
or host memory duplication is outside the ordinary profile. Ordinary wrong
transitions, missing/unknown data, credential disclosure, excess permissions,
fork/reentry/relaunch/bypass, replay and ineffective Shutdown remain defects;
they are not excluded by trusting the host. Observed material leakage or
unexpected privilege blocks the affected path. Decision27's proportionate
assurance does not become a maximal Codex-internals requirement.

Roles remain separate: untrusted requester/source/output; trusted admission and
source reader; GitHub journal writer/controller; Codespace lifecycle transport;
protected launcher; untrusted/model-visible reviewer; independent evidence
validator; publisher. Journal/publication/source/control credentials never reach
reviewer code/tools, prompt, argv, environment or retained evidence. A storage
workload proof has no execution authority.

## Original passive launcher before consumption

After exact operational/request/subject admission and PREPARED/capacity-PASS
checks, the original controller opens ONE authenticated non-TTY bounded SSH
command to the exact provisioned recipient. The pinned passive launcher verifies
its protected executable/config/import/ancestor/recipient context, packet/runtime/
policy/input snapshot and owns its original control descriptors and monotonic
wait deadline. No model-capable side effect occurs before authority validation.

It generates its own fresh256-bit CSPRNG challenge in memory, not a caller-
selected, journal-restored, persisted, inherited or checkpoint-recovered value.
A new process/recipient samples a new challenge. A nonce, PID/birth tick, file
marker, program hash or SSH success alone proves neither identity nor noncloning.

One bounded closed HELLO under the [workload wire contract](jch-workload-authority.md)
binds protocol/handshake version, exact request/attempt/packet, broker/recipient,
executing broker/launcher, input/capacity and reviewer runtime identities. The
controller retains its own original stream/process context; another controller
cannot adopt a peer hello or journaled challenge. Stream framing/error/deadline
uncertainty refuses; no reconnect/rebind after ARM.

The [single AtomicArm](jch-journal-v2.md) fixes that original controller/run,
launcher challenge, recipient and immutable workload in journal2/count1. Only
the original live positive-ACK/readback owner can mint one execution proof and
send it once over the same original authenticated stream. No stored reservation,
matching run ID, successful job, copied ticket or later reader restores ownership.
Lost submission/ACK/readback/mint/delivery opportunity remains spent/uncertain.

## One protected continuation

The same launcher independently verifies canonical complete proof, pinned issuer/
keys/time/audience/workflow/run, its OWN challenge/session, exact A/P/binding and
trusted deployment/input/runtime/recipient context. Legacy and storage envelopes
are refused. A caller's arm boolean or input hash is not authority.

One serial dispatcher atomically changes private WAITING→CLAIMED once BEFORE
one child-start call. No thread/message reentry, background retry, implicit
recovery, authorization serialization/copy, unbound alternative entrypoint or
reviewer callback can start another child. Fork/copy after challenge creation
is prohibited except the one intended close-descriptors/exec child path, which
cannot become an authorizing launcher or invoke a second start. This must be
qualified from actual code and OS observations; a perfect journal is insufficient.

The preferred retained-parent/synchronous-child arrangement preserves existing
post-start evidence capture. An exec-in-place design requires separately
qualified supervision to retain those guarantees; successful exec alone does
not prevent an earlier fork. An ephemeral exclusive packet marker is defense
in depth, never durable authority across executor loss.

The child receives exact verified prompt bytes held in memory, not the control
stream or a later reopened input pathname. It uses the pinned native Codex path,
mode/profile and isolated minimal environment; unrelated FDs close. Tokens,
authority bytes, control/source/publication credentials and launcher access remain
outside model reach, including inherited process/proc/descriptor capabilities.
The actual effective boundary must be qualified; requested flags are not proof.

CLAIMED never returns to WAITING. Crash after claim, failed/uncertain spawn,
child failure, timeout, shutdown/rebuild/deletion or replacement forfeits the
attempt. No new authorization ID, PID, packet directory, ordinal or local-state
reconstruction can reset count1. Missing or partial start evidence is uncertainty,
not proof of zero starts or entitlement to another first start.

## Terminal evidence, fencing and failure

Actual required capture/validation/retention/credential gates remain separate.
A process exit, valid JSON or empty findings cannot manufacture success. Results
retain independent execution/evidence/verdict/applicability dimensions and never
authorize consumer merge/adoption. Preserve contaminated-evidence vetoes.

[S2](jch-recovery-s2.md) fences incompatible post-ARM terminal decisions with
actual quiescence and held lifecycle custody. Cancellation transit, SSH/controller
loss, recent head read or timeout is not a start fence. An already launched
process cannot be undone retroactively. No second grant on any reconciliation.

Trust/bootstrap cannot silently initialize, repair, clear or recreate consumed
history. Original legacy trust/local-consumption boundaries remain operative for
legacy attempts until separately amended and qualified; this contract removes
no v1 guard. Historical Request82 and all consumed pilots remain closed.
