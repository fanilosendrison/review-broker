import tempfile,unittest
from pathlib import Path
from tests.packet_v2_test_support import admitted,git_capture,inline,profile,request_for_capture
from tests.test_git_file_packet_v3 import git_ref
from tests.test_github_git_file_v3 import Api as GitApi,reader as git_reader
from tests.test_github_issue_reference_v3 import Api,reader
from review_broker.admission_v3 import AdmissionV3CandidateError
from review_broker.packet_v2 import build_packet_v2_candidate,verify_packet_v2_candidate,PacketV2CandidateError
def issue_ref(): return {"id":"requirement","required":True,"source":{"kind":"github_issue_body","repository":"fanilosendrison/review-broker","issue":43}}
def comment_ref(): return {"id":"decision","required":True,"source":{"kind":"github_issue_comment","repository":"fanilosendrison/review-broker","comment_id":99}}
class Tests(unittest.TestCase):
 def test_mixed_four_kind_packet_and_offline_verification(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); cap=git_capture(root); refs=[inline("note","inline"),git_ref(),issue_ref(),comment_ref()]; req=request_for_capture(cap,refs)
   ir={"requirement":reader(Api()),"decision":reader(Api())}; adm=admitted(req,capture=cap,git_file_readers={"contract":git_reader(GitApi())},issue_reference_readers=ir)
   out=root/"packet"; m=build_packet_v2_candidate(adm,cap,profile(),out,ir)
   self.assertEqual(verify_packet_v2_candidate(out,adm,cap,profile())["packet_id"],m["packet_id"])
   self.assertEqual([x["source_kind"] for x in m["reference_sources"]],["inline","git_file","github_issue_body","github_issue_comment"])
   self.assertIn("SOURCE_KIND=github_issue_comment",(out/"input.txt").read_text())
 def test_mutable_body_may_change_before_capture_but_identity_must_not(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); cap=git_capture(root); req=request_for_capture(cap,[issue_ref()]); adm=admitted(req,capture=cap,issue_reference_readers={"requirement":reader(Api(body="old"))})
   out=root/"packet"; build_packet_v2_candidate(adm,cap,profile(),out,{"requirement":reader(Api(body="new"))})
   self.assertEqual((out/"sources/S003.bin").read_bytes(),b"new")
 def test_atomicity_true_mutable_references_rejected(self):
  for ref in (issue_ref(),comment_ref()):
   with tempfile.TemporaryDirectory() as t:
    root=Path(t); cap=git_capture(root); req=request_for_capture(cap,[ref],atomicity=True)
    with self.assertRaisesRegex(AdmissionV3CandidateError,"ATOMICITY_MUTABLE_REFERENCE_FORBIDDEN"): admitted(req,capture=cap,issue_reference_readers={ref["id"]:reader(Api())})
 def test_snapshot_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); cap=git_capture(root); req=request_for_capture(cap,[issue_ref()]); ir={"requirement":reader(Api())}; adm=admitted(req,capture=cap,issue_reference_readers=ir); out=root/"packet"; build_packet_v2_candidate(adm,cap,profile(),out,ir); (out/"sources/S003.bin").write_bytes(b"bad")
   with self.assertRaisesRegex(PacketV2CandidateError,"SOURCE_BYTES_MISMATCH"): verify_packet_v2_candidate(out,adm,cap,profile(),(reader(Api()).observe_issue_body(43),))
if __name__=="__main__": unittest.main()
