"""Calendar/provenance/immutability and pure-index checks for the accepted ADR profile."""
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

    def test_accepted_ids_profile_and_pinned_schema_provenance(self):
        self.assertEqual(self.profile['status'],'accepted')
        self.assertEqual([r.metadata['id'] for r in self.records],['ADR-001','ADR-002','ADR-003','ADR-004','ADR-005'])
        self.assertTrue(all(r.metadata['status']=='accepted' for r in self.records))
        source=self.profile['shared_profile']
        self.assertEqual(source['sha256'],'55c9ff189e686cb1d545d0cbcfc9527a72dd1e1185c5ba595a3a1da7f3aa8c57')
        self.assertEqual(source['repository'],'https://github.com/fanilosendrison/dotagents')
        self.assertEqual(source['commit'],'aa84e816385f082ea353b6254e490d85fe17bceb')
        self.assertEqual(hashlib.sha256((ROOT/'docs/adr'/source['vendored_path']).read_bytes()).hexdigest(),source['sha256'])

    def test_owner_adoption_changes_only_status_from_exact_reviewed_records(self):
        # Whole-file SHA256 pins from f5838b6, not hashes recomputed from the
        # adopted metadata. This also protects all pre-Context bytes and dates.
        reviewed={
            'ADR-001':'3e15daabfa0cc8ebc38a2553b9d01214b1edfe133eeffea9252196a64f4c40a3',
            'ADR-002':'b8a97a5bc237db5482dd88673fd59f72ad0330165b3a1064b9ccaa06688df43c',
            'ADR-003':'0714f16105a64d8c2fa7d76b5dfa43c28aea99a43abb63049eba84d441ba2556',
            'ADR-004':'7a8c7524260bb6ab7b72129448f9f7d28cb3733dfc20826f017bea0a218d63e1',
            'ADR-005':'2102cf98c0efed8b0822a9ccd9efc04bde92c2e92720439a17bf406797061af1',
        }
        self.assertEqual(self.profile['activation'],'owner-authorized-merge-into-dev')
        for record in self.records:
            with self.subTest(adr=record.metadata['id']):
                raw=record.path.read_bytes()
                self.assertEqual(raw.count(b'status: accepted\n'),1)
                original=raw.replace(b'status: accepted\n',b'status: proposed\n',1)
                self.assertEqual(hashlib.sha256(original).hexdigest(),reviewed[record.metadata['id']])
                proposed=replace(record,metadata=dict(record.metadata,status='proposed'))
                self.assertIsNone(assert_transition(proposed,record,self.profile))

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
        reopened=replace(previous,metadata=dict(previous.metadata,status='proposed'))
        with self.assertRaises(ADRProfileError):assert_transition(previous,reopened,self.profile)
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
                if mutation=='duplicate':raw=raw.replace(b'status: accepted',b'status: accepted\nstatus: proposed')
                if mutation=='date':raw=raw.replace(b"'2026-11-09'",b"'2025-02-29'")
                path.write_bytes(raw)
                with self.subTest(mutation=mutation),self.assertRaises((ADRProfileError,ValidationError)):
                    load_adrs(root)
