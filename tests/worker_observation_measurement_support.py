"""Count genuine composition calls; only external provider fixture transports are doubles."""
from collections import Counter, defaultdict
from contextlib import ExitStack
from functools import wraps
import time
from urllib.parse import urlsplit
from unittest.mock import patch

from tests.live_prep_artifact_provider_support import CompleteProviderService
from tests.live_prep_provider_support import controller_scenario
from tests.test_live_prep_complete_composition import worker_scenario


def category(request):
    path = urlsplit(request.full_url).path
    if '/git/ref/' in path:
        return 'journal_ref'
    if '/git/' in path:
        return 'journal_immutable'
    if '/actions/runs/' in path:
        return 'actions_jobs' if path.endswith('/jobs') else 'actions_runs'
    if '/actions/workflows/' in path:
        return 'controller_reconstruction' if path.endswith('/runs') else 'actions_workflows'
    if '/artifacts' in path:
        return 'artifact_metadata'
    return 'repository_or_issue'


class Measurements:
    def __init__(self):
        self.phase = 'setup'
        self.counts = defaultdict(Counter)
        self.seconds = Counter()

    def count(self, name):
        self.counts[self.phase][name] += 1

    def wrapper(self, method, *, phase=None, name=None):
        @wraps(method)
        def measured(*args, **kwargs):
            previous = self.phase
            if phase:
                self.phase = phase
            start = time.monotonic()
            if name:
                self.count(name)
            try:
                return method(*args, **kwargs)
            finally:
                if phase:
                    self.seconds[phase] += time.monotonic() - start
                self.phase = previous
        return measured

    def install(self, stack):
        from review_broker.pre_model_current_worker_v3 import CurrentBoundWorkerAuthorityV3
        from review_broker.github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
        from review_broker.github_actions_identity_v3 import GitHubActionsIdentityReaderV3
        from review_broker.github_journal_v3 import GitHubJournalV3
        from review_broker.pre_model_worker_v3 import PreModelWorkerV3
        from review_broker.live_source_admission_v3 import LiveSourceSessionV3
        from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
        from review_broker.github_policy_authority_v3 import GitHubProtectedPolicyAuthorityV3
        from review_broker.pre_model_policy_evidence_retention_v3 import LocalAuthorizedPacketStagesV3
        from review_broker.github_prepared_artifact_v3 import GitHubPreparedArtifactV3
        from review_broker.actions_artifact_child_v3 import GitHubActionsArtifactChildV3
        from review_broker.pre_model_remote_retention_v3 import RemoteRetainedPacketAuthorityV3
        methods = [
            (CurrentBoundWorkerAuthorityV3, 'require_current', None, 'full_current_auth'),
            (GitHubActionsDispatchAcknowledgmentAuthorityV3, 'authenticates', None, 'ack_auth'),
            (GitHubActionsDispatchAcknowledgmentAuthorityV3, 'principal_id', None, 'ack_reconstruction'),
            (GitHubActionsIdentityReaderV3, 'observe', None, 'worker_identity'),
            (GitHubJournalV3, 'read', None, 'journal_read'),
            (PreModelWorkerV3, 'run', 'WORKER_BINDING', None),
            (LiveSourceSessionV3, 'hydrate', 'SOURCE_HYDRATE', None),
            (LiveSourceSessionV3, 'capture', 'SOURCE_B_CAPTURE', None),
            (AuthorizedPolicyVerificationV3, 'prepare_references', 'REFERENCE_PREPARATION', None),
            (GitHubProtectedPolicyAuthorityV3, 'select_policy', 'POLICY_SELECTION', None),
            (LocalAuthorizedPacketStagesV3, 'build', 'PACKET_BUILD', None),
            (LocalAuthorizedPacketStagesV3, 'verify', 'PACKET_VERIFY', None),
            (LocalAuthorizedPacketStagesV3, 'persist', 'LOCAL_RETENTION', None),
            (LocalAuthorizedPacketStagesV3, 'cold_verify', 'LOCAL_COLD_VERIFY', None),
            (GitHubActionsArtifactChildV3, 'upload_once', 'ARTIFACT_UPLOAD', None),
            (GitHubPreparedArtifactV3, 'observe', 'ARTIFACT_METADATA', None),
            (GitHubPreparedArtifactV3, 'download', 'ARTIFACT_STORAGE', None),
            (RemoteRetainedPacketAuthorityV3, 'permits', 'PREPARED_PREPARATION', None),
        ]
        for owner, attribute, phase, name in methods:
            stack.enter_context(patch.object(owner, attribute,
                self.wrapper(getattr(owner, attribute), phase=phase, name=name)))
        import review_broker.live_pre_model_worker_v3 as live
        stack.enter_context(patch.object(live, 'collect_api_corpus_v3',
            self.wrapper(live.collect_api_corpus_v3, phase='HISTORICAL_CORPUS')))

    def report(self):
        totals = Counter()
        for counts in self.counts.values():
            totals.update(counts)
        return {'totals': dict(totals), 'phases': {p: dict(c) for p, c in self.counts.items()},
                'phase_seconds': dict(self.seconds)}


class CountingProvider(CompleteProviderService):
    def __init__(self, root, measurement):
        self.measurement = measurement
        self.diagnostic_reports = []
        super().__init__(root)

    def runtime(self, role, inputs):
        runtime = super().runtime(role, inputs)
        if hasattr(runtime, 'diagnostics'):
            runtime.diagnostics.sink = self.diagnostic_reports.append
        return runtime

    def __call__(self, request):
        if request.get_method() == 'GET' or request.full_url.endswith('/graphql'):
            self.measurement.count(category(request))
        return super().__call__(request)

    def source(self, request):
        self.measurement.count('source_reads')
        return super().source(request)

    def metadata(self, request, *, max_bytes):
        if '/artifacts' in request.full_url:
            self.measurement.count('artifact_metadata')
        return super().metadata(request, max_bytes=max_bytes)

    def storage(self, request, *, max_bytes):
        self.measurement.count('artifact_storage')
        yield from super().storage(request, max_bytes=max_bytes)


def measure_complete(root):
    measurement = Measurements()
    service = CountingProvider(root, measurement)
    with ExitStack() as stack:
        measurement.install(stack)
        measurement.phase = 'CONTROLLER'
        controller = controller_scenario(root, service)
        assert controller.status.value == 'DISPATCH_ACKNOWLEDGED', controller
        service.controller_running = False
        measurement.phase = 'ADMITTED_AND_REMOTE_COMPOSITION'
        result = worker_scenario(root, service, controller)
        assert result.cold_verified and result.state == 'PREPARED', result
    return measurement.report(), service, controller, result
