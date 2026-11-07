"""Dual-phase source-App acquisition; no journal/control credential enters this object."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import copy
from typing import Callable

from .admission_v3 import admit_initial_inline_v3
from .github_git_file_v3 import GitHubGitFileReaderV3
from .github_issue_reference_v3 import GitHubIssueReferenceReaderV3
from .github_pull_request_observation_v3 import GitHubPullRequestObservationReaderV3
from .github_requester_authority_v3 import GitHubRequesterAuthorityV3
from .github_source_authority_v3 import GitHubSourceAuthorityV3
from .github_subject_capture_v3 import capture_authenticated_subject_v3, bind_authenticated_capture_v3
from .github_http_live_v3 import urllib_executor
from .github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID
from .packet_retention_v3 import restore_preclaim_bytes_v3
from .request_v3 import parse_issue_envelope_v3

SOURCE_PERMISSIONS=frozenset({'contents:read','pull_requests:read','metadata:read','issues:read'})


class LiveSourceSessionV3:
    def __init__(self,token,*,app_slug,installation_id,root:Path,guard:Callable,
                 executor=urllib_executor,acquire_repository=None,observer=None):
        if app_slug!='review-broker-app':raise ValueError('SOURCE_APP_SLUG_NOT_APPROVED')
        self._token,self.root,self.guard=token,root,guard
        self._executor,self.acquire_repository,self.observer=executor,acquire_repository,observer
        self.closed=False;self._captures=0
        self._admission_issue_gate=None;self._admission_result=None
        self.authority=GitHubSourceAuthorityV3(token,expected_app_slug=app_slug,
            expected_installation_id=installation_id,repository=REPOSITORY,repository_id=REPOSITORY_ID,
            approved_permissions=SOURCE_PERMISSIONS,authorized_repositories=frozenset({REPOSITORY}),
            executor=self.execute)
        self.authority.observe_scope()

    def execute(self,request):
        if self.closed:raise ValueError('SOURCE_PHASE_CLOSED')
        self.guard()
        result=self._executor(request)
        if self.observer is not None:self.observer.http(request,result)
        return result

    def close(self):
        self.closed=True

    def readers(self,request):
        evidence=self.authority.authorize(REPOSITORY,REPOSITORY_ID).evidence_id
        git={};issues={}
        for reference in request['references']:
            kind=reference['source']['kind'];identifier=reference['id']
            options=dict(authority_evidence_id=evidence,source_authority=self.authority,executor=self.execute)
            if kind=='git_file':git[identifier]=GitHubGitFileReaderV3(self._token,REPOSITORY,REPOSITORY_ID,**options)
            elif kind in {'github_issue_body','github_issue_comment'}:
                issues[identifier]=GitHubIssueReferenceReaderV3(self._token,REPOSITORY,REPOSITORY_ID,**options)
        return git,issues

    def capture_request(self,request,guard,*,failure_observer=None,original_source=None):
        self.guard=guard;guard()
        subject=request['subject']
        reader=GitHubPullRequestObservationReaderV3(self._token,subject['repository'],subject['repository_id'],
            subject['pull_request'],subject['expected_head_commit'],source_authority=self.authority,
            executor=self.execute)
        scope=reader.observe_scope()
        if original_source is not None and (scope.pull_request_id!=original_source['pull_request_id']
                or scope.head_sha!=original_source['head_sha'] or scope.base_sha!=original_source['base_sha']):
            raise ValueError('WORKER_SUBJECT_METADATA_NOT_ORIGINAL')
        root=self.root/f'subject-{self._captures}';self._captures+=1
        guard()
        capture=capture_authenticated_subject_v3(scope,reader,
            self.authority.authorize(REPOSITORY,REPOSITORY_ID),self.authority.scope_observation.evidence_id,
            self._token,root,acquire_repository=self.acquire_repository,
            failure_observer=failure_observer,before_effect=guard,transfer_observer=self.observer)
        observation=reader.finalize(scope,capture)
        return reader,bind_authenticated_capture_v3(capture,
            self.authority.authorize(REPOSITORY,REPOSITORY_ID).evidence_id,observation.evidence_id)

    def admit_controller(self,controller,history):
        """Return complete data only; callers discard this token-bearing session before claim."""
        if self._token==controller.runtime.api.token:raise ValueError('CONTROL_TOKEN_IS_NOT_SOURCE_AUTHORITY')
        original=controller.require_current();request=parse_issue_envelope_v3(original.body)
        reader,_=self.capture_request(request,self.guard)
        git,issues=self.readers(request)
        # Same original observation must be used by admission, not a new approval
        # for a changed Issue. Its actual reader still independently reobserves.
        authority=GitHubRequesterAuthorityV3(requester_id=original.requester_id,
            broker_issue_id=original.issue_id,origin_evidence_id=original.evidence_id,authorized=True)
        origin_reader=copy.copy(controller.origin_reader)
        origin_reader._clock=lambda:datetime.fromisoformat(original.observed_at.replace('Z','+00:00'))
        admission=admit_initial_inline_v3(origin_reader,broker_issue_number=controller.issue,
            expected_broker_issue_id=original.issue_id,expected_requester_id=original.requester_id,
            requester_authority=authority,pr_authority=reader,
            source_authority=self.authority,history_authority=history,
            git_file_readers=git,issue_reference_readers=issues)
        issuer=object();self._admission_result=admission;self._admission_issue_gate=issuer
        try:controller.accept_source_admission(self,admission,issuer)
        finally:self._admission_issue_gate=None
        return admission

    def require_original_scope(self,admission):
        source=admission['source_observation'];current=self.authority.authorize(REPOSITORY,REPOSITORY_ID)
        if (admission.get('source_app_scope_evidence_id')!=self.authority.scope_observation.evidence_id
                or source['source_authorization_evidence_id']!=current.evidence_id
                or source['installation_id']!=current.installation_id
                or source['repository_id']!=current.repository_id):
            raise ValueError('WORKER_SOURCE_AUTHORITY_NOT_ORIGINAL')

    def hydrate(self,snapshot,guard,*,failure_observer=None):
        self.guard=guard;value=snapshot.record.attempt.admission
        self.require_original_scope(value);request=value['canonical_request']
        git,issues=self.readers(request)
        if failure_observer is not None:issues=failure_observer.bind_reference_readers(issues)
        references={r['id']:r for r in request['references']}
        def read(identifier):
            guard();r=references[identifier];s=r['source'];kind=s['kind']
            if kind=='git_file':observation=git[identifier].observe(s['commit'],s['path'],s.get('expected_sha256'))
            elif kind=='github_issue_body':observation=issues[identifier].observe_issue_body(s['issue'],s.get('expected_sha256'))
            else:observation=issues[identifier].observe_issue_comment(s['comment_id'],s.get('expected_sha256'))
            return observation.original_bytes
        return restore_preclaim_bytes_v3(value,self.origin_body,read)

    def capture(self,admission,before_effect,*,failure_observer=None):
        self.require_original_scope(admission.journal_admission())
        reader,capture=self.capture_request(admission.request,before_effect,failure_observer=failure_observer,
            original_source=admission.journal_admission()['source_observation'])
        observed=reader.observe(REPOSITORY,REPOSITORY_ID,admission.pull_request)
        expected=admission.journal_admission()['source_observation']
        if (observed.pull_request_id!=admission.pull_request_id or observed.head_sha!=admission.head_sha
                or observed.base_sha!=expected['base_sha'] or observed.evidence_id!=expected['pr_observation_evidence_id']
                or [dict(source_id=x.source_id,original_bytes=x.original_bytes,rendered_bytes=x.rendered_bytes)
                    for x in observed.subject_sources]!=expected['subject_sources']):
            raise ValueError('WORKER_SUBJECT_NOT_ORIGINAL')
        return capture

