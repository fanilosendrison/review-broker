"""GitHub dispatch wire representation and bounded, non-authoritative observations.

No effect, ACK, reservation, retry or dispatch permission is exposed here. The
original Controller adapter owns consumption; a diagnostic is never a permit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from urllib.error import URLError

from .github_http_live_v3 import GitHubHttpLiveV3Error, HttpResponseV3
from .github_live_runtime_v3 import REPOSITORY, WORKER_PATH
from .identity import canonical_bytes
from .pre_model_dispatch_v3 import InitialDispatchResultV3, InitialDispatchStatusV3
from .prepared_artifact_transport_v3 import PreparedMetadataReaderV3

_ERROR_CLASSES = frozenset({'TIMEOUT', 'URL_ERROR', 'OS_ERROR', 'TRANSPORT_UNAVAILABLE', 'OTHER_ERROR'})


def _bounded_text(value: object) -> bool:
    return (type(value) is str and 0 < len(value) <= 2048 and value.strip() == value
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _context(execution_ref: str, request_id: str, reservation_id: str, generation: int) -> None:
    if (not all(_bounded_text(v) for v in (execution_ref, request_id, reservation_id))
            or not execution_ref.startswith('refs/heads/')
            or execution_ref == 'refs/heads/' or type(generation) is not int or generation != 1):
        raise ValueError('DISPATCH_PROVIDER_CONTEXT_INVALID')


def workflow_dispatch_payload_v3(*, execution_ref: str, request_id: str,
                                 reservation_id: str, generation: int) -> dict[str, object]:
    """Only REST inputs become strings; no internal generation coercion is allowed."""
    _context(execution_ref, request_id, reservation_id, generation)
    return {'ref': execution_ref.removeprefix('refs/heads/'), 'inputs': {
        'request_id': request_id, 'reservation_id': reservation_id, 'generation': str(generation)},
        'return_run_details': True}


@dataclass(frozen=True, slots=True)
class GitHubActionsDispatchProviderObservationV3:
    schema_version: int
    provider: str
    workflow_path: str
    execution_ref: str
    request_id: str
    reservation_id: str
    generation: int
    http_outcome: str
    http_status: int | None
    response_body_sha256: str | None
    response_body_length: int | None
    recognized_run_id: int | None
    transport_error_class: str | None

    def __post_init__(self) -> None:
        _context(self.execution_ref, self.request_id, self.reservation_id, self.generation)
        if (type(self.schema_version) is not int or self.schema_version != 1
                or self.provider != 'github-actions' or self.workflow_path != WORKER_PATH):
            raise ValueError('DISPATCH_PROVIDER_OBSERVATION_INVALID')
        if self.http_outcome == 'HTTP_RESPONSE':
            if (type(self.http_status) is not int or not 100 <= self.http_status <= 599
                    or type(self.response_body_sha256) is not str
                    or re.fullmatch('[0-9a-f]{64}', self.response_body_sha256) is None
                    or type(self.response_body_length) is not int or self.response_body_length < 0
                    or self.transport_error_class is not None):
                raise ValueError('DISPATCH_HTTP_OBSERVATION_INVALID')
            if self.recognized_run_id is not None and (
                    self.http_status != 200 or type(self.recognized_run_id) is not int
                    or self.recognized_run_id < 1):
                raise ValueError('DISPATCH_RUN_OBSERVATION_INVALID')
        elif self.http_outcome == 'TRANSPORT_FAILURE':
            if (any(v is not None for v in (self.http_status, self.response_body_sha256,
                                           self.response_body_length, self.recognized_run_id))
                    or type(self.transport_error_class) is not str
                    or self.transport_error_class not in _ERROR_CLASSES):
                raise ValueError('DISPATCH_TRANSPORT_OBSERVATION_INVALID')
        else:
            raise ValueError('DISPATCH_OUTCOME_INVALID')
        # The existing RFC8785 implementation bounds JSON numbers without copying
        # another serializer's integer rules. Actual HTTP bytes remain bounded by
        # the existing live HTTP executor; no response bytes enter this value.
        try:
            canonical_bytes(asdict(self))
        except (TypeError, ValueError) as error:
            raise ValueError('DISPATCH_OBSERVATION_JSON_INVALID') from error

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _observation(*, workflow_path: str, execution_ref: str, request_id: str,
                 reservation_id: str, generation: int, http_outcome: str,
                 http_status=None, response_body_sha256=None, response_body_length=None,
                 recognized_run_id=None, transport_error_class=None):
    return GitHubActionsDispatchProviderObservationV3(1, 'github-actions', workflow_path,
        execution_ref, request_id, reservation_id, generation, http_outcome, http_status,
        response_body_sha256, response_body_length, recognized_run_id, transport_error_class)


def classify_dispatch_response_v3(response: HttpResponseV3, **context):
    """Response recognition yields only the existing unauthenticated run candidate.

    Keep the existing strict JSON decoder and URL/run checks. Arbitrary error
    payloads, messages, documentation URLs and headers are never retained.
    """
    result = InitialDispatchResultV3(InitialDispatchStatusV3.UNRESOLVED)
    if response.status == 204:
        result = InitialDispatchResultV3(InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID)
    elif response.status == 200:
        try:
            value = PreparedMetadataReaderV3.object(response)
            run = value.get('workflow_run_id')
            if (type(run) is int and run > 0
                    and value.get('run_url') == f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run}'
                    and value.get('html_url') == f'https://github.com/{REPOSITORY}/actions/runs/{run}'):
                canonical_bytes({'run_id': run})
                result = InitialDispatchResultV3(InitialDispatchStatusV3.OBSERVED, run)
        except (ValueError, TypeError):
            pass
    observation = _observation(**context, http_outcome='HTTP_RESPONSE', http_status=response.status,
        response_body_sha256=hashlib.sha256(response.body).hexdigest(),
        response_body_length=len(response.body), recognized_run_id=result.run_id)
    return result, observation


def dispatch_transport_observation_v3(error: Exception, **context):
    """Closed local classification, not raw exception text or proof of non-emission."""
    if isinstance(error, TimeoutError):
        kind = 'TIMEOUT'
    elif isinstance(error, URLError):
        kind = 'URL_ERROR'
    elif isinstance(error, OSError):
        kind = 'OS_ERROR'
    elif isinstance(error, GitHubHttpLiveV3Error):
        kind = 'TRANSPORT_UNAVAILABLE'
    else:
        kind = 'OTHER_ERROR'
    return _observation(**context, http_outcome='TRANSPORT_FAILURE', transport_error_class=kind)
