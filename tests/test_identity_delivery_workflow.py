"""Execute the actual workflow delivery script against offline GitHub/SSH oracles."""
from dataclasses import asdict
import copy
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from review_broker.codespace_identity import validate_recipient
from tests.test_prearm_workflow_cleanup import workflow_step

class IdentityDeliveryWorkflowTests(unittest.TestCase):
    def test_actual_delivery_script_revalidates_every_binding_before_ssh(self):
        for scenario in ['valid','missing','id','owner-id','owner-login','repo-id','repo-name','name','ambiguous']:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                value={'id':12,'name':'fixture-space','owner':{'login':'owner','id':23},
                       'repository':{'full_name':'sample/broker','id':34}}
                user={'login':'owner','id':23}
                original=validate_recipient(value,user,selection='fixture-space',repository='sample/broker',repository_id='34')
                (root/'review-broker-recipient.json').write_text(json.dumps(asdict(original)))
                (root/'review-broker-arm-authorization.json').write_bytes(b'synthetic-nonproduction')
                current=copy.deepcopy(value)
                if scenario=='missing':current={}
                elif scenario=='id':current['id']=13
                elif scenario=='owner-id':current['owner']['id']=24
                elif scenario=='owner-login':current['owner']['login']='other'
                elif scenario=='repo-id':current['repository']['id']=35
                elif scenario=='repo-name':current['repository']['full_name']='other/broker'
                elif scenario=='name':current['name']='different-space'
                api_calls=[];transports=[]
                def runner(command,**kwargs):
                    if command[:2]==['gh','api']:
                        api_calls.append(command[2])
                        data=user if command[2]=='user' else current
                        raw=json.dumps(data)
                        if scenario=='ambiguous' and command[2]!='user':raw='{"id":12,"id":13}'
                        return subprocess.CompletedProcess(command,0,stdout=raw)
                    self.assertEqual(command[:3],['gh','codespace','ssh'])
                    self.assertEqual(len(api_calls),2)
                    tokens=shlex.split(command[-1])
                    self.assertEqual(tokens[:4],['env','-u','PYTHONPATH','CODESPACE_NAME=fixture-space'])
                    self.assertNotIn('CODESPACES=true',tokens)
                    self.assertEqual(kwargs['stdin'].read(),b'synthetic-nonproduction')
                    self.assertIn("attempt;$(not-executed)'",tokens)
                    transports.append(command)
                    return subprocess.CompletedProcess(command,0)
                step=workflow_step('Invoke Codex once')
                code=textwrap.dedent(step.split('        run: |\n',1)[1])
                code=code.split("python - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
                env=dict(RUNNER_TEMP=tmp,EXPECTED_CODESPACE_ID='12',CODESPACE_NAME='fixture-space',
                    GITHUB_REPOSITORY='sample/broker',GITHUB_REPOSITORY_ID='34',REMOTE_ROOT='/tmp/fixture',
                    ATTEMPT_ID="attempt;$(not-executed)'",PACKET_ID='packet',BROKER_WHEEL_SHA256='f'*64,
                    CODEX_RUNTIME_ROOT='/fixture/runtime')
                with patch.dict(os.environ,env),patch('subprocess.run',side_effect=runner):
                    if scenario=='valid':exec(compile(code,'workflow-invoke','exec'),{})
                    else:
                        with self.assertRaises(ValueError):exec(compile(code,'workflow-invoke','exec'),{})
                self.assertEqual(len(transports),1 if scenario=='valid' else 0,'Unauthorized SSH/model transport forbidden')

    def test_existing_event_guard_is_unchanged(self):
        text=(Path(__file__).parents[1]/'.github/workflows/review-request.yml').read_text()
        self.assertIn("github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",text)
        for marker in ['workflow_dispatch','<!-- review-broker-request:v1 -->','<!-- review-broker-request:v2 -->']:
            self.assertIn(marker,text)
        self.assertNotIn('qualification_only',text)
