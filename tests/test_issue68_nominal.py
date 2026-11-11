import tempfile,unittest
from pathlib import Path
from tests.issue68_test_support import IntegratedScenario
from review_broker.queue import AttemptState
class Issue68NominalTests(unittest.TestCase):
 def test_I68_N01_N02_complete_four_reference_prepared_lifecycle(self):
  with tempfile.TemporaryDirectory() as temporary:
   scenario=IntegratedScenario(Path(temporary)).complete()
   self.assertEqual([x["operation"] for x in scenario.history],["claim","reserve_initial","register_worker","record_admission","prepare"])
   self.assertTrue(all(x["outcome"]=="COMMITTED" for x in scenario.history))
   self.assertEqual(scenario.prepared.record.attempt.state,AttemptState.PREPARED)
   self.assertEqual([x["source_kind"] for x in scenario.manifest["reference_sources"]],["inline","git_file","github_issue_body","github_issue_comment"])
   self.assertEqual(scenario.manifest["packet_id"],scenario.verified["packet_id"])
   self.assertEqual(scenario.packet_evidence_id,scenario.verified["packet_evidence_id"])
   events=[x.get("event") for x in scenario.prepared.record.attempt.history]
   self.assertEqual(events.count("PRE_MODEL_DISPATCH_RESERVED"),1);self.assertEqual(events.count("PRE_MODEL_WORKER_BOUND"),1)
   self.assertEqual(scenario.dispatches,1);self.assertEqual(scenario.prepared.record.attempt.invocation_count,0)
   self.assertEqual(len(scenario.transport.updates),4)
 def test_I68_N04_N05_mutable_bytes_refresh_before_prepared(self):
  with tempfile.TemporaryDirectory() as temporary:
   scenario=IntegratedScenario(Path(temporary),body="admitted body",comment="admitted comment").complete(preparation_body="prepared body",preparation_comment="prepared comment")
   refs={x["reference_id"]:x for x in scenario.manifest["reference_sources"]}
   self.assertNotEqual(refs["requirement"]["sha256"],scenario.admission.issue_reference_observations[0].sha256)
   self.assertNotEqual(refs["decision"]["sha256"],scenario.admission.issue_reference_observations[1].sha256)
   self.assertEqual((scenario.retention/"packet"/refs["requirement"]["snapshot"]).read_bytes(),b"prepared body")
if __name__=="__main__":unittest.main()
