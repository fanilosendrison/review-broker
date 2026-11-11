"""Bounded provider facts never authorize ACK, retry or generation changes."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import URLError

from review_broker.github_actions_dispatch_provider_v3 import (
    GitHubActionsDispatchProviderObservationV3, classify_dispatch_response_v3,
    dispatch_transport_observation_v3, workflow_dispatch_payload_v3,
)
from review_broker.github_actions_initial_dispatch_v3 import GitHubActionsInitialDispatchTransportV3
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_live_runtime_v3 import REPOSITORY, WORKER_PATH
from review_broker.pre_model_dispatch_v3 import InitialDispatchStatusV3
from review_broker.live_pre_model_controller_v3 import run_live_controller_v3
from review_broker.request_v3 import request_identity_v3
from tests.live_prep_provider_support import LiveProviderService
from tests.live_prep_actions_support import PRINCIPAL

CONTEXT = dict(workflow_path=WORKER_PATH, execution_ref='refs/heads/qualification-branch',
               request_id='qualification-only-not-a-broker-request',
               reservation_id='qualification-only-not-a-reservation', generation=1)


def response(status=200, value=None):
    if value is None:
        value = {'workflow_run_id': 70001,
                 'run_url': f'https://api.github.com/repos/{REPOSITORY}/actions/runs/70001',
                 'html_url': f'https://github.com/{REPOSITORY}/actions/runs/70001'}
    return HttpResponseV3(status, json.dumps(value).encode(), {})


class DispatchProviderObservationTests(unittest.TestCase):
    def test_DP04_exact_200_is_observed_not_authenticated_worker(self):
        raw = response(); result, observation = classify_dispatch_response_v3(raw, **CONTEXT)
        self.assertIs(result.status, InitialDispatchStatusV3.OBSERVED)
        self.assertEqual(result.run_id, 70001)
        self.assertEqual(observation.http_status, 200)
        self.assertEqual(observation.recognized_run_id, 70001)
        self.assertEqual(observation.response_body_sha256, hashlib.sha256(raw.body).hexdigest())
        self.assertEqual(observation.response_body_length, len(raw.body))
        self.assertIs(type(observation.generation), int)

    def test_DP05_malformed_200_preserves_status_digest_without_run_authority(self):
        good = json.loads(response().body)
        values = [{}, [], {**good, 'workflow_run_id': True}, {**good, 'workflow_run_id': 0},
                  {**good, 'run_url': 'https://wrong.invalid'}, {**good, 'html_url': 'bad'}]
        duplicate = b'{"workflow_run_id":0,' + response().body[1:]
        bodies = [json.dumps(v).encode() for v in values] + [b'not-json', b'\xff', duplicate]
        for body in bodies:
            with self.subTest(length=len(body)):
                result, observation = classify_dispatch_response_v3(HttpResponseV3(200, body, {}), **CONTEXT)
                self.assertIs(result.status, InitialDispatchStatusV3.UNRESOLVED)
                self.assertEqual(observation.http_status, 200)
                self.assertEqual(observation.response_body_sha256, hashlib.sha256(body).hexdigest())
                self.assertIsNone(observation.recognized_run_id)

    def test_DP06_204_is_accepted_without_run_id(self):
        result, observation = classify_dispatch_response_v3(HttpResponseV3(204, b'', {}), **CONTEXT)
        self.assertIs(result.status, InitialDispatchStatusV3.ACCEPTED_NO_RUN_ID)
        self.assertIsNone(result.run_id)
        self.assertEqual(observation.http_status, 204)
        self.assertEqual(observation.response_body_length, 0)

    def test_DP07_DP08_DP09_DP10_DP11_all_refusals_remain_unresolved(self):
        for status in (400, 403, 404, 409, 422, 500, 503):
            with self.subTest(status=status):
                raw = response(status, {'message': 'fixture provider refusal'})
                result, observation = classify_dispatch_response_v3(raw, **CONTEXT)
                self.assertIs(result.status, InitialDispatchStatusV3.UNRESOLVED)
                self.assertEqual(observation.http_outcome, 'HTTP_RESPONSE')
                self.assertEqual(observation.http_status, status)
                self.assertIsNone(observation.recognized_run_id)
                self.assertIsNone(observation.transport_error_class)
                self.assertEqual(observation.response_body_sha256, hashlib.sha256(raw.body).hexdigest())

    def test_DP12_DP13_transport_failure_classes_are_closed_and_scrubbed(self):
        private = 'inert-fixture-sensitive-text'
        for error, expected in ((TimeoutError(private), 'TIMEOUT'), (URLError(private), 'URL_ERROR'),
                                (OSError(private), 'OS_ERROR'), (ValueError(private), 'OTHER_ERROR')):
            observation = dispatch_transport_observation_v3(error, **CONTEXT)
            self.assertEqual(observation.http_outcome, 'TRANSPORT_FAILURE')
            self.assertEqual(observation.transport_error_class, expected)
            self.assertIsNone(observation.http_status)
            self.assertIsNone(observation.response_body_sha256)
            self.assertIsNone(observation.response_body_length)
            self.assertIsNone(observation.recognized_run_id)
            self.assertNotIn(private, json.dumps(observation.as_dict()))

    def test_DP14_observation_is_closed_bounded_immutable_and_contains_no_raw_material(self):
        private = 'inert-sensitive-fixture-value'
        raw = response(422, dict(temp_clone_token=private, documentation_url='https://unneeded.invalid'))
        raw = HttpResponseV3(raw.status, raw.body, dict(Authorization=private, Cookie=private))
        _, observation = classify_dispatch_response_v3(raw, **CONTEXT)
        value = observation.as_dict()
        self.assertEqual(set(value), {'schema_version', 'provider', 'workflow_path', 'execution_ref',
            'request_id', 'reservation_id', 'generation', 'http_outcome', 'http_status',
            'response_body_sha256', 'response_body_length', 'recognized_run_id', 'transport_error_class'})
        self.assertNotIn(private, json.dumps(value))
        self.assertNotIn('https://unneeded.invalid', json.dumps(value))
        with self.assertRaises(FrozenInstanceError):
            observation.http_status = 200
        for change in ({'provider': 'other'}, {'schema_version': True}, {'generation': '1'},
                       {'generation': True}, {'http_status': True}, {'response_body_length': -1},
                       {'response_body_sha256': 'bad'}, {'request_id': 'x' * 2049},
                       {'transport_error_class': private}):
            with self.subTest(change=tuple(change)):
                with self.assertRaises(ValueError):
                    replace(observation, **change)
        with self.assertRaises(TypeError):
            GitHubActionsDispatchProviderObservationV3(**value, headers={})

    def test_wire_builder_never_stringifies_invalid_internal_generation_or_ids(self):
        values = {k: v for k, v in CONTEXT.items() if k != 'workflow_path'}
        payload = workflow_dispatch_payload_v3(**values)
        self.assertEqual(payload['inputs']['generation'], '1')
        for change in ({'generation': '1'}, {'generation': True}, {'generation': 2},
                       {'request_id': 7}, {'reservation_id': False}, {'execution_ref': 'dev'}):
            with self.assertRaises(ValueError):
                workflow_dispatch_payload_v3(**{**values, **change})

    def run_controller(self, root, service, sink):
        identifier = request_identity_v3(service.request)
        runtime = service.runtime('controller', {'request_issue_number': 51, 'request_id': identifier})
        return run_live_controller_v3(runtime=runtime, issue=51, request_id=identifier,
            gates=service.gates(identifier), source_token=service.minted('controller'),
            app_slug='review-broker-app', installation_id=123, private_root=root/'source',
            source_executor=service.source, acquire_repository=service.acquire,
            observation_sink=sink)

    def test_DP15_diagnostic_cannot_authenticate_ack_or_mutate_journal(self):
        from review_broker.github_actions_dispatch_ack_v3 import GitHubActionsDispatchAcknowledgmentAuthorityV3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); service = LiveProviderService(root); seen = []
            result = self.run_controller(root, service, seen.append)
            self.assertEqual(result.status.value, 'DISPATCH_ACKNOWLEDGED')
            runtime = service.runtime('worker', {'request_id': result.dispatch_request.request_id,
                'reservation_id': result.dispatch_request.reservation_id, 'generation': 1})
            ack = GitHubActionsDispatchAcknowledgmentAuthorityV3(runtime.api, runtime.expected)
            from review_broker.pre_model_dispatch_ack_v3 import acknowledgment_from_record
            service.controller_running = False
            receipt = acknowledgment_from_record(result.acknowledgment_outcome.snapshot.record)
            self.assertTrue(ack.authenticates(receipt, dispatch_principal_id=PRINCIPAL))
            before = service.git.mutation_calls
            self.assertFalse(ack.authenticates(seen[0], dispatch_principal_id=PRINCIPAL))
            self.assertEqual(service.git.mutation_calls, before)

    def test_DP16_DP17_actual_adapter_second_dispatch_refused_even_if_diagnostic_replaced(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); service = LiveProviderService(root); seen = []; transports = []
            original = GitHubActionsInitialDispatchTransportV3
            def capture(*args, **kwargs):
                transport = original(*args, **kwargs); transports.append(transport); return transport
            with patch('review_broker.live_pre_model_controller_v3.GitHubActionsInitialDispatchTransportV3', capture):
                result = self.run_controller(root, service, seen.append)
            self.assertEqual(len(seen), 1)
            self.assertIs(type(result.dispatch_request.generation), int)
            before = len([c for c in service.calls if c[0] == 'POST'])
            transports[0].provider_observation = None
            with self.assertRaisesRegex(ValueError, 'INITIAL_DISPATCH_ALREADY_ATTEMPTED'):
                transports[0].dispatch(result.dispatch_request)
            self.assertEqual(len([c for c in service.calls if c[0] == 'POST']), before)

    def test_refusal_and_lost_response_publish_diagnostics_once_without_retry(self):
        for status, loss in ((422, False), (200, True)):
            with self.subTest(status=status, loss=loss), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve(); service = LiveProviderService(root); seen = []
                service.dispatch_status = status; service.dispatch_loss = loss
                result = self.run_controller(root, service, seen.append)
                self.assertEqual(result.status.value, 'DISPATCH_UNRESOLVED')
                self.assertEqual(len([c for c in service.calls if c[0] == 'POST']), 1)
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0].transport_error_class, 'TIMEOUT' if loss else None)
                self.assertEqual(seen[0].http_status, None if loss else 422)
                self.assertIsNone(result.acknowledgment_outcome)

    def test_cli_emits_only_the_bounded_observation_with_existing_status(self):
        # Serialization consumer test only. Actual admission/dispatch is exercised
        # above; the trusted runtime/composition dependencies are isolated here.
        from contextlib import redirect_stdout
        import io
        import os
        from types import SimpleNamespace
        from unittest.mock import patch
        from review_broker.live_pre_model_cli import run_v3_command
        from review_broker.pre_model_controller_v3 import ControllerResultV3, ControllerStatusV3
        _, observation = classify_dispatch_response_v3(response(422), **CONTEXT)
        result = ControllerResultV3(ControllerStatusV3.DISPATCH_UNRESOLVED,
                                    'DISPATCH_ACK_UNCONFIRMED_NO_RETRY')
        def compose(**kwargs):
            kwargs['observation_sink'](observation)
            return result
        environment = dict(GITHUB_TOKEN='fixture-control', GITHUB_SHA='c' * 40,
                           REVIEW_BROKER_SOURCE_APP_SLUG='review-broker-app',
                           REVIEW_BROKER_SOURCE_INSTALLATION_ID='123')
        args = SimpleNamespace(broker_repo=REPOSITORY, command='internal-v3-pre-model-controller',
                               issue=51, request_id=CONTEXT['request_id'])
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, environment, clear=True), \
                patch('review_broker.github_live_runtime_v3.ProtectedCheckoutV3.observe'), \
                patch('review_broker.github_live_runtime_v3.GitHubActionsRuntimeBoundaryV3'), \
                patch('review_broker.live_pre_model_controller_v3.run_live_controller_v3', side_effect=compose), \
                patch('review_broker.live_pre_model_cli.tempfile.mkdtemp', return_value=directory):
            output = io.StringIO()
            with redirect_stdout(output):
                code = run_v3_command(args, 'fixture-source')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue()), {'status': 'DISPATCH_UNRESOLVED',
            'reason': result.reason, 'provider_observation': observation.as_dict()})
        self.assertNotIn('fixture-control', output.getvalue())
        self.assertNotIn('fixture-source', output.getvalue())

    def test_diagnostic_sink_failure_cannot_retry_or_change_dispatch_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); service = LiveProviderService(root)
            def failing_sink(observation):
                raise RuntimeError('fixture observer unavailable')
            result = self.run_controller(root, service, failing_sink)
            self.assertEqual(result.status.value, 'DISPATCH_ACKNOWLEDGED')
            self.assertEqual(len([c for c in service.calls if c[0] == 'POST']), 1)
