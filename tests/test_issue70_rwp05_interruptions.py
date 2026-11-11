"""Concrete before/after phase cuts and actual per-cut decision/effect measurements."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.pre_model_failure_continuation_v3 import PreModelFailureResultV3
from review_broker.packet_v2_technical_policy import AuthorizedPolicyVerificationV3
from review_broker.github_prepared_artifact_v3 import GitHubPreparedArtifactV3
import review_broker.pre_model_remote_retention_v3 as remote_module
from tests.issue70_rwp05_test_support import FailureScenario
from tests.issue70_rwp05_remote_support import RemoteFailureScenario


def measure(s,phase,after,result):
    snapshot=s.current();ticket=s.producer._decision
    outcome=getattr(result,'journal_outcome',None)
    failure_outcome=outcome.status.value if type(result) is PreModelFailureResultV3 and outcome else 'NOT_ENTERED'
    active=False
    if ticket is not None:
        try:ticket.require_active(s.remote if hasattr(s,'remote') else s.producer);active=True
        except ValueError:pass
    return dict(phase=phase,after=after,continuation_outcome=None if result is None else result.status.value,
        failure_journal_outcome=failure_outcome,transport_state=snapshot.record.attempt.state.value,
        transport_disposition=snapshot.record.control.disposition,invocations=snapshot.record.attempt.invocation_count,
        ticket_state=None if ticket is None else ticket.state.value,
        observation_status=getattr(result,'observation_status','NONE'),
        remaining_authority='ORIGINAL_ACTIVE_DECISION_REQUIRES_CURRENT_GUARD' if active else 'OBSERVER_ONLY',
        journal_still_at_original_a=snapshot.commit_sha==s.authority.snapshot.commit_sha,
        retained_observations=len(list(s.archive.root.iterdir())),observation_puts=len(s.archive.puts),
        failure_cas=s.failure_cas_count(),prepared_cas=s.real.worker.transport.events.count('PREPARED'),
        dispatches=len(s.real.worker.dispatch.calls),captures=s.real.capture_calls,
        uploads=len(s.service.uploads) if hasattr(s,'service') else 0)


def persist_measurements(rows):
    directory=Path('artifacts/rwp05-private');directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='phase-cuts-',suffix='.json',dir=directory)
    with os.fdopen(fd,'w') as stream:json.dump(rows,stream,indent=2)


class FailurePhaseCutTests(unittest.TestCase):
    def scenario(self,remote=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return (RemoteFailureScenario if remote else FailureScenario)(Path(temporary.name),**({} if remote else {'status':200}))

    def test_F23_all_source_packet_phase_cuts_without_catalog_evidence_never_block(self):
        rows=[]
        for phase in ('capture','references','policy-source','policy-selection','build','verify','persist','cold'):
            for after in (False,True):
                s=self.scenario()
                if phase=='capture':target,name=s.real,'capture'
                elif phase=='references':target,name=AuthorizedPolicyVerificationV3,'prepare_references'
                elif phase=='policy-source':target,name=s.real.source_authority,'read_policy'
                elif phase=='policy-selection':target,name=s.real.selection_authority,'select_policy'
                else:target,name=s.real.stages,{'cold':'cold_verify'}.get(phase,phase)
                original=getattr(target,name)
                def cut(*args,**kwargs):
                    if not after:raise RuntimeError('fixture cut before phase')
                    original(*args,**kwargs);raise RuntimeError('fixture cut after phase')
                with patch.object(target,name,cut):result=s.run_packet()
                row=measure(s,phase,after,result);rows.append(row)
                with self.subTest(phase=phase,after=after):
                    self.assertNotEqual(result.status.value,'COMMITTED')
                    self.assertEqual((row['failure_cas'],row['prepared_cas'],row['observation_puts']),(0,0,0))
                    self.assertEqual((row['transport_state'],row['transport_disposition'],row['ticket_state']),('ADMITTED','RESERVED','CLOSED'))
                    self.assertIsNone(s.producer._remote_handoff)
                    self.assertEqual(row['remaining_authority'],'OBSERVER_ONLY')
        persist_measurements(rows)

    def test_F23_upload_download_extract_and_remote_verify_cuts_do_not_invent_cause(self):
        rows=[]
        for phase in ('upload','download','extract','remote-packet'):
            for after in (False,True):
                s=self.scenario(remote=True)
                if phase=='upload':target,name=s.uploader,'upload_once'
                elif phase=='download':target,name=GitHubPreparedArtifactV3,'download'
                elif phase=='extract':target,name=remote_module,'extract_prepared_packet_v3'
                else:target,name=remote_module,'load_packet_evidence_v3'
                original=getattr(target,name)
                def cut(*args,**kwargs):
                    if phase=='remote-packet' and args[0]!=s.remote_root:return original(*args,**kwargs)
                    if not after:raise RuntimeError('fixture cut before remote phase')
                    original(*args,**kwargs);raise RuntimeError('fixture cut after remote phase')
                with patch.object(target,name,cut):result=s.run_remote()
                row=measure(s,phase,after,result);rows.append(row)
                with self.subTest(phase=phase,after=after):
                    self.assertNotEqual(result.status.value,'COMMITTED')
                    self.assertEqual((row['failure_cas'],row['prepared_cas'],row['observation_puts']),(0,0,0))
                    self.assertEqual(row['ticket_state'],'CLOSED')
                    self.assertLessEqual(row['uploads'],1)
                    self.assertEqual(row['remaining_authority'],'OBSERVER_ONLY')
        persist_measurements(rows)

    def test_F23_hard_exit_before_after_observation_conservation_does_not_commit_failure(self):
        rows=[]
        for after in (False,True):
            s=self.scenario();s.reference_status=503
            original=s.archive.put_once
            def cut(*args,**kwargs):
                if after:original(*args,**kwargs)
                raise SystemExit('fixture hard flow interruption')
            with patch.object(s.archive,'put_once',cut),self.assertRaises(SystemExit):s.run_packet()
            row=measure(s,'observation-conservation',after,None);rows.append(row)
            self.assertEqual((row['failure_cas'],row['prepared_cas']),(0,0))
            self.assertEqual(row['ticket_state'],'CLOSED')
            self.assertEqual(row['retained_observations'],1 if after else 0)
            self.assertEqual(row['remaining_authority'],'OBSERVER_ONLY')
            before=len(s.real.worker.transport.proposal_calls);s.producer.run(s.real.worker.context)
            self.assertEqual(len(s.real.worker.transport.proposal_calls),before)
        persist_measurements(rows)
