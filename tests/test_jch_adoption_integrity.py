"""Preserve qualified inputs, legacy rules and inactive runtime while proposing authority."""
import hashlib
import json
from pathlib import Path
import unittest

from review_broker.admission import select_operational_admission, AdmissionError
from review_broker.request import validate_request
from rb91_full_abi_fixtures import prepared

ROOT=Path(__file__).resolve().parents[1]
OLD_STATUS='These v2 rules are normative but unimplemented. Existing executable journal and\nrecovery behavior remains v1-only until separately implemented and qualified.'
NEW_STATUS='These ReviewRequest v2 rules are normative and construction was integrated in\nversion0.4.17/PR41. Operational request2 admission remains default-disabled and\nrequires separate authorization. Existing executable journal/recovery is\njournal1, independent of request1/request2. Journal2/J-CH remains a proposed\nseparate authority, not an implemented or qualified execution path.'


class AdoptionIntegrityTests(unittest.TestCase):
    def test_qualified_f1_models_and_schemas_are_exact_frozen_references(self):
        data=json.loads((ROOT/'docs/adoption/jch-qualified-inputs.json').read_text())
        self.assertEqual(data['source_sha'],'b7316e5e8cadc718872ea56dfecfb61709c636ce')
        self.assertEqual(len(data['files']),16)
        for name,digest in data['files'].items():
            with self.subTest(path=name):self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)

    def test_runtime_existing_schemas_profiles_and_workflows_are_unchanged(self):
        data=json.loads((ROOT/'docs/adoption/jch-baseline-preservation.json').read_text())
        self.assertEqual(data['base_sha'],'3057192a6ad4e80663b3b8168cbaa52657c3db27')
        upstream=json.loads((ROOT/'docs/adoption/jch-upstream-preservation.json').read_text())
        replacements=upstream['historical_protected_replacements']
        self.assertEqual(set(replacements),set(data['unchanged_git_entries']) & set(upstream['entries']))
        for name,entry in data['unchanged_git_entries'].items():
            path=ROOT/name
            raw=path.readlink().as_posix().encode() if entry['mode']=='120000' else path.read_bytes()
            expected=entry['sha256']
            if name in replacements:
                self.assertEqual(replacements[name]['historical_sha256'],expected)
                expected=upstream['entries'][name]['sha256']
                self.assertEqual(replacements[name]['upstream_sha256'],expected)
            with self.subTest(path=name):self.assertEqual(hashlib.sha256(raw).hexdigest(),expected)
        change=data['test_dependency_amendment'];text=(ROOT/change['path']).read_text()
        self.assertEqual(text.count(change['after']),1)
        restored=text.replace(change['after'],change['before']).encode()
        self.assertEqual(hashlib.sha256(restored).hexdigest(),change['baseline_sha256'])

    def test_reconciled_dev_all_263_inherited_paths_are_exact(self):
        data=json.loads((ROOT/'docs/adoption/jch-upstream-preservation.json').read_text())
        self.assertEqual(data['upstream_commit'],'a47e42c9437357b18d79fb3e68776063f894b8ea')
        self.assertEqual(data['integration_pr'],131)
        self.assertEqual(data['supplemental_integration_pr'],133)
        self.assertEqual(data['historical_base'],'3057192a6ad4e80663b3b8168cbaa52657c3db27')
        self.assertEqual(len(data['entries']),263)
        for name,entry in data['entries'].items():
            path=ROOT/name
            with self.subTest(path=name):
                if entry['mode'] is None:self.assertFalse(path.exists() or path.is_symlink())
                else:
                    raw=path.readlink().as_posix().encode() if entry['mode']=='120000' else path.read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
                    self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),entry['git_oid'])

    def test_legacy_normative_body_tails_are_unchanged_except_explicit_ed04_status(self):
        data=json.loads((ROOT/'docs/adoption/jch-baseline-preservation.json').read_text())
        for name,entry in data['legacy_body_tails'].items():
            raw=(ROOT/name).read_bytes();tail=raw[raw.index(entry['anchor'].encode()):]
            if name=='docs/contracts/review-execution.md':
                self.assertEqual(tail.count(NEW_STATUS.encode()),1)
                tail=tail.replace(NEW_STATUS.encode(),OLD_STATUS.encode())
            with self.subTest(path=name):self.assertEqual(hashlib.sha256(tail).hexdigest(),entry['sha256'])

    def test_ed04_distinguishes_implemented_request2_from_proposed_journal2(self):
        request=prepared()['admission']['request'];validate_request(request)
        def no_source(_):raise AssertionError('admission must fail before source effects')
        with self.assertRaisesRegex(AdmissionError,'V2_OPERATIONAL_ADMISSION_DISABLED'):
            select_operational_admission(request,{},no_source,requester='authorized-operator')
        spec=(ROOT/'docs/specification/review-broker-spec.md').read_text()
        execution=(ROOT/'docs/contracts/review-execution.md').read_text()
        self.assertNotIn('ReviewRequest v1 remains the only implemented request contract',spec)
        self.assertNotIn(OLD_STATUS,execution)
        self.assertIn('50b89e4ed46963e11846e0159975bdebc0a30f40',spec)
        self.assertIn('Operational request2 admission remains default-disabled',execution)
        self.assertIn('Journal2/J-CH remains a proposed',execution)

    def test_every_new_contract_explicitly_proposed_and_no_normative_acceptance_claimed(self):
        names=['jch-journal-v2.md','jch-execution-authority.md','jch-workload-authority.md',
               'jch-result-retention.md','jch-recovery-s2.md']
        for name in names:
            text=(ROOT/'docs/contracts'/name).read_text()
            with self.subTest(contract=name):
                self.assertIn('adoption_status: "proposed"',text)
                self.assertRegex(text,r'version: "0[.]1[.][0-9]+"')
        text=(ROOT/'docs/adoption/jch-normative-adoption.md').read_text()
        self.assertIn('No final adoption, merge, construction or activation',text)
        self.assertIn('J20',text)

    def test_retention_normative_body_preserves_qualified_semantic_sections(self):
        # Explicit anchors ensure every major F1 scope survives transfer; the
        # schema parity and frozen behavioral suites supply independent oracles.
        text=(ROOT/'docs/contracts/jch-result-retention.md').read_text()
        for anchor in ['## A — Immutable execution provenance','## B — Separately authenticated storage provenance',
                       '## C — Result and evidence content identity','## Publication ownership and interruption']:
            self.assertIn(anchor,text)
        for required in ['creation strictly before expiry','provider repository/run/attempt/job/artifact',
                         'canonical JSON bytes','replacement cannot satisfy','POST is attempted at most once']:
            self.assertIn(required,text)
