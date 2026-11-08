"""Protected broker-code policy provenance and original-decision selection, not effective policy."""
from .github_git_file_v3 import GitHubGitFileReaderV3
from .github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID
from .identity import artifact_identity,canonical_bytes
from .pre_model_policy_source_v3 import PolicySourceObservationV3
from .pre_model_policy_selection_v3 import PolicySelectionReceiptV3
from .pre_model_policy_v3 import POLICY_SOURCE_PATH,parse_expected_policy_v3
from .prepared_journal_history_v3 import require_snapshot_origin_v3,require_journal_admission_origin_v3
from .pre_model_dispatch_ack_v3 import acknowledgment_from_record


class GitHubProtectedPolicyAuthorityV3:
    def __init__(self,*,api,journal,expected,dispatch_authority,selection_guard=None):
        self.api,self.journal,self.expected,self.dispatch=api,journal,expected,dispatch_authority
        self.selection_guard=selection_guard
        self._source=None
        self._verified_selection=None

    def _require_expected(self,expected):
        if expected!=self.expected or expected.repository!=REPOSITORY or expected.repository_id!=REPOSITORY_ID:
            raise ValueError('POLICY_EXECUTABLE_AUTHORITY_MISMATCH')

    def read_policy(self,expectation,*,before_effect):
        self._require_expected(expectation);before_effect()
        if self._source is None:
            # This reader is scoped to broker-owned executable policy, never subject
            # or references. Its qualification-only label is not source-App authority.
            authority=artifact_identity(canonical_bytes({'evidence_type':'github-protected-broker-policy-source',
                'repository':REPOSITORY,'repository_id':REPOSITORY_ID,
                'executable_sha':expectation.executing_source_sha,'source_path':POLICY_SOURCE_PATH})+b'\n')
            reader=GitHubGitFileReaderV3(self.api.token,REPOSITORY,REPOSITORY_ID,
                authority_evidence_id=authority,qualification_only=True,executor=self.api.execute)
            value=reader.observe(expectation.executing_source_sha,POLICY_SOURCE_PATH)
            observation=PolicySourceObservationV3(1,'v3-broker-policy-source-observation',
                REPOSITORY,REPOSITORY_ID,expectation.executing_source_sha,value.commit_sha,
                POLICY_SOURCE_PATH,value.git_blob_oid,value.sha256,value.original_byte_length,authority)
            parse_expected_policy_v3(value.original_bytes)
            self._source=value.original_bytes,observation
        before_effect()
        return self._source

    def verify_source(self,observation,original_bytes,expectation,*,before_effect=None):
        if before_effect is None:raise ValueError('POLICY_OBSERVATION_GUARD_REQUIRED')
        self._require_expected(expectation);before_effect()
        data,expected=self.read_policy(expectation,before_effect=before_effect)
        if observation!=expected or original_bytes!=data:raise ValueError('POLICY_SOURCE_UNRECOGNIZED')

    def _receipt(self,source,context,expectation,before_effect):
        self._require_expected(expectation);before_effect()
        a=self.journal.read_at(context.request_id,context.admitted_commit_sha)
        require_snapshot_origin_v3(self.journal,a);require_journal_admission_origin_v3(self.journal,a)
        control=a.record.control;admission=a.record.attempt.admission;ack=acknowledgment_from_record(a.record)
        if (a.record.attempt.state.value!='ADMITTED' or control.disposition!='RESERVED'
                or control.failure_receipt_id is not None or control.generation!=1
                or context.generation!=1 or context.claim_ref!=a.claim_ref
                or context.attempt_id!=a.record.attempt.attempt_id
                or context.review_intent_id!=admission['review_intent_id']
                or context.reservation_id!=control.reservation_id or context.worker!=control.worker
                or ack is None or ack.workflow_run_id!=context.worker.run_id
                or ack.executable_sha!=expectation.executing_source_sha):
            raise ValueError('POLICY_SELECTION_JOURNAL_AUTHORITY_MISMATCH')
        self.dispatch.principal_id(ack)
        data,original=self.read_policy(expectation,before_effect=before_effect)
        if source!=original:raise ValueError('POLICY_SELECTION_SOURCE_UNRECOGNIZED')
        policy=parse_expected_policy_v3(data)
        decision=artifact_identity(canonical_bytes({'schema_version':1,
            'evidence_type':'github-protected-pre-model-policy-selection',
            'policy_source_evidence_id':source.evidence_id,'executable_sha':expectation.executing_source_sha,
            'workflow_id':expectation.workflow_id,**context.basis})+b'\n')
        return PolicySelectionReceiptV3(1,'v3-broker-policy-selection',REPOSITORY,REPOSITORY_ID,
            expectation.executing_source_sha,source.source_commit_sha,source.source_path,source.evidence_id,
            policy.document['policy_name'],policy.document['policy_revision'],source.original_sha256,
            policy.technical_policy_id,context.request_id,context.review_intent_id,context.attempt_id,
            context.claim_ref,context.generation,context.reservation_id,context.worker,
            context.admitted_commit_sha,decision)

    def select_policy(self,source,context,expectation,*,before_effect):
        if self.selection_guard is None:raise ValueError('OBSERVER_CANNOT_SELECT_POLICY')
        self.selection_guard(context)
        return self._receipt(source,context,expectation,before_effect)

    def verify_selection(self,receipt,source,context,expectation,*,before_effect=None):
        if before_effect is None:raise ValueError('POLICY_OBSERVATION_GUARD_REQUIRED')
        self._require_expected(expectation);before_effect()
        # Immutable selection DATA only. Active selection still requires the original
        # decision; every external effect separately confronts mutable currentness.
        key=(receipt.canonical_receipt_bytes,source.canonical_receipt_bytes,
             canonical_bytes(context.basis),expectation)
        if key==self._verified_selection:return
        if receipt!=self._receipt(source,context,expectation,before_effect):
            raise ValueError('POLICY_SELECTION_UNRECOGNIZED')
        self._verified_selection=key
