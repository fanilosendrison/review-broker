"""Probe scope and one-call provider qualification; all external APIs are in-memory."""
import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import yaml

from review_broker.github_live_runtime_v3 import REPOSITORY, REPOSITORY_ID, OWNER_ID, WORKER_PATH, CONTROLLER_PATH
from review_broker.github_http_live_v3 import HttpResponseV3

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/dispatch-provider'
SHA = 'a' * 40
DEV = 'b' * 40
REF = 'refs/heads/qualification/issue70-dispatch-provider-fixture'


def probe_module():
    spec = importlib.util.spec_from_file_location('probe', ROOT/'scripts/qualify-dispatch-provider.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def environment():
    return dict(GITHUB_REPOSITORY=REPOSITORY, GITHUB_REPOSITORY_ID=str(REPOSITORY_ID),
        GITHUB_SHA=SHA, GITHUB_WORKFLOW_SHA=SHA, GITHUB_REF=REF,
        GITHUB_WORKFLOW_REF=f'{REPOSITORY}/{CONTROLLER_PATH}@{REF}',
        GITHUB_JOB='dispatch-provider-probe', GITHUB_EVENT_NAME='workflow_dispatch',
        GITHUB_RUN_ATTEMPT='1', GITHUB_ACTOR_ID=str(OWNER_ID), GITHUB_RUN_ID='77')


class Api:
    def __init__(self):
        self.calls = []; self.metadata = self; self.guard = lambda: None
        self.run = dict(id=77, workflow_id=410394070, path=CONTROLLER_PATH, event='workflow_dispatch',
            run_attempt=1, head_sha=SHA, head_branch=REF.removeprefix('refs/heads/'),
            actor={'id': OWNER_ID}, triggering_actor={'id': OWNER_ID}, status='in_progress')
        self.jobs = [dict(id=88, run_id=77, run_attempt=1, head_sha=SHA,
                          name='dispatch-provider-probe', status='in_progress')]
        self.stub = (FIXTURES/'inert-worker-stub.yml').read_bytes()
        self.ref = DEV; self.status = 200; self.error = None; self.before_post = None

    def get(self, suffix):
        self.calls.append(('GET', suffix))
        if suffix == '':return dict(id=REPOSITORY_ID, full_name=REPOSITORY, default_branch='dev')
        if suffix == '/actions/runs/77':return deepcopy(self.run)
        if suffix == '/actions/workflows/410394071':return dict(id=410394071, path=WORKER_PATH, state='active')
        if suffix == '/git/ref/heads/dev':return dict(ref='refs/heads/dev', object={'sha': self.ref})
        if suffix == '/contents/'+WORKER_PATH+'?ref='+DEV:
            return dict(type='file', encoding='base64', content=base64.b64encode(self.stub).decode())
        raise AssertionError(suffix)

    def listing(self, path, query, field, guard):
        assert path == '/actions/runs/77/attempts/1/jobs' and field == 'jobs'
        self.calls.append(('GET', path)); return deepcopy(self.jobs)

    def post_dispatch(self, payload):
        self.calls.append(('POST', payload))
        if self.before_post:self.before_post()
        if self.error:raise self.error
        body=json.dumps(dict(workflow_run_id=99,
            run_url=f'https://api.github.com/repos/{REPOSITORY}/actions/runs/99',
            html_url=f'https://github.com/{REPOSITORY}/actions/runs/99')).encode()
        return HttpResponseV3(self.status, body, {})


class InertProviderProbeTests(unittest.TestCase):
    def test_one_post_only_string_inputs_invalid_broker_identities_no_runtime_effect(self):
        probe=probe_module(); api=Api()
        result=probe.run_probe(api, environment(), caller_sha=SHA, caller_ref=REF, dev_sha=DEV)
        posts=[v for method,v in api.calls if method=='POST']; self.assertEqual(len(posts),1)
        self.assertEqual(posts[0], {'ref':'dev','inputs':{
            'request_id':probe.PROBE_REQUEST,'reservation_id':probe.PROBE_RESERVATION,
            'generation':'1'},'return_run_details':True})
        self.assertFalse(probe.PROBE_REQUEST.startswith('request:sha256:'))
        self.assertFalse(probe.PROBE_RESERVATION.startswith('preparation-dispatch:sha256:'))
        self.assertTrue(result['dispatch_observed'])
        self.assertEqual(result['provider_observation']['http_status'],200)
        self.assertEqual(result['provider_observation']['recognized_run_id'],99)
        self.assertEqual(result['target']['head_sha'],DEV)
        self.assertEqual(result['verified_run_url'],f'https://api.github.com/repos/{REPOSITORY}/actions/runs/99')
        self.assertEqual(result['verified_html_url'],f'https://github.com/{REPOSITORY}/actions/runs/99')
        self.assertFalse(any('/review-claims' in str(v) or '/issues/' in str(v) for _,v in api.calls))

    def test_any_stub_semantic_or_byte_change_refuses_before_dispatch(self):
        probe=probe_module()
        for raw in (b'permissions: write-all\n', b'if: true\n', (FIXTURES/'inert-worker-stub.yml').read_bytes()+b'\n'):
            api=Api();api.stub=raw
            with self.assertRaisesRegex(ValueError,'INERT_PROBE_STUB_CHANGED'):
                probe.run_probe(api,environment(),caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
            self.assertFalse(any(method=='POST' for method,_ in api.calls))

    def test_wrong_context_rerun_or_caller_job_refuses_before_dispatch(self):
        probe=probe_module()
        for field,value in (('GITHUB_RUN_ATTEMPT','2'),('GITHUB_JOB','controller'),
                            ('GITHUB_SHA','c'*40),('GITHUB_ACTOR_ID','1')):
            api=Api();env=environment();env[field]=value
            with self.assertRaises(ValueError):probe.run_probe(api,env,caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
            self.assertFalse(any(method=='POST' for method,_ in api.calls))
        for change in ({'run_attempt':True},{'head_sha':'c'*40},{'status':'completed'}):
            api=Api();api.run.update(change)
            with self.assertRaises(ValueError):probe.run_probe(api,environment(),caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
            self.assertFalse(any(method=='POST' for method,_ in api.calls))
        api=Api();api.jobs[0]['name']='controller'
        with self.assertRaises(ValueError):probe.run_probe(api,environment(),caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
        self.assertFalse(any(method=='POST' for method,_ in api.calls))

    def test_dev_move_and_provider_failure_never_cause_retry(self):
        probe=probe_module();api=Api();api.ref='c'*40
        with self.assertRaises(ValueError):probe.run_probe(api,environment(),caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
        self.assertFalse(any(method=='POST' for method,_ in api.calls))
        for status,error in ((422,None),(500,None),(200,TimeoutError('inert fixture'))):
            api=Api();api.status=status;api.error=error
            result=probe.run_probe(api,environment(),caller_sha=SHA,caller_ref=REF,dev_sha=DEV)
            self.assertFalse(result['dispatch_observed'])
            self.assertEqual(len([1 for method,_ in api.calls if method=='POST']),1)
            self.assertEqual(result['provider_observation']['http_status'],None if error else status)

    def test_active_template_reuses_inert_registration_without_broker_execution(self):
        doc=yaml.safe_load((FIXTURES/'probe-controller-active.yml').read_text())
        self.assertEqual(doc['name'],'v3 pre-model Controller')
        self.assertEqual(doc['run-name'],'v3 dispatch provider-only qualification')
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['permissions'],{})
        self.assertEqual(set(doc['jobs']),{'dispatch-provider-probe'})
        job=doc['jobs']['dispatch-provider-probe']
        self.assertEqual(job['permissions'],{'actions':'write','contents':'read'})
        self.assertIn('github.run_attempt == 1',job['if'])
        self.assertIn('inputs.request_issue_number == 0',job['if'])
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['request_id']['type'],'string')
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['request_issue_number']['type'],'number')
        serialized=(FIXTURES/'probe-controller-active.yml').read_text()
        self.assertNotIn('secrets.',serialized)
        self.assertNotIn('internal-v3-',serialized)
        self.assertNotIn('upload-artifact',serialized)
        self.assertNotIn('SOURCE_APP',serialized)
        worker=yaml.safe_load((FIXTURES/'inert-worker-stub.yml').read_text())
        self.assertEqual(worker['permissions'],{})
        self.assertEqual(worker['jobs']['worker']['if'],'${{ false }}')
        self.assertEqual(hashlib.sha256((FIXTURES/'inert-worker-stub.yml').read_bytes()).hexdigest(),probe_module().STUB_SHA256)
