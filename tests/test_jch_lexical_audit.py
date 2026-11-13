"""Audit freshness only: a matching report is NOT a passing lexical conformance gate."""
import json
import unittest
from jch_lexical_audit import ROOT, audit


class LexicalAuditFreshnessTests(unittest.TestCase):
    def test_committed_observations_match_all_current_pattern_occurrences(self):
        expected=json.loads((ROOT/'docs/adoption/jch-adoption-lexical-audit.json').read_text())
        self.assertEqual(audit(),expected)
        identities=[(item['schema'],item['pointer']) for item in expected['entries']]
        self.assertEqual(len(identities),len(set(identities)))
        self.assertEqual(expected['occurrences'],len(identities))

    def test_adoption_preserves_all_historical_lexical_observations(self):
        historical=json.loads((ROOT/'docs/adoption/jch-lexical-audit.json').read_text())
        current=json.loads((ROOT/'docs/adoption/jch-adoption-lexical-audit.json').read_text())
        # Only schema file identities changed due to explicitly accepted root
        # annotations. Preserve the complete entries, domains and outcomes.
        self.assertEqual(set(historical['schema_sha256']),set(current['schema_sha256']))
        self.assertEqual({k:v for k,v in current.items() if k!='schema_sha256'},
                         {k:v for k,v in historical.items() if k!='schema_sha256'})
