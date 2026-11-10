"""Concrete owner-gated Actions Controller authority and exact original admission recognition."""
from __future__ import annotations

import hashlib
import json
import re

from .admission_evidence_v3 import validate_journal_admission_v3
from .github_issue_origin_v3 import GitHubIssueOriginReaderV3
from .github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID, OWNER_ID, WORKER_PATH, exact_positive
from .identity import artifact_identity, canonical_bytes
from .pre_model_controller_v3 import ControllerAuthorizationV3
from .pre_model_dispatch_v3 import InitialDispatchTargetV3
from .request_v3 import parse_issue_envelope_v3, request_identity_v3

GATES = ("REVIEW_BROKER_V3_LIVE_PREP_SHA", "REVIEW_BROKER_V3_LIVE_REQUEST_ID",
         "REVIEW_BROKER_V3_LIVE_REQUEST_ISSUE", "REVIEW_BROKER_V3_LIVE_REQUEST_BODY_SHA256")


def require_owner_gates_v3(gates,*,sha,request_id,issue,body=None):
    if any(type(gates.get(k)) is not str or not gates[k] for k in GATES):
        raise ValueError('OWNER_GATE_MISSING')
    if (gates[GATES[0]]!=sha or gates[GATES[1]]!=request_id
            or exact_positive(gates[GATES[2]])!=issue
            or re.fullmatch(r'[0-9a-f]{64}',gates[GATES[3]]) is None
            or body is not None and hashlib.sha256(body).hexdigest()!=gates[GATES[3]]):
        raise ValueError('OWNER_GATE_BINDING_MISMATCH')


class GitHubActionsControllerAuthorityV3:
    def __copy__(self):raise ValueError('CONTROLLER_AUTHORITY_COPY_FORBIDDEN')
    def __deepcopy__(self,memo):raise ValueError('CONTROLLER_AUTHORITY_COPY_FORBIDDEN')
    def __reduce__(self):raise ValueError('CONTROLLER_AUTHORITY_SERIALIZATION_FORBIDDEN')

    def _require_original(self):
        if self._authority_origin is not self:raise ValueError('ORIGINAL_CONTROLLER_AUTHORITY_REQUIRED')

    def __init__(self, runtime, *, issue: int, request_id: str, gates):
        if runtime.role != "controller" or type(issue) is not int or issue < 1:
            raise ValueError("CONTROLLER_RUNTIME_BINDING_INVALID")
        require_owner_gates_v3(gates,sha=runtime.checkout.sha,request_id=request_id,issue=issue)
        self._authority_origin = self
        self.runtime, self.issue, self.request_id = runtime, issue, request_id
        self.gates = {key: gates[key] for key in GATES}
        if runtime.inputs != {"request_issue_number": issue, "request_id": request_id}:
            raise ValueError("CONTROLLER_OWNER_BINDING_MISMATCH")
        self.origin_reader = GitHubIssueOriginReaderV3(runtime.api.token, REPOSITORY,
            REPOSITORY_ID, executor=runtime.api.execute)
        self._admission = None
        self._source_admission_bytes = None
        self.target = InitialDispatchTargetV3(WORKER_PATH, runtime.expected.workflow_execution_ref,
                                               runtime.checkout.sha)

    def require_current(self):
        self._require_original()
        observed = self.runtime.observe()
        if observed.actor_id != OWNER_ID or observed.triggering_actor_id != OWNER_ID:
            raise ValueError("CONTROLLER_ACTOR_UNAUTHORIZED")
        issue = self.origin_reader.observe(self.issue)
        require_owner_gates_v3(self.gates,sha=self.runtime.checkout.sha,request_id=self.request_id,
            issue=self.issue,body=None if issue.body is None else issue.body.encode())
        if (issue.requester_id != OWNER_ID or issue.body is None
                or request_identity_v3(parse_issue_envelope_v3(issue.body)) != self.request_id):
            raise ValueError("CONTROLLER_REQUEST_ORIGIN_UNAUTHORIZED")
        return issue

    def accept_source_admission(self,source,admission,issuer):
        self._require_original()
        from .live_source_admission_v3 import LiveSourceSessionV3
        if type(source) is not LiveSourceSessionV3:
            raise ValueError('ORIGINAL_COMPLETE_SOURCE_PHASE_REQUIRED')
        source.consume_admission_registration(self,admission,issuer)
        self.require_current()
        self._source_admission_bytes=canonical_bytes(admission.journal_admission())

    def authorize(self, *, broker_repository, broker_repository_node_id, target,
                  journal_admission_bytes, origin_body_bytes):
        self._require_original()
        origin = self.require_current()
        value = validate_journal_admission_v3(json.loads(journal_admission_bytes), origin_body_bytes)
        repository = self.runtime.api.get("")
        if (broker_repository != REPOSITORY or repository.get("node_id") != broker_repository_node_id
                or target != self.target or origin_body_bytes != origin.body.encode()
                or value["request_id"] != self.request_id
                or value["broker_issue_id"] != origin.issue_id
                or value["requester_id"] != OWNER_ID
                or journal_admission_bytes != canonical_bytes(value)
                or journal_admission_bytes != self._source_admission_bytes):
            return None
        self._admission = value
        return ControllerAuthorizationV3(True, broker_repository, broker_repository_node_id,
            target, journal_admission_bytes, origin_body_bytes)

    def evidence_id(self, *, repository, request, admission):
        self._require_original()
        self.require_current()
        if (self._admission is None or repository != REPOSITORY
                or canonical_bytes(admission) != canonical_bytes(self._admission)
                or request != self._admission["canonical_request"]):
            return None
        return artifact_identity(canonical_bytes(self._admission) + b"\n")

    def permits_evidence(self, *, repository, request_id, admission, evidence_id):
        return (request_id == self.request_id and evidence_id is not None
                and evidence_id == self.evidence_id(repository=repository,
                    request=admission["canonical_request"], admission=admission))

    def recognize_original(self, admission, body):
        """Historical admission recognition never recreates an active Controller."""
        return self.authorize(broker_repository=REPOSITORY,
            broker_repository_node_id=self.runtime.api.get("")["node_id"], target=self.target,
            journal_admission_bytes=canonical_bytes(admission), origin_body_bytes=body)
