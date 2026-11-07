"""Independent reviewer copy counterexamples at genuine source/reservation moments."""
import copy
import pickle
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from review_broker.github_actions_initial_dispatch_v3 import GitHubActionsInitialDispatchTransportV3
from review_broker.github_actions_controller_authority_v3 import GitHubActionsControllerAuthorityV3
from tests.live_prep_provider_support import LiveProviderService,controller_scenario


class OriginalInstanceReplayTests(unittest.TestCase):
    def test_R1_copy_during_original_dispatch_observation_cannot_emit_second_POST(self):
        holder={};original_bind=GitHubActionsInitialDispatchTransportV3.bind_controller
        def observed_bind(transport,controller):
            original_bind(transport,controller);holder['original']=transport
            try:holder['copy']=copy.copy(transport)
            except ValueError:holder['copy_refused']=True
        class Service(LiveProviderService):
            def __call__(self,request):
                transport=holder.get('original');controller=None if transport is None else transport._controller
                if (controller is not None and controller._dispatch_issuance_gate is not None
                        and not holder.get('attempted') and urlsplit(request.full_url).path.endswith('/actions/runs/60001')):
                    holder['attempted']=True
                    candidate=holder.get('copy')
                    if candidate is not None:
                        try:
                            candidate.bind_initial_reservation(controller,controller._dispatch_issuance_gate)
                            candidate.dispatch(controller._dispatch_issuance_request)
                        except ValueError:holder['copy_refused']=True
                return super().__call__(request)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=Service(root)
            with patch.object(GitHubActionsInitialDispatchTransportV3,'bind_controller',observed_bind):
                result=controller_scenario(root,service)
            posts=[c for c in service.calls if c[0]=='POST']
            self.assertTrue(holder.get('attempted'))
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertEqual(len(posts),1,'copied transport emitted a second dispatch')
            self.assertTrue(holder.get('copy_refused'))
            for operation in (copy.copy,copy.deepcopy,pickle.dumps):
                with self.assertRaises(ValueError):operation(holder['original'])
            self.assertTrue(holder['original']._controller._dispatch_opportunity_consumed)
            self.assertEqual(service.mints,['controller']);self.assertEqual(service.claim_count(),1)

    def test_R2_copy_or_wrong_receiver_cannot_replay_source_registration(self):
        holder={};original_accept=GitHubActionsControllerAuthorityV3.accept_source_admission
        def measured_accept(receiver,source,admission,issuer):
            holder.update(receiver=receiver,source=source,admission=admission,issuer=issuer)
            try:holder['copy']=copy.copy(source)
            except ValueError:holder['copy_refused']=True
            fresh=GitHubActionsControllerAuthorityV3(receiver.runtime,issue=receiver.issue,
                request_id=receiver.request_id,gates=receiver.gates)
            try:original_accept(fresh,source,admission,issuer);holder['wrong_receiver_accepted']=True
            except ValueError:holder['wrong_receiver_refused']=True
            return original_accept(receiver,source,admission,issuer)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();service=LiveProviderService(root)
            with patch.object(GitHubActionsControllerAuthorityV3,'accept_source_admission',measured_accept):
                result=controller_scenario(root,service)
            self.assertEqual(result.status.value,'DISPATCH_ACKNOWLEDGED',result)
            self.assertTrue(holder['source'].closed)
            before=service.git.mutation_calls
            if 'copy' in holder:
                receiver=holder['receiver'];fresh=GitHubActionsControllerAuthorityV3(receiver.runtime,
                    issue=receiver.issue,request_id=receiver.request_id,gates=receiver.gates)
                with self.assertRaises(ValueError):
                    original_accept(fresh,holder['copy'],holder['admission'],holder['issuer'])
            self.assertFalse(holder.get('wrong_receiver_accepted',False))
            self.assertTrue(holder.get('wrong_receiver_refused'))
            self.assertTrue(holder.get('copy_refused'))
            self.assertEqual(service.git.mutation_calls,before)
            for operation in (copy.copy,copy.deepcopy,pickle.dumps):
                with self.assertRaises(ValueError):operation(holder['source'])
            with self.assertRaises(ValueError):
                original_accept(holder['receiver'],holder['source'],holder['admission'],holder['issuer'])
            self.assertEqual(service.git.mutation_calls,before)
