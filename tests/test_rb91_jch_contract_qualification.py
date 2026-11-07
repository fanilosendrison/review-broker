"""Non-inference J-CH journal core qualification. NOT a production schema or authority."""
import copy
import hashlib
import json
import os
import unittest
from pathlib import Path

from rb91_jch_contract_model import (
    ContractViolation, REAL_REPO_CONTRACT, SCHEMA, VALIDATOR, _canonical, _attempt,
    artifact, classify_get, fixture_armed, fixture_capacity, fixture_prepared,
    fixture_transition, parse_strict, post_arm_gate, validate, validate_transition,
)

PARENT='1'*40

class ContractQualificationTests(unittest.TestCase):
    def setUp(self):
        self.pre=fixture_prepared()
        self.ready=fixture_capacity(self.pre)
        self.arm=fixture_armed(self.ready, parent_sha=PARENT)
        validate(self.pre)
        validate(self.ready)
        validate(self.arm)

    def forbidden(self, x, *, parent=None, operation=None):
        with self.assertRaises((ContractViolation, ValueError)):
            if parent is None:validate(x)
            else:validate_transition(parent,x,parent_sha=PARENT,operation=operation)

    def test_ci_uses_real_project_implementation(self):
        if os.environ.get('GITHUB_ACTIONS')=='true':
            self.assertTrue(REAL_REPO_CONTRACT,'CI must import real pinned review_broker/rfc8785, never the local fallback')

    def test_schema_meta_and_fixture_valid(self):
        self.assertEqual(SCHEMA['$schema'], 'https://json-schema.org/draft/2020-12/schema')
        for x in [self.pre,self.ready,self.arm,fixture_transition(self.arm,'INDETERMINATE')]:
            with self.subTest(state=x['state']):self.assertEqual(list(VALIDATOR.iter_errors(x)),[])

    def test_prearm_or_postarm_indeterminate_distinct(self):
        for source in (self.pre,self.arm):
            x=fixture_transition(source,'INDETERMINATE');validate(x)
            self.assertEqual(x['invocation_count'],source['invocation_count'])
            self.assertEqual(x['arm_binding'],source['arm_binding'])
            validate(fixture_transition(x,'STOPPED'))

    def test_version_dispatch_and_unknown_fields(self):
        for field,value in [('schema_version',True),('schema_version',False),('schema_version',1),
                            ('schema_version',3),('schema_version',None),('protocol_id','j-ch-v2')]:
            x=copy.deepcopy(self.pre);x[field]=value
            with self.subTest(field=field,value=value):self.forbidden(x)
        x=copy.deepcopy(self.pre);x.pop('schema_version');self.forbidden(x)
        for scope in ('top','binding'):
            x=copy.deepcopy(self.arm)
            (x if scope=='top' else x['arm_binding'])['arbitrary']='unknown'
            with self.subTest(scope=scope):self.forbidden(x)

    def test_missing_binding_properties_and_wrong_types(self):
        keys=list(self.arm['arm_binding'])
        for key in keys:
            x=copy.deepcopy(self.arm);x['arm_binding'].pop(key)
            with self.subTest(key=key):self.forbidden(x)
        for key in ('challenge','packet_id','prepared_parent_sha','capacity_receipt_id','workflow_sha',
                    'reviewer_policy_sha256','recipient_preflight_sha256','codespace_id'):
            x=copy.deepcopy(self.arm);x['arm_binding'][key]=True
            with self.subTest(key=key):self.forbidden(x)

    def test_prearm_binding_and_count_invalid(self):
        for mode in ('pre_count1','pre_binding','arm_count0','arm_null_binding','arm_count_true'):
            x=copy.deepcopy(self.arm if mode.startswith('arm') else self.pre)
            if mode=='pre_count1':x['invocation_count']=1
            if mode=='pre_binding':x['arm_binding']=copy.deepcopy(self.arm['arm_binding'])
            if mode=='arm_count0':x['invocation_count']=0
            if mode=='arm_null_binding':x['arm_binding']=None
            if mode=='arm_count_true':x['invocation_count']=True
            with self.subTest(mode=mode):self.forbidden(x)

    def test_parent_identity_and_capacity_consistency(self):
        changes=[('request_id','request:sha256:'+'9'*64),('attempt_id','attempt:sha256:'+'9'*64)]
        for k,v in changes:
            x=copy.deepcopy(self.arm);x[k]=v
            with self.subTest(k=k):self.forbidden(x)
        for k,v in [('input_sha256','0'*64),('capacity_receipt_id','artifact:sha256:'+'0'*64),
                    ('packet_id','packet:sha256:'+'0'*64),('workflow_sha','0'*40)]:
            x=copy.deepcopy(self.arm);x['arm_binding'][k]=v
            with self.subTest(k=k):self.forbidden(x)
        x=copy.deepcopy(self.ready);x['input_capacity']['capacity_units']=4;self.forbidden(x)
        x=copy.deepcopy(self.ready);x['input_capacity']['status']='REJECTED';self.forbidden(x)
        x=copy.deepcopy(self.arm);x['input_capacity']['status']='REJECTED';self.forbidden(x)

    def test_atomic_arm_single_transition(self):
        self.assertTrue(validate_transition(self.ready,self.arm,parent_sha=PARENT,operation='atomic_arm'))
        x=copy.deepcopy(self.arm);x['arm_binding']['prepared_parent_sha']='0'*40
        self.forbidden(x,parent=self.ready,operation='atomic_arm')
        self.forbidden(self.arm,parent=self.ready,operation='transition')
        x=copy.deepcopy(self.arm);x['invocation_count']=0
        self.forbidden(x,parent=self.ready,operation='atomic_arm')

    def test_history_cannot_drop_arming_event_or_backwards_transition(self):
        x=copy.deepcopy(self.arm)
        x['history'].pop();self.forbidden(x)
        x=copy.deepcopy(self.arm)
        x['history'][-1]['event']='INPUT_CAPACITY_ASSESSED';self.forbidden(x)
        x=copy.deepcopy(self.arm)
        x['history'][-1]['binding_sha256']='0'*64;self.forbidden(x)
        x=copy.deepcopy(self.arm)
        x['history'].append(copy.deepcopy(x['history'][-1]));self.forbidden(x)
        x=copy.deepcopy(self.arm);x['state']='PREPARED';x['invocation_count']=0;x['arm_binding']=None
        self.forbidden(x)

    def test_evidence_history_append_exact(self):
        x=copy.deepcopy(self.arm);x['evidence_ids']=x['evidence_ids'][:-1];self.forbidden(x)
        x=copy.deepcopy(self.arm);x['history'][-1]['evidence_ids'].append('artifact:sha256:'+'8'*64);self.forbidden(x)
        x=copy.deepcopy(self.ready);x['history'][1]['evidence_ids']=[];self.forbidden(x)
        x=copy.deepcopy(self.ready);x['history'].reverse();self.forbidden(x)

    def test_mutation_no_op_and_binding_immutability(self):
        self.forbidden(self.ready,parent=self.ready,operation='capacity')
        self.forbidden(self.arm,parent=self.arm,operation='atomic_arm')
        x=fixture_transition(self.arm,'INDETERMINATE')
        self.assertTrue(validate_transition(self.arm,x,parent_sha=PARENT,operation='transition'))
        tampered=copy.deepcopy(x);tampered['arm_binding']['challenge']='0'*64
        self.forbidden(tampered,parent=self.arm,operation='transition')
        tampered=copy.deepcopy(x);tampered['input_capacity']['input_sha256']='0'*64
        self.forbidden(tampered,parent=self.arm,operation='transition')
        self.forbidden(x,parent=self.arm,operation='atomic_arm')

    def test_prearm_capacity_append(self):
        self.assertTrue(validate_transition(self.pre,self.ready,parent_sha=PARENT,operation='capacity'))
        x=copy.deepcopy(self.ready);x['input_capacity']['status']='REJECTED'
        self.forbidden(x,parent=self.pre,operation='capacity')
        self.forbidden(self.ready,parent=self.pre,operation='transition')

    def test_end_state_cannot_rearm(self):
        ind=fixture_transition(self.arm,'INDETERMINATE')
        stopped=fixture_transition(ind,'STOPPED')
        validate(stopped)
        self.forbidden(self.arm,parent=ind,operation='atomic_arm')
        self.forbidden(self.arm,parent=stopped,operation='atomic_arm')
        after=fixture_transition(self.pre,'INDETERMINATE')
        self.forbidden(self.arm,parent=after,operation='atomic_arm')

    def test_canonical_raw_and_duplicate_keys(self):
        raw=_canonical(self.arm)+b'\n'
        self.assertEqual(parse_strict(raw),self.arm)
        for bad in [raw[:-1],raw+b'\n',b'{"schema_version":2,"schema_version":2}\n',
                    b'{"bad":NaN}\n',b'\xff',b'x'*524289]:
            with self.subTest(length=len(bad)):
                with self.assertRaises(ContractViolation):parse_strict(bad)

        # Canonical JSON can still contain a schema-invalid boolean; decoding
        # and structural validation are intentionally separate gates.
        self.forbidden(parse_strict(b'{"schema_version":true}\n'))

    def test_read_classification(self):
        self.assertEqual(classify_get(return_code=0,http_status=200,body_valid=True,authenticated=True,repository_verified=True),'PRESENT_VERIFIED')
        self.assertEqual(classify_get(return_code=1,http_status=404,body_valid=False,authenticated=True,repository_verified=True),'ABSENT_AUTHENTICATED')
        for code in (0,401,403,408,409,422,429,500,503,None):
            for auth in (True,False):
                x=classify_get(return_code=1,http_status=code,body_valid=False,authenticated=auth,repository_verified=auth)
                with self.subTest(code=code,auth=auth):
                    self.assertEqual(x,'UNKNOWN')
        self.assertEqual(classify_get(return_code=1,http_status=404,body_valid=False,authenticated=True,repository_verified=False),'UNKNOWN')

    def test_mutation_ambiguity_and_owner(self):
        ok={'return_code':0,'data':{'updateRefs':{'clientMutationId':'synthetic'}}}
        self.assertEqual(post_arm_gate(mutation_result=ok,readback_ok=True,exact_head=True,original_live_controller=True),'ELIGIBLE_SINGLE_MINT')
        samples=[{'return_code':1,'data':{'updateRefs':{'clientMutationId':'synthetic'}}},
                 {'return_code':0,'errors':[{'message':'Something went wrong while executing your query'}]},
                 {'return_code':0,'data':{}},
                 {'return_code':0,'data':{'updateRefs':None}},
                 {'return_code':0,'data':{'updateRefs':{'unexpected':'yes'}}},
                 None]
        for x in samples:
            with self.subTest(result=x):
                self.assertEqual(post_arm_gate(mutation_result=x,readback_ok=True,exact_head=True,original_live_controller=True),'NO_MINT_NO_RETRY')
        for flags in [{'readback_ok':False},{'exact_head':False},{'original_live_controller':False}]:
            kw={'mutation_result':ok,'readback_ok':True,'exact_head':True,'original_live_controller':True};kw.update(flags)
            self.assertEqual(post_arm_gate(**kw),'NO_MINT_NO_RETRY')

    def test_core_scope_rejects_opaque_domain_objects(self):
        for field in ('admission','evidence_locator_plan','evidence_locator','publication_intent','publication_receipt'):
            x=copy.deepcopy(self.arm)
            x[field]={'source':'unqualified'}
            with self.subTest(field=field):self.forbidden(x)

    def test_concurrent_candidates_unchanged_parent(self):
        a=self.arm
        b=fixture_armed(self.ready,parent_sha=PARENT)
        b['arm_binding']['challenge']='9'*64
        b['history'][-1]['binding_sha256']=hashlib.sha256(_canonical(b['arm_binding'])).hexdigest()
        self.assertNotEqual(a['arm_binding'],b['arm_binding'])
        for v in (a,b):validate_transition(self.ready,v,parent_sha=PARENT,operation='atomic_arm')
        # The model checks child legality; GitHub's real compare-and-swap behavior
        # was separately qualified in Q3, and is not re-implemented here.

    @unittest.skipUnless(REAL_REPO_CONTRACT,'actual review_broker package available only in GitHub CI')
    def test_existing_real_capacity_and_identity_validators(self):
        from review_broker.identity import attempt_identity,canonical_bytes
        from review_broker.input_capacity import validate_capacity_receipt
        self.assertEqual(attempt_identity(self.pre['request_id'],1),self.pre['attempt_id'])
        self.assertEqual(canonical_bytes(self.arm)+b'\n',_canonical(self.arm)+b'\n')
        self.assertEqual(validate_capacity_receipt(self.ready['input_capacity']),artifact(self.ready['input_capacity']))

    @unittest.skipUnless(REAL_REPO_CONTRACT,'actual old writer available only in GitHub CI')
    def test_real_legacy_decoder_drops_v2_fields(self):
        from review_broker.queue import AttemptRecord
        old=AttemptRecord.from_dict(copy.deepcopy(self.arm))
        reencoded=old.as_dict()
        self.assertEqual(reencoded['schema_version'],1)
        self.assertNotIn('protocol_id',reencoded)
        self.assertNotIn('arm_binding',reencoded)
        self.assertNotEqual(reencoded,self.arm)

    @unittest.skipUnless(REAL_REPO_CONTRACT,'actual old writer available only in GitHub CI')
    @unittest.expectedFailure
    def test_expected_failure_old_decoder_should_reject_v2_before_cutover(self):
        from review_broker.queue import AttemptRecord
        with self.assertRaises(ValueError):
            AttemptRecord.from_dict(copy.deepcopy(self.arm))

if __name__=='__main__':unittest.main()