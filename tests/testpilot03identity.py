"""Deterministic identity and fixed-input tests for RB-PILOT-03."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from review_broker.identity import attempt_identity, request_identity
from review_broker.pilot03_controller import pilot03_identities
from review_broker.pilot03_synthetic import pilot_fixture_03
from review_broker.pilot_synthetic import PILOT_MISSION, PILOT_SOURCE, pilot_fixture, pilot_fixture_02


class Pilot03IdentityTests(unittest.TestCase):
    def test_identity_is_deterministic_and_distinct_without_fixture_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = pilot_fixture(root / "one")
            second = pilot_fixture_02(root / "two")
            third = pilot_fixture_03(root / "three")
            repeated = pilot_fixture_03(root / "repeat")
            expected = request_identity({
                "kind": "RB-PILOT-03",
                "fixture_sha256": hashlib.sha256(PILOT_SOURCE).hexdigest(),
                "ordinal": 1,
            })
            self.assertEqual(third, repeated)
            self.assertEqual(third["request_id"], expected)
            self.assertNotIn(expected, {first["request_id"], second["request_id"]})
            self.assertEqual(
                (root / "three/evidence/sources/S001.bin").read_bytes(), PILOT_SOURCE,
            )
            self.assertIn(PILOT_MISSION.encode(), (root / "three/evidence/input.txt").read_bytes())
            self.assertEqual(third["subject_id"], first["subject_id"])
            self.assertEqual(pilot03_identities(), (expected, attempt_identity(expected, 1)))
