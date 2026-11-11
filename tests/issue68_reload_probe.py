"""Fresh-interpreter cold verification probe for Issue #68 tests."""
import json,sys
from pathlib import Path
from tests.issue68_test_support import ExactAdmissionAuthority,REPOSITORY,restore_transport
from tests.journal_v3_test_support import BASE_SHA,NODE_ID,TrustedMutationAuthority,TrustedPredecessorAuthority,TrustedRejectionAuthority
from review_broker.github_journal_v3 import GitHubJournalV3
from review_broker.packet_preparation_authority_v3 import verify_prepared_readback_v3

def main():
 retention,transport_path,request_id=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
 transport=restore_transport(transport_path);claim=GitHubJournalV3.claim_ref(request_id);raw=transport.commits[transport.refs[claim]].journal_bytes
 admission=json.loads(raw)["admission"]
 journal=GitHubJournalV3(REPOSITORY,NODE_ID,BASE_SHA,transport,ExactAdmissionAuthority(admission),TrustedMutationAuthority(),TrustedRejectionAuthority(),TrustedPredecessorAuthority())
 result=verify_prepared_readback_v3(retention,journal.read(request_id));sys.stdout.write(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
