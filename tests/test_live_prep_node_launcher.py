"""LP-02 real local Node execution, only the external Python spawn replaced."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
LAUNCHER=ROOT/'.github/actions/v3-pre-model-worker-launch/index.js'


class NodeLauncherTests(unittest.TestCase):
    def environment(self):
        return dict(PATH=os.environ['PATH'],HOME='/private/test-home',LANG='C.UTF-8',
            **{'INPUT_REQUEST-ID':'request:sha256:'+'a'*64,
               'INPUT_RESERVATION-ID':'preparation-dispatch:sha256:'+'b'*64,
               'INPUT_GENERATION':'1'},
            ACTIONS_RUNTIME_TOKEN='fixture-artifact',ACTIONS_RESULTS_URL='https://fixture.invalid',
            GITHUB_TOKEN='fixture-control',REVIEW_BROKER_SOURCE_TOKEN='fixture-source-B',
            REVIEW_BROKER_ARTIFACT_HELPER_ROOT='/trusted/helper',
            REVIEW_BROKER_SOURCE_APP_SLUG='review-broker-app',REVIEW_BROKER_SOURCE_INSTALLATION_ID='123',
            ARBITRARY_AMBIENT_SECRET='must-not-reach-python',GH_TOKEN='must-not-reach-python',
            NODE_OPTIONS='',REVIEW_BROKER_V3_LIVE_PREP_SHA='owner-gate-not-for-child',
            REVIEW_BROKER_NODE_EXECUTABLE='/arbitrary/substitution')

    def execute(self,script,env=None):
        p=subprocess.run(['node','-e',script,str(LAUNCHER)],env=env or self.environment(),
            capture_output=True,text=True,check=True,timeout=20)
        return json.loads(p.stdout)

    def test_LP02_03_10_exactly_one_python_and_allowlist(self):
        value=self.execute("""const m=require(process.argv[1]);let calls=[];
const code=m.launch((exe,args,opts)=>{calls.push({exe,args,opts});return {status:23}});
process.stdout.write(JSON.stringify({code,calls,node:process.execPath}));""")
        self.assertEqual(value['code'],23);self.assertEqual(len(value['calls']),1)
        call=value['calls'][0];env=call['opts']['env']
        self.assertEqual(call['exe'],'python')
        self.assertEqual(call['args'][:3],['-m','review_broker.cli','internal-v3-pre-model-worker'])
        self.assertFalse(call['opts']['shell'])
        self.assertEqual(env['ACTIONS_RUNTIME_TOKEN'],'fixture-artifact')
        self.assertEqual(env['ACTIONS_RESULTS_URL'],'https://fixture.invalid')
        self.assertEqual(env['GITHUB_TOKEN'],'fixture-control')
        self.assertEqual(env['REVIEW_BROKER_SOURCE_TOKEN'],'fixture-source-B')
        self.assertEqual(env['REVIEW_BROKER_NODE_EXECUTABLE'],value['node'])
        for key in ('ARBITRARY_AMBIENT_SECRET','GH_TOKEN','NODE_OPTIONS',
                    'REVIEW_BROKER_V3_LIVE_PREP_SHA','REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY'):
            self.assertNotIn(key,env)

    def test_LP02_09_private_key_or_bad_input_refuses_without_spawn(self):
        script="""const m=require(process.argv[1]);let calls=0,rejected=false;
try {m.launch(()=>{calls++;return {status:0}})}catch(_){rejected=true}
process.stdout.write(JSON.stringify({calls,rejected}));"""
        for key,value in (('REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY','fake-private-key'),
                          ('INPUT_GENERATION','2'),('INPUT_REQUEST-ID','arbitrary'),
                          ('ACTIONS_RUNTIME_TOKEN','')):
            env=self.environment();env[key]=value
            self.assertEqual(self.execute(script,env),{'calls':0,'rejected':True})

    def test_LP02_11_12_nonzero_and_exception_never_respawn(self):
        for result in ('return {status:9}','throw new Error("external Python launch failure")',
                       'return {status:null,signal:"SIGTERM"}'):
            value=self.execute("const m=require(process.argv[1]);let calls=0,code=1;try{code=m.launch(()=>{calls++;"+
                result+"})}catch(_){};process.stdout.write(JSON.stringify({calls,code}));")
            self.assertEqual(value['calls'],1);self.assertNotEqual(value['code'],0)

    def test_LP02_01_02_metadata_has_no_lifecycle_or_npm_dependency(self):
        text=LAUNCHER.with_name('action.yml').read_text()
        self.assertIn('using: node24',text);self.assertIn('main: index.js',text)
        self.assertNotIn('pre:',text);self.assertNotIn('post:',text)
        self.assertFalse(LAUNCHER.with_name('package.json').exists())
        source=LAUNCHER.read_text()
        for term in ('npm install','fetch(','https.request','upload-artifact','prepare.py','continue.py'):
            self.assertNotIn(term,source)
