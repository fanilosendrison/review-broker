"""Authenticated routing context is neither shell code nor execution authority."""
import copy
import json
import shlex
import unittest
from review_broker.codespace_identity import validate_recipient, parse_api, context_command
from review_broker.codex_policy import sanitized_environment

class CodespaceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.value={'id':12,'name':'fixture-space','owner':{'login':'fixture-owner','id':23},
                    'repository':{'full_name':'sample/broker','id':34}}
        self.user={'login':'fixture-owner','id':23}

    def validate(self,value):
        return validate_recipient(value,self.user,selection='fixture-space',repository='sample/broker',repository_id='34')

    def test_invalid_api_identity_is_rejected(self):
        for field in ['missing','id','owner','repository','name','bool-id','shell']:
            with self.subTest(field=field):
                value=copy.deepcopy(self.value)
                if field=='missing':value={}
                elif field=='id':value['id']=0
                elif field=='owner':value['owner']['login']='other'
                elif field=='repository':value['repository']['id']=35
                elif field=='name':value['name']='other-space'
                elif field=='bool-id':value['id']=True
                else:value['name']='fixture-space; touch /tmp/forbidden'
                with self.assertRaises(ValueError):self.validate(value)

    def test_ambiguous_api_json_is_rejected(self):
        for raw in ['[]','null','{"id":1,"id":2}']:
            with self.assertRaises(ValueError):parse_api(raw)

    def test_context_is_safely_quoted_and_does_not_set_native_flag(self):
        identity=self.validate(self.value)
        command=['python3','-P','-m','review_broker.cli','internal-invoke','--packet-dir',"a;$(touch forbidden)'"]
        tokens=shlex.split(context_command(identity,command))
        self.assertEqual(tokens,['env','-u','PYTHONPATH','CODESPACE_NAME=fixture-space',*command])
        self.assertFalse(any(s.startswith('CODESPACES=')for s in tokens))

    def test_child_environment_drops_context_and_credentials_only(self):
        source={'CODESPACE_NAME':'fixture-space','CODESPACES':'true','GH_TOKEN':'control',
                'GITHUB_TOKEN':'publication','ACTIONS_ID_TOKEN_REQUEST_TOKEN':'oidc','PATH':'/bin'}
        result,_=sanitized_environment(source)
        self.assertEqual(result,{'CODESPACES':'true','PATH':'/bin','CODEX_MANAGED_BY_NPM':'1'})
        self.assertEqual(source['CODESPACE_NAME'],'fixture-space')
