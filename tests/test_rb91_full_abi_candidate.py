"""Falsification of complete candidate ABI, not runtime/operational qualification."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import ValidationError
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptRecord
from rb91_jch_contract_model import artifact, fixture_transition
from rb91_full_abi_model import (
    SCHEMA, VALIDATOR, validate, validate_transition, validate_result_bytes,
)
from rb91_full_abi_fixtures import prepared, armed, publication_chain


class CompleteCandidateTests(unittest.TestCase):
    def test_full_chain_all_domains_and_legal_updates(self):
        chain, raw = publication_chain()
        for record in [prepared(1), prepared(2), armed(), *chain]:
            validate(record)
            self.assertEqual(list(VALIDATOR.iter_errors(record)), [])
        for before, after in zip(chain, chain[1:]):
            operation = 'transition' if before['state'] != after['state'] else 'metadata'
            self.assertTrue(validate_transition(before, after, parent_sha='1'*40, operation=operation))
        validate_result_bytes(chain[-1], raw)

    def test_claim_origin_and_no_implicit_v1_promotion(self):
        value = prepared()
        value.pop('input_capacity')
        value['history'] = value['history'][:1]
        value['evidence_ids'] = []
        value['state'] = 'REQUESTED'
        validate(value)
        with self.assertRaises(ValueError):
            AttemptRecord.from_dict(value)
        value['schema_version'] = 1
        with self.assertRaises(ValidationError):
            validate(value)

    def test_unknown_keys_at_every_embedded_object_refuse(self):
        chain, _ = publication_chain()
        cases = [(['admission'], prepared()), (['admission_authority'], prepared()),
            (['admission','subject'],prepared()), (['admission','request'],prepared()),
            (['admission','request','mission'],prepared()),
            (['input_capacity'],prepared()), (['arm_binding'],armed()),
            (['evidence_locator_plan'],chain[-1]), (['evidence_locator'],chain[-1]),
            (['evidence_locator','artifacts','terminal-capture.json'],chain[-1]),
            (['publication_intent'],chain[-1]),
            (['publication_intent','publisher'],chain[-1]),
            (['publication_intent','result_artifact'],chain[-1]),
            (['publication_intent','result_artifact','location'],chain[-1]),
            (['publication_receipt'],chain[-1]),
            (['publication_receipt','publisher'],chain[-1])]
        for path, original in cases:
            value = deepcopy(original)
            cursor = value
            for field in path:
                cursor = cursor[field]
            cursor['unknown'] = 'not accepted'
            with self.subTest(path=path), self.assertRaises(ValidationError):
                validate(value)

    def test_missing_fields_at_every_schema_definition_refuse(self):
        chain, _ = publication_chain()
        original = chain[-1]
        for name, definition in SCHEMA['$defs'].items():
            field = {'binding':'arm_binding','plan':'evidence_locator_plan','locator':'evidence_locator',
                     'intent':'publication_intent','receipt':'publication_receipt'}.get(name,name)
            for key in definition['required']:
                value = deepcopy(original)
                value[field].pop(key)
                with self.subTest(definition=name,key=key), self.assertRaises(ValidationError):
                    VALIDATOR.validate(value)

    def test_identity_substitution_refuses(self):
        for field in ('request_id','subject_id','mission_id','policy_id','review_intent_id'):
            value = prepared()
            value['admission'][field] = value['admission'][field].split(':')[0]+':sha256:'+'0'*64
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(value)
        value = prepared()
        value['admission']['subject']['head_commit'] = '0'*40
        with self.assertRaises(ValueError):
            validate(value)

    def test_same_shape_wrong_artifact_and_publication_links_refuse(self):
        chain, _ = publication_chain()
        paths = [('evidence_locator','subject_id'),('evidence_locator','packet_id'),
            ('evidence_locator','workflow_run_id'),('publication_receipt','result_id'),
            ('publication_intent','request_id')]
        for field, key in paths:
            value = deepcopy(chain[-1])
            old = value[field][key]
            value[field][key] = '2' if key == 'workflow_run_id' else old.split(':')[0]+':sha256:'+'0'*64
            with self.subTest(field=field,key=key), self.assertRaises(ValueError):
                validate(value)

    def test_metadata_history_and_single_field_ownership_refuse(self):
        chain, _ = publication_chain()
        value = deepcopy(chain[1])
        value['evidence_ids'][-1] = 'artifact:sha256:'+'0'*64
        value['history'][-1]['evidence_ids'] = [value['evidence_ids'][-1]]
        with self.assertRaises(ValueError):
            validate(value)
        value = deepcopy(chain[2])
        value['evidence_locator_plan']['artifact_name'] = 'changed'
        with self.assertRaises(ValueError):
            validate_transition(chain[1],value,parent_sha='1'*40,operation='metadata')

    def test_reference_is_not_replaced_by_opaque_result_or_missing_bytes(self):
        chain, raw = publication_chain()
        for bad in (raw[:-1], raw+b' ', canonical_bytes({'schema_version':1})+b'\n'):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                validate_result_bytes(chain[-1],bad)
        value = deepcopy(chain[-1])
        value['publication_intent']['result'] = {}
        with self.assertRaises(ValidationError):
            validate(value)

    def test_pre_and_post_arm_terminal_count_binding_remain_distinct(self):
        for initial in (prepared(), armed()):
            value = fixture_transition(initial,'INDETERMINATE')
            validate(value)
            stopped = fixture_transition(value,'STOPPED')
            validate(stopped)
            self.assertEqual(stopped['invocation_count'],initial['invocation_count'])
            self.assertEqual(stopped['arm_binding'],initial['arm_binding'])
        # These are structural fixtures, NOT receipts proving quiescence/Shutdown.

    def test_immutable_admission_and_unknown_versions(self):
        parent = prepared()
        child = armed()
        child['admission_authority']['actor'] = 'other'
        with self.assertRaises(ValueError):
            validate_transition(parent,child,parent_sha='1'*40,operation='atomic_arm')
        for version in (True, 0, 1, 3, None, '2'):
            value = prepared()
            value['schema_version'] = version
            with self.subTest(version=version), self.assertRaises((ValueError,ValidationError)):
                validate(value)
        value = prepared()
        value['admission']['request']['schema_version'] = True
        with self.assertRaises(ValidationError):
            validate(value)

    def test_historical_profiles_unchanged_against_real_decoder(self):
        root = Path(__file__).parent / 'fixtures/rb91-original-seven-field-journal-v1.json'
        data = json.loads(root.read_text())
        for case in [*data['cases'],data['extended_producer']]:
            value = case['record']
            self.assertEqual(canonical_bytes(AttemptRecord.from_dict(value).as_dict()),canonical_bytes(value))

    def test_rejected_capacity_cannot_leave_prepared(self):
        value = prepared()
        cap = value['input_capacity']
        for key in ('capacity_units','utf8_bytes','unicode_scalar_characters','utf16_code_units'):
            cap[key] = 1048577
        cap['status'] = 'REJECTED'
        value['history'][-1]['evidence_ids'] = [artifact(cap)]
        value['evidence_ids'][-1] = artifact(cap)
        validate(value)
        with self.assertRaises(ValueError):
            validate(fixture_transition(value,'INDETERMINATE'))
