"""Closed non-authoritative counters and monotonic phase durations; no request material."""
from collections import Counter
from contextlib import contextmanager
from functools import wraps
import json
import math
import time
from urllib.parse import urlsplit

PHASES = frozenset({'ACK_GATE', 'SOURCE_B_CAPTURE', 'WORKER_BINDING', 'ADMITTED',
    'PACKET_BUILD_VERIFY', 'LOCAL_RETENTION', 'LOCAL_COLD_VERIFY', 'ARTIFACT_UPLOAD',
    'ARTIFACT_READBACK', 'PREPARED_CAS', 'FINAL_COLD_RECONSTRUCTION'})
COUNTERS = frozenset({'TOTAL_GITHUB_READS', 'JOURNAL_REF_READS', 'JOURNAL_IMMUTABLE_READS',
    'ACTIONS_WORKFLOW_READS', 'ACTIONS_RUN_READS', 'ACTIONS_JOB_READS',
    'ACK_RECONSTRUCTION_COUNT', 'FULL_CURRENT_AUTH_COUNT', 'WORKER_IDENTITY_COUNT',
    'SOURCE_READS', 'ARTIFACT_METADATA_READS', 'ARTIFACT_STORAGE_READS'})


class PreModelObservationDiagnosticsV3:
    def __init__(self, sink=None):
        self.counts, self.seconds, self.completed = Counter(), Counter(), Counter()
        self.sink = sink

    def count(self, category):
        if category in COUNTERS:
            self.counts[category] = min(self.counts[category] + 1, 1_000_000)

    def http(self, request, *, source=False, artifact=False):
        # Never retain URL, headers, query, body or provider exception material.
        path = urlsplit(request.full_url).path
        if request.get_method() != 'GET':
            if path != '/graphql': return
            try:
                if not json.loads(request.data)['query'].startswith('query'): return
            except (ValueError, TypeError, KeyError):
                return
        self.count('TOTAL_GITHUB_READS')
        if source: self.count('SOURCE_READS')
        elif artifact and '/artifacts' in path: self.count('ARTIFACT_METADATA_READS')
        elif '/git/ref/' in path: self.count('JOURNAL_REF_READS')
        elif '/git/' in path: self.count('JOURNAL_IMMUTABLE_READS')
        elif '/actions/runs/' in path:
            self.count('ACTIONS_JOB_READS' if path.endswith('/jobs') else 'ACTIONS_RUN_READS')
        elif '/actions/workflows/' in path: self.count('ACTIONS_WORKFLOW_READS')

    def wrap(self, executor, *, source=False):
        def execute(request):
            try:
                self.http(request, source=source)
            except Exception:
                pass
            return executor(request)
        return execute

    @contextmanager
    def phase(self, name):
        if name not in PHASES:
            raise ValueError('UNKNOWN_PREMODEL_DIAGNOSTIC_PHASE')
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            if math.isfinite(elapsed) and elapsed >= 0:
                self.seconds[name] += elapsed
                self.completed[name] += 1
            if self.sink is not None:
                try:
                    self.sink(self.as_dict())
                except Exception:
                    pass  # Diagnostic delivery cannot change authority, result or one-shot state.

    def as_dict(self):
        return {'schema_version': 1, 'scope': 'non-authoritative-pre-model-observation',
                'counts': dict(self.counts),
                'phase_seconds': {k: round(v, 6) for k, v in self.seconds.items()},
                'phase_completions': dict(self.completed)}


def measured_phase_v3(name):
    """Optional diagnostics over an existing module boundary, never a guard."""
    def decorate(method):
        @wraps(method)
        def measured(self, *args, **kwargs):
            diagnostics = getattr(self, 'diagnostics', None)
            if diagnostics is None:
                return method(self, *args, **kwargs)
            with diagnostics.phase(name):
                return method(self, *args, **kwargs)
        return measured
    return decorate
