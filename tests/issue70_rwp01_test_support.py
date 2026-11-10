"""Measured injected Git server and dispatch fixtures; no live effects."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import threading

from review_broker.github_journal_transport_v3 import (
    CreateRefResultV3, CreateRefStatusV3, TransportSnapshotV3,
)
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.identity import canonical_bytes
from review_broker.journal_record_v3 import JournalRecordV3Error, decode_journal_v2
from review_broker.pre_model_controller_v3 import (
    ControllerAuthorizationV3, PreModelControllerV3,
)
from review_broker.pre_model_dispatch_v3 import (
    InitialDispatchResultV3, InitialDispatchStatusV3, InitialDispatchTargetV3,
)
from tests.issue68_test_support import ExactAdmissionAuthority, REPOSITORY
from tests.journal_v3_test_support import (
    BASE_SHA, NODE_ID, FakeGitHubTransportV3, TrustedMutationAuthority,
    TrustedPredecessorAuthority, TrustedRejectionAuthority,
)

TARGET = InitialDispatchTargetV3(
    "v3-pre-model-worker.yml", "refs/heads/experimental-worker", "c" * 40,
)


def alternate_origin_admission(authenticated):
    """Construct, rather than forge, a valid different-origin admission."""
    from review_broker.admission_v3 import admit_initial_inline_v3
    from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
    from tests.request_v3_test_support import HistoryAuthority, origin
    reader = origin(authenticated.request, issue_id=42)
    observed = reader.observe(51)
    return admit_initial_inline_v3(
        reader, broker_issue_number=51, expected_broker_issue_id=42,
        expected_requester_id=observed.requester_id,
        requester_authority=GitHubRequesterAuthorityV3(
            requester_id=observed.requester_id, broker_issue_id=42,
            origin_evidence_id=observed.evidence_id, authorized=True),
        pr_authority=authenticated.pr_reader, source_authority=authenticated.source,
        history_authority=HistoryAuthority(), git_file_readers=authenticated.git_readers,
        issue_reference_readers=authenticated.issue_readers,
    )


class MeasuredTransport(FakeGitHubTransportV3):
    """Reuse the existing CAS simulation, including identical-target races."""

    def __init__(self):
        super().__init__()
        self.update_barrier = None
        self.identical_commits = False
        self.creation_unknown = False
        self.creation_applies = False
        self.commit_calls = 0
        self.create_calls = 0

    def create_journal_commit(self, parent_sha, journal_bytes):
        with self.lock:
            self.commit_calls += 1
            if self.identical_commits:
                sha = hashlib.sha1(
                    b"simulated-commit:" + parent_sha.encode() + journal_bytes,
                    usedforsecurity=False,
                ).hexdigest()
                self.commits[sha] = TransportSnapshotV3(sha, parent_sha, journal_bytes)
                return sha
            return super().create_journal_commit(parent_sha, journal_bytes)

    def create_ref(self, claim_ref, commit_sha):
        self.create_calls += 1
        if self.creation_unknown:
            if self.creation_applies:
                super().create_ref(claim_ref, commit_sha)
            return CreateRefResultV3(CreateRefStatusV3.UNKNOWN)
        return super().create_ref(claim_ref, commit_sha)

    def update_ref(self, update):
        if self.update_barrier is not None:
            self.update_barrier.wait()
        return super().update_ref(update)


class ExactControllerAuthority:
    """A bounded decision pinned independently, never inferred from API success."""

    def __init__(self, admission):
        self.decision = ControllerAuthorizationV3(
            True, REPOSITORY, NODE_ID, TARGET,
            canonical_bytes(admission.journal_admission()), admission.origin_body_bytes,
        )
        self.calls = []

    def authorize(self, **context):
        self.calls.append(context)
        return self.decision


class RecordingDispatch:
    """Record injected calls and the actual journal state at their boundary."""

    def __init__(self, transport):
        self.transport = transport
        self.calls = []
        self.journal_at_call = []
        self.result = InitialDispatchResultV3(InitialDispatchStatusV3.OBSERVED, 70001)
        self.error = None
        self.lock = threading.Lock()

    def dispatch(self, request):
        with self.lock:
            self.calls.append(request)
            sha = self.transport.refs[request.claim_ref]
            self.journal_at_call.append(self.transport.commits[sha])
        if self.error is not None:
            raise self.error
        return self.result


class ControllerScenario:
    def __init__(self, admission):
        self.admission = admission
        self.transport = MeasuredTransport()
        self.predecessor = TrustedPredecessorAuthority()
        self.journal = GitHubJournalV3(
            REPOSITORY, NODE_ID, BASE_SHA, self.transport,
            ExactAdmissionAuthority(admission.journal_admission()),
            TrustedMutationAuthority(), TrustedRejectionAuthority(), self.predecessor,
        )
        self.authority = ExactControllerAuthority(admission)
        self.dispatch = RecordingDispatch(self.transport)
        self.controller = self.new_controller()

    def new_controller(self):
        return PreModelControllerV3(
            self.journal, TARGET, self.dispatch, self.authority,
        )

    def measurement(self):
        import json
        final = []
        for sha in self.transport.refs.values():
            raw = self.transport.commits[sha].journal_bytes
            try:
                record = decode_journal_v2(raw)
                final.append((record.attempt.state.value, record.control.generation,
                              record.control.disposition, record.control.worker))
            except JournalRecordV3Error:
                final.append(("INVALID_JOURNAL", json.loads(raw)["schema_version"], None, None))
        return {
            "claims_created": self.transport.create_statuses.count(CreateRefStatusV3.CREATED),
            "cas_attempted": len(self.transport.updates),
            "dispatch_calls": len(self.dispatch.calls),
            "final_journal": final,
        }

    def initial_claim(self):
        return self.journal.claim(
            self.admission.request, self.admission.journal_admission(),
        )

    def mismatch_decision(self, **changes):
        self.authority.decision = replace(self.authority.decision, **changes)
