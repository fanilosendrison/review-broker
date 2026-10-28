# Private retention mode normalization qualification

## Scope

Review Broker 0.4.9 normalizes a freshly transferred staged artifact to
owner-only mode before local identity verification. This correction is local
and offline. It does not authorize or record a Codespace operation, controller
invocation, pilot or model inference.

## Demonstrated mechanism

The existing local identity gate accepts an owner-controlled, single-link
regular file in mode 0600 and rejects the same safe, hash-correct bytes in mode
0644. This permission compatibility mechanism was independently reproduced.
The retained RB-PILOT-05 metadata does not establish the historical copied
file's mode, so permissions are not claimed as the proven cause of its original
`LOCAL_VALIDATION_FAILED` status.

The byte-exact supplemental recovery from the retained event stream remains a
separate private artifact. It does not change the original RB05 result:
functional PASS, operational acceptance FAIL, partial raw-diagnostic retention,
and supplemental recovery PASS.

## Corrected boundary

After a literal transfer into the private 0700 staging directory, the broker
opens the path without following symbolic links. It requires matching pathname
and descriptor identities, current-user ownership, regular-file type and one
hard link. It applies mode 0600 through the verified descriptor, synchronizes
metadata, and repeats all identity and mode checks before the existing size,
hash, credential and destination-publication gates run unchanged.

Symlinks, hardlinks, nonregular files, ownership mismatches, identity races,
normalization failures, hash mismatches, oversized files, credential-shaped
content and destination conflicts remain fail-closed. Successful retained files
finish in mode 0600 without content changes.

RB-PILOT-01 through RB-PILOT-05 identities, claims, receipts, runtime bindings
and historical wheels remain unchanged. RB05 remains consumed. Codex remains
0.164.0 with Sol/xhigh, production security remains unqualified, and
operational admission remains separately gated.
