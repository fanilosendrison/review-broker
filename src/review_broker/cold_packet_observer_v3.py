"""Cold observer over a private, parent-authenticated API corpus; no effect-capable transport."""
from __future__ import annotations

import base64
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .github_actions_identity_v3 import GitHubActionsExpectationV3
from .github_journal_transport_v3 import ReadResultV3,ReadStatusV3,TransportSnapshotV3
from .github_journal_v3 import GitHubJournalV3
from .identity import canonical_bytes,artifact_identity
from .packet_retention_v3 import load_packet_evidence_v3
from .packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from .pre_model_dispatch_ack_v3 import DispatchAcknowledgmentV3,acknowledgment_from_record
from .pre_model_policy_source_v3 import PolicySourceObservationV3
from .pre_model_policy_selection_v3 import PolicySelectionReceiptV3
from .prepared_journal_history_v3 import PreparedJournalHistoryV3
from .prepared_packet_readback_v3 import reconstruct_prepared_packet_v3
from .historical_policy_verification_v3 import HistoricalAuthorizedPolicyVerificationV3
from .cold_network_boundary_v3 import minimal_environment


class FrozenApiCorpusV3:
    """An explicitly trusted local channel, populated only AFTER independent API verification.

    Neither packet/archive bytes nor caller booleans populate this corpus. A new
    observer may recollect it from GitHub. It cannot authorize an active operation.
    """
    def __init__(self,value):
        self.value=value;self.expected=GitHubActionsExpectationV3(**value['expected'])
        self.snapshots={x['sha']:TransportSnapshotV3(x['sha'],x['parent'],base64.b64decode(x['bytes']))
            for x in value['snapshots']}
        self.source=PolicySourceObservationV3.from_bytes(base64.b64decode(value['policy_source']))
        self.selection=PolicySelectionReceiptV3.from_bytes(base64.b64decode(value['policy_selection']))
        self.policy=base64.b64decode(value['policy_bytes'])
        self.ack=DispatchAcknowledgmentV3.from_dict(value['ack'])

    def read_claim(self,claim_ref):
        if claim_ref!=self.value['claim_ref']:raise ValueError('COLD_CLAIM_MISMATCH')
        return self.read_journal_commit(self.value['current_sha'])

    def read_journal_commit(self,sha):
        snapshot=self.snapshots.get(sha)
        return ReadResultV3(ReadStatusV3.FOUND,snapshot) if snapshot else ReadResultV3(ReadStatusV3.MISSING)

    def create_journal_commit(self,*args,**kwargs):raise ValueError('COLD_OBSERVER_ONLY')
    def create_ref(self,*args,**kwargs):raise ValueError('COLD_OBSERVER_ONLY')
    def update_ref(self,*args,**kwargs):raise ValueError('COLD_OBSERVER_ONLY')
    def select_policy(self,*args,**kwargs):raise ValueError('COLD_OBSERVER_CANNOT_SELECT')
    def read_policy(self,*args,**kwargs):raise ValueError('COLD_OBSERVER_CANNOT_CAPTURE')

    def evidence_id(self,*,repository=None,snapshot=None,request=None,admission=None,claim_ref=None,request_id=None):
        if snapshot is not None:
            if self.snapshots.get(snapshot.commit_sha)!=snapshot:return None
            from .github_journal_transition_authority_v3 import transition_target_identity_v3
            return transition_target_identity_v3(repository=self.value['repository'],
                repository_node_id=self.value['node_id'],claim_ref=self.value['claim_ref'],
                predecessor_sha=snapshot.parent_sha,successor_sha=snapshot.commit_sha)
        if repository!=self.value['repository'] or admission!=self.value['admission'] or request!=admission['canonical_request']:
            return None
        return artifact_identity(canonical_bytes(admission)+b'\n')

    def permits_evidence(self,*,evidence_id,**values):
        if 'admission' in values:
            if values.get('request_id')!=self.value['admission']['request_id']:return False
            values['request']=values['admission']['canonical_request']
        return evidence_id is not None and evidence_id==self.evidence_id(**values)
    def permits(self,update,evidence_id):
        snapshot=self.snapshots.get(update.after_oid)
        return (snapshot is not None and update.force is False and snapshot.parent_sha==update.before_oid
            and update.repository_id==self.value['node_id'] and update.name==self.value['claim_ref']
            and evidence_id==self.evidence_id(snapshot=snapshot))
    def authenticates(self,receipt,*,dispatch_principal_id):
        return receipt==self.ack and dispatch_principal_id==self.value['principal']
    def verify_source(self,observation,original_bytes,expectation,*,before_effect=None):
        if before_effect:before_effect()
        if (observation!=self.source or original_bytes!=self.policy or expectation!=self.expected):
            raise ValueError('COLD_INDEPENDENT_SOURCE_REJECTED')
    def verify_selection(self,receipt,source,context,expectation,*,before_effect=None):
        if before_effect:before_effect()
        if (receipt!=self.selection or source!=self.source or expectation!=self.expected
                or any(receipt.basis[k]!=v for k,v in context.basis.items())):
            raise ValueError('COLD_INDEPENDENT_SELECTION_REJECTED')


def collect_api_corpus_v3(*,journal,snapshot,expected,policy,dispatch,packet_root,prepared=False):
    """Authenticate outside the network-denied child, independently of packet assertions."""
    if prepared:
        history=PreparedJournalHistoryV3.read(journal,snapshot.record.attempt.request_id,
            expected,dispatch,dispatch.principal_id(acknowledgment_from_record(snapshot.record)))
        a=history.admitted
        verification=HistoricalAuthorizedPolicyVerificationV3(history,policy,policy)
        snapshots=(a,history.prepared)
    else:
        a=snapshot;verification=AuthorizedPolicyVerificationV3(journal,a,expected,policy,policy)
        snapshots=(a,)
    _,_,profile,_=load_packet_evidence_v3(packet_root,a.record.attempt.admission,policy_verification=verification)
    ack=acknowledgment_from_record(a.record)
    return dict(schema_version=1,repository=journal.repository,node_id=journal.repository_node_id,
        claim_ref=a.claim_ref,current_sha=snapshot.commit_sha,base_sha=journal.base_sha,
        expected=asdict(expected),admission=a.record.attempt.admission,ack=ack.as_dict(),
        principal=dispatch.principal_id(ack),prepared=prepared,
        snapshots=[{'sha':s.commit_sha,'parent':s.parent_sha,'bytes':base64.b64encode(s.journal_bytes).decode()} for s in snapshots],
        policy_source=base64.b64encode(profile.source.canonical_receipt_bytes).decode(),
        policy_selection=base64.b64encode(profile.selection.canonical_receipt_bytes).decode(),
        policy_bytes=base64.b64encode(profile.original_bytes).decode())


def run_cold_observer_v3(*,corpus,packet_root,private_base,before_effect,storage=None):
    before_effect()
    directory=Path(tempfile.mkdtemp(prefix='cold-observer-',dir=private_base))
    path=directory/'authenticated-api-corpus.json'
    if storage is not None:corpus={**corpus,'storage':storage}
    before_effect()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(canonical_bytes(corpus)+b'\n')
    before_effect()
    result=subprocess.run([sys.executable,'-m','review_broker.cold_packet_observer_v3',str(path),str(packet_root)],
        env=minimal_environment(directory),stdin=subprocess.DEVNULL,capture_output=True,text=True,
        close_fds=True,pass_fds=(),timeout=120,check=True)
    return json.loads(result.stdout)


def main():
    if sys.platform=='linux':
        from .cold_network_boundary_v3 import require_no_socket_descriptors,install_filter,require_installed_filter
        require_no_socket_descriptors();install_filter();require_installed_filter()
    path,root=map(Path,sys.argv[1:])
    if path.is_symlink() or path.stat().st_mode&0o077 or path.stat().st_size>8_000_000:
        raise ValueError('COLD_API_CHANNEL_NOT_PRIVATE_BOUNDED')
    data=json.loads(path.read_bytes());corpus=FrozenApiCorpusV3(data)
    journal=GitHubJournalV3(data['repository'],data['node_id'],data['base_sha'],corpus,corpus,corpus,corpus,corpus)
    snapshot=journal.read(data['admission']['request_id'])
    if data['prepared']:
        history=PreparedJournalHistoryV3.read(journal,data['admission']['request_id'],corpus.expected,corpus,data['principal'])
        reconstructed=reconstruct_prepared_packet_v3(root,history=history,source_authority=corpus,
            selection_authority=corpus,authenticated_storage=data['storage'])
        output={'packet_id':reconstructed.packet_id,'remote_receipt_id':reconstructed.remote_receipt.evidence_id}
    else:
        verification=AuthorizedPolicyVerificationV3(journal,snapshot,corpus.expected,corpus,corpus)
        _,_,_,output=load_packet_evidence_v3(root,data['admission'],policy_verification=verification)
    sys.stdout.write(canonical_bytes(output).decode()+'\n')


if __name__=='__main__':main()
