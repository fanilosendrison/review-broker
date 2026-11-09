"""Bounded assertions with explicit negative controls; zero inference."""
import unittest
from rb91_continuation_model import explore


class ContinuationCandidateTests(unittest.TestCase):
    def test_stop_first_preserves_both_safety_properties_with_reachable_starts(self):
        result = explore('stop_first')
        self.assertTrue(result['launch_reachable'])
        self.assertTrue(result['stopped_reachable'])
        self.assertTrue(result['start_during_cancel'])
        self.assertIsNone(result['double_start'])
        self.assertIsNone(result['late_start'])
        self.assertFalse(result['lost_ack_start'])
        self.assertFalse(result['stop_without_shutdown'])

    def test_mark_first_and_cancel_send_are_not_fences(self):
        for mode in ('mark_first','cancel_only','read_before_start'):
            result = explore(mode)
            with self.subTest(mode=mode):
                self.assertIsNotNone(result['late_start'])
                self.assertIsNone(result['double_start'])
                self.assertFalse(result['lost_ack_start'])

    def test_cloning_and_reentry_remain_decisive_negative_controls(self):
        for mode in ('clone','reenter'):
            result = explore(mode)
            with self.subTest(mode=mode):
                self.assertIsNotNone(result['double_start'])
                self.assertIsNone(result['late_start'])
