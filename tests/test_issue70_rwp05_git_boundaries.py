"""Actual BLOCKED orchestration through concrete Git HTTP edges and consumed-choice guards."""
from pathlib import Path
import tempfile
import unittest

from review_broker.pre_model_active_decision_v3 import PreModelDecisionStateV3
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_git_support import install_concrete_failure_writer


class FailureGitBoundaryTests(unittest.TestCase):
    def scenario(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return FailureScenario(Path(temporary.name))

    def run_concrete(self,s,**kwargs):
        installed=[]
        def install():installed.extend(install_concrete_failure_writer(s,**kwargs))
        s.archive.on_put=install
        return s.run_packet(),installed[0]

    def writes(self,api):
        return [(url,body) for method,url,body,auth in api.calls
                if method=='POST' and ('/git/' in url or url.endswith('/graphql') and body['query'].startswith('mutation'))]

    def test_F12_positive_consumed_blocked_choice_completes_all_git_edges(self):
        s=self.scenario();result,api=self.run_concrete(s)
        self.assertEqual((result.status.value,result.disposition),('COMMITTED','BLOCKED'),result)
        writes=self.writes(api)
        self.assertEqual([url.rsplit('/',1)[-1] for url,_ in writes],['blobs','trees','commits','graphql'])
        self.assertEqual(writes[-1][1]['variables']['beforeOid'],s.authority.snapshot.commit_sha)
        self.assertIs(writes[-1][1]['variables']['force'],False)
        self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
        self.assertEqual(s.failure_cas_count(),1)

    def test_F12_head_movement_after_each_blob_tree_commit_stops_next_http_effect(self):
        for trigger,count in (('blobs',1),('trees',2),('commits',3)):
            s=self.scenario();result,api=self.run_concrete(s,revoke_after=trigger)
            with self.subTest(trigger=trigger):
                self.assertEqual(result.status.value,'UNRESOLVED')
                self.assertEqual([u.rsplit('/',1)[-1] for u,_ in self.writes(api)],['blobs','trees','commits'][:count])
                self.assertEqual(s.failure_cas_count(),0)
                self.assertEqual(len(api.calls),api.revoke_index)  # No following GET or POST escaped.
                self.assertNotEqual(s.current().commit_sha,s.authority.snapshot.commit_sha)
                self.assertIs(s.producer._decision.state,PreModelDecisionStateV3.CONSUMED_FOR_BLOCKED)
                before=len(self.writes(api));s.producer.run(s.real.worker.context)
                self.assertEqual(len(self.writes(api)),before)

    def test_F13_last_identity_observation_cannot_authorize_stale_update_refs(self):
        s=self.scenario();result,api=self.run_concrete(s,revoke_after='identity')
        self.assertEqual(result.status.value,'UNRESOLVED')
        self.assertEqual([u.rsplit('/',1)[-1] for u,_ in self.writes(api)],['blobs','trees','commits'])
        self.assertEqual(s.failure_cas_count(),0)
        self.assertEqual(len(api.calls),api.revoke_index)

    def test_F13_emitted_graphql_permission_error_is_not_source_permanence_or_success(self):
        s=self.scenario();result,api=self.run_concrete(s,permission_status=403)
        self.assertEqual(result.status.value,'UNRESOLVED',result)
        self.assertEqual(s.current().record.control.disposition,'RESERVED')
        self.assertEqual([u.rsplit('/',1)[-1] for u,_ in self.writes(api)],['blobs','trees','commits','graphql'])
        self.assertIsNotNone(result.journal_outcome.pending)
        self.assertNotIn('PERMANENT',result.reason)
        self.assertEqual(s.failure_cas_count(),0)
        before=len(self.writes(api))
        s.real.worker.journal.reconcile(result.journal_outcome.pending)
        self.assertEqual(len(self.writes(api)),before)
