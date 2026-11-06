"""New concrete boundary classes with injected provider only; real RWP continuations."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from review_broker.actions_artifact_child_v3 import GitHubActionsArtifactChildV3
from review_broker.github_actions_failure_archive_v3 import GitHubActionsFailureObservationArchiveV3
from review_broker.github_prepared_artifact_v3 import PreparedArtifactUploaderV3, PreparedUploadPlanV3
from review_broker.pre_model_failure_observation_v3 import FailureObservationV3
from tests.issue70_rwp04_test_support import RemoteScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario
from tests.test_issue70_live_prep_artifact_child import ENV


class ArtifactIntegrationTests(unittest.TestCase):
    def test_real_rwp04_zip_through_child_boundary_and_independent_rest(self):
        for lost in (False, True):
            with self.subTest(lost=lost), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                scenario = RemoteScenario(root)
                calls = []
                def run(argv, environment, log, **options):
                    raw = Path(environment["INPUT_PATH"]).read_bytes()
                    calls.append(raw)
                    # This is the external service double, not a constructed broker intermediate.
                    plan = PreparedUploadPlanV3(environment["INPUT_NAME"], b"unused-by-service",
                        scenario.s.worker.context)
                    scenario.service.upload_once(plan, raw, before_effect=lambda: None)
                    if lost: raise TimeoutError("lost pinned child response")
                    return 0
                private = root / "private"
                private.mkdir(mode=0o700)
                child = GitHubActionsArtifactChildV3(trusted_root=private, node=Path("/trusted/node24"),
                    private_base=private, environment=ENV, max_bytes=2_000_000, runner=run,
                    verifier=lambda p: p / "dist/upload/index.js")
                scenario.continuation.uploader = PreparedArtifactUploaderV3(child)
                result = scenario.run()
                self.assertEqual(result.status.value, "COMMITTED", result)
                self.assertEqual(result.state, "PREPARED")
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0], result.archive_bytes)
                self.assertTrue(calls[0].startswith(b"PK"))
                self.assertTrue(scenario.service.metadata_calls)
                self.assertTrue(scenario.service.downloads)
                self.assertEqual(scenario.service.storage_headers, [{}])
                self.assertEqual(result.remote_receipt.value["storage"]["artifact_digest"],
                    "sha256:" + hashlib.sha256(calls[0]).hexdigest())
                self.assertEqual(scenario.s.worker.journal.read(scenario.s.worker.admission.request_id)
                    .record.attempt.invocation_count, 0)

    def test_failure_json_raw_remote_readback_and_metadata_substitution_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            scenario = RemoteFailureScenario(root)
            # Obtain an actual classified boundary observation from the existing RWP-05 path.
            scenario.service.metadata_failure = 503
            result = scenario.run_remote()
            self.assertEqual(scenario.failure_cas_count(), 1)
            observation = FailureObservationV3(scenario.archive.puts[0][1])
            snapshot = scenario.authority.snapshot
            private = root / "failure-child"
            private.mkdir(mode=0o700)
            spawned = []
            def run(argv, environment, log, **options):
                raw = Path(environment["INPUT_PATH"]).read_bytes()
                spawned.append(raw)
                plan = PreparedUploadPlanV3(environment["INPUT_NAME"], b"unused",
                    scenario.real.worker.context)
                scenario.service.upload_once(plan, raw, before_effect=lambda: None)
                return 0
            child = GitHubActionsArtifactChildV3(trusted_root=private, node=Path("/trusted/node24"),
                private_base=private, environment=ENV, max_bytes=16000, runner=run,
                verifier=lambda p: p / "dist/upload/index.js")
            scenario.service.metadata_failure = None
            archive = GitHubActionsFailureObservationArchiveV3(child=child,
                adapter=scenario.adapter, snapshot=snapshot, active_context=scenario.real.worker.context)
            outcome = archive.put_once(observation.evidence_id, observation.canonical_bytes,
                before_effect=lambda: None)
            self.assertEqual(outcome.status.value, "ACK")
            restored = archive.read(observation.evidence_id, max_bytes=16000, before_effect=lambda: None)
            self.assertEqual(restored, observation.canonical_bytes)
            self.assertEqual(spawned, [restored])
            self.assertFalse(restored.startswith(b"PK"))
            self.assertEqual(scenario.service.storage_headers[-1], {})
            scenario.service.artifacts[0]["expires_at"] = "2026-12-06T00:00:00Z"
            with self.assertRaisesRegex(ValueError, "IDENTITY_CHANGED"):
                archive.read(observation.evidence_id, max_bytes=16000, before_effect=lambda: None)
            with self.assertRaisesRegex(ValueError, "ALREADY_ATTEMPTED"):
                archive.put_once(observation.evidence_id, restored, before_effect=lambda: None)
            # Backend upload/readback never creates an additional BLOCKED authority.
            self.assertEqual(scenario.failure_cas_count(), 1)
