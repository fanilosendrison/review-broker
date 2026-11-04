"""Parse the actual workflow; independently evaluate its small condition subset as a test oracle."""
import ast
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT/'.github/workflows/review-request.yml'


def selected(expression, context):
    # Test-only oracle for the actual trusted expression, not a production Actions interpreter.
    for name in sorted(context, key=len, reverse=True):
        expression = expression.replace(name, repr(context[name]))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'\btrue\b', 'True', expression)
    expression = re.sub(r'\bfalse\b', 'False', expression)
    return eval(expression, {'__builtins__': {}, 'contains': lambda x,y:y in x,
                             'format': lambda x,*a:x.format(*a)})


class QualificationWorkflowTests(unittest.TestCase):
    def setUp(self):
        # BaseLoader retains the YAML 1.2 Actions key "on" rather than YAML 1.1 boolean coercion.
        self.workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        self.jobs = self.workflow['jobs']
        self.context = {'github.event_name': 'workflow_dispatch', 'inputs.qualification_only': True,
            'github.repository': 'fanilosendrison/review-broker', 'github.ref': 'refs/heads/dev',
            'github.event.repository.default_branch': 'dev', 'github.sha': 'a'*40,
            'github.workflow_sha': 'a'*40, 'inputs.qualification_sha': 'a'*40,
            'github.event.issue.body': ''}

    def test_actual_job_selection_is_exclusive_for_all_admitted_event_paths(self):
        variants = [({},(True,False)), ({'inputs.qualification_only':False},(False,True)),
            ({'github.event_name':'issues','inputs.qualification_only':False,
              'github.event.issue.body':'<!-- review-broker-request:v1 -->'},(False,True)),
            ({'github.event_name':'issues','inputs.qualification_only':False,
              'github.event.issue.body':'<!-- review-broker-request:v2 -->'},(False,True)),
            ({'github.event_name':'issues','inputs.qualification_only':True},(False,False)),
            ({'github.ref':'refs/heads/feature'},(False,False)),
            ({'inputs.qualification_sha':'b'*40},(False,False)),
            ({'github.workflow_sha':'b'*40},(False,False)),
            ({'github.repository':'attacker/repo'},(False,False)),
            ({'github.event_name':'pull_request'},(False,False)),
            ({'github.event.repository.default_branch':'main'},(False,False))]
        for changes, expected in variants:
            with self.subTest(changes=changes):
                context=dict(self.context, **changes)
                actual=tuple(bool(selected(self.jobs[n]['if'],context)) for n in ['qualification','review'])
                self.assertEqual(actual,expected)
                self.assertFalse(all(actual))

    def test_boolean_default_and_minimal_explicit_job_permissions(self):
        dispatch=self.workflow['on']['workflow_dispatch']['inputs']
        self.assertEqual(dispatch['qualification_only']['type'],'boolean')
        self.assertEqual(dispatch['qualification_only']['default'],'false')
        self.assertEqual(dispatch['issue_number']['required'],'false')
        self.assertEqual(self.jobs['qualification']['permissions'],{'contents':'read','id-token':'write'})
        self.assertEqual(self.jobs['review']['permissions'],
            {'actions':'read','contents':'write','issues':'write','id-token':'write'})
        self.assertEqual(self.workflow['concurrency'],
            {'group':'review-broker-single-reviewer','cancel-in-progress':'false'})

    def test_actual_manual_selector_guard_runs_first_and_rejects_before_any_admission(self):
        steps=self.jobs['review']['steps'];guard=steps[0]
        self.assertEqual(guard['name'],'Validate manual ReviewRequest selector before admission')
        code=guard['run'].split("python - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        for value, success in [('',False),('0',False),('-1',False),('1.5',False),
                               ('$(command)',False),('83',True)]:
            with self.subTest(value=value):
                p=subprocess.run([sys.executable,'-c',code],text=True,capture_output=True,
                    env={'EVENT_NAME':'workflow_dispatch','MANUAL_ISSUE_NUMBER':value})
                self.assertEqual(p.returncode==0,success)
        p=subprocess.run([sys.executable,'-c',code],env={'EVENT_NAME':'issues'},capture_output=True)
        self.assertEqual(p.returncode,0)
        self.assertLess(steps.index(guard),next(i for i,s in enumerate(steps)
            if s.get('id')=='prepare'))

    def test_qualification_source_and_only_capability_bearing_entry_are_exact(self):
        job=self.jobs['qualification'];raw=json.dumps(job)
        for forbidden in ['secrets.', 'github.token', 'GH_TOKEN', 'CODESPACE', 'SOURCE_TOKEN',
                          'internal-', 'reviewctl', 'review-claims', 'ReviewRequest', 'ReviewResult',
                          'CODEX', 'actions/github-script']:
            self.assertNotIn(forbidden,raw)
        steps=job['steps']
        self.assertEqual(steps[0]['with'],{'ref':'${{ github.sha }}','persist-credentials':'false'})
        check=steps[1]['run']
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',check)
        self.assertIn('test "$GITHUB_WORKFLOW_SHA" = "$GITHUB_SHA"',check)
        commands=[s['run'] for s in steps if 'run'in s]
        self.assertEqual(len(commands),3)
        self.assertEqual(commands[-1],'python -m review_broker.oidc_qualification')
        upload=steps[-1]
        self.assertEqual(upload['with']['path'],'oidc-qualification.json')
        self.assertNotIn('always()',upload.get('if',''))

    def test_entire_existing_review_job_other_than_guard_and_selector_is_unchanged(self):
        baseline=yaml.load(subprocess.check_output(['git','show',
            'f3f24d942ad13d368975843f4796b1943dc7cdcb:.github/workflows/review-request.yml'],
            cwd=ROOT,text=True),Loader=yaml.BaseLoader)
        current=copy.deepcopy(self.jobs['review']);previous=baseline['jobs']['review']
        current.pop('if');previous.pop('if');current['steps'].pop(0)
        self.assertEqual(current,previous)
        self.assertEqual(self.workflow['on']['issues'],baseline['on']['issues'])

    def test_isolated_qualification_import_graph_has_no_mutating_or_model_capable_modules(self):
        allowed={'oidc_qualification','github_oidc','identity'}
        for module in allowed:
            tree=ast.parse((ROOT/'src/review_broker'/f'{module}.py').read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom) and node.level:
                    self.assertIn(node.module,allowed)
        # The normal orchestrator and production arm schema are not even imported by qualification.
        self.assertNotIn('from .arm_authority', (ROOT/'src/review_broker/oidc_qualification.py').read_text())
