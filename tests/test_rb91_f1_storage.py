"""F1 positive/negative admission through real JWT, ZIP and evidence validators."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError
from review_broker.github_oidc import GitHubOIDCError, verify_github_identity
from rb91_full_abi_model import validate, validate_transition, validate_result_bytes
from rb91_result_reference_model import REFERENCE_SCHEMA
from rb91_storage_fixtures import StorageCase
from rb91_storage_provenance_model import verify_storage, authorization_receipt
from rb91_jch_contract_model import artifact, fixture_armed


class F1StorageTests(unittest.TestCase):
    def case(self, **options):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return StorageCase(Path(directory.name),**options)

    def verify(self, case, *, token=None, suffix='verified'):
        return verify_storage(case.record,case.policy,token=case.token() if token is None else token,
            issuer_reader=case.issuer,runner=case.runner,destination=case.root/suffix)

    def refused(self, case, **options):
        with self.assertRaisesRegex(ValueError,'RESULT_STORAGE_UNVERIFIED'):
            self.verify(case,**options)

    def test_original_storage_is_accepted_without_state_changes(self):
        c=self.case(recovery=False);before=deepcopy(c.record)
        self.assertEqual(self.verify(c),authorization_receipt(c.record['publication_intent']['result_artifact'],c.policy))
        self.assertEqual(c.record,before)
        self.assertTrue(all(cmd[:2]==['gh','api'] and len(cmd)==3 for cmd in c.calls))

    def test_authorized_recovery_keeps_original_execution_and_content(self):
        c=self.case();original=deepcopy(c.record['publication_intent']['result_artifact']['execution'])
        result_id=c.record['publication_intent']['result_id'];raw=c.raw
        self.verify(c)
        self.assertEqual(c.record['publication_intent']['result_artifact']['execution'],original)
        self.assertEqual(c.raw,raw);self.assertEqual(c.record['publication_intent']['result_id'],result_id)
        self.assertEqual(c.record['invocation_count'],1)
        self.assertEqual(sum(e.get('event')=='ATOMIC_ARM_CONSUMED' for e in c.record['history']),1)

    def test_later_attempt_is_storage_only_not_original_run_impersonation(self):
        c=self.case(attempt='2',same_run=True)
        self.verify(c)
        self.assertEqual(c.record['publication_intent']['result_artifact']['storage']['run_id'],
                         c.record['arm_binding']['controller_run_id'])
        self.assertEqual(c.record['arm_binding']['controller_run_attempt'],'1')
        self.assertEqual(c.record['publication_intent']['result_artifact']['storage']['run_attempt'],'2')

    def test_recovery_cannot_claim_original_run_even_with_signed_new_statement(self):
        c=self.case();token=c.token()
        pointer=c.record['publication_intent']['result_artifact'];e=pointer['execution'];s=pointer['storage']
        s.update(mode='original',run_id=e['controller_run_id'],run_attempt=e['controller_run_attempt'],
                 workflow_ref=e['controller_workflow_ref'],workflow_sha=e['controller_workflow_sha'])
        pointer['location'].update(workflow_run_id=s['run_id'],workflow_run_attempt=s['run_attempt'])
        c.resign_reference();self.refused(c,token=token)
        self.refused(c,suffix='signed-false-original')

    def test_unapproved_workflow_actor_trigger_or_event_refuses(self):
        for changed in ('workflow','actor','trigger','event'):
            c=self.case();s=c.record['publication_intent']['result_artifact']['storage']
            if changed=='workflow':s['workflow_sha']='0'*40
            if changed=='actor':s['actor']=dict(login='other',id=99)
            if changed=='trigger':s['triggering_actor']=dict(login='other',id=99)
            if changed=='event':
                endpoint=next(k for k in c.responses if '/attempts/' in k and '/jobs?' not in k)
                c.responses[endpoint]['event']='pull_request'
            c.resign_reference()
            with self.subTest(changed=changed):self.refused(c)

    def test_signed_wrong_workload_claims_and_wrong_audience_refuse(self):
        for claims in (dict(run_id='999'),dict(run_attempt='8'),dict(actor_id='999'),
                       dict(repository_id='999'),dict(workflow_sha='0'*40),
                       dict(aud='urn:review-broker:arm-authority:v1:sha256:'+'1'*64),dict(exp=1)):
            c=self.case()
            with self.subTest(claims=claims):self.refused(c,token=c.token(**claims))

    def test_storage_token_is_not_an_arm_token(self):
        c=self.case();token=c.token();self.verify(c,token=token)
        with self.assertRaises(GitHubOIDCError):
            verify_github_identity(token,audience='urn:review-broker:arm-authority:v1:sha256:'+'1'*64,
                expected_claims={},issuer_reader=c.issuer,allow_thumbprints=True)

    def test_issuer_signature_is_not_a_declarative_authenticated_flag(self):
        c=self.case();token=c.token()
        c.jwks['keys'][0]['n']='AQAB'
        self.refused(c,token=token)
        c=self.case();self.refused(c,token='not-a-jwt')

    def test_wrong_request_attempt_subject_policy_packet_and_arm_are_refused(self):
        for key in ('request_id','attempt_id','subject_id','policy_id','packet_id','arm_commit_sha'):
            c=self.case();execution=c.record['publication_intent']['result_artifact']['execution']
            execution[key]='0'*40 if key=='arm_commit_sha' else execution[key].split(':')[0]+':sha256:'+'0'*64
            c.resign_reference()
            with self.subTest(key=key):self.refused(c)

    def test_validation_and_terminal_reference_cannot_be_substituted(self):
        for key in ('validation_id','terminal_capture_id','terminal_locator_id','arm_binding_sha256'):
            c=self.case();execution=c.record['publication_intent']['result_artifact']['execution']
            execution[key]='0'*64 if key.endswith('sha256') else 'artifact:sha256:'+'0'*64
            c.resign_reference()
            with self.subTest(key=key):self.refused(c)

    def test_missing_or_changed_terminal_archive_refuses(self):
        for mode in ('absent','changed','missing-capture'):
            c=self.case();base='repos/'+c.repository+'/actions/artifacts/11'
            if mode=='absent':c.responses.pop(base+'/zip')
            elif mode=='changed':c.responses[base+'/zip']=b'not retained terminal evidence'
            else:
                # Removing the bound terminal member cannot satisfy retained inventory.
                import io,zipfile
                data=io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(c.responses[base+'/zip'])) as source,zipfile.ZipFile(data,'w') as dest:
                    for name in source.namelist():
                        if name!='terminal-capture.json':dest.writestr(name,source.read(name))
                c.responses[base+'/zip']=data.getvalue()
            with self.subTest(mode=mode):self.refused(c)

    def test_missing_expired_or_contradictory_result_artifact_refuses(self):
        for mode in ('missing','expired','name','run','sha','job','upload','incomplete','duplicate-job','cancelled','window','actor'):
            c=self.case();key='repos/'+c.repository+'/actions/artifacts/12'
            if mode=='missing':c.responses.pop(key)
            elif mode=='expired':c.responses[key]['expired']=True
            elif mode=='name':c.responses[key]['name']='different'
            elif mode=='run':c.responses[key]['workflow_run']['id']=99
            elif mode=='sha':c.responses[key]['workflow_run']['head_sha']='0'*40
            elif mode=='actor':
                endpoint=next(k for k in c.responses if '/attempts/' in k and '/jobs?' not in k)
                c.responses[endpoint]['actor']=dict(login='other',id=99)
            else:
                jobs=c.responses[next(k for k in c.responses if '/jobs?' in k)]
                if mode=='job':jobs['jobs'][0]['id']=99
                if mode=='upload':jobs['jobs'][0]['steps'][0]['conclusion']='failure'
                if mode=='incomplete':jobs['total_count']=101
                if mode=='cancelled':jobs['jobs'][0].update(status='completed',conclusion='cancelled')
                if mode=='window':c.responses[key]['created_at']='2001-01-01T00:00:00Z'
                if mode=='duplicate-job':jobs['jobs'].append(deepcopy(jobs['jobs'][0]));jobs['total_count']=2
            with self.subTest(mode=mode):self.refused(c)

    def test_changed_result_bytes_and_wrong_receipt_refuse(self):
        c=self.case();c.responses['repos/'+c.repository+'/actions/artifacts/12/zip']=b'changed result'
        self.refused(c)
        c=self.case();c.record['publication_intent']['result_artifact']['storage']['authorization_receipt_id']='artifact:sha256:'+'0'*64
        c.reseal();self.refused(c)

    def test_recovery_cannot_create_another_atomic_arm(self):
        c=self.case();before=deepcopy(c.policy.execution_snapshot)
        self.verify(c)
        proposed=fixture_armed(before)
        with self.assertRaises(ValueError):validate_transition(before,proposed,parent_sha='1'*40,operation='atomic_arm')
        self.assertEqual(c.policy.execution_snapshot,before)

    def test_valid_hashes_and_signature_do_not_bless_invalid_terminal_citations(self):
        c=self.case();c.corrupt_terminal_quote_with_consistent_hashes()
        self.refused(c)
        self.assertEqual(len(c.calls),6,'must reach actual evidence validation, before result retrieval')

    def test_result_identifiers_are_checked_after_authenticated_exact_byte_retrieval(self):
        for field in ('request_id','attempt_id','packet_id','subject_id','policy_id'):
            c=self.case();result=json.loads(c.raw)
            result[field]=field.removesuffix('_id')+':sha256:'+'0'*64
            c.rebind_result(result)
            with self.subTest(field=field):
                self.refused(c)
                self.assertEqual(len(c.calls),8,'must reach result validator after both verified archives')
        c=self.case();result=json.loads(c.raw);result['validation']['semantic_correctness_validated']=True
        c.rebind_result(result);self.refused(c);self.assertEqual(len(c.calls),8)

    def test_canonical_admission_identity_rejects_bool_integer_aliases(self):
        for field in ('schema_version','policy_version'):
            c=self.case();result=json.loads(c.raw)
            if field=='schema_version':result['resolved_request']['schema_version']=True
            else:result['resolved_request']['request']['policy']['version']=True
            c.rebind_result(result)
            with self.subTest(field=field):
                self.refused(c)
                self.assertEqual(len(c.calls),8,'must reach the exact resolved-admission comparison')

    def test_observed_actor_identity_does_not_coerce_boolean_to_integer(self):
        c=self.case();s=c.record['publication_intent']['result_artifact']['storage']
        s['actor']=dict(login='operator',id=1);s['triggering_actor']=dict(login='operator',id=1)
        c.policy=replace(c.policy,actors=frozenset({1}));c.resign_reference()
        key=next(k for k in c.responses if '/attempts/' in k and '/jobs?' not in k)
        c.responses[key]['actor']=dict(login='operator',id=True)
        c.responses[key]['triggering_actor']=dict(login='operator',id=True)
        self.refused(c);self.assertEqual(len(c.calls),2)
        c.responses[key]['actor']=dict(login='operator',id=1)
        c.responses[key]['triggering_actor']=dict(login='operator',id=1)
        self.verify(c,suffix='typed-actor-valid')
        self.assertEqual(len(c.calls),10)

    def test_faithful_result_projection_cannot_turn_no_go_into_go(self):
        c=self.case(verdict='NO_GO');honest=json.loads(c.raw)
        self.assertEqual(honest['validation']['review_verdict'],'NO_GO')
        self.verify(c,suffix='honest');c.calls.clear()
        forged=deepcopy(honest);forged['review_verdict']='GO';c.rebind_result(forged)
        self.refused(c,suffix='forged');self.assertEqual(len(c.calls),8)

    def test_coherent_signed_result_cannot_erase_or_fabricate_original_review(self):
        for field, value in [('findings',[]),('sources_examined',[]),('remaining_uncertainties',[]),
                             ('execution_status','FAILED'),('evidence_status','INVALID')]:
            c=self.case();result=json.loads(c.raw)
            self.assertNotEqual(result[field],value,'negative must actually change an evidence-derived field')
            result[field]=value;c.rebind_result(result)
            with self.subTest(field=field):self.refused(c);self.assertEqual(len(c.calls),8)
        for key, value in [('effective_model_identity_verified',True),('effective_reasoning_effort_verified',True),
                           ('model_requested','fabricated-model'),('reasoning_effort_requested','fabricated-effort')]:
            c=self.case();result=json.loads(c.raw);result['reviewer'][key]=value;c.rebind_result(result)
            with self.subTest(key=key):self.refused(c);self.assertEqual(len(c.calls),8)

    def test_public_v1_reviewer_extensions_are_preserved_without_changing_core_fields(self):
        c=self.case();result=json.loads(c.raw)
        result['reviewer']['extension_note']='Synthetic non-authoritative runtime note'
        c.rebind_result(result);self.verify(c)
        self.assertEqual(json.loads(c.raw)['reviewer']['extension_note'],result['reviewer']['extension_note'])

    def test_original_terminal_source_metadata_is_checked_before_zip_and_on_every_read(self):
        for field, value in [('head_sha','0'*40),('id',99),('repository_id',99)]:
            c=self.case();c.responses['repos/'+c.repository+'/actions/artifacts/11']['workflow_run'][field]=value
            with self.subTest(field=field):self.refused(c);self.assertEqual(len(c.calls),5)
        c=self.case();endpoint='repos/'+c.repository+'/actions/artifacts/12';reads=[]
        def changing(command,**kwargs):
            if command[2]==endpoint:
                reads.append(True)
                if len(reads)==2:c.responses[endpoint]['workflow_run']['head_sha']='0'*40
            return c.runner(command,**kwargs)
        with self.assertRaisesRegex(ValueError,'RESULT_STORAGE_UNVERIFIED'):
            verify_storage(c.record,c.policy,token=c.token(),issuer_reader=c.issuer,runner=changing,destination=c.root/'verified')
        self.assertEqual(len(c.calls),7);self.assertEqual(len(reads),2)

    def test_malformed_policy_actor_cannot_authorize_integer_identity_through_bool_alias(self):
        c=self.case();s=c.record['publication_intent']['result_artifact']['storage']
        s['actor']=dict(login='operator',id=1);s['triggering_actor']=dict(login='operator',id=1)
        key=next(k for k in c.responses if '/attempts/' in k and '/jobs?' not in k)
        c.responses[key]['actor']=dict(login='operator',id=1);c.responses[key]['triggering_actor']=dict(login='operator',id=1)
        c.policy=replace(c.policy,actors=frozenset({True}));c.resign_reference()
        self.refused(c);self.assertEqual(c.calls,[])
        c.policy=replace(c.policy,actors=frozenset({1}));c.resign_reference()
        self.verify(c,suffix='valid-policy');self.assertEqual(len(c.calls),8)

    def test_provider_incidental_actor_fields_are_not_journal_fields(self):
        c=self.case();key=next(k for k in c.responses if '/attempts/' in k and '/jobs?' not in k)
        for field in ('actor','triggering_actor'):
            c.responses[key][field]=dict(c.responses[key][field],type='User',avatar_url='https://example.invalid/image')
        self.verify(c)

    def test_f1_nested_objects_are_closed_and_required(self):
        c=self.case();pointer=c.record['publication_intent']['result_artifact']
        for name in ('execution','storage','location','authorization'):
            path=['storage','authorization'] if name=='authorization' else [name]
            for field in [*REFERENCE_SCHEMA['$defs'][name]['required'],'__unknown__']:
                value=deepcopy(pointer);target=value
                for component in path:target=target[component]
                if field=='__unknown__':target['authenticated']=True
                else:target.pop(field)
                with self.subTest(name=name,field=field),self.assertRaises(ValidationError):
                    Draft202012Validator(REFERENCE_SCHEMA).validate(value)
        validate(c.record);validate_result_bytes(c.record,c.raw)
