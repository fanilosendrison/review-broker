"""Independent conformance of proposed resource placement and workload boundaries."""
from copy import deepcopy
import hashlib
import json
import unittest

from jsonschema import ValidationError
from review_broker.arm_authority_contract import validate_envelope, ArmAuthorityError
from review_broker.identity import canonical_bytes
from rb91_full_abi_fixtures import publication_chain
from jch_normative_fixtures import workload, quiescence
from jch_normative_schemas import (
    ROOT, PREFIX, RESOURCES, check, validate_arm, arm_audience, frame_payload, proof_budget,
)

MAPPING={'urn:review-broker:rb91:candidate:journal-v2:0.2.0':PREFIX+'jch-journal-v2.schema.json',
         'urn:review-broker:rb91:candidate:result-reference-v2:0.1.0':PREFIX+'jch-result-reference-v2.schema.json'}


def relocate(value):
    if isinstance(value,dict):
        return {key:(MAPPING.get(item,item) if key in ('$id','$ref') and isinstance(item,str) else relocate(item)) for key,item in value.items()}
    if isinstance(value,list):return [relocate(item) for item in value]
    return value


class NormativeSchemaTests(unittest.TestCase):
    def test_promoted_journal_and_reference_have_exact_qualified_constraints(self):
        for old,new,title in [('rb91-journal-v2-candidate.schema.json','jch-journal-v2.schema.json','Proposed J-CH Journal v2'),
                              ('rb91-result-reference-v2.schema.json','jch-result-reference-v2.schema.json','Proposed J-CH Result Reference v2')]:
            value=relocate(json.loads((ROOT/'docs/architecture/qualification'/old).read_text()))
            value['title']=title
            if 'description' in value:value['description']='Proposed normative resource. Formal integration, implementation, J20 and operational admission remain separate.'
            self.assertEqual(RESOURCES[new],value)
        self.assertEqual(len(RESOURCES['jch-journal-v2.schema.json']['required']),15)

    def test_public_resources_execute_valid_and_invalid_qualified_vectors(self):
        records,_=publication_chain()
        for record in records:check('jch-journal-v2.schema.json',record)
        check('jch-result-reference-v2.schema.json',records[-1]['publication_intent']['result_artifact'])
        invalid=deepcopy(records[-1]);invalid['unknown_authority']=True
        with self.assertRaises(ValidationError):check('jch-journal-v2.schema.json',invalid)
        invalid=deepcopy(records[-1]);invalid['arm_binding']['challenge']=True
        with self.assertRaises(ValidationError):check('jch-journal-v2.schema.json',invalid)

    def test_closed_cross_bound_workload_example_and_disjoint_domain(self):
        envelope,hello,record,deployment,metadata=workload()
        validate_arm(envelope,hello=hello,record=record,deployment=deployment,
                     arm_commit_sha='b'*40,metadata_bytes=metadata)
        self.assertTrue(arm_audience(envelope).startswith('urn:review-broker:j-ch-v1:arm-authority:sha256:'))
        with self.assertRaises(ArmAuthorityError):validate_envelope(envelope)
        self.assertNotIn('result-retention',arm_audience(envelope))

    def test_unknown_versions_fields_and_legacy_shape_refuse(self):
        envelope,*_=workload()
        for field,value in [('schema_version',True),('schema_version',2),('protocol_id','legacy-v1')]:
            bad=deepcopy(envelope);bad[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValidationError):check('jch-arm-envelope-v1.schema.json',bad)
        bad=deepcopy(envelope);bad['binding']['unbound_permission']=True
        with self.assertRaises(ValidationError):check('jch-arm-envelope-v1.schema.json',bad)
        bad=deepcopy(envelope);bad.pop('protocol_id')
        with self.assertRaises(ValidationError):check('jch-arm-envelope-v1.schema.json',bad)

    def test_semantic_mismatch_cannot_be_hidden_by_valid_shape(self):
        envelope,hello,record,deployment,metadata=workload()
        for target,key,value in [('envelope','arm_commit_sha','c'*40),('hello','challenge','d'*64),
                                 ('deployment','codespace_id','999'),('deployment','permission_profile_sha256','0'*64)]:
            objects=dict(envelope=deepcopy(envelope),hello=deepcopy(hello),deployment=deepcopy(deployment))
            objects[target][key]=value
            with self.subTest(target=target,key=key),self.assertRaises(ValueError):
                validate_arm(objects['envelope'],hello=objects['hello'],record=record,deployment=objects['deployment'],
                             arm_commit_sha='b'*40,metadata_bytes=metadata)

    def test_complete_broker_metadata_is_not_only_a_mutable_hash(self):
        envelope,hello,record,deployment,raw=workload()
        value=json.loads(raw);value['requester']='other';bad_raw=canonical_bytes(value)+b'\n'
        envelope['broker_metadata_sha256']=hashlib.sha256(bad_raw).hexdigest()
        with self.assertRaises(ValueError):
            validate_arm(envelope,hello=hello,record=record,deployment=deployment,arm_commit_sha='b'*40,metadata_bytes=bad_raw)
        value=json.loads(raw);value['admission_checks']['public_repository_verified']=False
        with self.assertRaises(ValidationError):check('jch-broker-metadata-v1.schema.json',value)

    def test_full_frame_budget_uses_maximal_jwt_not_16k_fixture(self):
        envelope,hello,*_=workload()
        frame=frame_payload(hello);self.assertEqual(int.from_bytes(frame[:4],'big'),len(frame)-4)
        self.assertFalse(frame[4:].endswith(b'\n'))
        proof=proof_budget(envelope);self.assertLessEqual(len(proof)-4,100000)
        self.assertGreater(len(proof)-4,16384)
        bad=dict(protocol_id='j-ch-v1',handshake_version=dict(major=1,minor=0),message_type='PROOF',
                 envelope=envelope,jwt='a.'+'b'*32765+'.c')
        with self.assertRaises(ValidationError):frame_payload(bad)
        bad=deepcopy(hello);bad['handshake_version']['minor']=1
        with self.assertRaises(ValidationError):frame_payload(bad)

    def test_capacity_refusal_happens_before_an_oversized_proof_can_be_armed(self):
        envelope,*_=workload()
        # A schema-shaped huge decimal is not operational provider identity.
        # This vector independently proves the complete pre-ARM byte-budget gate.
        envelope['binding']['controller_run_id']='1'*100000
        with self.assertRaises(ValueError):proof_budget(envelope)

    def test_quiescence_shape_disambiguates_pre_post_arm_and_shutdown(self):
        _,_,record,_,_=workload()
        for count in (0,1):
            for method in ('codespace-shutdown','protected-process-tree-quiet'):
                check('jch-quiescence-v1.schema.json',quiescence(record,count=count,method=method))
        bad=quiescence(record);bad['observed_state']='QUIESCENT'
        with self.assertRaises(ValidationError):check('jch-quiescence-v1.schema.json',bad)
        bad=quiescence(record,count=0);bad['arm_commit_sha']='a'*40
        with self.assertRaises(ValidationError):check('jch-quiescence-v1.schema.json',bad)
        bad=quiescence(record);bad['invocation_count']=True
        with self.assertRaises(ValidationError):check('jch-quiescence-v1.schema.json',bad)
