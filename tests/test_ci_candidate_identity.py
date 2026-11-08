"""The remote qualification must execute the published commit, not a merge projection."""
from pathlib import Path
import unittest

import yaml


class CandidateCiIdentityTests(unittest.TestCase):
    def test_ci_checkout_selects_exact_pr_head_or_push_sha_without_write_authority(self):
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/ci.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        first = workflow['jobs']['test']['steps'][0]
        self.assertEqual(first['uses'], 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683')
        self.assertEqual(first['with']['ref'], '${{ github.event.pull_request.head.sha || github.sha }}')
