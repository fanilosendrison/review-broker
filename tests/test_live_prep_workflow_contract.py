"""Independent YAML/launcher/CLI oracles for protected code and literal input provenance."""
import ast
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import yaml

ROOT=Path(__file__).resolve().parents[1]
APP='actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349'


def document(path):return yaml.load(path.read_text(),Loader=yaml.BaseLoader)


class WorkflowContractTests(unittest.TestCase):
    def test_active_events_inputs_permissions_and_owner_gates_are_exact(self):
        for role,actions in (('controller','write'),('worker','read')):
            path=ROOT/f'.github/workflows/v3-pre-model-{role}.yml';value=document(path)
            stub=document(ROOT/f'tests/fixtures/v3-registration-stubs/{role}.yml')
            self.assertEqual(set(value['on']),{'workflow_dispatch'})
            self.assertEqual(value['on'],stub['on'])
            self.assertEqual(value['permissions'],{'contents':'write','actions':actions,'issues':'read'})
            self.assertEqual(set(value['jobs']),{role});job=value['jobs'][role]
            self.assertEqual(job['name'],role);self.assertEqual(job['runs-on'],'ubuntu-24.04')
            for gate in ('REVIEW_BROKER_V3_LIVE_PREP_SHA','REVIEW_BROKER_V3_LIVE_REQUEST_ID',
                         'REVIEW_BROKER_V3_LIVE_REQUEST_ISSUE','REVIEW_BROKER_V3_LIVE_REQUEST_BODY_SHA256'):
                self.assertIn('vars.'+gate,job['if'])
            self.assertIn("github.repository_id == '1433701208'",job['if'])
            self.assertIn('github.run_attempt == 1',job['if'])
            self.assertIn('github.workflow_ref == format(',job['if'])

    def test_both_mints_have_same_exact_read_profile_and_no_key_leaves_mint_step(self):
        required={'app-id':'${{ vars.REVIEW_BROKER_SOURCE_APP_ID }}',
            'private-key':'${{ secrets.REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY }}',
            'owner':'fanilosendrison','repositories':'review-broker',
            'permission-contents':'read','permission-pull-requests':'read',
            'permission-metadata':'read','permission-issues':'read'}
        for role in ('controller','worker'):
            value=document(ROOT/f'.github/workflows/v3-pre-model-{role}.yml');job=value['jobs'][role]
            steps=job['steps'];mints=[s for s in steps if s.get('uses')==APP]
            self.assertEqual(len(mints),1);self.assertEqual(mints[0]['with'],required)
            self.assertNotIn('REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY',json.dumps(job.get('env',{})))
            for step in steps:
                if step is not mints[0]:self.assertNotIn('PRIVATE_KEY',json.dumps(step))

    def test_ACK_precedes_mint_and_only_literal_node_mapping_can_start_original_worker(self):
        job=document(ROOT/'.github/workflows/v3-pre-model-worker.yml')['jobs']['worker'];steps=job['steps']
        gate=next(i for i,s in enumerate(steps) if 'internal-v3-wait-dispatch-ack' in s.get('run',''))
        mint=next(i for i,s in enumerate(steps) if s.get('uses')==APP)
        node=next(i for i,s in enumerate(steps) if s.get('uses')=='./.github/actions/v3-pre-model-worker-launch')
        self.assertLess(gate,mint);self.assertLess(mint,node);self.assertEqual(node,len(steps)-1)
        self.assertNotIn('continue-on-error',steps[gate])
        self.assertNotIn('if',steps[mint]);self.assertNotIn('if',steps[node])
        self.assertEqual(steps[node]['with'],{'request-id':'${{ inputs.request_id }}',
            'reservation-id':'${{ inputs.reservation_id }}','generation':'${{ inputs.generation }}'})
        self.assertEqual(steps[node]['env']['REVIEW_BROKER_SOURCE_TOKEN'],'${{ steps.source.outputs.token }}')
        self.assertNotIn('internal-v3-pre-model-worker', '\n'.join(s.get('run','') for s in steps))
        for forbidden in ('internal-arm','codespace','internal-invoke','upload-artifact@'):
            self.assertNotIn(forbidden,json.dumps(job).lower())
        # The only public helper checkout is fully pinned and checked before Python.
        helper=next(s for s in steps if s.get('with',{}).get('repository')=='actions/upload-artifact')
        self.assertEqual(helper['with']['ref'],'cf430e030ddbb5b0abf93d22962f4752f3646cd9')
        self.assertEqual(helper['with']['persist-credentials'],'false')
        text=(ROOT/'.github/workflows/v3-pre-model-worker.yml').read_text()
        self.assertIn('7b3f92ae681d6eeca5f5e5e4cf892ad0dfb254ea',text)

    def test_controller_runtime_start_gate_precedes_mint_and_no_artifact_or_packet_step(self):
        steps=document(ROOT/'.github/workflows/v3-pre-model-controller.yml')['jobs']['controller']['steps']
        gate=next(i for i,s in enumerate(steps) if 'internal-v3-controller-start-gate' in s.get('run',''))
        mint=next(i for i,s in enumerate(steps) if s.get('uses')==APP)
        self.assertLess(gate,mint)
        self.assertIn('internal-v3-pre-model-controller',steps[-1]['run'])
        self.assertNotIn('upload-artifact',json.dumps(steps))
        self.assertNotIn('internal-v3-pre-model-worker',json.dumps(steps))

    def test_cli_removes_source_token_before_dispatch_without_leaking_errors(self):
        from review_broker import cli
        output=io.StringIO()
        with patch.dict(os.environ,{'REVIEW_BROKER_SOURCE_TOKEN':'fixture-source-not-to-be-printed'},clear=True),redirect_stdout(output):
            code=cli.main(['internal-v3-pre-model-controller','--issue','51','--request-id','request:sha256:'+'a'*64])
            self.assertNotIn('REVIEW_BROKER_SOURCE_TOKEN',os.environ)
        self.assertEqual(code,1);self.assertNotIn('fixture-source',output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['status'],'REJECTED')
        for p in (ROOT/'src/review_broker').glob('*live*v3.py'):
            self.assertNotIn('os.environ.get("REVIEW_BROKER_SOURCE_TOKEN"',p.read_text())

    def test_launcher_engine_is_qualified_on_actual_linux_node24(self):
        version=subprocess.check_output(['node','--version'],text=True).strip()
        if sys.platform=='linux':self.assertEqual(int(version.split('.')[0][1:]),24)
        action=document(ROOT/'.github/actions/v3-pre-model-worker-launch/action.yml')
        self.assertEqual(action['runs'],{'using':'node24','main':'index.js'})
        self.assertEqual(set(action['inputs']),{'request-id','reservation-id','generation'})
