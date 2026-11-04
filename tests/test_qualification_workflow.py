"""Parse the actual workflow; independently evaluate its small condition subset as a test oracle."""
import ast
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT/'.github/workflows/review-request.yml'
BASELINE_COMMIT = 'f3f24d942ad13d368975843f4796b1943dc7cdcb'
BASELINE_TREE = 'acc12a1ee8ef01166ac44fe184d575585d6a0956'
BASELINE_BLOB = '806f543b04aa53c0aaa1f69d216f36dbe9460150'
BASELINE_ENV = 'REVIEW_BROKER_ISSUE83_BASELINE_WORKFLOW_CHECKOUT'
BASELINE_PATH = '.github/workflows/review-request.yml'


def historical_workflow():
    """Read only the exact historical object or an independently verified pinned checkout."""
    configured = os.environ.get(BASELINE_ENV)
    directory = ROOT
    if configured is not None:
        directory = Path(configured)
        if not directory.is_absolute() or not directory.is_dir():
            raise AssertionError('ISSUE83_BASELINE_FIXTURE_REQUIRED')
    def git(*args, **kwargs):
        return subprocess.check_output(['git', *args], cwd=directory, **kwargs)
    if configured is not None:
        if (git('rev-parse', 'HEAD').strip().decode() != BASELINE_COMMIT
            or git('rev-parse', '--abbrev-ref', 'HEAD').strip() != b'HEAD'):
            raise AssertionError('ISSUE83_BASELINE_HEAD_MISMATCH')
    if git('rev-parse', BASELINE_COMMIT + '^{tree}').strip().decode() != BASELINE_TREE:
        raise AssertionError('ISSUE83_BASELINE_TREE_MISMATCH')
    if git('rev-parse', BASELINE_COMMIT + ':' + BASELINE_PATH).strip().decode() != BASELINE_BLOB:
        raise AssertionError('ISSUE83_BASELINE_BLOB_MISMATCH')
    if configured is None:
        raw = git('show', BASELINE_COMMIT + ':' + BASELINE_PATH)
    else:
        path = directory / BASELINE_PATH
        if path.is_symlink() or not path.is_file():
            raise AssertionError('ISSUE83_BASELINE_FILE_REQUIRED')
        raw = path.read_bytes()
    if git('hash-object', '--no-filters', '--stdin', input=raw).strip().decode() != BASELINE_BLOB:
        raise AssertionError('ISSUE83_BASELINE_BLOB_MISMATCH')
    return yaml.load(raw, Loader=yaml.BaseLoader)


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
        baseline=historical_workflow()
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


class HistoricalWorkflowFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name) / 'baseline'
        source = Path(os.environ.get(BASELINE_ENV, str(ROOT)))
        common = Path(subprocess.check_output(['git', 'rev-parse', '--git-common-dir'],
            cwd=source, text=True).strip())
        if not common.is_absolute():
            common = source / common
        for args in [ ['init', str(self.fixture)],
            ['-C', str(self.fixture), 'fetch', '--no-tags', '--depth', '1',
             common.resolve().as_uri(), BASELINE_COMMIT],
            ['-C', str(self.fixture), 'checkout', '--detach', 'FETCH_HEAD'] ]:
            subprocess.run(['git', *args], check=True, capture_output=True)

    def test_verified_fixture_and_exact_local_object_produce_same_historical_oracle(self):
        with patch.dict(os.environ, {BASELINE_ENV: str(self.fixture)}):
            verified = historical_workflow()
        with patch.dict(os.environ), patch(__name__ + '.ROOT', self.fixture):
            os.environ.pop(BASELINE_ENV, None)
            local = historical_workflow()
        self.assertEqual(verified, local)
        self.assertEqual(verified['jobs']['review']['steps'][0]['uses'],
            'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683')
        self.assertNotIn('qualification', verified['jobs'])

    def test_tampered_fixture_is_rejected_without_using_available_local_history(self):
        path = self.fixture / BASELINE_PATH
        path.write_bytes(path.read_bytes() + b'\n# altered fixture\n')
        with patch.dict(os.environ, {BASELINE_ENV: str(self.fixture)}):
            with self.assertRaisesRegex(AssertionError, 'ISSUE83_BASELINE_BLOB_MISMATCH'):
                historical_workflow()

    def test_empty_absent_symlinked_and_attached_fixtures_are_not_fallback_authority(self):
        for value in ['', str(self.fixture / 'absent')]:
            with self.subTest(value=value), patch.dict(os.environ, {BASELINE_ENV: value}):
                with self.assertRaisesRegex(AssertionError, 'ISSUE83_BASELINE_FIXTURE_REQUIRED'):
                    historical_workflow()
        path = self.fixture / BASELINE_PATH
        preserved = self.fixture / 'preserved.yml'
        path.rename(preserved)
        path.symlink_to(preserved)
        with patch.dict(os.environ, {BASELINE_ENV: str(self.fixture)}):
            with self.assertRaisesRegex(AssertionError, 'ISSUE83_BASELINE_FILE_REQUIRED'):
                historical_workflow()
        path.unlink()
        preserved.rename(path)
        subprocess.run(['git', '-C', str(self.fixture), 'checkout', '-b', 'attached'],
            check=True, capture_output=True)
        with patch.dict(os.environ, {BASELINE_ENV: str(self.fixture)}):
            with self.assertRaisesRegex(AssertionError, 'ISSUE83_BASELINE_HEAD_MISMATCH'):
                historical_workflow()

    def test_ci_pins_and_checks_history_without_changing_pr72_fixture(self):
        ci = yaml.load((ROOT/'.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
        steps = ci['jobs']['test']['steps']
        fixture = next(s for s in steps if s.get('with', {}).get('path') ==
                       'artifacts/issue83-baseline-workflow')
        self.assertEqual(fixture, {'uses': 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
            'with': {'ref': BASELINE_COMMIT, 'path': 'artifacts/issue83-baseline-workflow',
                     'persist-credentials': 'false', 'fetch-depth': '1'}})
        verify = next(s for s in steps if s.get('name') ==
                      'Verify exact Issue83 historical workflow fixture')
        for value in [BASELINE_COMMIT, BASELINE_TREE, BASELINE_BLOB,
                      'rev-parse HEAD', 'HEAD^{tree}', 'HEAD:$WORKFLOW',
                      'hash-object --no-filters', 'test -f', 'test ! -L']:
            self.assertIn(value, verify['run'])
        tests = next(s for s in steps if s.get('name') == 'Unit and adversarial tests')
        self.assertEqual(tests['env'][BASELINE_ENV],
            '${{ github.workspace }}/artifacts/issue83-baseline-workflow')
        self.assertLess(steps.index(fixture), steps.index(verify))
        self.assertLess(steps.index(verify), steps.index(tests))
        self.assertEqual(sum(BASELINE_ENV in s.get('env', {}) for s in steps), 1)
        pr72 = next(s for s in steps if s.get('with', {}).get('path') == 'artifacts/pr72-test-checkout')
        self.assertEqual(pr72['with'], {'ref': 'e65e4db932cb59d7a0fcfbd442ba19e548fc141d',
            'path': 'artifacts/pr72-test-checkout', 'persist-credentials': 'false', 'fetch-depth': '1'})
        pr72_verify = next(s for s in steps if s.get('name') == 'Verify exact PR72 test fixture')
        self.assertIn('420a18d006e421e197d23b8e93681376fbabc2db', pr72_verify['run'])
        self.assertEqual(tests['env']['REVIEW_BROKER_PR72_TEST_CHECKOUT'],
            '${{ github.workspace }}/artifacts/pr72-test-checkout')
