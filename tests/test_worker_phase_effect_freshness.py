"""Schedule external races around actual one-shot upload and expected-old provider CAS."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.actions_artifact_child_v3 import GitHubActionsArtifactChildV3
from review_broker.journal_record_v3 import decode_journal_v2
from tests.live_prep_artifact_provider_support import CompleteProviderService
from tests.live_prep_provider_support import controller_scenario
from tests.test_live_prep_complete_composition import worker_scenario


def current_record(service, claim):
    commit = service.git.refs[claim]
    tree = service.git.trees[service.git.commits[commit][0]]
    blob = next(e['sha'] for e in tree if e['path'] == '.review-broker/attempt.json')
    return decode_journal_v2(service.git.blobs[blob])


def move_claim(service, claim):
    current = service.git.refs[claim]
    service.git.refs[claim] = service.git.commits[current][1][0]


class WorkerPhaseEffectFreshnessTests(unittest.TestCase):
    def test_S2_claim_moves_before_upload_child_so_no_spawn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            service = CompleteProviderService(root)
            controller = controller_scenario(root, service)
            service.controller_running = False
            claim = controller.dispatch_request.claim_ref
            original = GitHubActionsArtifactChildV3.upload_once

            def scheduled(child, *args, **kwargs):
                move_claim(service, claim)
                return original(child, *args, **kwargs)

            with patch.object(GitHubActionsArtifactChildV3, 'upload_once', scheduled):
                result = worker_scenario(root, service, controller)
            self.assertFalse(result.cold_verified)
            self.assertEqual(service.uploads, [])
            self.assertNotEqual(current_record(service, claim).attempt.state.value, 'PREPARED')

    def test_S3_claim_moves_after_upload_no_PREPARED_and_no_second_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            service = CompleteProviderService(root)
            controller = controller_scenario(root, service)
            service.controller_running = False
            claim = controller.dispatch_request.claim_ref
            original = service.runner

            def runner(*args, **kwargs):
                result = original(*args, **kwargs)
                move_claim(service, claim)
                return result

            service.runner = runner
            result = worker_scenario(root, service, controller)
            self.assertFalse(result.cold_verified)
            self.assertEqual(len(service.uploads), 1)
            self.assertNotEqual(current_record(service, claim).attempt.state.value, 'PREPARED')

    def test_S12_expected_old_CAS_still_required_after_last_currentness_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            service = CompleteProviderService(root)
            updates = []
            original = service.git.after_mutation

            def race(path):
                original(path)
                if path == '/graphql':
                    updates.append(path)
                    if len(updates) == 5:
                        claims = [r for r in service.git.refs if '/review-claims-v3/' in r]
                        self.assertEqual(len(claims), 1)
                        move_claim(service, claims[0])

            service.git.after_mutation = race
            controller = controller_scenario(root, service)
            service.controller_running = False
            result = worker_scenario(root, service, controller)
            self.assertFalse(result.cold_verified)
            self.assertEqual(len(updates), 5)
            self.assertEqual(len(service.uploads), 1)
            record = current_record(service, controller.dispatch_request.claim_ref)
            self.assertNotEqual(record.attempt.state.value, 'PREPARED')
            self.assertEqual(record.attempt.invocation_count, 0)
