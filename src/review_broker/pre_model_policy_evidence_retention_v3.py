"""Private local authorized-policy evidence and explicit packet lifecycle adapter."""
from __future__ import annotations

from dataclasses import replace
import ctypes
import os
import sys
from pathlib import Path
from typing import Callable

from .admission_v3 import PreclaimAdmissionV3
from .github_journal_transport_v3 import VerifiedJournalSnapshotV3
from .packet_v2_subject import SubjectCaptureV2
from .packet_v2_technical_policy import (
    AuthorizedPolicySnapshotV3, AuthorizedPolicyVerificationV3, PacketV2CandidateError,
)
from .pre_model_policy_selection_v3 import PolicySelectionReceiptV3
from .pre_model_policy_source_v3 import PolicySourceObservationV3

POLICY_EVIDENCE_NAMES = frozenset({
    "expected-policy.bin", "policy-source-observation.json", "policy-selection-receipt.json",
})


def persist_policy_evidence_v3(root: Path, profile: AuthorizedPolicySnapshotV3,
                               verification: AuthorizedPolicyVerificationV3) -> None:
    """Only exclusive private staged writes; caller owns atomic final publication."""
    for name, data in (
        ("expected-policy.bin", profile.original_bytes),
        ("policy-source-observation.json", profile.source.canonical_receipt_bytes),
        ("policy-selection-receipt.json", profile.selection.canonical_receipt_bytes),
    ):
        verification.before_effect()
        descriptor = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb", buffering=0) as stream:
            verification.before_effect()
            stream.write(data)
            verification.before_effect()
            os.fsync(stream.fileno())
        verification.before_effect()


def load_policy_evidence_v3(root: Path,
                            verification: AuthorizedPolicyVerificationV3 | None,
                            admission: PreclaimAdmissionV3) -> AuthorizedPolicySnapshotV3:
    if type(verification) is not AuthorizedPolicyVerificationV3:
        raise PacketV2CandidateError("RETAINED_POLICY_INDEPENDENT_AUTHORITY_REQUIRED")
    verification.require_admission(admission.journal_admission())
    # The containing retained tree is checked before any file is interpreted.
    def read(name):
        verification.before_effect()
        return (root / name).read_bytes()
    profile = AuthorizedPolicySnapshotV3(
        read("expected-policy.bin"),
        PolicySourceObservationV3.from_bytes(read("policy-source-observation.json")),
        PolicySelectionReceiptV3.from_bytes(read("policy-selection-receipt.json")),
    )
    verification.verify(profile, admission)
    return profile


def rename_exclusive_policy_tree_v3(staging: Path, destination: Path, *,
                                    before_effect: Callable[[], None]) -> None:
    """Native atomic directory rename with no replacement, on macOS and Linux."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        operation, flags = library.renameatx_np, 0x00000004  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        operation, flags = library.renameat2, 1  # RENAME_NOREPLACE
    else:
        raise PacketV2CandidateError("RETENTION_EXCLUSIVE_RENAME_UNSUPPORTED")
    operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    # Absolute names make AT_FDCWD irrelevant; Darwin and Linux use different values.
    cwd = -2 if sys.platform == "darwin" else -100
    before_effect()
    if operation(cwd, os.fsencode(staging.absolute()), cwd,
                 os.fsencode(destination.absolute()), flags) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def observe_path_v3(operation, before_effect=None):
    """One filesystem observation; absent guard is only the legacy synthetic path."""
    if before_effect is not None: before_effect()
    return operation()


def policy_tree_paths_v3(root: Path, before_effect=None):
    """Walk without symlink traversal, guarding each directory enumeration."""
    yield root
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in observe_path_v3(lambda: tuple(directory.iterdir()), before_effect):
            yield path
            if (not observe_path_v3(path.is_symlink, before_effect)
                    and observe_path_v3(path.is_dir, before_effect)):
                pending.append(path)


def require_private_policy_tree_v3(root: Path, before_effect=None) -> None:
    for path in policy_tree_paths_v3(root, before_effect):
        if (observe_path_v3(path.is_symlink, before_effect)
                or not (observe_path_v3(path.is_file, before_effect)
                        or observe_path_v3(path.is_dir, before_effect))
                or observe_path_v3(path.stat, before_effect).st_mode & 0o077):
            raise PacketV2CandidateError("RETAINED_AUTHORIZED_TREE_NOT_PRIVATE_REGULAR")


class LocalAuthorizedPacketStagesV3:
    """Real candidate packet/verifier/retention calls, no remote or model interfaces.

    The cold verifier is an independent injected process boundary and must not
    inherit this adapter's mutable admission/capture/profile members.
    """

    def __init__(self, *, candidate_directory: Path, retention_base: Path,
                 verification: Callable[[], AuthorizedPolicyVerificationV3],
                 cold_verifier: Callable[[Path, VerifiedJournalSnapshotV3, Callable[[], None]], dict[str, object]]):
        self.candidate_directory, self.retention_base = candidate_directory, retention_base
        self.verification_factory, self.cold_verifier = verification, cold_verifier
        self._inputs = None

    def build(self, admission, capture, policy_bytes, source, selection,
              selection_context, readers, before_effect):
        profile = AuthorizedPolicySnapshotV3(policy_bytes, source, selection)
        # The factory must pin its trusted snapshot independently of receipt bytes.
        verification = self.verification_factory()
        verification = replace(verification, effect_guard=before_effect)
        if verification.selection_context(admission.request) != selection_context:
            raise PacketV2CandidateError("PACKET_STAGE_SELECTION_CONTEXT_MISMATCH")
        from .packet_v2 import build_packet_v2_candidate
        build_packet_v2_candidate(admission, capture, profile, self.candidate_directory,
                                  readers, policy_verification=verification)
        self._inputs = admission, capture, profile, verification, readers
        return self.candidate_directory

    def verify(self, candidate, before_effect):
        before_effect()
        admission, capture, profile, verification, _ = self._require_inputs(candidate)
        from .packet_v2 import verify_packet_v2_candidate
        return verify_packet_v2_candidate(candidate, admission, capture, profile,
                                           policy_verification=verification)

    def persist(self, candidate, snapshot, before_effect):
        from .packet_retention_v3 import persist_packet_evidence_v3, packet_retention_locator_v3
        admission, capture, profile, verification, readers = self._require_inputs(candidate)
        if snapshot != verification.snapshot:
            raise PacketV2CandidateError("PACKET_STAGE_ADMITTED_SNAPSHOT_MISMATCH")
        before_effect()
        persist_packet_evidence_v3(admission, capture, profile, self.retention_base, snapshot,
                                   verification.journal, readers, policy_verification=verification,
                                   candidate_directory=candidate)
        return packet_retention_locator_v3(self.retention_base, snapshot.claim_ref)

    def cold_verify(self, retained, snapshot, before_effect):
        before_effect()
        return self.cold_verifier(retained, snapshot, before_effect)

    def _require_inputs(self, candidate):
        if self._inputs is None or candidate != self.candidate_directory:
            raise PacketV2CandidateError("PACKET_STAGE_CANDIDATE_NOT_BOUND")
        return self._inputs
