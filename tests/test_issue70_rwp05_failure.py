"""Closed original-observation and legacy-receipt oracles, independent of implementation output."""
import copy
import hashlib
import json
import unittest

from review_broker.identity import canonical_bytes
from review_broker.journal_record_v3 import WorkerIdentityV3
from review_broker.pre_model_failure_v3 import validate_permanent_failure_receipt
from review_broker.pre_model_failure_observation_v3 import FailureObservationV3

REQUEST = 'request:sha256:f25131395ed5fafd74021be9eaf4de505cdaf86add6e8d2f85fe004dfe243087'
ATTEMPT = 'attempt:sha256:181187792ede967e0408545d0d8098b173a55d3594e8989e33b29476512862d9'
RESERVATION = 'preparation-dispatch:sha256:191aee996bba6af24cf0afdf68fd3814130b14f8267cf8ef4604ab663a537e96'
ARTIFACT = 'artifact:sha256:'+'7'*64
PACKET = 'packet:sha256:'+'9'*64
PERMANENT_BYTES = b'{"admission_evidence_id":"artifact:sha256:8888888888888888888888888888888888888888888888888888888888888888","attempt_id":"attempt:sha256:181187792ede967e0408545d0d8098b173a55d3594e8989e33b29476512862d9","classification":"PERMANENT","evidence_type":"pre-model-preparation-failure","generation":1,"observation_evidence_id":"artifact:sha256:7777777777777777777777777777777777777777777777777777777777777777","observed_at":"2026-10-30T00:00:00Z","reason_code":"SOURCE_DIGEST_MISMATCH","reference_id":"contract","request_id":"request:sha256:f25131395ed5fafd74021be9eaf4de505cdaf86add6e8d2f85fe004dfe243087","reservation_id":"preparation-dispatch:sha256:191aee996bba6af24cf0afdf68fd3814130b14f8267cf8ef4604ab663a537e96","schema_version":1,"workflow_run_attempt":1,"workflow_run_id":70001}\n'


def observation(phase='REFERENCE_READ', operation='GITHUB_ISSUE_GET', fact=None):
    remote = phase.startswith('REMOTE_')
    return dict(schema_version=1, evidence_type='pre-model-preparation-failure-observation',
        repository='example/review-broker', repository_node_id='R_example',
        claim_ref='refs/heads/review-claims-v3/'+REQUEST.rsplit(':',1)[-1],
        admitted_commit_sha='a'*40, request_id=REQUEST, attempt_id=ATTEMPT,
        admission_evidence_id='artifact:sha256:'+'8'*64, generation=1,
        reservation_id=RESERVATION, workflow_run_id=70001, workflow_run_attempt=1,
        phase=phase, operation=operation, reference_id='contract' if phase=='REFERENCE_READ' else None,
        packet_id=PACKET if remote else None,
        artifact_name='rb-v3-prepared-'+REQUEST.rsplit(':',1)[-1]+'-70001-1' if remote else None,
        artifact_id='991' if phase=='REMOTE_RECONSTRUCTION' else None,
        fact={'kind':'HTTP_STATUS','status':503} if fact is None else fact,
        observed_at='2026-11-06T07:00:00Z')


class FailureObservationTests(unittest.TestCase):
    def test_F01_six_reasons_and_every_verification_fact(self):
        cases = [
            ('REFERENCE_READ','GITHUB_ISSUE_GET',{'kind':'HTTP_STATUS','status':503},'TRANSIENT','SOURCE_API_UNAVAILABLE'),
            ('REFERENCE_READ','GITHUB_ISSUE_COMMENT_GET',{'kind':'HTTP_STATUS','status':404},'UNKNOWN','SOURCE_ACCESS_AMBIGUOUS'),
            ('SOURCE_ACQUISITION','GIT_CLONE',{'kind':'TRANSFER_TIMEOUT','process_terminated':True},'TRANSIENT','SOURCE_TRANSFER_INTERRUPTED'),
            ('REMOTE_UPLOAD','ACTIONS_ARTIFACT_UPLOAD',{'kind':'UPLOAD_OUTCOME_UNKNOWN','emitted':True,'reconciliation':'UNCONFIRMED'},'UNKNOWN','ARTIFACT_UPLOAD_UNCONFIRMED'),
            ('REMOTE_READ','ACTIONS_ARTIFACT_METADATA_GET',{'kind':'HTTP_STATUS','status':429},'TRANSIENT','ARTIFACT_READ_UNAVAILABLE'),
            ('REMOTE_READ','ACTIONS_ARTIFACT_DOWNLOAD',{'kind':'READ_TIMEOUT'},'TRANSIENT','ARTIFACT_READ_UNAVAILABLE'),
        ]
        for check,op in [('ARCHIVE_BYTES','VERIFY_ARCHIVE_BYTES'),('INVENTORY','VERIFY_ARCHIVE_INVENTORY'),
                         ('MANIFEST','VERIFY_REMOTE_MANIFEST'),('PACKET_ID','VERIFY_REMOTE_PACKET')]:
            prefix='packet' if check=='PACKET_ID' else 'artifact'
            fact=dict(kind='VERIFICATION_FAILED',check=check,expected_id=prefix+':sha256:'+'1'*64,
                observed_id=prefix+':sha256:'+'2'*64,expected_size=12 if check=='ARCHIVE_BYTES' else None,
                observed_size=11 if check=='ARCHIVE_BYTES' else None)
            cases.append(('REMOTE_RECONSTRUCTION',op,fact,'UNKNOWN','REMOTE_RECONSTRUCTION_UNCONFIRMED'))
        for phase,op,fact,classification,reason in cases:
            value=observation(phase,op,fact)
            with self.subTest(reason=reason,fact=fact):
                obs=FailureObservationV3.from_value(value)
                # Independent ASCII/integer-domain canonical byte and digest oracle.
                expected=json.dumps(value,sort_keys=True,separators=(',',':')).encode()+b'\n'
                self.assertEqual(obs.canonical_bytes,expected)
                self.assertEqual(obs.evidence_id,'artifact:sha256:'+hashlib.sha256(expected).hexdigest())
                self.assertEqual(obs.classification,classification)
                self.assertEqual(obs.reason_code,reason)
                self.assertEqual(FailureObservationV3(obs.canonical_bytes),obs)

    def test_F01_every_http_catalog_status_and_non_catalog_remote_permission(self):
        for status in (403,404,429,502,503,504):
            obs=FailureObservationV3.from_value(observation(fact={'kind':'HTTP_STATUS','status':status}))
            self.assertEqual(obs.classification,'UNKNOWN' if status in (403,404) else 'TRANSIENT')
            self.assertEqual(obs.reason_code,'SOURCE_ACCESS_AMBIGUOUS' if status in (403,404) else 'SOURCE_API_UNAVAILABLE')
            if status in (403,404):
                with self.assertRaises(ValueError):
                    FailureObservationV3.from_value(observation('REMOTE_READ','ACTIONS_ARTIFACT_METADATA_GET',{'kind':'HTTP_STATUS','status':status}))
        fact=dict(kind='VERIFICATION_FAILED',check='INVENTORY',expected_id=ARTIFACT,observed_id=ARTIFACT,expected_size=None,observed_size=None)
        with self.assertRaises(ValueError):FailureObservationV3.from_value(observation('REMOTE_RECONSTRUCTION','VERIFY_ARCHIVE_INVENTORY',fact))
        fact['observed_id']='artifact:sha256:'+'1'*64
        with self.assertRaises(ValueError):FailureObservationV3.from_value(observation('REMOTE_RECONSTRUCTION','VERIFY_REMOTE_PACKET',fact))

    def test_F01_closed_fields_and_strict_numbers(self):
        value=observation()
        for key in list(value)+['secret','classification','reason_code']:
            changed=copy.deepcopy(value)
            if key in changed:del changed[key]
            else:changed[key]='caller secret or reason'
            with self.subTest(key=key),self.assertRaises(ValueError):FailureObservationV3.from_value(changed)
        for key in ('schema_version','generation','workflow_run_id','workflow_run_attempt'):
            for bad in (True,False,1.0,'1',0,-1):
                changed={**value,key:bad}
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):FailureObservationV3.from_value(changed)
        for bad in (True,503.0,500,401,'503'):
            with self.subTest(status=bad),self.assertRaises(ValueError):
                FailureObservationV3.from_value(observation(fact={'kind':'HTTP_STATUS','status':bad}))

    def test_F01_phase_nulls_time_and_canonical_bytes(self):
        for key,bad in [('reference_id',None),('packet_id',PACKET),('artifact_name','secret'),
                        ('artifact_id','01'),('observed_at','2026-11-06T07:00:00+00:00'),
                        ('observed_at','2026-02-30T07:00:00Z'),('operation','GIT_FETCH')]:
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                FailureObservationV3.from_value({**observation(),key:bad})
        raw=FailureObservationV3.from_value(observation()).canonical_bytes
        for changed in (raw.rstrip(),raw+b'\n',b' '+raw):
            with self.assertRaises(ValueError):FailureObservationV3(changed)
        for fact in ({'kind':'TRANSFER_TIMEOUT','process_terminated':False},
                     {'kind':'UPLOAD_OUTCOME_UNKNOWN','emitted':True}, {'kind':'READ_TIMEOUT','secret':'x'}):
            with self.assertRaises(ValueError):FailureObservationV3.from_value(observation(fact=fact))

    def test_F01_every_fact_is_closed_and_requires_its_own_fields(self):
        cases=[observation(),observation('SOURCE_ACQUISITION','GIT_FETCH',{'kind':'TRANSFER_TIMEOUT','process_terminated':True}),
            observation('REMOTE_UPLOAD','ACTIONS_ARTIFACT_UPLOAD',{'kind':'UPLOAD_OUTCOME_UNKNOWN','emitted':True,'reconciliation':'UNCONFIRMED'}),
            observation('REMOTE_READ','ACTIONS_ARTIFACT_DOWNLOAD',{'kind':'READ_TIMEOUT'}),
            observation('REMOTE_RECONSTRUCTION','VERIFY_REMOTE_PACKET',dict(kind='VERIFICATION_FAILED',check='PACKET_ID',
                expected_id='packet:sha256:'+'1'*64,observed_id='packet:sha256:'+'2'*64,expected_size=None,observed_size=None))]
        for value in cases:
            FailureObservationV3.from_value(value)
            for key in list(value['fact'])+['secret']:
                changed=copy.deepcopy(value)
                if key=='secret':changed['fact'][key]='private text'
                else:del changed['fact'][key]
                with self.subTest(phase=value['phase'],key=key),self.assertRaises(ValueError):FailureObservationV3.from_value(changed)
        for field in ('artifact_id',):
            for bad in ('01','0','+1',' 991','991 ',991,True):
                value=observation('REMOTE_READ','ACTIONS_ARTIFACT_DOWNLOAD',{'kind':'READ_TIMEOUT'});value[field]=bad
                with self.subTest(bad=bad),self.assertRaises(ValueError):FailureObservationV3.from_value(value)

    def test_F01_blocked_receipt_closed_types_codes_and_reference_nulls(self):
        from tests.test_journal_record_v3 import admitted_record
        from review_broker.github_journal_transport_v3 import VerifiedJournalSnapshotV3
        from review_broker.journal_record_v3 import encode_journal_v2
        from review_broker.pre_model_failure_v3 import blocked_failure_receipt_v3,validate_blocked_failure_receipt
        record=admitted_record();a,c=record.attempt,record.control
        snapshot=VerifiedJournalSnapshotV3('example/review-broker','R_example',
            'refs/heads/review-claims-v3/'+a.request_id.rsplit(':',1)[-1],'a'*40,'b'*40,encode_journal_v2(record),record,ARTIFACT)
        obs=FailureObservationV3.from_value({**observation(), 'request_id':a.request_id,'attempt_id':a.attempt_id,
            'admission_evidence_id':a.admission['admission_evidence_id'],'reservation_id':c.reservation_id,
            'workflow_run_id':c.worker.run_id,'workflow_run_attempt':c.worker.run_attempt})
        receipt=blocked_failure_receipt_v3(snapshot,obs)
        def validate(value):
            return validate_blocked_failure_receipt(value,failure_receipt_id='artifact:sha256:'+hashlib.sha256(canonical_bytes(value)+b'\n').hexdigest(),
                request_id=a.request_id,attempt_id=a.attempt_id,admission_evidence_id=a.admission['admission_evidence_id'],
                generation=1,reservation_id=c.reservation_id,worker=c.worker,accepted_reference_ids=a.admission['reference_ids'])
        validate(receipt)
        for key in list(receipt)+['secret']:
            changed=dict(receipt)
            if key=='secret':changed[key]='private text'
            else:del changed[key]
            with self.subTest(key=key),self.assertRaises(ValueError):validate(changed)
        for key,bad in [('classification','PERMANENT'),('reason_code','ARBITRARY_FAILURE'),('reference_id',None),
                        ('generation',True),('workflow_run_id',True),('workflow_run_attempt',True),
                        ('schema_version',True),('observed_at','2026-02-30T00:00:00Z')]:
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):validate({**receipt,key:bad})
        for reason in ('SOURCE_TRANSFER_INTERRUPTED','ARTIFACT_READ_UNAVAILABLE'):
            validate({**receipt,'reason_code':reason,'classification':'TRANSIENT','reference_id':None})
            with self.assertRaises(ValueError):validate({**receipt,'reason_code':reason,'reference_id':'contract'})

    def test_F01_permanent_bytes_identity_and_diagnostics_unchanged(self):
        # Frozen from the exact accepted BASE_SHA before modifying its validator.
        value=json.loads(PERMANENT_BYTES)
        identity='artifact:sha256:f1ff51197a5ad62c2336ac2a5eaca93d7bf140e6fdc363efbdc117e0c7509f61'
        result=validate_permanent_failure_receipt(value,failure_receipt_id=identity,
            request_id=REQUEST,attempt_id=ATTEMPT,admission_evidence_id=value['admission_evidence_id'],
            generation=1,reservation_id=RESERVATION,worker=WorkerIdentityV3(70001,1),accepted_reference_ids=['contract'])
        self.assertEqual(canonical_bytes(result)+b'\n',PERMANENT_BYTES)
        self.assertEqual('artifact:sha256:'+hashlib.sha256(PERMANENT_BYTES).hexdigest(),identity)
