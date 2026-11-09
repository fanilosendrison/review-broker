"""Concurrent/interrupted downstream recovery; no inference or live publication."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from review_broker.publication import PublicationError
from rb91_publication_recovery_model import PublicationStore
from rb91_storage_fixtures import StorageCase


class CommentTransport:
    def __init__(self):
        self.comments=[];self.posts=0;self.lost_ack=False;self.drop=False;self.fail_read=False

    def __call__(self,command,**kwargs):
        method,endpoint=command[3:5]
        if method=='GET':
            if self.fail_read:return subprocess.CompletedProcess(command,1,'','synthetic unavailable')
            return subprocess.CompletedProcess(command,0,json.dumps(self.comments),'')
        if method!='POST' or not endpoint.endswith('/comments'):raise AssertionError('publication boundary only')
        self.posts+=1
        if not self.drop:
            self.comments.append(dict(id=8,node_id='synthetic-node',html_url='https://github.com/sample/broker/issues/7#issuecomment-8',
                created_at='2026-11-09T00:00:00Z',
                user=dict(login='broker',id=9,type='Bot',node_id='synthetic-user',html_url='https://github.com/broker'),
                body=json.loads(kwargs['input'])['body']))
        return subprocess.CompletedProcess(command,1 if self.lost_ack or self.drop else 0,'{}','')


class F1PublicationTests(unittest.TestCase):
    def case(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        c=StorageCase(Path(tmp.name));return c,PublicationStore(c.policy.execution_snapshot)

    def reserve(self,c,store,**kwargs):
        return store.reserve(c.record,c.policy,token=c.token(),issuer_reader=c.issuer,runner=c.runner,
                             destination=c.root/'verification',**kwargs)

    def test_recovery_after_original_job_exit_can_retain_reserve_and_publish(self):
        c,store=self.case();before=deepcopy(c.armed)
        # Only the original consumed snapshot and terminal archive survive to recovery.
        store=PublicationStore(deepcopy(c.policy.execution_snapshot))
        permission=self.reserve(c,store);api=CommentTransport()
        self.assertIsNotNone(permission);self.assertTrue(store.post(permission,c.raw,api))
        self.assertEqual(api.posts,1);self.assertEqual(store.record['state'],'REPORTED')
        self.assertEqual(store.record['arm_binding'],before['arm_binding'])
        self.assertEqual(store.record['invocation_count'],1)
        self.assertEqual(c.record['publication_intent']['result_artifact']['storage']['mode'],'recovery')

    def test_competing_recovery_reservations_create_one_post_capability(self):
        c,store=self.case();barrier=threading.Barrier(2,timeout=10);local=threading.local()
        def runner(command,**kwargs):
            if not getattr(local,'entered',False):local.entered=True;barrier.wait()
            return c.runner(command,**kwargs)
        def reserve(index):
            return store.reserve(c.record,c.policy,token=c.token(),issuer_reader=c.issuer,runner=runner,
                                 destination=c.root/('verification-'+str(index)))
        with ThreadPoolExecutor(max_workers=2) as pool:permissions=list(pool.map(reserve,[0,1]))
        self.assertEqual(sum(p is not None for p in permissions),1)
        api=CommentTransport();winner=next(p for p in permissions if p is not None)
        self.assertTrue(store.post(winner,c.raw,api));self.assertEqual(api.posts,1)
        with self.assertRaises(ValueError):store.post(None,c.raw,api)
        self.assertEqual(api.posts,1)

    def test_lost_reservation_ack_does_not_reconstruct_creator_permission(self):
        c,store=self.case();self.assertIsNone(self.reserve(c,store,lose_ack=True))
        # Replaying signed storage proof or reconstructing a process does not own the CAS.
        restarted=PublicationStore(deepcopy(store.record))
        self.assertIsNone(self.reserve(c,restarted))
        api=CommentTransport()
        with self.assertRaises(ValueError):restarted.post(object(),c.raw,api)
        self.assertFalse(restarted.observe(c.raw,api));self.assertEqual(api.posts,0)

    def test_interrupted_storage_before_reservation_can_resume_without_model(self):
        c,store=self.case();endpoint='repos/'+c.repository+'/actions/artifacts/12/zip'
        retained=c.responses.pop(endpoint)
        with self.assertRaises(ValueError):self.reserve(c,store)
        self.assertIsNone(store.record['publication_intent']);self.assertEqual(store.record['invocation_count'],1)
        c.responses[endpoint]=retained
        # A new isolated verification reads retained evidence afresh, never retries ARM.
        permission=store.reserve(c.record,c.policy,token=c.token(),issuer_reader=c.issuer,runner=c.runner,
            destination=c.root/'verification-after-interruption')
        self.assertIsNotNone(permission)
        api=CommentTransport();self.assertTrue(store.post(permission,c.raw,api));self.assertEqual(api.posts,1)

    def test_post_reply_loss_with_observed_comment_finishes_without_second_post(self):
        c,store=self.case();permission=self.reserve(c,store);api=CommentTransport();api.lost_ack=True
        self.assertTrue(store.post(permission,c.raw,api));self.assertEqual(api.posts,1)
        restarted=PublicationStore(deepcopy(store.record))
        self.assertIsNone(self.reserve(c,restarted));self.assertTrue(restarted.observe(c.raw,api))
        with self.assertRaises(ValueError):restarted.post(permission,c.raw,api)
        self.assertEqual(api.posts,1)

    def test_unknown_post_outcome_remains_ambiguous_without_retry(self):
        c,store=self.case();permission=self.reserve(c,store);api=CommentTransport();api.drop=True
        self.assertFalse(store.post(permission,c.raw,api));self.assertEqual(api.posts,1)
        with self.assertRaises(ValueError):store.post(permission,c.raw,api)
        self.assertFalse(store.observe(c.raw,api));self.assertEqual(api.posts,1)
        self.assertEqual(store.record['state'],'VALIDATED')

    def test_duplicate_publication_observation_is_an_incident_not_permission(self):
        c,store=self.case();permission=self.reserve(c,store);api=CommentTransport()
        store.post(permission,c.raw,api);api.comments.append(deepcopy(api.comments[0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_PUBLICATION_INCIDENT'):store.observe(c.raw,api)
        self.assertEqual(api.posts,1)

    def test_realistic_actor_metadata_retains_existing_publication_without_repost(self):
        c,store=self.case();permission=self.reserve(c,store);api=CommentTransport()
        self.assertTrue(store.post(permission,c.raw,api));self.assertEqual(api.posts,1)
        api.comments[0]['user']['avatar_url']='https://example.invalid/image'
        restarted=PublicationStore(deepcopy(store.record))
        self.assertTrue(restarted.observe(c.raw,api));self.assertIsNone(self.reserve(c,restarted))
        self.assertEqual(api.posts,1)

    def test_unknown_comment_read_cannot_post_or_create_an_observation(self):
        c,store=self.case();permission=self.reserve(c,store);api=CommentTransport();api.fail_read=True
        with self.assertRaises(PublicationError):store.post(permission,c.raw,api)
        self.assertEqual(api.posts,0);self.assertIsNone(store.record['publication_receipt'])
