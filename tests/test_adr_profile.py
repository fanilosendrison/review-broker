"""Calendar/provenance/immutability and pure-index checks for the proposed ADR profile."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from jsonschema import ValidationError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from adr_profile_contract import (
    ADRProfileError, load_adrs, render_index, assert_transition, calendar_checker,
)


class ADRProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile,self.records=load_adrs(ROOT)

    def test_proposed_ids_profile_and_pinned_schema_provenance(self):
        self.assertEqual(self.profile['status'],'proposed')
        self.assertEqual([r.metadata['id'] for r in self.records],['ADR-001','ADR-002','ADR-003','ADR-004','ADR-005'])
        self.assertTrue(all(r.metadata['status']=='proposed' for r in self.records))
        source=self.profile['shared_profile']
        self.assertEqual(source['sha256'],'55c9ff189e686cb1d545d0cbcfc9527a72dd1e1185c5ba595a3a1da7f3aa8c57')
        self.assertEqual(source['repository'],'https://github.com/fanilosendrison/dotagents')
        self.assertEqual(source['commit'],'aa84e816385f082ea353b6254e490d85fe17bceb')
        self.assertEqual(hashlib.sha256((ROOT/'docs/adr'/source['vendored_path']).read_bytes()).hexdigest(),source['sha256'])

    def test_calendar_dates_are_asserted_not_annotation(self):
        checker=calendar_checker()
        self.assertTrue(checker.conforms('2024-02-29','date'))
        for invalid in ('2025-02-29','2026-02-30','2026-13-01','2026-00-01','2026-01-00'):
            with self.subTest(date=invalid):self.assertFalse(checker.conforms(invalid,'date'))

    def test_accepted_body_metadata_and_relations_cannot_change(self):
        previous=replace(self.records[0],metadata=dict(self.records[0].metadata,status='accepted'))
        self.assertIsNone(assert_transition(previous,replace(previous,metadata=dict(previous.metadata,status='superseded')),self.profile))
        with self.assertRaises(ADRProfileError):assert_transition(previous,replace(previous,decision_body=previous.decision_body+b'changed\n'),self.profile)
        for key,value in [('date','2026-11-10'),('name','Different meaning'),('governs',['different-scope'])]:
            current=replace(previous,metadata=dict(previous.metadata,**{key:value}))
            with self.subTest(key=key),self.assertRaises(ADRProfileError):assert_transition(previous,current,self.profile)
        changed=deepcopy(previous.metadata);changed['relations']['confirms']=['ADR-002']
        with self.assertRaises(ADRProfileError):assert_transition(previous,replace(previous,metadata=changed),self.profile)

    def test_lifecycle_cannot_reopen_an_accepted_or_retired_record(self):
        previous=replace(self.records[0],metadata=dict(self.records[0].metadata,status='accepted'))
        with self.assertRaises(ADRProfileError):assert_transition(previous,self.records[0],self.profile)
        retired=replace(previous,metadata=dict(previous.metadata,status='superseded'))
        with self.assertRaises(ADRProfileError):assert_transition(retired,previous,self.profile)

    def test_index_is_exact_derived_projection(self):
        expected=render_index(ROOT).encode()
        self.assertEqual((ROOT/'docs/adr/README.md').read_bytes(),expected)
        self.assertEqual(sum(line.startswith('| ADR-') for line in expected.decode().splitlines()),5)
        for record in self.records:self.assertEqual(record.metadata['relations'],dict(clarifies=[],amends=[],supersedes=[],confirms=[]))

    def test_check_refuses_stale_or_missing_index_without_repairing(self):
        target=ROOT/'artifacts/adoption/adr-test-data';target.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target) as directory:
            root=Path(directory);shutil.copytree(ROOT/'docs/adr',root/'docs/adr')
            index=root/'docs/adr/README.md';index.write_bytes(b'# stale\n')
            command=[sys.executable,str(ROOT/'scripts/render-adr-index.py'),'--check','--root',str(root)]
            result=subprocess.run(command,capture_output=True,timeout=30)
            self.assertNotEqual(result.returncode,0);self.assertEqual(index.read_bytes(),b'# stale\n')
            index.unlink();result=subprocess.run(command,capture_output=True,timeout=30)
            self.assertNotEqual(result.returncode,0);self.assertFalse(index.exists())
            subprocess.run([sys.executable,str(ROOT/'scripts/render-adr-index.py'),'--write','--root',str(root)],check=True,timeout=30)
            subprocess.run(command,check=True,timeout=30)

    def test_bad_hash_id_h1_duplicate_and_crlf_refuse(self):
        # Actual parser/schema is exercised through a copied isolated profile tree.
        target=ROOT/'artifacts/adoption/adr-test-data';target.mkdir(parents=True,exist_ok=True)
        for mutation in ('body','crlf','bom','id','h1','duplicate','date'):
            with tempfile.TemporaryDirectory(dir=target) as directory:
                root=Path(directory);shutil.copytree(ROOT/'docs/adr',root/'docs/adr')
                path=next((root/'docs/adr').glob('adr-001-*.md'));raw=path.read_bytes()
                if mutation=='body':raw+=b'Uncommitted meaning\n'
                if mutation=='crlf':raw=raw.replace(b'\n',b'\r\n')
                if mutation=='bom':raw=b'\xef\xbb\xbf'+raw
                if mutation=='id':raw=raw.replace(b'id: ADR-001',b'id: ADR-099')
                if mutation=='h1':raw=raw.replace(b'# ADR-001',b'# ADR-002')
                if mutation=='duplicate':raw=raw.replace(b'status: proposed',b'status: proposed\nstatus: accepted')
                if mutation=='date':raw=raw.replace(b"'2026-11-09'",b"'2025-02-29'")
                path.write_bytes(raw)
                with self.subTest(mutation=mutation),self.assertRaises((ADRProfileError,ValidationError)):
                    load_adrs(root)
