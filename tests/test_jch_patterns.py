"""Native ECMAScript comparison and local-validator isolation/sensitivity oracles."""
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil
import subprocess
import unittest

from jsonschema import Draft202012Validator, ValidationError
from jch_lexical_audit import SAMPLES
from jch_patterns import CATALOGUE, JCHValidator, matches, qualified_resources
from jch_normative_schemas import RESOURCES, check
from jch_normative_fixtures import workload
from test_jch_challenge_domain import challenge_objects


class PatternDialectTests(unittest.TestCase):
    def test_all_occurrences_use_the_exact_qualified_catalogue(self):
        found=[]
        def walk(value):
            if isinstance(value,dict):
                if 'pattern' in value:found.append(value['pattern'])
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        for value in RESOURCES.values():walk(value)
        self.assertEqual(len(found),164);self.assertEqual(set(found),set(CATALOGUE))
        self.assertEqual(set(SAMPLES),set(CATALOGUE))
        self.assertTrue(all(p.startswith('^') and p.endswith('$') for p in found))

    def test_native_ecmascript_differential_corpus(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'NATIVE_ECMASCRIPT_REQUIRED')
        rng=random.Random(132)
        separators=['\n','\r','\r\n','\u2028','\u2029','\t','\x00',' ','\\','/','é','😀']
        common=['','a','0','1','A','１２','a/b','../a','a/../b','a\\b',
                'a\u2028\\b','a\u2029../b','a\u2028/../b','\ud800','\udfff']
        common+=[''.join(rng.choices('aAZ019_./\\-\n\r\u2028é😀',k=rng.randrange(0,90))) for _ in range(1000)]
        vectors=[]
        for pattern in CATALOGUE:
            sample=SAMPLES[pattern];values=set(common+[sample,sample*2])
            for length in (0,1,19,20,31,32,39,40,63,64,65,199,200,201,254,255,256):
                values.add('a'*length);values.add('1'*length)
            for separator in separators:
                values.update((sample+separator,separator+sample,
                               sample[:len(sample)//2]+separator+sample[len(sample)//2:]))
            for i in range(len(sample)):
                values.add(sample[:i]+sample[i+1:])
                for ch in ('A','g','é','😀','\U00010000','\U0010ffff','\ud800','\udfff','\n','\u2028'):
                    values.add(sample[:i]+ch+sample[i+1:])
            vectors.extend([pattern,value] for value in sorted(values))
        script='const fs=require("node:fs"); const v=JSON.parse(fs.readFileSync(0,"utf8")); process.stdout.write(JSON.stringify(v.map(([p,s])=>new RegExp(p).test(s))));'
        result=subprocess.run([node,'-e',script],input=json.dumps(vectors,ensure_ascii=True),
                              text=True,capture_output=True,timeout=60,check=True)
        expected=json.loads(result.stdout);self.assertEqual(len(expected),len(vectors))
        for (pattern,value),accepted in zip(vectors,expected):
            self.assertEqual(matches(pattern,value),accepted,(pattern,repr(value)))

    def test_utf16_single_wildcard_and_unbounded_negated_classes(self):
        pattern=next(p for p in CATALOGUE if p.startswith('^https'))
        for scalar in (0x10000,0x1f600,0x10ffff):
            ch=chr(scalar)
            self.assertFalse(matches(pattern,'https://github'+ch+'com/o/r/issues/1#issuecomment-1'))
            self.assertTrue(matches(pattern,'https://github.com/'+ch+'/r/issues/1#issuecomment-1'))
        self.assertTrue(matches(pattern,'https://githubécom/o/r/issues/1#issuecomment-1'))
        self.assertTrue(matches(pattern,'https://githubXcom/o/r/issues/1#issuecomment-1'))

    def test_all_ascii_scalars_against_native_engine(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        vectors=[]
        for pattern in CATALOGUE:
            sample=SAMPLES[pattern]
            for ch in map(chr,range(128)):
                vectors.extend([[pattern,sample+ch],[pattern,ch+sample],[pattern,sample[:1]+ch+sample[1:]]])
        script='const fs=require("node:fs");process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,"utf8")).map(([p,s])=>new RegExp(p).test(s))));'
        result=subprocess.run([node,'-e',script],input=json.dumps(vectors),text=True,
                              capture_output=True,timeout=60,check=True)
        for (pattern,value),expected in zip(vectors,json.loads(result.stdout)):
            self.assertEqual(matches(pattern,value),expected,(pattern,repr(value)))

    def test_unknown_pattern_and_dialect_fail_before_validation(self):
        for mutation in ('pattern','dialect','nested'):
            resources=deepcopy(RESOURCES);schema=resources['jch-journal-v2.schema.json']
            if mutation=='pattern':schema['pattern']='^new$'
            elif mutation=='dialect':schema['$schema']='https://example.invalid/schema'
            else:schema['$defs']['binding']['$schema']=schema['$schema']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):qualified_resources(resources)
        with self.assertRaises(ValueError):JCHValidator({'pattern':'^new$'}).validate('new')

    def test_global_validator_and_public_resources_remain_exact(self):
        original=deepcopy(RESOURCES);before=Draft202012Validator.VALIDATORS['pattern']
        evaluated,registry=qualified_resources(RESOURCES)
        for name,value in evaluated.items():
            self.assertEqual(value,{k:v for k,v in original[name].items() if k!='$schema'})
        self.assertEqual(original,RESOURCES)
        self.assertIs(Draft202012Validator.VALIDATORS['pattern'],before)
        schema={'type':'string','pattern':'^[0-9a-f]{64}$'};value='a'*64+'\n'
        Draft202012Validator(schema).validate(value)
        with self.assertRaises(ValidationError):JCHValidator(schema).validate(value)
        self.assertTrue(JCHValidator({'pattern':'^[0-9a-f]{64}$'}).is_valid(1))

    def test_ref_evaluation_cannot_revert_to_historical_pattern_engine(self):
        envelope,hello,record,_,_=workload()
        record['arm_binding']['launcher_program_sha256']+='\n'
        envelope['binding']=deepcopy(record['arm_binding'])
        with self.assertRaises(ValidationError):check('jch-arm-envelope-v1.schema.json',envelope)
        for challenge in ('a'*64,'a'*64+'\n'):
            envelope,hello,record,_,_=challenge_objects(challenge)
            if challenge.endswith('\n'):
                with self.assertRaises(ValidationError):check('jch-arm-envelope-v1.schema.json',envelope)
            else:check('jch-arm-envelope-v1.schema.json',envelope)
