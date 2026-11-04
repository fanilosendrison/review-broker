"""Independent deterministic policy archives for offline RWP-03 tests only."""
from dataclasses import replace
from datetime import datetime, timezone
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from review_broker.github_actions_identity_v3 import GitHubActionsExpectationV3, GitHubActionsIdentityReaderV3
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.journal_record_v3 import WorkerIdentityV3, decode_journal_v2
from tests.issue70_rwp01_test_support import MeasuredTransport
from tests.issue70_rwp02_test_support import MeasuredWorkerTransport, ScopedPredecessor, WorkerScenario
from review_broker.pre_model_policy_source_v3 import PolicySourceObservationV3
from review_broker.pre_model_policy_selection_v3 import (
    PolicySelectionContextV3, PolicySelectionReceiptV3,
)

# Independent fixture, never populated from the producer's policy read or receipt.
POLICY_BYTES = b'{"kind":"pre-model-expected-technical-policy","policy_name":"review-broker","policy_revision":1,"requirements":{"allow_login_shell":false,"approval_policy":"never","credential_material_access":"deny","filesystem_minimal":"read","include_environment_context":false,"include_environment_context_time":false,"network_enabled":false,"packet_directory":"read","reviewed_source_execution":"forbidden","reviewer_home":"deny","shell_environment_inheritance":"none","trusted_workspace":"deny"},"reviewer":{"backend":"codex-cli","model":"gpt-5.6-sol","reasoning_effort":"xhigh"},"schema_version":1}\n'
DIGEST = "6f9c0d9ed04cc708fd633bb7ed12e168338d1c91e92456f7a7188205deb63e63"
CONTENT_ID = "technical-policy:sha256:f8bc47647605790cc41fbc51f801bd702617ab96da50d8807a15ed442800c024"
SHA = "c" * 40
REPOSITORY = "fanilosendrison/review-broker"
PATH = ".github/workflows/v3-pre-model-worker.yml"
REF = "refs/heads/experimental-worker"
EXPECTED = GitHubActionsExpectationV3(
    REPOSITORY, 1433701208, 77, PATH, f"{REPOSITORY}/{PATH}@{REF}", REF,
    "workflow_dispatch", SHA, SHA, "worker", "worker", True,
    "Experimental v3 pre-model Worker (disarmed)",
)
SOURCE = PolicySourceObservationV3(
    1, "v3-broker-policy-source-observation", REPOSITORY, 1433701208, SHA, SHA,
    "src/review_broker/profiles/pre-model-v3-expected-policy.json",
    "5bdd27d4d8fd66b591f07a6d165a73aca15a50de", DIGEST, 589,
    artifact_identity(b"independent-fixture-source-archive"),
)
CONTEXT = PolicySelectionContextV3(
    "request:sha256:" + "1" * 64, "review-intent:sha256:" + "2" * 64,
    "attempt:sha256:" + "3" * 64, "refs/review-broker/claims/fixture", 1,
    "fixture-reservation", WorkerIdentityV3(70001, 1), "d" * 40,
)
SELECTION = PolicySelectionReceiptV3(
    1, "v3-broker-policy-selection", REPOSITORY, 1433701208, SHA, SHA,
    SOURCE.source_path, SOURCE.evidence_id, "review-broker", 1, DIGEST, CONTENT_ID,
    CONTEXT.request_id, CONTEXT.review_intent_id, CONTEXT.attempt_id, CONTEXT.claim_ref,
    1, CONTEXT.reservation_id, CONTEXT.worker, CONTEXT.admitted_commit_sha,
    artifact_identity(b"independent-fixture-approved-decision"),
)


class ContinuationTransport(MeasuredWorkerTransport):
    """Add measurement of normal state transitions without changing RWP-02 fixtures."""

    def update_ref(self, update):
        entry = decode_journal_v2(self.commits[update.after_oid].journal_bytes).attempt.history[-1]
        if "event" in entry:
            return super().update_ref(update)
        event = entry["state"]
        self.events.append(event)
        if self.event_hook:
            self.event_hook(event)
        if self.crash_event == event and not self.crash_after_apply:
            raise RuntimeError("synthetic interruption before application")
        result = MeasuredTransport.update_ref(self, update)
        with self.lock:
            if self.refs[update.name] == update.after_oid and update.after_oid not in self.applied:
                self.applied.append(update.after_oid)
            if self.crash_event == event:
                raise RuntimeError("synthetic interruption after application")
            if result.writer_evidence_id:
                self.attributed.add(update.after_oid)
        hook = getattr(self, "after_update_hook", None)
        if hook is not None:
            hook(event, result)
        return result


class ContinuationWorkerScenario(WorkerScenario):
    def __init__(self, admission):
        super().__init__(admission)
        self.transport = ContinuationTransport()
        self.journal.transport = self.transport
        self.journal.predecessor_authority = ScopedPredecessor(self.transport)


class FixturePolicySourceAuthority:
    """Pinned external fixture archive; not real GitHub source attestation."""

    def read_policy(self, expectation, *, before_effect):
        before_effect()
        self.verify_source(SOURCE, POLICY_BYTES, expectation, before_effect=before_effect)
        return POLICY_BYTES, SOURCE

    def verify_source(self, observation, original_bytes, expectation, *, before_effect=None):
        if before_effect is not None: before_effect()
        if (observation != SOURCE or original_bytes != POLICY_BYTES
                or expectation != EXPECTED):
            raise ValueError("fixture source object not independently recognized")


class FixturePolicySelectionAuthority:
    """Fixed owner decision external to receipt parsing and content hashing."""

    def select_policy(self, source, context, expectation, *, before_effect):
        before_effect()
        self.verify_selection(SELECTION, source, context, expectation, before_effect=before_effect)
        return SELECTION

    def verify_selection(self, receipt, source, context, expectation, *, before_effect=None):
        if before_effect is not None: before_effect()
        if (receipt != SELECTION or source != SOURCE or context != CONTEXT
                or expectation != EXPECTED):
            raise ValueError("fixture decision not independently recognized")


class ArchivedSelectionAuthority:
    """Independent fixture decision archive; verification NEVER issues an approval."""
    def __init__(self, archive):
        self.archive = Path(archive)

    def select_policy(self, source, context, expectation, *, before_effect):
        before_effect()
        receipt = PolicySelectionReceiptV3.from_bytes(self.archive.read_bytes())
        self.verify_selection(receipt, source, context, expectation, before_effect=before_effect)
        return receipt

    def verify_selection(self, receipt, source, context, expectation, *, before_effect=None):
        if before_effect is None: raise ValueError("external archive requires effect guard")
        before_effect()
        approved = PolicySelectionReceiptV3.from_bytes(self.archive.read_bytes())
        if (receipt != approved or source != SOURCE or expectation != EXPECTED
                or any(receipt.basis[key] != value for key, value in context.basis.items())):
            raise ValueError("decision absent from independent fixture archive")


class ArchivedJournalAuthority:
    """Cold predecessor recognition from an independently supplied server fixture."""
    def __init__(self, path):
        self.observed = json.loads(Path(path).read_bytes())

    def evidence_id(self, *, snapshot, **values):
        observed = {"commit_sha": snapshot.commit_sha, "parent_sha": snapshot.parent_sha,
                    "journal_bytes_id": artifact_identity(snapshot.journal_bytes)}
        return artifact_identity(canonical_bytes(observed)) if observed == self.observed else None

    def permits_evidence(self, *, snapshot, evidence_id, **values):
        return evidence_id is not None and evidence_id == self.evidence_id(snapshot=snapshot)


def fixture_owner_approval(snapshot, archive, journal_archive):
    """External test-owner observes the simulated server, not a producer receipt.

    Called only by the simulated server's ADMITTED observation hook. The cold
    verifier has no call to this function and cannot generate fresh permission.
    """
    record = snapshot.record
    if record.attempt.state.value != "ADMITTED" or record.control.worker != WorkerIdentityV3(70001, 1):
        raise AssertionError("fixture owner refuses non-ADMITTED or other Worker")
    receipt = replace(SELECTION, request_id=record.attempt.request_id,
        review_intent_id=record.attempt.admission["review_intent_id"],
        attempt_id=record.attempt.attempt_id, claim_ref=snapshot.claim_ref,
        reservation_id=record.control.reservation_id, worker=record.control.worker,
        admitted_commit_sha=snapshot.commit_sha)
    with open(archive, "xb") as stream:
        stream.write(receipt.canonical_receipt_bytes)
    os.chmod(archive, 0o600)
    observation = {"commit_sha": snapshot.commit_sha, "parent_sha": snapshot.parent_sha,
                   "journal_bytes_id": artifact_identity(snapshot.journal_bytes)}
    with open(journal_archive, "xb") as stream:
        stream.write(canonical_bytes(observation) + b"\n")
    os.chmod(journal_archive, 0o600)


class RealContinuationScenario:
    """Actual source/admission/journal/packet functions; only transports injected."""
    def __init__(self, root):
        from tests.issue70_test_support import AuthenticatedScenario
        from tests.issue70_rwp02_test_support import BOUNDARY, PRINCIPAL
        from review_broker.pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
        from review_broker.pre_model_packet_continuation_v3 import PreModelPacketContinuationV3
        from review_broker.pre_model_policy_evidence_retention_v3 import LocalAuthorizedPacketStagesV3
        self.root = Path(root)
        self.inputs = AuthenticatedScenario(self.root)
        self.worker = ContinuationWorkerScenario(self.inputs.admission)
        self.worker.seed()
        assert self.worker.run().status.value == "COMMITTED"
        self.archive = self.root / "independent-owner-approval.json"
        self.transport_archive = self.root / "authenticated-journal-fixture.json"
        self.journal_authority_archive = self.root / "independent-server-observation.json"
        self.source_authority = FixturePolicySourceAuthority()
        self.selection_authority = ArchivedSelectionAuthority(self.archive)
        self.capture_calls = 0
        s = self.worker
        self.authority = CurrentBoundWorkerAuthorityV3(
            journal=s.journal, actions_reader=GitHubActionsIdentityReaderV3(
                "synthetic-token", s.expected.repository, s.expected.repository_id,
                executor=s.api, clock=lambda: datetime(2026, 11, 3, tzinfo=timezone.utc)),
            expected=s.expected, execution_boundary=s.boundary, execution_boundary_id=BOUNDARY,
            dispatch_authority=s.dispatch_authority, dispatch_principal_id=PRINCIPAL)
        def observe(event, result):
            if event == "ADMITTED" and result.writer_evidence_id:
                fixture_owner_approval(s.journal.read(s.admission.request_id), self.archive,
                                      self.journal_authority_archive)
        s.transport.after_update_hook = observe
        self.stages = LocalAuthorizedPacketStagesV3(
            candidate_directory=self.root/"candidate", retention_base=self.root/"retained",
            verification=self.verification, cold_verifier=self.cold)
        self.continuation = PreModelPacketContinuationV3(
            journal=s.journal, current_worker_authority=self.authority,
            original_admission=s.admission, capture_provider=self,
            reference_readers=self.reference_readers, policy_source_authority=self.source_authority,
            policy_selection_authority=self.selection_authority, packet_stages=self.stages)

    def verification(self):
        from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
        s = self.worker
        return AuthorizedPolicyVerificationV3(s.journal, s.journal.read(s.admission.request_id),
            s.expected, self.source_authority, self.selection_authority)

    def reference_readers(self, guard):
        result = {}
        for identifier, reader in self.inputs.issue_readers.items():
            clone = copy.copy(reader)
            executor = reader._executor
            def execute(request, executor=executor):
                guard()
                return executor(request)
            clone._executor = execute
            result[identifier] = clone
        return result

    def capture(self, admission, before_effect):
        import review_broker.github_subject_capture_v3 as capture_module
        from tests.issue69_test_support import TOKEN, local_acquirer
        before_effect()
        self.capture_calls += 1
        reader = copy.copy(self.inputs.pr_reader)
        execute = reader._executor
        def guarded_execute(request):
            before_effect()
            return execute(request)
        reader._executor = guarded_execute
        scope = reader.observe_scope()
        acquire = local_acquirer(self.inputs.root / "subject")
        def guarded_acquire(destination, environment):
            import shutil
            before_effect()
            run, tree, copy_file, copy_metadata = subprocess.run, shutil.copytree, shutil.copy2, shutil.copystat
            def guarded_run(*args, **kwargs):
                before_effect()
                return run(*args, **kwargs)
            def guarded_file(*args, **kwargs):
                before_effect()
                return copy_file(*args, **kwargs)
            def guarded_metadata(*args, **kwargs):
                before_effect()
                return copy_metadata(*args, **kwargs)
            def guarded_tree(*args, **kwargs):
                before_effect()
                if len(args) < 5: kwargs.setdefault("copy_function", guarded_file)
                return tree(*args, **kwargs)
            with patch.object(subprocess, "run", guarded_run), patch.object(
                    shutil, "copytree", guarded_tree), patch.object(shutil, "copystat", guarded_metadata):
                return acquire(destination, environment)
        popen = capture_module._popen
        def guarded_popen(*args, **kwargs):
            before_effect()
            return popen(*args, **kwargs)
        before_effect()
        from functools import partial
        from review_broker.packet_v2 import GuardedPacketGitReaderV3
        with patch.object(capture_module, "_popen", guarded_popen), patch.object(
                capture_module, "GitSourceReader",
                partial(GuardedPacketGitReaderV3, before_effect=before_effect)):
            capture = capture_module.capture_authenticated_subject_v3(
                scope, reader, self.inputs.source.authorize(scope.repository, scope.repository_id),
                self.inputs.source.scope_observation.evidence_id, TOKEN,
                self.root/"continued-source", acquire_repository=guarded_acquire)
        observation = reader.finalize(scope, capture)
        return capture_module.bind_authenticated_capture_v3(
            capture, self.inputs.source.authorize(scope.repository, scope.repository_id).evidence_id,
            observation.evidence_id)

    def cold(self, retained, snapshot, before_effect=None):
        from tests.issue68_test_support import IntegratedScenario
        if before_effect is None: before_effect = self.verification().before_effect
        archive = self.transport_archive
        class GuardedArchive:
            def write_bytes(self, data):
                before_effect()
                return archive.write_bytes(data)
        IntegratedScenario.save_transport(self.worker, GuardedArchive())
        before_effect()
        process = subprocess.run([sys.executable, "-m", "tests.issue70_rwp03_test_support",
            str(retained), str(self.transport_archive), str(self.archive),
            str(self.journal_authority_archive), snapshot.record.attempt.request_id], capture_output=True, text=True,
            env={key: value for key, value in os.environ.items() if key != "PYTHONHOME"},
            timeout=90, check=True)
        return json.loads(process.stdout)


def alternate_admission(scenario):
    """Independently admit the same request under a different origin authorization."""
    from review_broker.admission_v3 import admit_initial_inline_v3
    from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
    from tests.request_v3_test_support import HistoryAuthority, origin
    inputs = scenario.inputs
    reader = origin(inputs.request, login="independently-observed-owner")
    observed = reader.observe(51)
    authority = GitHubRequesterAuthorityV3(
        requester_id=observed.requester_id, broker_issue_id=observed.issue_id,
        origin_evidence_id=observed.evidence_id, authorized=True)
    return admit_initial_inline_v3(
        reader, broker_issue_number=51, expected_broker_issue_id=6106789428,
        expected_requester_id=30498238, requester_authority=authority,
        pr_authority=inputs.pr_reader, source_authority=inputs.source,
        history_authority=HistoryAuthority(), git_file_readers=inputs.git_readers,
        issue_reference_readers=inputs.issue_readers)


def cold_probe():
    from tests.issue68_test_support import restore_transport, ExactAdmissionAuthority, REPOSITORY
    from tests.journal_v3_test_support import BASE_SHA, NODE_ID, TrustedMutationAuthority, TrustedRejectionAuthority
    from review_broker.github_journal_v3 import GitHubJournalV3
    from review_broker.packet_retention_v3 import load_packet_evidence_v3
    from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
    retained, transport_path, archive, journal_authority_archive, request_id = sys.argv[1:]
    with patch("socket.socket.connect", side_effect=AssertionError("COLD_NETWORK_FORBIDDEN")):
        transport = restore_transport(Path(transport_path))
        raw = transport.commits[transport.refs[GitHubJournalV3.claim_ref(request_id)]].journal_bytes
        admission = json.loads(raw)["admission"]
        journal = GitHubJournalV3(REPOSITORY, NODE_ID, BASE_SHA, transport,
            ExactAdmissionAuthority(admission), TrustedMutationAuthority(),
            TrustedRejectionAuthority(), ArchivedJournalAuthority(journal_authority_archive))
        snapshot = journal.read(request_id)
        verification = AuthorizedPolicyVerificationV3(journal, snapshot, EXPECTED,
            FixturePolicySourceAuthority(), ArchivedSelectionAuthority(archive))
        _, _, _, manifest = load_packet_evidence_v3(Path(retained), admission,
                                                   policy_verification=verification)
        sys.stdout.write(json.dumps(manifest))


if __name__ == "__main__":
    cold_probe()
