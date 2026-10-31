import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from tests.issue68_test_support import IntegratedScenario
class Issue68RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name);self.scenario=IntegratedScenario(self.root).complete();self.request_id=self.scenario.admission.request_id;self.transport=self.root/"transport.json";self.scenario.save_transport(self.transport)
 def tearDown(self): self.temporary.cleanup()
 def probe(self,retention=None,transport=None):
  environment={**os.environ,"PYTHONPATH":str(Path(__file__).parents[1])}
  return subprocess.run([sys.executable,"-m","tests.issue68_reload_probe",str(retention or self.scenario.retention_base),str(transport or self.transport),self.request_id],text=True,capture_output=True,env=environment)
 def test_I68_N03_fresh_process_reconstructs_exact_prepared_packet(self):
  expected_packet=self.scenario.manifest["packet_id"];expected_evidence=self.scenario.packet_evidence_id
  del self.scenario.admission,self.scenario.capture,self.scenario.manifest,self.scenario.issue_readers,self.scenario.git_readers
  result=self.probe();self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout)
  self.assertEqual(value["outcome"],"PASS");self.assertEqual(value["packet_id"],expected_packet);self.assertEqual(value["packet_evidence_id"],expected_evidence)
 def test_recovery_counterexamples_fail_closed(self):
  cases=[("source",lambda r:(r/"packet/sources/S001.bin").write_bytes(b"bad")),
   ("profile",lambda r:(r/"evidence/technical-profile.bin").unlink()),
   ("request",lambda r:(r/"evidence/origin-body.bin").write_bytes(b"bad")),
   ("admission-reference",lambda r:(r/"evidence/admitted-references/contract.bin").write_bytes(b"bad")),
   ("receipt",lambda r:(r/"evidence/preparation-receipt.json").write_bytes(b"{}\n")),
   ("manifest",lambda r:(r/"packet/input-manifest.json").write_bytes(b"{}\n")),
   ("public-prompt-mode",lambda r:(r/"packet/input.txt").chmod(0o644)),
   ("public-receipt-mode",lambda r:(r/"evidence/preparation-receipt.json").chmod(0o644))]
  for name,mutate in cases:
   with self.subTest(name=name):
    base=self.root/f"copy-{name}";copy=base/self.scenario.retention.name;shutil.copytree(self.scenario.retention,copy);mutate(copy);result=self.probe(base);self.assertNotEqual(result.returncode,0)
 def test_altered_journal_and_missing_packet_fail_closed(self):
  missing=self.root/"missing";result=self.probe(missing);self.assertNotEqual(result.returncode,0)
  value=json.loads(self.transport.read_bytes());claim=next(iter(value["refs"]));sha=value["refs"][claim];value["commits"][sha]["parent_sha"]="0"*40
  altered=self.root/"altered.json";altered.write_text(json.dumps(value));self.assertNotEqual(self.probe(transport=altered).returncode,0)
if __name__=="__main__":unittest.main()
