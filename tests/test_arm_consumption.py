"""Kernel-exclusive one-use claims and explicit crash boundaries on local POSIX fixtures."""
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_broker.arm_authority_contract import ArmAuthorityError
from review_broker.arm_consumption import consume_attempt


def competing_consumer(envelope, trust, barrier, results):
    barrier.wait(timeout=10)
    try:
        consume_attempt(envelope, trust)
        results.put('accepted')
    except ArmAuthorityError:
        results.put('refused')


class ArmConsumptionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.store = self.root/'consumption'
        self.store.mkdir(mode=0o700)
        st = self.store.stat()
        self.trust = dict(consumption_directory=str(self.store), consumption_identity=[st.st_dev, st.st_ino],
                          consumption_owner=os.geteuid())
        self.envelope = dict(attempt_id='attempt:sha256:'+'a'*64, authorization_id='b'*64,
                             journal_commit_sha='c'*40)

    def test_two_processes_only_one_can_consume_one_attempt(self):
        context = multiprocessing.get_context('spawn')
        barrier, results = context.Barrier(2), context.Queue()
        children = [context.Process(target=competing_consumer,
                    args=(self.envelope, self.trust, barrier, results)) for _ in range(2)]
        for child in children:
            child.start()
        try:
            outcomes = [results.get(timeout=15), results.get(timeout=15)]
            self.assertEqual(sorted(outcomes), ['accepted', 'refused'])
            for child in children:
                child.join(timeout=10)
                self.assertEqual(child.exitcode, 0)
        finally:
            for child in children:
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=10)
            results.close()
            results.join_thread()

    def test_interrupted_persistence_at_each_fsync_leaves_permanent_refusal(self):
        for fail_on in [1, 2]:
            with self.subTest(fail_on=fail_on):
                store = self.root/str(fail_on)
                store.mkdir(mode=0o700)
                st = store.stat()
                trust = dict(self.trust, consumption_directory=str(store),
                             consumption_identity=[st.st_dev, st.st_ino])
                actual = os.fsync
                calls = []
                def fsync(fd):
                    calls.append(fd)
                    if len(calls) == fail_on:
                        raise OSError('simulated interruption')
                    actual(fd)
                with patch('review_broker.arm_consumption.os.fsync', side_effect=fsync), \
                     self.assertRaises(ArmAuthorityError):
                    consume_attempt(self.envelope, trust)
                self.assertEqual(len(list(store.iterdir())), 1)
                with self.assertRaises(ArmAuthorityError):
                    consume_attempt(self.envelope, trust)

    def test_crash_after_consumption_before_model_start_stays_consumed(self):
        consume_attempt(self.envelope, self.trust)
        # Fresh process state cannot reset the durable marker; no process-local cache is involved.
        context = multiprocessing.get_context('spawn')
        barrier, results = context.Barrier(1), context.Queue()
        child = context.Process(target=competing_consumer,
                                args=(self.envelope, self.trust, barrier, results))
        child.start()
        try:
            self.assertEqual(results.get(timeout=15), 'refused')
            child.join(timeout=10)
            self.assertEqual(child.exitcode, 0)
        finally:
            if child.is_alive():
                child.terminate()
                child.join(timeout=10)
            results.close()
            results.join_thread()

    def test_symlinked_or_writable_store_and_existing_alias_are_refused(self):
        alias = self.root/'alias'
        alias.symlink_to(self.store, target_is_directory=True)
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.envelope, dict(self.trust, consumption_directory=str(alias)))
        self.store.chmod(0o770)
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.envelope, self.trust)
        self.store.chmod(0o700)
        marker = self.store/('a'*64+'.json')
        marker.symlink_to(self.root/'elsewhere')
        with self.assertRaises(ArmAuthorityError):
            consume_attempt(self.envelope, self.trust)
        self.assertFalse((self.root/'elsewhere').exists())
