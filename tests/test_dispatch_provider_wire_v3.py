"""Actual concrete Controller/HTTP wire oracle; no real provider mutations."""
import json
from pathlib import Path
import tempfile
import unittest

from tests.live_prep_provider_support import LiveProviderService, controller_scenario


class DispatchProviderWireTests(unittest.TestCase):
    def test_DP01_DP02_DP03_actual_rest_inputs_are_strings_internal_generation_is_int(self):
        with tempfile.TemporaryDirectory() as directory:
            service = LiveProviderService(Path(directory).resolve())
            result = controller_scenario(Path(directory).resolve(), service)
            self.assertEqual(result.status.value, 'DISPATCH_ACKNOWLEDGED', result)
            posts = [c for c in service.calls if c[0] == 'POST']
            self.assertEqual(len(posts), 1)
            payload = json.loads(posts[0][2])
            self.assertEqual(payload, {'ref': 'qualification-branch', 'inputs': {
                'request_id': result.dispatch_request.request_id,
                'reservation_id': result.dispatch_request.reservation_id,
                'generation': '1'}, 'return_run_details': True})
            self.assertTrue(all(type(value) is str for value in payload['inputs'].values()))
            self.assertIs(type(result.dispatch_request.generation), int)
            self.assertEqual(result.dispatch_request.generation, 1)
            self.assertIs(type(payload['return_run_details']), bool)
