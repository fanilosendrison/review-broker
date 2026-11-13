"""Issue130: real-resource lexical checks with coherently resealed canonical records."""
from copy import deepcopy
import hashlib
import unittest

from jsonschema import ValidationError
from review_broker.identity import canonical_bytes
from jch_normative_fixtures import workload
from jch_normative_schemas import check, RESOURCES, validate_arm
from rb91_jch_contract_model import parse_strict
from rb91_full_abi_model import validate as historical_validate


def challenge_objects(challenge):
    envelope,hello,record,policy,metadata=workload()
    record['arm_binding']['challenge']=challenge
    record['history'][-1]['binding_sha256']=hashlib.sha256(canonical_bytes(record['arm_binding'])).hexdigest()
    envelope['binding']=deepcopy(record['arm_binding']);hello['challenge']=challenge
    return envelope,hello,record,policy,metadata


class ChallengeDomainTests(unittest.TestCase):
    def test_exact_domain_in_all_three_complete_resources(self):
        valid=('0'*64,'a'*64,'0123456789abcdef'*4)
        invalid=('a'*63,'a'*65,'a'*64+'\n','a'*64+'\r\n','a'*31+'\n'+'a'*32,
                 'a'*63+'\t','a'*63+'é','a'*63+'Ａ','a'*63+'A','a'*63+'g','',
                 None,True,64,[],{})
        for accepted,values in ((True,valid),(False,invalid)):
            for value in values:
                envelope,hello,record,policy,metadata=challenge_objects(value)
                raw=canonical_bytes(record)+b'\n';decoded=parse_strict(raw)
                self.assertEqual(decoded['arm_binding']['challenge'],value)
                self.assertEqual(canonical_bytes(decoded)+b'\n',raw)
                self.assertEqual(record['history'][-1]['binding_sha256'],
                                 hashlib.sha256(canonical_bytes(decoded['arm_binding'])).hexdigest())
                for name,obj in [('jch-journal-v2.schema.json',decoded),
                                 ('jch-arm-envelope-v1.schema.json',envelope),
                                 ('jch-launcher-message-v1.schema.json',hello)]:
                    with self.subTest(value=value,resource=name):
                        if accepted:check(name,obj)
                        else:
                            with self.assertRaises(ValidationError):check(name,obj)
                if accepted:
                    validate_arm(envelope,hello=hello,record=record,deployment=policy,
                                 arm_commit_sha='b'*40,metadata_bytes=metadata)

    def test_arm_references_journal_binding_and_domains_are_exact(self):
        expected={'type':'string','pattern':'^[0-9a-f]{64}$','minLength':64,'maxLength':64}
        journal=RESOURCES['jch-journal-v2.schema.json']
        self.assertEqual(journal['$defs']['binding']['properties']['challenge'],expected)
        self.assertEqual(RESOURCES['jch-arm-envelope-v1.schema.json']['properties']['binding'],
                         {'$ref':journal['$id']+'#/$defs/binding'})
        hello=RESOURCES['jch-launcher-message-v1.schema.json']['oneOf'][0]['properties']['challenge']
        self.assertEqual(hello['pattern'],expected['pattern']);self.assertEqual(hello['maxLength'],64)
        # Pattern already requires64; its lower bound1 does not broaden the domain.
        self.assertEqual(hello,dict(expected,minLength=1))

    def test_frozen_model_is_not_retroactively_requalified(self):
        _,_,record,_,_=challenge_objects('a'*64+'\n')
        raw=canonical_bytes(record)+b'\n'
        self.assertIn(b'\\n"',raw)
        self.assertEqual(raw[-1:],b'\n');self.assertNotEqual(raw[-2:],b'\n\n')
        historical_validate(parse_strict(raw))
        with self.assertRaises(ValidationError):check('jch-journal-v2.schema.json',parse_strict(raw))
