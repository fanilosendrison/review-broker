"""Audit freshness only: a matching report is NOT a passing lexical conformance gate."""
import json
import unittest
from jch_lexical_audit import ROOT, audit


class LexicalAuditFreshnessTests(unittest.TestCase):
    def test_committed_observations_match_all_current_pattern_occurrences(self):
        expected=json.loads((ROOT/'docs/adoption/jch-lexical-audit.json').read_text())
        self.assertEqual(audit(),expected)
        identities=[(item['schema'],item['pointer']) for item in expected['entries']]
        self.assertEqual(len(identities),len(set(identities)))
        self.assertEqual(expected['occurrences'],len(identities))
