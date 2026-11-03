"""Workflow -> real preflight -> authorized fake invocation -> real assurance consumer."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import textwrap
import unittest
from unittest.mock import patch
from review_broker.assurance_validation import assurance_errors
from review_broker.bounded_preflight import build_bounded_preflight
from review_broker.codex import invoke_once
from review_broker.codex_runtime_identity import load_codex_release_trust
from review_broker.identity import canonical_bytes
from review_broker.reviewer_profile import install_reviewer_profile
from review_broker.validation import validate_evidence
from tests import arm_authority_fixture as auth
from tests import test_capacity_boundaries as fixture
from tests.test_input_capacity import ATTEMPT
from tests.test_prearm_workflow_cleanup import workflow_step

MISMATCH='BOUNDED_PREFLIGHT_ENVIRONMENT_EVIDENCE_MISMATCH'

class BoundedEnvironmentParityTests(unittest.TestCase):
    def exercise(self,mode,*,different_context=False,fabricated=False):
        factory=fixture.CapacityBoundaryTests();factory.setUp();self.addCleanup(factory.doCleanups)
        directory,manifest,_,schema,arguments=factory.invocation_fixture()
        root=directory.parent;destination=root/'evidence';directory.rename(destination);directory=destination
        install_reviewer_profile(root/'home',arguments['trusted_workspace'],directory)
        release=load_codex_release_trust();platform=release['platforms']['linux-x86_64']
        runtime=replace(arguments['runtime_verifier']({},root),
            launcher_sha256=release['distribution']['launcher_sha256'],native_sha256=platform['native_sha256'],
            root_dist_integrity=release['distribution']['dist_integrity'],platform_dist_integrity=platform['dist_integrity'])
        arguments['runtime_verifier']=lambda *_:runtime
        bundle,trust=auth.authorization(directory,manifest,ATTEMPT)
        if mode=='bounded-private-v1':
            metadata=json.loads((directory/'broker-metadata.json').read_text())
            metadata['admission_mode']=mode
            metadata['admission_checks']={'requester_authorized':True,'repository_authorized':True,
                'executing_sha_admitted':True,'bounded_private_request_admitted':True,
                'private_repository_verified':True,'private_source_credential_scope_verified':True,
                'public_repository_verified':False}
            raw=canonical_bytes(metadata)+b'\n';(directory/'broker-metadata.json').write_bytes(raw)
            bundle['envelope']['broker_metadata_sha256']=hashlib.sha256(raw).hexdigest()
            bundle['jwt']=auth.sign(bundle['envelope'])
        (directory/'resolved-request.json').write_bytes(canonical_bytes({'request_id':manifest['request_id'],
            'subject_id':manifest['subject_id']})+b'\n')
        identity={'name':'fixture-space','codespace_id':12,'owner_login':'trusted','owner_id':23,
                  'repository':'sample/broker','repository_id':34}
        (root/'review-broker-recipient.json').write_text(json.dumps(identity))
        (root/'review-broker-arm-authorization.json').write_bytes(canonical_bytes(bundle)+b'\n')
        native=dict(arguments['environment'],CODESPACES='true',GH_TOKEN='synthetic-control',
                    GITHUB_TOKEN='synthetic-publication',ACTIONS_ID_TOKEN_REQUEST_TOKEN='synthetic-oidc')
        controller=dict(RUNNER_TEMP=str(root),REMOTE_ROOT=str(root),CODESPACE_NAME='fixture-space',
            EXPECTED_CODESPACE_ID='12',GITHUB_REPOSITORY='sample/broker',GITHUB_REPOSITORY_ID='34',
            ATTEMPT_ID=ATTEMPT,PACKET_ID=manifest['packet_id'],BROKER_WHEEL_SHA256=arguments['broker_wheel_sha256'],
            CODEX_RUNTIME_ROOT=str(arguments['codex_runtime_root']),GITHUB_SHA='a'*40,
            CAPTURE=str(root/'captured-argv'))
        local=root/'controller';(local/'evidence').mkdir(parents=True)
        receipt_path=local/'evidence/bounded-v1-preflight.json'
        calls=[];receipts=[];original_run=subprocess.run
        def model(command,**kwargs):
            self.assertNotIn('CODESPACE_NAME',kwargs['env'])
            self.assertEqual(kwargs['env']['CODESPACES'],'true')
            for key in ['GH_TOKEN','GITHUB_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:
                self.assertNotIn(key,kwargs['env'])
            calls.append(command);(directory/'codex-final.json').write_bytes(b'{}')
            return subprocess.CompletedProcess(command,0)
        def remote(command,**kwargs):
            tokens=shlex.split(command[-1]) if len(command[command.index('--')+1:])==1 else command[command.index('--')+1:]
            self.assertEqual(tokens[:3],['env','-u','PYTHONPATH'])
            environment=dict(native);index=3
            while '=' in tokens[index]:
                key,value=tokens[index].split('=',1);self.assertEqual(key,'CODESPACE_NAME')
                environment[key]=value;index+=1
            operation=tokens[tokens.index('review_broker.cli')+1]
            for flag,expected in [('--packet-dir',str(directory)),('--schema',str(schema))]:
                if flag=='--schema':
                    # The fake remote layout maps the transferred schema to its real local fixture.
                    self.assertTrue(tokens[tokens.index(flag)+1].endswith('reviewer-findings-v1.codex-wire.schema.json'))
                else:self.assertEqual(tokens[tokens.index(flag)+1],expected)
            if operation=='internal-bounded-v1-preflight':
                receipt=build_bounded_preflight(directory,schema,attempt_id=ATTEMPT,
                    expected_packet_id=manifest['packet_id'],broker_wheel_sha256=arguments['broker_wheel_sha256'],
                    trusted_workspace=arguments['trusted_workspace'],codex_runtime_root=arguments['codex_runtime_root'],
                    executing_broker_sha='a'*40,environment=environment,runtime_verifier=arguments['runtime_verifier'])
                receipts.append(receipt)
                raw=canonical_bytes(receipt)+b'\n'
                if kwargs.get('stdout') is not None:kwargs['stdout'].write(raw)
                else:receipt_path.write_bytes(raw)
            else:
                self.assertEqual(operation,'internal-invoke')
                if different_context:environment['OPENAI_API_KEY']='additional-synthetic-context'
                with auth.trusted_fixture(trust),patch.dict(os.environ,environment,clear=True):
                    invoke_once(directory,schema,ATTEMPT,runner=model,
                        authorization_bundle=kwargs['stdin'].read(),**dict(arguments,environment=environment))
            return subprocess.CompletedProcess(command,0)
        def runner(command,**kwargs):
            if command[:2]==['gh','api']:
                value={'login':'trusted','id':23} if command[2]=='user' else {
                    'name':'fixture-space','id':12,'owner':{'login':'trusted','id':23},
                    'repository':{'full_name':'sample/broker','id':34}}
                return subprocess.CompletedProcess(command,0,stdout=json.dumps(value))
            return remote(command,**kwargs)
        def workflow(name):
            run=textwrap.dedent(workflow_step(name).split('        run: |\n',1)[1])
            with patch.dict(os.environ,controller),patch('subprocess.run',side_effect=runner):
                if "python - <<'PY'" in run:
                    code=run.split("python - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
                    previous=Path.cwd()
                    try:
                        os.chdir(local)
                        exec(compile(code,'actual-workflow','exec'),{})
                    finally:os.chdir(previous)
                else:
                    run=run.replace('${{ steps.prepare.outputs.attempt_id }}',ATTEMPT).replace('${{ steps.prepare.outputs.packet_id }}',manifest['packet_id'])
                    capture='gh() { printf "%s\\0" "$@" > "$CAPTURE"; };\n'
                    original_run(['bash','-c',capture+run],env=dict(os.environ),cwd=local,check=True)
                    args=(root/'captured-argv').read_bytes().decode().rstrip('\0').split('\0')
                    remote(['gh',*args])
        workflow('Verify bounded low-sensitivity pre-arm evidence')
        if fabricated:
            value=json.loads(receipt_path.read_text())
            value['broker_wheel_sha256']='f'*64
            receipt_path.write_bytes(canonical_bytes(value)+b'\n')
        workflow('Invoke Codex once')
        # Recovery reunites controller-side preflight stdout and remote runtime evidence.
        (directory/'bounded-v1-preflight.json').write_bytes(receipt_path.read_bytes())
        attempt=json.loads((directory/'attempt.json').read_text())
        errors=assurance_errors(directory,manifest,mode)
        self.assertEqual(len(calls),1)
        self.last_model_runner_calls=len(calls)
        self.last_validation=validate_evidence(directory,setup=manifest)
        return receipts[0],attempt,errors

    def test_public_and_private_real_producers_and_consumer_agree(self):
        for mode in ['low-sensitivity-v1','bounded-private-v1']:
            with self.subTest(mode=mode):
                preflight,attempt,errors=self.exercise(mode)
                self.assertEqual(errors,[],f'REAL_ASSURANCE_ERRORS={errors}; '
                    f'PREFLIGHT_REMOVED={preflight["environment_keys_removed"]}; '
                    f'INVOCATION_REMOVED={attempt["environment_keys_removed"]}; FAKE_MODEL_RUNNER_CALLS=1')
                self.assertEqual(preflight['environment_keys_removed'],attempt['environment_keys_removed'])
                self.assertIn('CODESPACE_NAME',preflight['environment_keys_removed'])

    def test_genuinely_different_context_is_still_rejected(self):
        for mode in ['low-sensitivity-v1','bounded-private-v1']:
            with self.subTest(mode=mode):
                _,_,errors=self.exercise(mode,different_context=True)
                self.assertIn(MISMATCH,errors)

    def test_fabricated_preflight_allows_authorized_transport_but_blocks_acceptance(self):
        for mode in ['low-sensitivity-v1','bounded-private-v1']:
            with self.subTest(mode=mode):
                _,_,errors=self.exercise(mode,fabricated=True)
                self.assertEqual(self.last_model_runner_calls,1)
                reason='BOUNDED_PREFLIGHT_FIELD_INVALID:broker_wheel_sha256'
                self.assertIn(reason,errors)
                self.assertIn(reason,self.last_validation['validation_reasons'])
                self.assertEqual(self.last_validation['evidence_status'],'INVALID')
                self.assertEqual(self.last_validation['review_verdict'],'UNDETERMINED')

    def test_fabricated_preflight_is_still_rejected(self):
        _,_,errors=self.exercise('low-sensitivity-v1',fabricated=True)
        self.assertIn('BOUNDED_PREFLIGHT_FIELD_INVALID:broker_wheel_sha256',errors)
