"""Measured external artifact service and independent RWP-04 fixture trust roots."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import MethodType
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_journal_transport_v3 import ReadResultV3, ReadStatusV3
from review_broker.identity import canonical_bytes
from review_broker.prepared_artifact_transport_v3 import PreparedArtifactBudgetV3, PreparedMetadataReaderV3
from review_broker.github_prepared_worker_history_v3 import GitHubPreparedWorkerHistoryV3
from review_broker.github_prepared_artifact_v3 import (
    GitHubPreparedArtifactV3, PreparedArtifactUploaderV3, PreparedUploadResultV3, UploadStatusV3,
)
from review_broker.pre_model_remote_retention_v3 import PreModelRemoteRetentionV3
from tests.issue70_rwp03_test_support import RealContinuationScenario
from tests.issue70_rwp02_test_support import PRINCIPAL, REPO_ID, RUN_ID, SHA, JOB_ID

BUDGET = PreparedArtifactBudgetV3(2_000_000, 4_000_000, 100, 5, 200_000)
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


class ArtifactService:
    """External injected service; effects counted separately from broker results."""
    def __init__(self, scenario):
        self.s = scenario
        self.uploads, self.downloads, self.resolutions = [], [], []
        self.metadata_calls = []
        self.storage_headers = []
        self.archive = None
        self.artifacts = []
        self.lost_upload_response = False
        self.refuse_upload = False
        self.upload_hook = None
        self.metadata_hook = None
        self.storage_hook = None
        self.redirect = "https://fixture.blob.core.windows.net/private/archive?sig=fixture"
        self.run, self.jobs = copy.deepcopy(scenario.worker.api.run), copy.deepcopy(scenario.worker.api.jobs)
        self.pages = {}

    def upload_once(self, plan, archive, *, before_effect):
        before_effect()
        self.uploads.append((plan, archive))
        if self.refuse_upload: return PreparedUploadResultV3(UploadStatusV3.REFUSED)
        if self.upload_hook: self.upload_hook("before", before_effect)
        before_effect()
        self.archive = archive
        self.artifacts = [dict(id=991, name=plan.artifact_name, digest="sha256:" + hashlib.sha256(archive).hexdigest(),
            size_in_bytes=len(archive), expired=False, created_at="2026-11-05T00:00:00Z",
            expires_at="2026-12-05T00:00:00Z", workflow_run=dict(
                id=RUN_ID, repository_id=REPO_ID, head_repository_id=REPO_ID, head_sha=SHA))]
        if self.upload_hook: self.upload_hook("after", before_effect)
        if self.lost_upload_response: raise OSError("fixture response lost after remote creation")
        return PreparedUploadResultV3(UploadStatusV3.ACK)

    def metadata(self, request, *, max_bytes):
        assert request.get_method() == "GET"
        self.metadata_calls.append(request.full_url)
        path = urlsplit(request.full_url).path
        if self.metadata_hook: self.metadata_hook(request)
        if request.full_url in self.pages:
            return self.pages[request.full_url]
        if path.endswith(f"/actions/runs/{RUN_ID}/attempts/1"):
            body = self.run
        elif path.endswith(f"/actions/runs/{RUN_ID}/attempts/1/jobs"):
            body = dict(total_count=len(self.jobs), jobs=self.jobs)
        elif path.endswith(f"/actions/runs/{RUN_ID}/artifacts"):
            assert "name" in parse_qs(urlsplit(request.full_url).query)
            body = dict(total_count=len(self.artifacts), artifacts=self.artifacts)
        elif path.endswith("/actions/artifacts/991/zip"):
            self.resolutions.append(path)
            return HttpResponseV3(302, b"", {"Location": self.redirect})
        elif path == f"/repos/{self.s.worker.expected.repository}":
            body = dict(id=REPO_ID, node_id=self.s.worker.journal.repository_node_id,
                        full_name=self.s.worker.expected.repository)
        else:
            return HttpResponseV3(404, b"{}", {})
        raw = json.dumps(body, separators=(",", ":")).encode()
        if len(raw) > max_bytes: raise ValueError("fixture response budget")
        return HttpResponseV3(200, raw, {})

    def storage(self, request, *, max_bytes):
        self.downloads.append(request.full_url)
        self.storage_headers.append(dict(request.header_items()))
        assert request.full_url == self.redirect
        for offset in range(0, len(self.archive), 97):
            if self.storage_hook: self.storage_hook(offset)
            yield self.archive[offset:offset + 97]


def install_historical_reads(transport):
    def read_at(self, sha):
        return ReadResultV3(ReadStatusV3.FOUND, self.commits[sha]) if sha in self.commits else ReadResultV3(ReadStatusV3.MISSING)
    transport.read_journal_commit = MethodType(read_at, transport)


class RemoteScenario:
    def __init__(self, root: Path, *, no_remote=False):
        if no_remote:
            with patch("tests.issue70_test_support.AuthenticatedScenario", NoRemoteAuthenticatedScenario):
                self.s = RealContinuationScenario(root)
        else:
            self.s = RealContinuationScenario(root)
        self.handoff = self.s.continuation.run(self.s.worker.context)
        if self.handoff.status.value != "COMMITTED": raise AssertionError(self.handoff.reason)
        self.verification = self.s.verification()
        install_historical_reads(self.s.worker.transport)
        self.service = ArtifactService(self.s)
        self.adapter = self.make_adapter()
        self.uploader = PreparedArtifactUploaderV3(self.service)
        self.continuation = PreModelRemoteRetentionV3(producer=self.s.continuation,
            retention_base=root/"retained", verification=self.verification,
            uploader=self.uploader, adapter=self.adapter, remote_verification_root=root/"downloaded")

    def make_adapter(self, budget=BUDGET, clock=lambda: NOW):
        metadata = PreparedMetadataReaderV3(token="fixture-github-credential", repository=self.s.worker.expected.repository,
                                             executor=self.service.metadata, budget=budget)
        worker = GitHubPreparedWorkerHistoryV3(metadata, self.s.worker.expected,
                                               self.s.worker.dispatch_authority, PRINCIPAL)
        return GitHubPreparedArtifactV3(metadata=metadata, worker_history=worker,
            storage_executor=self.service.storage, budget=budget, clock=clock)

    def run(self):
        return self.continuation.run(self.s.worker.context, self.handoff)

    def readback(self, destination):
        from review_broker.prepared_packet_readback_v3 import readback_prepared_packet_v3
        return readback_prepared_packet_v3(journal=self.s.worker.journal,
            request_id=self.s.worker.admission.request_id, adapter=self.adapter,
            source_authority=self.s.source_authority, selection_authority=self.s.selection_authority,
            destination=destination)


from tests.issue70_test_support import AuthenticatedScenario


class NoRemoteAuthenticatedScenario(AuthenticatedScenario):
    """Independently admit an empty-reference request through real admission."""
    def __init__(self, root):
        super().__init__(root)
        from review_broker.admission_v3 import admit_initial_inline_v3
        from review_broker.github_requester_authority_v3 import GitHubRequesterAuthorityV3
        from tests.request_v3_test_support import HistoryAuthority, origin
        self.request = {**self.request, "references": []}
        self.git_readers, self.issue_readers = {}, {}
        reader = origin(self.request)
        observed = reader.observe(51)
        authority = GitHubRequesterAuthorityV3(requester_id=observed.requester_id,
            broker_issue_id=observed.issue_id, origin_evidence_id=observed.evidence_id, authorized=True)
        self.admission = admit_initial_inline_v3(reader, broker_issue_number=51,
            expected_broker_issue_id=6106789428, expected_requester_id=30498238,
            requester_authority=authority, pr_authority=self.pr_reader, source_authority=self.source,
            history_authority=HistoryAuthority(), git_file_readers={}, issue_reference_readers={})
