"""Internal I/O revocation and crash points measured independently of reason codes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from review_broker.pre_model_remote_retention_v3 import RemoteRetainedPacketAuthorityV3
from review_broker.packet_preparation_authority_v3 import retained_inventory_v3
from tests.issue70_rwp04_test_support import RemoteScenario


class RemoteRacesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.r = RemoteScenario(self.root)

    def move(self):
        s = self.r.s.worker
        a = s.journal.read(s.admission.request_id)
        sha = s.transport.create_journal_commit(a.commit_sha, a.journal_bytes)
        s.transport.attributed.add(sha)
        s.transport.refs[a.claim_ref] = sha

    def refused(self, *, uploads):
        result = self.r.run()
        self.assertNotEqual(result.status.value, "COMMITTED", result)
        self.assertEqual(len(self.r.service.uploads), uploads)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)
        self.r.run()
        self.assertEqual(len(self.r.service.uploads), uploads)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)
        return result

    def test_Q16_movement_inside_inventory_stops_next_file_read(self):
        reads, original = [], Path.read_bytes
        def inventory(root, *, before_effect):
            def read(path):
                data = original(path)
                reads.append(path)
                self.move()
                return data
            with patch.object(Path, "read_bytes", read):
                return retained_inventory_v3(root, before_effect=before_effect)
        with patch("review_broker.pre_model_remote_retention_v3.retained_inventory_v3", inventory):
            self.refused(uploads=0)
        self.assertEqual(len(reads), 1)

    def test_Q16_movement_inside_archive_stops_next_write_and_upload(self):
        writes, original = [], zipfile.ZipFile.writestr
        def write(bundle, *args, **kwargs):
            result = original(bundle, *args, **kwargs)
            writes.append(args[0].filename)
            self.move()
            return result
        with patch.object(zipfile.ZipFile, "writestr", write):
            self.refused(uploads=0)
        self.assertEqual(len(writes), 1)

    def test_Q16_movement_inside_observation_stops_following_transport_calls(self):
        self.r.service.metadata_hook = lambda request: self.move()
        self.refused(uploads=1)
        self.assertEqual(len(self.r.service.metadata_calls), 1)
        self.assertEqual(self.r.service.downloads, [])

    def test_Q16_movement_after_prepare_authority_before_cas_prevents_git_effect(self):
        original, calls = RemoteRetainedPacketAuthorityV3.permits, []
        def permits(authority, **kwargs):
            allowed = original(authority, **kwargs)
            calls.append(allowed)
            self.move()
            return allowed
        with patch.object(RemoteRetainedPacketAuthorityV3, "permits", permits):
            self.refused(uploads=1)
        self.assertEqual(calls, [True])

    def test_Q19_upload_interruption_before_creation_is_unknown_without_retry(self):
        def interrupt(stage, guard):
            if stage == "before": raise RuntimeError("fixture interruption")
        self.r.service.upload_hook = interrupt
        result = self.refused(uploads=1)
        self.assertEqual(result.status.value, "UNRESOLVED")
        self.assertIsNone(self.r.service.archive)

    def test_Q20_cas_interruption_before_and_after_application_never_retries(self):
        for after in (False, True):
            if after: self.setUp()
            transport = self.r.s.worker.transport
            transport.crash_event, transport.crash_after_apply = "PREPARED", after
            result = self.r.run()
            self.assertEqual(result.status.value, "UNRESOLVED", result)
            self.assertEqual(transport.events.count("PREPARED"), 1)
            self.r.run()
            self.assertEqual(transport.events.count("PREPARED"), 1)
            self.assertEqual(len(self.r.service.uploads), 1)
            snapshot = self.r.s.worker.journal.read(self.r.s.worker.admission.request_id)
            self.assertEqual(snapshot.record.attempt.state.value, "PREPARED" if after else "ADMITTED")

    def test_Q21_admitted_observer_cannot_publish_or_prepare(self):
        result = self.r.readback(self.root/"observer")
        self.assertEqual(result.journal_transition, "UNRESOLVED")
        self.assertEqual(len(self.r.service.uploads), 0)
        self.assertEqual(self.r.s.worker.transport.events.count("PREPARED"), 0)
        self.assertEqual(self.r.service.downloads, [])
