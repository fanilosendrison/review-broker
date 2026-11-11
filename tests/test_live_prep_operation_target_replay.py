"""Second independent review: real emitted ref target and accepted receiver identity."""
import copy
import pickle
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.github_git_database_transport_v3 import GitHubJournalEvidenceTransportV3
from review_broker.github_actions_controller_authority_v3 import GitHubActionsControllerAuthorityV3
from review_broker.identity import canonical_bytes
from tests.live_prep_provider_support import LiveProviderService,controller_scenario


class OperationTargetReplayTests(unittest.TestCase):
    def test_R3_unrelated_ref_cannot_borrow_original_missing_ref_guard(self):
        original=GitHubJournalEvidenceTransportV3.create_ref;attempts=[]
        other='refs/heads/review-claims-v3/'+'f'*64
        def interpose(transport,ref,sha):
            if not attempts:
                attempts.append('attempted')
                try:original(transport,other,sha)
                except (ValueError,RuntimeError):attempts.append('refused')
                # A second detached provider commit with the same genuine tree/
                # parent is valid Git data but is NOT this operation's successor.
                alternate='a0'*20
                service.git.commits[alternate]=service.git.commits[sha]
                try:original(transport,ref,alternate)
                except (ValueError,RuntimeError):attempts.append('successor refused')
                try:transport._rest('POST','/git/refs',{'ref':other,'sha':sha,'query':'query'})
                except (ValueError,RuntimeError):attempts.append('REST query field refused')
            return original(transport,ref,sha)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubJournalEvidenceTransportV3,'create_ref',interpose):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            refs=[c for c in service.git.calls if c[0]=='POST' and c[1].endswith('/git/refs')]
            self.assertNotIn(other,service.git.refs)
            self.assertEqual(len(refs),1)
            self.assertEqual(refs[0][2]['sha'],result.claim_outcome.snapshot.commit_sha)
            self.assertEqual(service.claim_count(),1)

    def test_R5_readonly_composition_never_accepts_REST_write_with_query_field(self):
        from review_broker.live_journal_composition_v3 import live_journal_v3,GitHubOriginalAdmissionAuthorityV3
        from review_broker.request_v3 import request_identity_v3
        from tests.live_prep_actions_support import SHA
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            identifier=request_identity_v3(service.request)
            runtime=service.runtime('controller',{'request_issue_number':51,'request_id':identifier})
            def deny():raise ValueError('read-only composition')
            journal=live_journal_v3(runtime,GitHubOriginalAdmissionAuthorityV3(runtime.api),write_guard=deny)
            before=service.git.mutation_calls
            for query in ('query','query {}','query($owner:String!){repository{id}}'):
                with self.assertRaises((ValueError,RuntimeError)):
                    journal.transport._rest('POST','/git/refs',{
                        'ref':'refs/heads/review-claims-v3/'+'d'*64,'sha':SHA,'query':query})
            with self.assertRaises((ValueError,RuntimeError)):
                journal.transport._graphql('query { viewer { id } }',{})
            self.assertEqual(service.git.mutation_calls,before)
            self.assertEqual(service.claim_count(),0)

    def test_R3_intended_ref_mutation_opportunity_is_consumed_once(self):
        original=GitHubJournalEvidenceTransportV3.create_ref;attempts=[]
        def duplicate(transport,ref,sha):
            result=original(transport,ref,sha)
            if not attempts:
                attempts.append('attempted')
                original(transport,ref,sha)
            return result
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubJournalEvidenceTransportV3,'create_ref',duplicate):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertEqual(len([c for c in service.git.calls if c[0]=='POST' and c[1].endswith('/git/refs')]),1)

    def test_R3_CAS_payload_predecessor_successor_ref_and_query_match_operation(self):
        from review_broker.github_git_database_transport_v3 import GitHubTransportLiveV3
        original=GitHubTransportLiveV3._graphql;attempts=[]
        def variants(transport,query,variables):
            if query.startswith('mutation') and not attempts:
                attempts.append('checked')
                for change in ({'name':'refs/heads/review-claims-v3/'+'e'*64},
                        {'beforeOid':'0'*40},{'afterOid':'0'*40},{'force':True},{'force':0},{'force':0.0},
                        {'repositoryId':'R_wrong'},{'extra':'not-in-operation'}):
                    try:original(transport,query,{**variables,**change})
                    except (ValueError,RuntimeError):attempts.append('refused')
                try:original(transport,query+' ',variables)
                except (ValueError,RuntimeError):attempts.append('query refused')
            return original(transport,query,variables)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubTransportLiveV3,'_graphql',variants):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            mutations=[c for c in service.git.calls if c[0]=='POST' and c[1].endswith('/graphql')
                and c[2]['query'].startswith('mutation')]
            self.assertEqual(len(mutations),2)  # reservation and ACK only
            self.assertEqual(attempts.count('refused'),8)
            self.assertIn('query refused',attempts)

    def test_R3_preparation_payloads_cannot_change_original_journal_or_parent(self):
        from review_broker.github_git_database_transport_v3 import GitHubTransportLiveV3
        original=GitHubTransportLiveV3._rest;seen=set();refused=[]
        def variants(transport,method,suffix,payload=None):
            if method=='POST' and suffix in {'/git/blobs','/git/trees','/git/commits'} and suffix not in seen:
                seen.add(suffix)
                changes=({'content':'bm90LW9yaWdpbmFs'} if suffix=='/git/blobs' else
                         {'base_tree':'0'*40} if suffix=='/git/trees' else {'parents':['0'*40]})
                try:original(transport,method,suffix,{**payload,**changes})
                except (ValueError,RuntimeError):refused.append(suffix)
            return original(transport,method,suffix,payload)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubTransportLiveV3,'_rest',variants):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertEqual(set(refused),{'/git/blobs','/git/trees','/git/commits'})
            self.assertEqual(service.git.mutation_calls,12)  # three original operations, four requests each

    def test_R4_copied_accepted_receiver_cannot_authorize_or_supply_evidence(self):
        original=GitHubActionsControllerAuthorityV3.accept_source_admission;seen={}
        def observe(receiver,source,admission,issuer):
            original(receiver,source,admission,issuer)
            seen.update(source=source,admission=admission,receiver=receiver)
            try:seen['copy']=copy.copy(receiver)
            except ValueError:seen['copy_refused']=True
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubActionsControllerAuthorityV3,'accept_source_admission',observe):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertTrue(seen['source'].closed)
            before=service.git.mutation_calls
            if 'copy' in seen:
                candidate=seen['copy'];admission=seen['admission']
                try:
                    decision=candidate.authorize(broker_repository=candidate.runtime.expected.repository,
                        broker_repository_node_id=service.node_id,target=candidate.target,
                        journal_admission_bytes=canonical_bytes(admission.journal_admission()),
                        origin_body_bytes=admission.origin_body_bytes)
                except (ValueError,RuntimeError):decision=None
                self.assertIsNone(decision,'copied receiver recreated active admission authorization')
                try:identity=candidate.evidence_id(repository=candidate.runtime.expected.repository,
                    request=admission.request,admission=admission.journal_admission())
                except (ValueError,RuntimeError):identity=None
                self.assertIsNone(identity)
            self.assertTrue(seen.get('copy_refused'))
            for operation in (copy.copy,copy.deepcopy,pickle.dumps):
                with self.assertRaises(ValueError):operation(seen['receiver'])
            # Preserve a raw shallow state clone without inventing field values:
            # original-instance guards must still reject it beyond copy hooks.
            shadow=object.__new__(GitHubActionsControllerAuthorityV3)
            vars(shadow).update(vars(seen['receiver']))
            with self.assertRaises(ValueError):shadow.require_current()
            with self.assertRaises(ValueError):
                shadow.authorize(broker_repository=shadow.runtime.expected.repository,
                    broker_repository_node_id=service.node_id,target=shadow.target,
                    journal_admission_bytes=canonical_bytes(seen['admission'].journal_admission()),
                    origin_body_bytes=seen['admission'].origin_body_bytes)
            with self.assertRaises(ValueError):
                shadow.evidence_id(repository=shadow.runtime.expected.repository,
                    request=seen['admission'].request,admission=seen['admission'].journal_admission())
            fresh=GitHubActionsControllerAuthorityV3(seen['receiver'].runtime,
                issue=seen['receiver'].issue,request_id=seen['receiver'].request_id,gates=seen['receiver'].gates)
            self.assertIsNone(fresh.authorize(broker_repository=fresh.runtime.expected.repository,
                broker_repository_node_id=service.node_id,target=fresh.target,
                journal_admission_bytes=canonical_bytes(seen['admission'].journal_admission()),
                origin_body_bytes=seen['admission'].origin_body_bytes))
            self.assertIsNone(fresh.evidence_id(repository=fresh.runtime.expected.repository,
                request=seen['admission'].request,admission=seen['admission'].journal_admission()))
            self.assertEqual(service.git.mutation_calls,before)
