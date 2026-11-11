"""Timing/count metadata cannot carry provider material or alter an operation result."""
import json
import unittest
from urllib.request import Request

from review_broker.pre_model_observation_diagnostics_v3 import PreModelObservationDiagnosticsV3


class ObservationDiagnosticsTests(unittest.TestCase):
    def test_no_headers_bodies_urls_or_exception_material_retained(self):
        d = PreModelObservationDiagnosticsV3()
        request = Request('https://api.github.com/repos/example/repo/actions/runs/1?private=hidden',
                          headers=dict([('Authorization', 'Bearer fixture-only-material')]))
        d.http(request)
        out = json.dumps(d.as_dict())
        self.assertNotIn('fixture-only-material', out)
        self.assertNotIn('hidden', out)
        self.assertNotIn('api.github.com', out)
        self.assertEqual(d.counts['ACTIONS_RUN_READS'], 1)
        self.assertEqual(d.counts['TOTAL_GITHUB_READS'], 1)

    def test_graphql_mutations_and_dispatch_not_counted_as_reads(self):
        d = PreModelObservationDiagnosticsV3()
        for query in ('query{repository{id}}', 'mutation{updateRefs{id}}'):
            d.http(Request('https://api.github.com/graphql', method='POST',
                           data=json.dumps({'query': query}).encode()))
        d.http(Request('https://api.github.com/repos/example/repo/dispatches', method='POST', data=b'{}'))
        self.assertEqual(d.counts['TOTAL_GITHUB_READS'], 1)

    def test_sink_failure_does_not_change_success_or_original_failure(self):
        def broken(_):
            raise RuntimeError('diagnostic sink unavailable')
        d = PreModelObservationDiagnosticsV3(broken)
        with d.phase('PACKET_BUILD_VERIFY'):
            result = object()
        self.assertIsNotNone(result)
        original = ValueError('original operation failure')
        with self.assertRaises(ValueError) as failure:
            with d.phase('PREPARED_CAS'):
                raise original
        self.assertIs(failure.exception, original)
        self.assertGreaterEqual(d.seconds['PACKET_BUILD_VERIFY'], 0)

    def test_closed_finite_categories(self):
        d = PreModelObservationDiagnosticsV3()
        for _ in range(10):
            d.count('untrusted-body-or-label')
        self.assertEqual(d.as_dict()['counts'], {})
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_PREMODEL_DIAGNOSTIC_PHASE'):
            with d.phase('untrusted phase'):
                pass
